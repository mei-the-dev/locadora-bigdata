# ============================================================================
# batch/spark/jobs/gold_dimensional.py - Fase 5 (Silver -> Gold dimensional).
# Materializa Fato_Telemetria_Diaria (snapshot diario por veiculo) a partir do
# Silver de telemetria: agrega por (vehicle_id, dia, empresa), calcula o
# score_conducao/faixa (fleetlib.scoring, mesma logica testada) e resolve as
# surrogate keys por JOIN nas dimensoes (Chaudhuri & Dayal 1997). Padrao ELT
# stg -> UPSERT (ON CONFLICT) => idempotente e incremental (SK estaveis).
# Uso: spark-submit gold_dimensional.py
# ============================================================================
"""ELT Silver -> Gold: Fato_Telemetria_Diaria com score e resolução de SK."""

from __future__ import annotations

import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths, pg  # noqa: E402
from common.session import build_spark  # noqa: E402

_STG = "stg_fato_telemetria"

_UPSERT = f"""
INSERT INTO Fato_Telemetria_Diaria
    (sk_veiculo, sk_tempo, sk_empresa, sk_patio, sk_faixa_conducao, km_rodados,
     velocidade_media, velocidade_maxima, consumo_medio_bateria, autonomia_media_km,
     num_eventos_conducao_brusca, tempo_movimento_seg, score_conducao)
SELECT sk_veiculo, sk_tempo, sk_empresa, sk_patio, sk_faixa_conducao, km_rodados,
       velocidade_media, velocidade_maxima, consumo_medio_bateria, autonomia_media_km,
       num_eventos_conducao_brusca, tempo_movimento_seg, score_conducao
FROM {_STG}
ON CONFLICT (sk_veiculo, sk_tempo, sk_empresa) DO UPDATE SET
    km_rodados                  = EXCLUDED.km_rodados,
    velocidade_media            = EXCLUDED.velocidade_media,
    velocidade_maxima           = EXCLUDED.velocidade_maxima,
    consumo_medio_bateria       = EXCLUDED.consumo_medio_bateria,
    autonomia_media_km          = EXCLUDED.autonomia_media_km,
    num_eventos_conducao_brusca = EXCLUDED.num_eventos_conducao_brusca,
    tempo_movimento_seg         = EXCLUDED.tempo_movimento_seg,
    sk_faixa_conducao           = EXCLUDED.sk_faixa_conducao,
    score_conducao              = EXCLUDED.score_conducao
"""


def _udf_score():
    from pyspark.sql import functions as F

    def _calc(km, vmed, vmax, bruscos, consumo):
        from fleetlib.scoring import FeaturesConducao, calcular_score

        return calcular_score(FeaturesConducao(
            km_rodados=float(km or 0.0), velocidade_media=float(vmed or 0.0),
            velocidade_maxima=float(vmax or 0.0), eventos_bruscos=int(bruscos or 0),
            consumo_bateria_pct=float(consumo or 0.0)))

    return F.udf(_calc, "double")


def _udf_faixa():
    from pyspark.sql import functions as F

    def _f(score):
        from fleetlib.scoring import faixa_do_score

        return faixa_do_score(float(score))[0]

    return F.udf(_f, "int")


def main() -> None:
    from pyspark.sql import functions as F

    spark = build_spark("fleet-gold-dimensional")
    score_udf, faixa_udf = _udf_score(), _udf_faixa()

    silver = spark.read.format("delta").load(paths.silver("telemetria"))

    # Agrega ao grao diario por veiculo (snapshot periodico acumulado)
    agg = (
        silver.groupBy("vehicle_id", "empresa", "patio_base", "dt")
        .agg(
            F.sum("km_percorridos").alias("km_rodados"),
            F.avg("velocidade_media").alias("velocidade_media"),
            F.max("velocidade_maxima").alias("velocidade_maxima"),
            (F.max("bateria_min") - F.min("bateria_fim")).alias("consumo_bruto"),
            F.avg("autonomia_fim_km").alias("autonomia_media_km"),
            F.sum("eventos_bruscos").alias("num_eventos_conducao_brusca"),
            (F.count("*") * F.lit(30)).alias("tempo_movimento_seg"),
        )
        .withColumn("consumo_medio_bateria", F.greatest(F.col("consumo_bruto"), F.lit(0.0)))
        .withColumn("sk_tempo", F.date_format(F.col("dt"), "yyyyMMdd").cast("int"))
        .withColumn("score_conducao",
                    score_udf("km_rodados", "velocidade_media", "velocidade_maxima",
                              "num_eventos_conducao_brusca", "consumo_medio_bateria"))
        .withColumn("sk_faixa_conducao", faixa_udf("score_conducao"))
    )

    # Resolve surrogate keys por JOIN nas dimensoes conformadas (JDBC)
    dim_v = pg.ler_tabela(spark, "dw_locadora.Dim_Veiculo").select(
        F.col("sk_veiculo"), F.col("id_veiculo_origem"))
    dim_e = pg.ler_tabela(spark, "dw_locadora.Dim_Empresa").select(
        F.col("sk_empresa"), F.col("nome_empresa"))
    dim_p = pg.ler_tabela(spark, "dw_locadora.Dim_Patio").select(
        F.col("sk_patio"), F.col("nome_patio"))

    fato = (
        agg.join(dim_v, agg.vehicle_id == dim_v.id_veiculo_origem, "left")
        .join(dim_e, agg.empresa == dim_e.nome_empresa, "left")
        .join(dim_p, agg.patio_base == dim_p.nome_patio, "left")
        .select(
            F.coalesce("sk_veiculo", F.lit(-1)).alias("sk_veiculo"),
            F.col("sk_tempo"),
            F.coalesce("sk_empresa", F.lit(-1)).alias("sk_empresa"),
            F.coalesce("sk_patio", F.lit(-1)).alias("sk_patio"),
            F.col("sk_faixa_conducao"),
            F.round("km_rodados", 2).alias("km_rodados"),
            F.round("velocidade_media", 2).alias("velocidade_media"),
            F.round("velocidade_maxima", 2).alias("velocidade_maxima"),
            F.round("consumo_medio_bateria", 2).alias("consumo_medio_bateria"),
            F.round("autonomia_media_km", 2).alias("autonomia_media_km"),
            F.col("num_eventos_conducao_brusca"),
            F.col("tempo_movimento_seg"),
            F.round("score_conducao", 2).alias("score_conducao"),
        )
    )

    # ELT: escreve o staging (overwrite) e faz o UPSERT idempotente no fato
    pg.escrever_tabela(fato, _STG, mode="overwrite")
    pg.executar_sql(spark, _UPSERT)
    print(f"[GOLD] Fato_Telemetria_Diaria upsert de {fato.count()} snapshots", flush=True)
    spark.stop()


if __name__ == "__main__":
    main()
