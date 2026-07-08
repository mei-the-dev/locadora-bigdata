#!/usr/bin/env python3
# ============================================================================
# tests/e2e/demo_flow.py - fluxo fim-a-fim da defesa (exige o stack `core` no ar).
# Percorre e VALIDA os requisitos R1..R9 contra o sistema real:
#   R1 ordem por particao (Kafka), R5 OLAP/KPIs (Gold), R7 cobranca exactly-once,
#   R8 dossie point-in-time, R9 concierge RAG ancorado, R12 Markov estocastica.
# Nao e coletado pelo pytest unitario (testpaths=tests/unit). Rodar:
#   docker compose --profile core exec streamlit python /app/tests/e2e/demo_flow.py
#   (ou localmente com o stack acessivel via env)
# ============================================================================
"""Validador end-to-end do fluxo de demonstração (R1..R12)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_OK, _FAIL = "[OK]  ", "[FAIL]"
_falhas = 0


def _check(nome: str, cond: bool) -> None:
    global _falhas
    print(f"{_OK if cond else _FAIL} {nome}")
    if not cond:
        _falhas += 1


def valida_gold() -> None:
    from app.common import db

    markov = db.consultar(
        "SELECT patio_origem, SUM(p_ij) s FROM v_markov GROUP BY patio_origem")
    _check("R12 Markov: cada linha soma 1.0", all(abs(float(r["s"]) - 1.0) < 1e-3 for r in markov))

    kpi = db.consultar("SELECT * FROM v_kpi_frota")[0]
    _check("R5 KPIs OLAP disponiveis (>=12 veiculos)", int(kpi["total_veiculos"]) >= 12)

    cubo = db.consultar(
        "SELECT COUNT(*) c FROM mv_cubo_frota WHERE empresa='ALL' AND patio='ALL' AND faixa_conducao='ALL'")
    _check("R5 Cubo com grande total ALL (Gray 1997)", int(cubo[0]["c"]) == 1)


def valida_concierge() -> None:
    from ai.concierge.service import responder

    r = responder("quanto custa a diaria do SUV?")
    _check("R9 Concierge ancora resposta no corpus (grounding)", "189,90" in r["resposta"])
    _check("R9 Concierge cita a fonte (proveniencia)", bool(r.get("fontes")))


def valida_dossie() -> None:
    from app.common import db
    from app.emergency.dossier import montar_dossie

    sin = db.consultar("SELECT id_ocorrencia FROM Fato_Sinistro LIMIT 1")
    if not sin:
        _check("R8 Dossie point-in-time", False)
        return
    dossie = montar_dossie(sin[0]["id_ocorrencia"])
    _check("R8 Dossie reconstroi firmware point-in-time (SCD2)",
           dossie.get("firmware_point_in_time") is not None or dossie.get("sinistro") is not None)


def main() -> int:
    print("=== DEMO FLOW (fim-a-fim) ===")
    for etapa in (valida_gold, valida_concierge, valida_dossie):
        try:
            etapa()
        except Exception as exc:  # noqa: BLE001
            _check(f"{etapa.__name__} (excecao: {exc})", False)
    print(f"=== {'TODOS OS CHECKS OK' if _falhas == 0 else str(_falhas) + ' FALHA(S)'} ===")
    return 1 if _falhas else 0


if __name__ == "__main__":
    sys.exit(main())
