# ============================================================================
# batch/spark/jobs/sink_cassandra.py - Fase 3 (Silver -> Cassandra).
# Persiste a telemetria conformada no store wide-column (AP/BASE): particao por
# vehicle_id, clustering por event_ts DESC -> leitura por janela ja ORDENADA
# (R1) e escrita de alta concorrencia (R4) - Lakshman 2009; DeCandia 2007.
# Tambem materializa `posicao_atual` (ultima leitura por veiculo).
# Uso: spark-submit sink_cassandra.py
# ============================================================================
"""Sink Silver -> Cassandra (telemetria_por_veiculo + posicao_atual)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths  # noqa: E402
from common.session import build_spark  # noqa: E402

_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "frota")


def _escrever_cassandra(df, tabela: str) -> None:
    (df.write.format("org.apache.spark.sql.cassandra")
        .options(keyspace=_KEYSPACE, table=tabela)
        .mode("append")
        .save())


def main() -> None:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    spark = build_spark("fleet-sink-cassandra")
    silver = spark.read.format("delta").load(paths.silver("telemetria"))

    # Serie temporal por veiculo (nomes alinhados a persistence/cassandra/init.cql)
    serie = silver.select(
        F.col("vehicle_id"),
        F.col("window_end_ts").alias("event_ts"),
        F.col("empresa"),
        F.col("velocidade_media"), F.col("velocidade_maxima"),
        F.col("bateria_min"), F.col("bateria_fim"),
        F.col("autonomia_fim_km"), F.col("temperatura_media"),
        F.col("lat_fim"), F.col("lon_fim"),
        F.col("km_percorridos"), F.col("eventos_bruscos"), F.col("n_leituras"),
    )
    _escrever_cassandra(serie, "telemetria_por_veiculo")
    print(f"[CASSANDRA] telemetria_por_veiculo: {serie.count()} linhas", flush=True)

    # Posicao atual = leitura mais recente por veiculo
    w = Window.partitionBy("vehicle_id").orderBy(F.col("window_end_ts").desc())
    posicao = (
        silver.withColumn("_rn", F.row_number().over(w)).where(F.col("_rn") == 1)
        .select(
            F.col("vehicle_id"),
            F.col("window_end_ts").alias("event_ts"),
            F.col("patio_base").alias("patio_base"),
            F.col("lat_fim").alias("lat"), F.col("lon_fim").alias("lon"),
            F.col("bateria_fim").alias("bateria"),
            F.col("autonomia_fim_km").alias("autonomia_km"),
        )
    )
    _escrever_cassandra(posicao, "posicao_atual")
    print(f"[CASSANDRA] posicao_atual: {posicao.count()} veiculos", flush=True)
    spark.stop()


if __name__ == "__main__":
    main()
