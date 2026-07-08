# ============================================================================
# batch/spark/common/session.py - construtor de SparkSession do Lakehouse.
# Configura Delta Lake (log transacional/ACID sobre object store) + conector
# S3A para o MinIO (object store desacoplado de compute - Armbrust 2021;
# Ghemawat 2003). Endpoints/credenciais vem do ambiente (.env).
# ============================================================================
"""Fabrica de SparkSession configurada para Delta + MinIO (S3A)."""

from __future__ import annotations

import os


def _env(nome: str, padrao: str) -> str:
    return os.getenv(nome, padrao)


def build_spark(app_name: str):
    """Cria a SparkSession com Delta e S3A/MinIO habilitados.

    Import de pyspark/delta e local (nao quebra `py_compile`/import fora do
    container Spark). Os pacotes (delta-spark, kafka, hadoop-aws) sao providos
    por `submit.sh` via --packages.
    """
    from pyspark.sql import SparkSession

    endpoint = _env("MINIO_ENDPOINT", "http://minio:9000")
    access = _env("MINIO_ROOT_USER", "fleetadmin")
    secret = _env("MINIO_ROOT_PASSWORD", "fleetsecret123")

    builder = (
        SparkSession.builder.appName(app_name)
        # Delta Lake
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # S3A -> MinIO
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access)
        .config("spark.hadoop.fs.s3a.secret.key", secret)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        # Cassandra (usado pelos sinks; ignorado se o conector nao estiver no --packages)
        .config("spark.cassandra.connection.host", _env("CASSANDRA_HOST", "cassandra"))
        .config("spark.cassandra.connection.port", _env("CASSANDRA_PORT", "9042"))
        .config("spark.sql.session.timeZone", "America/Sao_Paulo")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
