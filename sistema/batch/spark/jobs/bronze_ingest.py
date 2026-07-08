# ============================================================================
# batch/spark/jobs/bronze_ingest.py - Fase 2 (Kafka -> Bronze Delta/MinIO).
# Zona BRONZE = bruta, append-only, imutavel (1 registro = 1 evento cru), com
# metadados de linhagem (particao/offset Kafka, ingest_ts). Escrita exactly-once
# via checkpoint do Structured Streaming (Armbrust 2020 - acao txn do Delta).
# Modo `availableNow` (default) processa o backlog e encerra (bom para a demo);
# modo `stream` roda continuamente.
# Uso: spark-submit bronze_ingest.py [--mode availableNow|stream] [--topic telemetry]
# ============================================================================
"""Ingestao Kafka -> Bronze (Delta) por topico, com schema Avro."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths  # noqa: E402
from common.session import build_spark  # noqa: E402

# topico Kafka -> (schema avro, dataset Bronze)
_TOPICOS = {
    os.getenv("KAFKA_TOPIC_TELEMETRIA", "telemetry"): ("telemetry", "telemetria"),
    os.getenv("KAFKA_TOPIC_EMERGENCIA", "emergency"): ("emergency", "emergencia"),
    os.getenv("KAFKA_TOPIC_VIAGEM", "trip"): ("trip", "viagem"),
}
_BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")


def ingerir(spark, kafka_topic: str, schema_nome: str, dataset: str, modo: str) -> None:
    """Le um topico Kafka, decodifica Avro e grava (append) na Bronze."""
    from pyspark.sql import functions as F
    from pyspark.sql.avro.functions import from_avro

    schema_json = paths.avro_schema_json(schema_nome)

    fonte = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", _BROKER)
        .option("subscribe", kafka_topic)
        .option("startingOffsets", "earliest")
        .option("maxOffsetsPerTrigger", 5000)
        .load()
    )

    decodificado = (
        fonte.select(
            F.col("key").cast("string").alias("kafka_key"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("kafka_ts"),
            from_avro(F.col("value"), schema_json).alias("evt"),
        )
        .select("kafka_key", "kafka_partition", "kafka_offset", "kafka_ts", "evt.*")
        .withColumn("ingest_ts", F.current_timestamp())
        .withColumn("dt", F.to_date(F.from_unixtime(
            F.coalesce(F.col("event_ts"), F.col("window_end_ts")) / 1000)))
    )

    writer = (
        decodificado.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", paths.checkpoint(f"bronze_{dataset}"))
        .partitionBy("dt")
    )
    if modo == "stream":
        query = writer.start(paths.bronze(dataset))
        query.awaitTermination()
    else:  # availableNow: processa o disponivel e para
        query = writer.trigger(availableNow=True).start(paths.bronze(dataset))
        query.awaitTermination()
    print(f"[BRONZE] {kafka_topic} -> {paths.bronze(dataset)} (modo={modo})", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="availableNow", choices=["availableNow", "stream"])
    ap.add_argument("--topic", default="all", help="topico Kafka ou 'all'")
    args = ap.parse_args()

    spark = build_spark("fleet-bronze-ingest")
    alvos = _TOPICOS if args.topic == "all" else {args.topic: _TOPICOS[args.topic]}
    for kafka_topic, (schema_nome, dataset) in alvos.items():
        ingerir(spark, kafka_topic, schema_nome, dataset, args.mode)
    spark.stop()


if __name__ == "__main__":
    main()
