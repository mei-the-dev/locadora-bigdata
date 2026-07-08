# ============================================================================
# simulator/config.py - configuracao do simulador via variaveis de ambiente.
# Valores padrao coerentes com .env.example. Sementes deterministicas para
# reprodutibilidade (idempotencia do reprocesso a jusante).
# ============================================================================
"""Configuracao do simulador de frota (lida do ambiente)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(nome: str, padrao: int) -> int:
    return int(os.getenv(nome, str(padrao)))


def _float(nome: str, padrao: float) -> float:
    return float(os.getenv(nome, str(padrao)))


@dataclass(frozen=True)
class SimConfig:
    mqtt_host: str = os.getenv("MQTT_HOST", "mosquitto")
    mqtt_port: int = _int("MQTT_PORT", 1883)
    topico_telemetria: str = os.getenv("MQTT_TOPIC_TELEMETRIA", "frota/telemetria")
    topico_emergencia: str = os.getenv("MQTT_TOPIC_EMERGENCIA", "frota/emergencia")
    topico_viagem: str = os.getenv("MQTT_TOPIC_VIAGEM", "frota/viagem")

    num_veiculos: int = _int("FLEET_NUM_VEICULOS", 12)
    seed: int = _int("FLEET_SEED", 42)
    edge_window: int = _int("FLEET_EDGE_WINDOW", 10)
    emit_interval_s: float = _float("FLEET_EMIT_INTERVAL_S", 1.0)
    desordem_max_ms: int = _int("FLEET_DESORDEM_MAX_MS", 3000)
    prob_emergencia: float = _float("FLEET_PROB_EMERGENCIA", 0.02)


def carregar() -> SimConfig:
    return SimConfig()
