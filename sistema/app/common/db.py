# ============================================================================
# app/common/db.py - acesso ao PostgreSQL Gold (camada ROLAP do Lakehouse).
# psycopg2 importado sob demanda. Helpers de consulta parametrizada (nunca
# concatena SQL - previne injecao). Usado por dashboard, cobranca, dossie e RAG.
# ============================================================================
"""Conexao e consulta ao PostgreSQL Gold (parametrizada)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Sequence


def _dsn() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "postgres-gold"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB", "dw"),
        "user": os.getenv("POSTGRES_USER", "dw"),
        "password": os.getenv("POSTGRES_PASSWORD", "dwsecret"),
    }


@contextmanager
def conexao() -> Iterator[Any]:
    """Context manager de conexao (fecha ao sair). search_path = dw_locadora."""
    import psycopg2  # lazy

    conn = psycopg2.connect(**_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO %s", (os.getenv("POSTGRES_SCHEMA", "dw_locadora"),))
        yield conn
    finally:
        conn.close()


def consultar(sql: str, params: Sequence[Any] | None = None) -> list[dict]:
    """Executa SELECT parametrizado e retorna lista de dicts (colunas -> valores)."""
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        colunas = [d[0] for d in cur.description]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def executar(sql: str, params: Sequence[Any] | None = None) -> int:
    """Executa DML parametrizado (INSERT/UPDATE); retorna linhas afetadas."""
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        conn.commit()
        return cur.rowcount
