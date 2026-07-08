# ============================================================================
# fleetlib.domain - constantes canonicas do consorcio de 6 locadoras.
# Fonte unica da verdade para simulador, seeds do Gold (Postgres), Cassandra,
# MongoDB e Neo4j. Mantem "Veiculo", "Patio", "Empresa" com o mesmo significado
# em toda a arquitetura (dimensoes conformadas - Chaudhuri & Dayal 1997).
# ============================================================================
"""Constantes canonicas da frota (patios, empresas, categorias, sensores)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

# ----------------------------------------------------------------------------
# 6 patios canonicos compartilhados (chave natural = nome do patio, como no DW).
# Coordenadas aproximadas (Rio de Janeiro) para roteirizacao (Neo4j) e geo.
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Patio:
    id: str
    nome: str
    localizacao: str
    empresa_dona: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Empresa:
    id: str
    nome: str


PATIOS: tuple[Patio, ...] = (
    Patio("PAT-GAL", "Galeao", "Aeroporto Internacional - Ilha do Governador", "AutoRio Locadora", -22.809, -43.250),
    Patio("PAT-SDU", "Santos Dumont", "Centro - Orla da Baia de Guanabara", "MoveFrota", -22.910, -43.163),
    Patio("PAT-BAR", "Barra", "Barra da Tijuca - Av. das Americas", "VelozCar", -23.000, -43.365),
    Patio("PAT-COP", "Copacabana", "Zona Sul - Orla de Copacabana", "AutoRio Locadora", -22.971, -43.182),
    Patio("PAT-CEN", "Centro", "Centro - Av. Presidente Vargas", "UnidasFrota", -22.906, -43.185),
    Patio("PAT-NIT", "Niteroi", "Niteroi - Centro / Terminal", "MoveFrota", -22.895, -43.123),
)

EMPRESAS: tuple[Empresa, ...] = (
    Empresa("EMP-AUTORIO", "AutoRio Locadora"),
    Empresa("EMP-MOVEFROTA", "MoveFrota"),
    Empresa("EMP-VELOZCAR", "VelozCar"),
    Empresa("EMP-UNIDAS", "UnidasFrota"),
    Empresa("EMP-CARIOCA", "Carioca Rent"),
    Empresa("EMP-LITORAL", "Litoral Autos"),
)

# Categorias (grupos) de veiculo - dominio fechado, alinhado a Dim_Veiculo.
CATEGORIAS: tuple[str, ...] = ("Economico", "Intermediario", "SUV", "Executivo", "Utilitario")

# Cambio conformado (Dim_Veiculo.mecanizacao) - dominio fechado {Automatico|Manual}.
MECANIZACOES: tuple[str, ...] = ("Automatico", "Manual")

# Tipos de sensor de borda (Dim_Sensor.tipo_sensor - dominio fechado do 06_ddl).
TIPOS_SENSOR: tuple[str, ...] = (
    "GPS",
    "Acelerometro",
    "Camera360",
    "Bateria",
    "Temperatura",
    "LIDAR",
    "Ultrassom",
    "Combustivel",
)

# Categorias de evento de emergencia/manutencao (Dim_TipoEvento - dominio fechado).
CATEGORIAS_EVENTO: tuple[str, ...] = (
    "Pane",
    "Acidente",
    "Colisao",
    "Violacao",
    "Falha_Sensor",
    "Bateria_Critica",
    "Manutencao",
    "Outro",
)

# Cidades de origem dos clientes (para Dim_Cliente.cidade/estado / relatorios C e D).
CIDADES_CLIENTE: tuple[tuple[str, str], ...] = (
    ("Rio de Janeiro", "RJ"),
    ("Niteroi", "RJ"),
    ("Sao Goncalo", "RJ"),
    ("Duque de Caxias", "RJ"),
    ("Sao Paulo", "SP"),
    ("Belo Horizonte", "MG"),
    ("Vitoria", "ES"),
    ("Campinas", "SP"),
)


def patio_ids() -> tuple[str, ...]:
    """IDs canonicos dos patios (chave de particao/roteirizacao)."""
    return tuple(p.id for p in PATIOS)


def patio_por_id(patio_id: str) -> Patio | None:
    """Retorna o patio pelo id canonico, ou None se inexistente."""
    for p in PATIOS:
        if p.id == patio_id:
            return p
    return None


def empresa_nomes() -> tuple[str, ...]:
    """Nomes canonicos das 6 locadoras (Dim_Empresa)."""
    return tuple(e.nome for e in EMPRESAS)


def rotas_canonicas() -> tuple[tuple[str, str, float], ...]:
    """Arestas (origem, destino, distancia_km aproximada) para o grafo Neo4j.

    Distancia derivada de forma deterministica das coordenadas (haversine
    simplificada). Mantida como funcao pura para o init.cypher e para os testes.
    """
    arestas: list[tuple[str, str, float]] = []
    for a in PATIOS:
        for b in PATIOS:
            if a.id == b.id:
                continue
            arestas.append((a.id, b.id, round(_haversine_km(a.lat, a.lon, b.lat, b.lon), 2)))
    return tuple(arestas)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia great-circle em km (formula de haversine)."""
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    h = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(h))


def as_uf(cidade_estado: Sequence[str]) -> str:
    """Extrai a UF de uma tupla (cidade, uf)."""
    return cidade_estado[1]
