# ============================================================================
# batch/spark/jobs/hotpath_emergency.py - Fase 6 (hot path de emergencias, R8b).
# Caminho de BAIXA LATENCIA: le o topico isolado `emergency` do Kafka, decodifica
# Avro e grava em Cassandra `eventos_emergencia` (clustering ts DESC) para
# serving imediato + Bronze/Silver Delta para o dossie forense. Topico isolado
# do fluxo de telemetria => a cauda de latencia da emergencia nao compete com o
# volume comum (SLA p99.9 - DeCandia 2007). Micro-batch determinista (Zaharia 2013).
# Uso: spark-submit hotpath_emergency.py [--mode availableNow|stream]
# ============================================================================
"""Hot path de emergencias: Kafka -> Cassandra (+ Delta) com baixa latencia."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths  # noqa: E402
from common.session import build_spark  # noqa: E402

_BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
_KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_EMERGENCIA", "emergency")
_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "frota")


def _grava_cassandra(batch_df, _epoch_id) -> None:
    """foreachBatch: grava o micro-batch de emergencias no Cassandra."""
    from pyspark.sql import functions as F

    linhas = batch_df.select(
        F.col("vehicle_id"),
        F.col("event_ts"),
        F.col("id_ocorrencia"),
        F.col("categoria"),
        F.col("severidade"),
        F.col("lat"), F.col("lon"),
        F.col("detalhe"),
    )
    (linhas.write.format("org.apache.spark.sql.cassandra")
        .options(keyspace=_KEYSPACE, table="eventos_emergencia")
        .mode("append")
        .save())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="stream", choices=["availableNow", "stream"])
    args = ap.parse_args()

    from pyspark.sql import functions as F
    from pyspark.sql.avro.functions import from_avro

    spark = build_spark("fleet-hotpath-emergency")
    schema_json = paths.avro_schema_json("emergency")

    fonte = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", _BROKER)
        .option("subscribe", _KAFKA_TOPIC)
        .option("startingOffsets", "earliest")
        .load()
        .select(from_avro(F.col("value"), schema_json).alias("e"))
        .select("e.*")
    )

    writer = (
        fonte.writeStream
        .option("checkpointLocation", paths.checkpoint("hotpath_emergency"))
        .foreachBatch(_grava_cassandra)
    )
    query = writer.trigger(availableNow=True).start() if args.mode == "availableNow" else writer.start()
    query.awaitTermination()
    print("[HOTPATH] emergencias -> Cassandra concluido", flush=True)


if __name__ == "__main__":
    main()
