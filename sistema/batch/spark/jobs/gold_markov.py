# ============================================================================
# batch/spark/jobs/gold_markov.py - Fase 5 (Silver trips -> Fato_Movimentacao).
# Agrega as viagens/reposicionamentos (topico `trip`) em movimentacoes por
# (veiculo, origem, destino, dia, empresa), resolve SKs e faz UPSERT no
# Fato_Movimentacao (que alimenta a view v_markov, cada linha soma 1.0). Alem
# disso, calcula a DISTRIBUICAO ESTACIONARIA (fleetlib.markov) usada para o
# reposicionamento do veiculo vazio (R12). Idempotente (stg -> ON CONFLICT).
# Uso: spark-submit gold_markov.py
# ============================================================================
"""ELT trips -> Fato_Movimentacao + distribuição estacionária (reposicionamento)."""

from __future__ import annotations

import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths, pg  # noqa: E402
from common.session import build_spark  # noqa: E402

_STG = "stg_fato_movimentacao"

_UPSERT = f"""
INSERT INTO Fato_Movimentacao
    (sk_veiculo, sk_patio_origem, sk_patio_destino, sk_tempo, sk_empresa, qtd_movimentacoes)
SELECT sk_veiculo, sk_patio_origem, sk_patio_destino, sk_tempo, sk_empresa, qtd_movimentacoes
FROM {_STG}
ON CONFLICT (sk_veiculo, sk_patio_origem, sk_patio_destino, sk_tempo, sk_empresa)
DO UPDATE SET qtd_movimentacoes = EXCLUDED.qtd_movimentacoes
"""


def _distribuicao_estacionaria(spark) -> None:
    """Le v_markov da Gold, normaliza e calcula pi (fleetlib.markov)."""
    from fleetlib.markov import distribuicao_estacionaria

    linhas = pg.ler_tabela(spark, "dw_locadora.v_markov").select(
        "patio_origem", "patio_destino", "p_ij").collect()
    matriz: dict = {}
    for r in linhas:
        matriz.setdefault(r["patio_origem"], {})[r["patio_destino"]] = float(r["p_ij"])
    pi = distribuicao_estacionaria(matriz)
    print("[MARKOV] distribuicao estacionaria (ocupacao de longo prazo):", flush=True)
    for patio, prob in sorted(pi.items(), key=lambda kv: kv[1], reverse=True):
        print(f"    {patio:16s} {prob:.4f}", flush=True)


def main() -> None:
    from pyspark.sql import functions as F

    spark = build_spark("fleet-gold-markov")

    trips = spark.read.format("delta").load(paths.silver("viagem"))
    dim_v = pg.ler_tabela(spark, "dw_locadora.Dim_Veiculo").select("sk_veiculo", "id_veiculo_origem")
    dim_e = pg.ler_tabela(spark, "dw_locadora.Dim_Empresa").select("sk_empresa", "nome_empresa")
    dim_p = pg.ler_tabela(spark, "dw_locadora.Dim_Patio").select("sk_patio", "nome_patio")

    po = dim_p.select(F.col("sk_patio").alias("sk_o"), F.col("nome_patio").alias("nome_o"))
    pd_ = dim_p.select(F.col("sk_patio").alias("sk_d"), F.col("nome_patio").alias("nome_d"))

    mov = (
        trips.join(dim_v, trips.vehicle_id == dim_v.id_veiculo_origem, "left")
        .join(dim_e, trips.empresa == dim_e.nome_empresa, "left")
        .join(po, trips.patio_origem == po.nome_o, "left")
        .join(pd_, trips.patio_destino == pd_.nome_d, "left")
        .groupBy(
            F.coalesce("sk_veiculo", F.lit(-1)).alias("sk_veiculo"),
            F.coalesce("sk_o", F.lit(-1)).alias("sk_patio_origem"),
            F.coalesce("sk_d", F.lit(-1)).alias("sk_patio_destino"),
            F.col("sk_tempo"),
            F.coalesce("sk_empresa", F.lit(-1)).alias("sk_empresa"),
        )
        .agg(F.count("*").alias("qtd_movimentacoes"))
    )

    pg.escrever_tabela(mov, _STG, mode="overwrite")
    pg.executar_sql(spark, _UPSERT)
    print(f"[GOLD] Fato_Movimentacao upsert de {mov.count()} arestas", flush=True)

    _distribuicao_estacionaria(spark)
    spark.stop()


if __name__ == "__main__":
    main()
