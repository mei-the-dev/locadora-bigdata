#!/usr/bin/env bash
# ============================================================================
# batch/spark/submit.sh - wrapper de spark-submit com os pacotes do Lakehouse.
# Delta Lake + Kafka + Avro + hadoop-aws (S3A/MinIO). Executado DENTRO do
# container `spark` (bitnami/spark:3.5.1). fleetlib + jobs sao montados em
# /opt/fleet. Uso: bash submit.sh jobs/bronze_ingest.py [--mode availableNow]
# ============================================================================
set -euo pipefail

JOB="${1:?uso: submit.sh <job.py> [args...]}"
shift || true

export PYTHONPATH="/opt/fleet:/opt/fleet/spark:${PYTHONPATH:-}"

# Versoes alinhadas ao Spark 3.5.1 / Scala 2.12.
PACKAGES="io.delta:delta-spark_2.12:3.2.0,\
org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,\
org.apache.spark:spark-avro_2.12:3.5.1,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262,\
com.datastax.spark:spark-cassandra-connector_2.12:3.5.0,\
org.postgresql:postgresql:42.7.3,\
org.mongodb.spark:mongo-spark-connector_2.12:10.3.0"

exec spark-submit \
  --master "local[2]" \
  --packages "${PACKAGES}" \
  --conf spark.driver.memory="${SPARK_DRIVER_MEMORY:-1g}" \
  --conf spark.executor.memory="${SPARK_EXECUTOR_MEMORY:-1g}" \
  --conf spark.sql.shuffle.partitions=8 \
  "/opt/fleet/spark/${JOB}" "$@"
