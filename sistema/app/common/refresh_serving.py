# ============================================================================
# app/common/refresh_serving.py - passo `refresh_serving` do ELT.
# Refresca os cubos materializados (Gray 1997) e AQUECE o cache Redis com os
# KPIs e a matriz de Markov (estado quente do dashboard - Cattell 2011; Manu
# 2022 delta consistency). Reutilizavel pelo Makefile (`make seed`) e pelo DAG
# do Airflow. Sem Spark: so Postgres Gold + Redis.
# ============================================================================
"""Refresh dos cubos + aquecimento do cache Redis (serving)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.common import cache, db  # noqa: E402

_MVS = ("mv_cubo_frota", "mv_cubo_financeiro")


def refrescar_cubos() -> None:
    """REFRESH MATERIALIZED VIEW dos cubos executivos."""
    for mv in _MVS:
        db.executar(f"REFRESH MATERIALIZED VIEW dw_locadora.{mv}")
    print(f"[SERVING] cubos refrescados: {', '.join(_MVS)}", flush=True)


def aquecer_kpis() -> dict:
    """Le v_kpi_frota e grava no cache (chave fleet:kpi)."""
    kpi = db.consultar("SELECT * FROM dw_locadora.v_kpi_frota")[0]
    cache.set_json("fleet:kpi", kpi)
    return kpi


def aquecer_markov() -> list[dict]:
    """Le v_markov e grava no cache (chave fleet:markov)."""
    linhas = db.consultar(
        "SELECT patio_origem, patio_destino, p_ij, p_ij_pct FROM dw_locadora.v_markov")
    cache.set_json("fleet:markov", linhas)
    return linhas


def aquecer_ocupacao() -> list[dict]:
    """Ocupacao atual por patio (v_posicao_atual) -> cache."""
    linhas = db.consultar(
        "SELECT patio_atual AS patio, COUNT(*) AS veiculos "
        "FROM dw_locadora.v_posicao_atual GROUP BY patio_atual ORDER BY 2 DESC")
    cache.set_json("fleet:ocupacao", linhas)
    return linhas


def executar_tudo() -> None:
    """Pipeline completo de refresh do serving."""
    refrescar_cubos()
    kpi = aquecer_kpis()
    aquecer_markov()
    aquecer_ocupacao()
    print(f"[SERVING] cache aquecido. KPIs: {kpi}", flush=True)


if __name__ == "__main__":
    executar_tudo()
