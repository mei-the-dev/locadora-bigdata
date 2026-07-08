# ============================================================================
# app/common/cache.py - cache "ao vivo" do dashboard em Redis (Camada 4).
# Estado quente com staleness limitado (delta consistency - Manu 2022; cache de
# RDBMS - Cattell 2011). get_or_compute: retorna do cache (rapido, <50 ms) ou
# recomputa da Gold e revalida com TTL best-effort. redis importado sob demanda.
# ============================================================================
"""Cache Redis de KPIs/agregados quentes do dashboard."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

_TTL = int(os.getenv("REDIS_TTL_S", "15"))


def _cliente():
    import redis  # lazy

    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )


def get_or_compute(chave: str, computar: Callable[[], Any], ttl: int | None = None) -> tuple[Any, bool]:
    """Retorna (valor, hit). hit=True veio do cache; False recomputou da Gold.

    Degrada com graca: se o Redis estiver indisponivel, apenas recomputa (o
    dashboard nunca quebra por causa do cache - best-effort).
    """
    try:
        r = _cliente()
        bruto = r.get(chave)
        if bruto is not None:
            return json.loads(bruto), True
        valor = computar()
        r.setex(chave, ttl or _TTL, json.dumps(valor, default=str))
        return valor, False
    except Exception:  # noqa: BLE001 - cache e opcional (staleness/indisponibilidade)
        return computar(), False


def set_json(chave: str, valor: Any, ttl: int | None = None) -> bool:
    """Grava um valor no cache (best-effort). Retorna True se gravou."""
    try:
        _cliente().setex(chave, ttl or _TTL, json.dumps(valor, default=str))
        return True
    except Exception:  # noqa: BLE001
        return False


def invalidar(chave: str) -> None:
    """Remove uma chave do cache (best-effort)."""
    try:
        _cliente().delete(chave)
    except Exception:  # noqa: BLE001
        pass
