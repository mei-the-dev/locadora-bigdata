# ============================================================================
# batch/spark/common/pg.py - ponte Spark <-> PostgreSQL Gold via JDBC.
# Le dimensoes (para resolver surrogate keys) e escreve fatos. O driver
# org.postgresql:postgresql e provido por submit.sh. A Gold e ROLAP/ACID; o
# Spark faz o ELT declarativo (Catalyst/pushdown - Armbrust 2015) e materializa.
# ============================================================================
"""Leitura/escrita JDBC entre Spark e o PostgreSQL Gold."""

from __future__ import annotations

import os

_SCHEMA = os.getenv("POSTGRES_SCHEMA", "dw_locadora")


def jdbc_url() -> str:
    host = os.getenv("POSTGRES_HOST", "postgres-gold")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "dw")
    return f"jdbc:postgresql://{host}:{port}/{db}"


def _props() -> dict:
    return {
        "user": os.getenv("POSTGRES_USER", "dw"),
        "password": os.getenv("POSTGRES_PASSWORD", "dwsecret"),
        "driver": "org.postgresql.Driver",
        "currentSchema": _SCHEMA,
    }


def ler_tabela(spark, tabela: str):
    """Le uma tabela/consulta da Gold (ex.: 'dw_locadora.Dim_Veiculo')."""
    return (
        spark.read.format("jdbc")
        .option("url", jdbc_url())
        .option("dbtable", tabela)
        .options(**_props())
        .load()
    )


def escrever_tabela(df, tabela: str, mode: str = "append") -> None:
    """Escreve um DataFrame numa tabela da Gold via JDBC."""
    (
        df.write.format("jdbc")
        .option("url", jdbc_url())
        .option("dbtable", tabela)
        .options(**_props())
        .mode(mode)
        .save()
    )


def executar_sql(spark, sql: str) -> None:
    """Executa um comando SQL na Gold via JDBC (usa o driver JVM do Spark).

    Necessario para o UPSERT idempotente (INSERT ... ON CONFLICT) do padrao ELT
    stg -> fato, que o writer JDBC do Spark nao expressa sozinho.
    """
    gw = spark.sparkContext._gateway
    driver_manager = gw.jvm.java.sql.DriverManager
    p = _props()
    conn = driver_manager.getConnection(jdbc_url(), p["user"], p["password"])
    try:
        stmt = conn.createStatement()
        stmt.execute(f"SET search_path TO {_SCHEMA}")
        stmt.execute(sql)
        stmt.close()
    finally:
        conn.close()
