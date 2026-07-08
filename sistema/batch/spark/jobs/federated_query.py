# ============================================================================
# batch/spark/jobs/federated_query.py - Fase 9 (Data Fabric / query federada).
# Uma UNICA consulta Spark que junta 4 stores poliglotas via a Data Source API
# com pushdown (Armbrust 2015): Delta/MinIO (Silver) + Cassandra (posicao) +
# MongoDB (cadastral) + PostgreSQL Gold (dimensao). Demonstra a convergencia
# DW x BigData: cada uma das 6 locadoras e um produto de dados sobre o object
# store aberto compartilhado (Data Mesh - Armbrust 2021).
# Uso: spark-submit federated_query.py
# ============================================================================
"""Consulta federada (Data Fabric) sobre Delta + Cassandra + Mongo + Postgres."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths, pg  # noqa: E402
from common.session import build_spark  # noqa: E402

_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "frota")
_MONGO_URI = (
    f"mongodb://{os.getenv('MONGO_USER', 'frota')}:{os.getenv('MONGO_PASSWORD', 'frotasecret')}"
    f"@{os.getenv('MONGO_HOST', 'mongodb')}:{os.getenv('MONGO_PORT', '27017')}/"
    f"{os.getenv('MONGO_DB', 'frota')}.veiculos?authSource=admin"
)


def main() -> None:
    from pyspark.sql import functions as F

    spark = build_spark("fleet-federated-query")

    # 1) PostgreSQL Gold - dimensao conformada (ROLAP/ACID)
    dim_v = pg.ler_tabela(spark, "dw_locadora.Dim_Veiculo").select(
        F.col("id_veiculo_origem").alias("vehicle_id"), "categoria", "empresa_origem")

    # 2) Cassandra - posicao atual (AP/BASE, wide-column)
    posicao = (
        spark.read.format("org.apache.spark.sql.cassandra")
        .options(keyspace=_KEYSPACE, table="posicao_atual")
        .load()
        .select("vehicle_id", "patio_base", "bateria", "autonomia_km")
    )

    # 3) MongoDB - cadastral (document store, aninhado)
    cadastral = (
        spark.read.format("mongodb")
        .option("spark.mongodb.read.connection.uri", _MONGO_URI)
        .load()
        .select("vehicle_id", "firmware.versao")
        .withColumnRenamed("versao", "firmware_versao")
    )

    # 4) Delta/MinIO - agregado do Silver (Lakehouse)
    silver = (
        spark.read.format("delta").load(paths.silver("telemetria"))
        .groupBy("vehicle_id").agg(F.avg("velocidade_media").alias("vel_media_hist"))
    )

    federado = (
        dim_v.join(posicao, "vehicle_id", "left")
        .join(cadastral, "vehicle_id", "left")
        .join(silver, "vehicle_id", "left")
        .orderBy("vehicle_id")
    )
    print("[FABRIC] Query federada sobre 4 stores (Postgres+Cassandra+Mongo+Delta):", flush=True)
    federado.show(50, truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
