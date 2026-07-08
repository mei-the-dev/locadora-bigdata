# ============================================================================
# simulator/fleet_model.py - modelo de simulacao por veiculo (Camada 0).
# A funcao `passo()` e DETERMINISTICA dado um random.Random -> testavel. Gera
# leituras cruas (LeituraCrua da fleetlib.edge) que o simulador combina na borda
# antes de enviar (combiner - Dean 2004). Tambem decide cenarios injetaveis
# (emergencia, reposicionamento vazio).
# ============================================================================
"""Modelo de estado e evolucao de cada veiculo autonomo simulado."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from fleetlib.domain import PATIOS, Patio, patio_por_id
from fleetlib.edge import LeituraCrua

_VEL_MIN, _VEL_MAX = 0.0, 160.0
_RECARGA_LIMIAR = 15.0  # abaixo disso, tende a recarregar/reposicionar


@dataclass(frozen=True)
class EstadoVeiculo:
    """Estado imutavel de um veiculo (evolui via `passo`, retornando copia)."""

    vehicle_id: str
    empresa: str
    patio_base: str  # id canonico do patio (ex.: PAT-GAL)
    lat: float
    lon: float
    velocidade: float
    bateria: float  # 0..100
    autonomia_km: float
    temperatura: float

    @property
    def patio(self) -> Patio:
        p = patio_por_id(self.patio_base)
        return p if p else PATIOS[0]


def estado_inicial(vehicle_id: str, empresa: str, patio: Patio, rng: random.Random) -> EstadoVeiculo:
    """Cria o estado inicial de um veiculo posicionado em um patio."""
    return EstadoVeiculo(
        vehicle_id=vehicle_id,
        empresa=empresa,
        patio_base=patio.id,
        lat=patio.lat + rng.uniform(-0.01, 0.01),
        lon=patio.lon + rng.uniform(-0.01, 0.01),
        velocidade=rng.uniform(0, 40),
        bateria=rng.uniform(60, 100),
        autonomia_km=rng.uniform(150, 320),
        temperatura=rng.uniform(28, 38),
        )


def passo(estado: EstadoVeiculo, ts_ms: int, rng: random.Random) -> tuple[EstadoVeiculo, LeituraCrua]:
    """Avanca 1 tick: retorna (novo_estado, leitura_crua) - deterministico p/ rng.

    Modela deriva de velocidade (random walk limitado), consumo de bateria
    proporcional a velocidade, pequenos deslocamentos geograficos e deteccao de
    evento brusco (aceleracao/frenagem forte). Nao muta `estado`.
    """
    dv = rng.uniform(-12, 12)
    nova_vel = min(_VEL_MAX, max(_VEL_MIN, estado.velocidade + dv))
    brusco = abs(dv) > 10.0 or nova_vel > 130.0

    consumo = 0.02 + nova_vel * 0.0015  # % por tick
    nova_bat = max(0.0, estado.bateria - consumo)
    nova_aut = max(0.0, estado.autonomia_km - nova_vel * 0.02)

    # deslocamento geografico proporcional a velocidade (1 grau ~ 111 km)
    passo_graus = nova_vel / 111000.0
    novo_lat = estado.lat + rng.uniform(-1, 1) * passo_graus
    novo_lon = estado.lon + rng.uniform(-1, 1) * passo_graus
    nova_temp = min(60.0, max(20.0, estado.temperatura + rng.uniform(-0.5, 0.8)))

    novo_estado = replace(
        estado, velocidade=nova_vel, bateria=nova_bat, autonomia_km=nova_aut,
        lat=novo_lat, lon=novo_lon, temperatura=nova_temp,
    )
    leitura = LeituraCrua(
        vehicle_id=estado.vehicle_id, event_ts=ts_ms, velocidade=nova_vel,
        bateria=nova_bat, autonomia_km=nova_aut, temperatura=nova_temp,
        lat=novo_lat, lon=novo_lon, evento_brusco=brusco,
    )
    return novo_estado, leitura


def precisa_reposicionar(estado: EstadoVeiculo) -> bool:
    """True se o veiculo (autonomo) deve voltar sozinho ao patio (R12/R13)."""
    return estado.bateria <= _RECARGA_LIMIAR


def destino_reposicionamento(estado: EstadoVeiculo, rng: random.Random) -> Patio:
    """Escolhe um patio de destino para o reposicionamento do veiculo vazio."""
    candidatos = [p for p in PATIOS if p.id != estado.patio_base]
    return rng.choice(candidatos)
