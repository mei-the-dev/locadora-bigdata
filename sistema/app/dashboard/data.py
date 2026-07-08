# ============================================================================
# app/dashboard/data.py - camada de dados do dashboard (OLAP sobre a Gold).
# Consultas encapsuladas com cache Redis (get_or_compute) para KPIs quentes
# (<50 ms - Cattell 2011). Cada funcao degrada com graca (retorna vazio) se a
# Gold/cache estiver indisponivel, para o dashboard nunca quebrar.
# ============================================================================
"""Consultas OLAP do dashboard, com cache Redis best-effort."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.common import cache, db  # noqa: E402


def _safe(fn, default):
    try:
        return fn()
    except Exception:  # noqa: BLE001 - dashboard resiliente a falha de dado
        return default


def kpis() -> dict:
    """KPIs de topo (cacheados)."""
    valor, _hit = cache.get_or_compute(
        "fleet:kpi", lambda: db.consultar("SELECT * FROM v_kpi_frota")[0])
    return valor


def ocupacao() -> list[dict]:
    return _safe(lambda: db.consultar(
        "SELECT patio_atual AS patio, COUNT(*) AS veiculos "
        "FROM v_posicao_atual GROUP BY patio_atual ORDER BY 2 DESC"), [])


def markov() -> list[dict]:
    return _safe(lambda: db.consultar(
        "SELECT patio_origem, patio_destino, p_ij_pct FROM v_markov"), [])


def score_frota() -> list[dict]:
    return _safe(lambda: db.consultar("SELECT * FROM v_score_frota"), [])


def emergencias() -> list[dict]:
    return _safe(lambda: db.consultar("SELECT * FROM v_emergencias"), [])


def faturamento_dia() -> list[dict]:
    return _safe(lambda: db.consultar("SELECT * FROM v_faturamento_dia"), [])


def cubo_financeiro() -> list[dict]:
    return _safe(lambda: db.consultar(
        "SELECT empresa, ano_mes, n_cobrancas, total_faturado, total_multa "
        "FROM mv_cubo_financeiro ORDER BY total_faturado DESC"), [])


def cubo_frota() -> list[dict]:
    return _safe(lambda: db.consultar(
        "SELECT empresa, patio, faixa_conducao, km_total, score_medio, eventos_bruscos "
        "FROM mv_cubo_frota ORDER BY empresa, patio"), [])


def relatorio_reservas() -> list[dict]:
    """Relatorio C (Av.02): reservas por grupo/patio/cidade (retiradas futuras)."""
    return _safe(lambda: db.consultar(
        """SELECT v.categoria AS grupo, p.nome_patio AS patio, c.cidade, c.estado AS uf,
                  SUM(f.qtd_reservas) AS reservas
           FROM Fato_Reserva f
           JOIN Dim_Veiculo v ON v.sk_veiculo = f.sk_veiculo
           JOIN Dim_Patio p ON p.sk_patio = f.sk_patio_retirada
           JOIN Dim_Cliente c ON c.sk_cliente = f.sk_cliente
           GROUP BY v.categoria, p.nome_patio, c.cidade, c.estado
           ORDER BY reservas DESC"""), [])
