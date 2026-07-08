# ============================================================================
# batch/spark/jobs/silver_conform.py - Fase 2 (Bronze -> Silver).
# SILVER = limpo/conformado/deduplicado. Dedup por (vehicle_id, window_end_ts)
# (telemetria) e por id (emergencia/viagem) na transicao Bronze->Silver
# (Ghemawat 2003). Conformacao de dominios reutiliza fleetlib.conform (mesma
# logica testada por unidade). Idempotente via MERGE do Delta: reprocessar
# converge ao mesmo estado (Zaharia 2013).
# Uso: spark-submit silver_conform.py
# ============================================================================
"""Conformacao e deduplicacao Bronze -> Silver (Delta MERGE idempotente)."""

from __future__ import annotations

import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths  # noqa: E402
from common.session import build_spark  # noqa: E402


def _merge_delta(spark, df, destino: str, chave: list[str]) -> None:
    """MERGE idempotente: upsert por `chave`. Cria a tabela se ainda nao existe."""
    from delta.tables import DeltaTable

    if DeltaTable.isDeltaTable(spark, destino):
        alvo = DeltaTable.forPath(spark, destino)
        cond = " AND ".join([f"t.{c} = s.{c}" for c in chave])
        (alvo.alias("t").merge(df.alias("s"), cond)
             .whenMatchedUpdateAll()
             .whenNotMatchedInsertAll()
             .execute())
    else:
        df.write.format("delta").mode("overwrite").save(destino)


def conformar_telemetria(spark) -> None:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    faixa_udf = F.udf(_faixa_horaria)

    bronze = spark.read.format("delta").load(paths.bronze("telemetria"))
    # dedup: mantem o registro de maior ingest_ts por (vehicle_id, window_end_ts)
    w = Window.partitionBy("vehicle_id", "window_end_ts").orderBy(F.col("ingest_ts").desc())
    dedup = (
        bronze.withColumn("_rn", F.row_number().over(w))
        .where(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("event_hour", F.hour(F.from_unixtime(F.col("window_end_ts") / 1000)))
        .withColumn("faixa_horaria", faixa_udf(F.col("event_hour")))
        .withColumn("sk_tempo", F.date_format(F.col("dt"), "yyyyMMdd").cast("int"))
    )
    _merge_delta(spark, dedup, paths.silver("telemetria"), ["vehicle_id", "window_end_ts"])
    print(f"[SILVER] telemetria conformada: {dedup.count()} linhas", flush=True)


def conformar_por_id(spark, dataset: str, id_col: str) -> None:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    bronze = spark.read.format("delta").load(paths.bronze(dataset))
    w = Window.partitionBy(id_col).orderBy(F.col("ingest_ts").desc())
    dedup = (
        bronze.withColumn("_rn", F.row_number().over(w))
        .where(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("sk_tempo", F.date_format(F.col("dt"), "yyyyMMdd").cast("int"))
    )
    _merge_delta(spark, dedup, paths.silver(dataset), [id_col])
    print(f"[SILVER] {dataset} conformada: {dedup.count()} linhas", flush=True)


def _faixa_horaria(hora) -> str:
    """UDF wrapper: reutiliza a logica testada de fleetlib.conform."""
    from fleetlib.conform import faixa_horaria

    return faixa_horaria(int(hora)) if hora is not None else "Nao_informado"


def main() -> None:
    spark = build_spark("fleet-silver-conform")
    conformar_telemetria(spark)
    conformar_por_id(spark, "emergencia", "id_ocorrencia")
    conformar_por_id(spark, "viagem", "id_viagem")
    spark.stop()


if __name__ == "__main__":
    main()
