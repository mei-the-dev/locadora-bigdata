# ============================================================================
# fleetlib.edge - Camada 0 (Borda / Edge Computing).
# Combiner do "computador de bordo": pre-agrega N leituras cruas em 1 pacote
# antes de enviar pela banda movel cara e finita (R3). Fundamento: Dean &
# Ghemawat 2004 (localidade + combiner reduzem o trafego de rede); Kreps 2011
# (batch amortiza o custo de RPC).
# Logica PURA e deterministica -> testavel sem MQTT/Kafka.
# ============================================================================
"""Combiner de borda: reduz volume de telemetria antes de trafegar na rede."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Iterable, Sequence


@dataclass(frozen=True)
class LeituraCrua:
    """Uma leitura instantanea de sensores no veiculo (grao sub-segundo)."""

    vehicle_id: str
    event_ts: int  # epoch milissegundos (event-time)
    velocidade: float  # km/h
    bateria: float  # % 0..100
    autonomia_km: float
    temperatura: float  # C
    lat: float
    lon: float
    evento_brusco: bool  # frenagem/aceleracao/curva brusca detectada na borda


@dataclass(frozen=True)
class PacoteAgregado:
    """Pacote pre-agregado emitido pela borda (o que realmente trafega)."""

    vehicle_id: str
    window_start_ts: int
    window_end_ts: int
    n_leituras: int
    velocidade_media: float
    velocidade_maxima: float
    bateria_min: float
    bateria_fim: float
    autonomia_fim_km: float
    temperatura_media: float
    lat_fim: float
    lon_fim: float
    km_percorridos: float
    eventos_bruscos: int

    def as_dict(self) -> dict:
        """Serializa para dict (compatibilidade com Avro/JSON)."""
        return {
            "vehicle_id": self.vehicle_id,
            "window_start_ts": self.window_start_ts,
            "window_end_ts": self.window_end_ts,
            "n_leituras": self.n_leituras,
            "velocidade_media": round(self.velocidade_media, 3),
            "velocidade_maxima": round(self.velocidade_maxima, 3),
            "bateria_min": round(self.bateria_min, 3),
            "bateria_fim": round(self.bateria_fim, 3),
            "autonomia_fim_km": round(self.autonomia_fim_km, 3),
            "temperatura_media": round(self.temperatura_media, 3),
            "lat_fim": round(self.lat_fim, 6),
            "lon_fim": round(self.lon_fim, 6),
            "km_percorridos": round(self.km_percorridos, 4),
            "eventos_bruscos": self.eventos_bruscos,
        }


def _km_entre(a: LeituraCrua, b: LeituraCrua) -> float:
    """Distancia aproximada entre duas leituras consecutivas (haversine)."""
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(h))


def combinar(leituras: Sequence[LeituraCrua]) -> PacoteAgregado:
    """Combiner: reduz uma janela de leituras cruas de UM veiculo a 1 pacote.

    Pre-condicao: todas as leituras sao do mesmo vehicle_id. As leituras sao
    ordenadas por event_ts (a ordem estrita por veiculo e garantida ainda na
    borda - R1). Distancia percorrida acumulada por haversine entre pontos
    consecutivos (proxy de km sem odometro).

    Raises:
        ValueError: se a lista estiver vazia ou misturar veiculos.
    """
    if not leituras:
        raise ValueError("combinar() requer ao menos 1 leitura")
    ids = {l.vehicle_id for l in leituras}
    if len(ids) != 1:
        raise ValueError(f"combiner e por veiculo; recebeu multiplos ids: {sorted(ids)}")

    ordenadas = sorted(leituras, key=lambda l: l.event_ts)
    km = sum(_km_entre(ordenadas[i - 1], ordenadas[i]) for i in range(1, len(ordenadas)))
    ultima = ordenadas[-1]

    return PacoteAgregado(
        vehicle_id=ultima.vehicle_id,
        window_start_ts=ordenadas[0].event_ts,
        window_end_ts=ultima.event_ts,
        n_leituras=len(ordenadas),
        velocidade_media=fmean(l.velocidade for l in ordenadas),
        velocidade_maxima=max(l.velocidade for l in ordenadas),
        bateria_min=min(l.bateria for l in ordenadas),
        bateria_fim=ultima.bateria,
        autonomia_fim_km=ultima.autonomia_km,
        temperatura_media=fmean(l.temperatura for l in ordenadas),
        lat_fim=ultima.lat,
        lon_fim=ultima.lon,
        km_percorridos=km,
        eventos_bruscos=sum(1 for l in ordenadas if l.evento_brusco),
    )


def taxa_compressao(n_leituras_cruas: int, n_pacotes: int) -> float:
    """Fator de reducao de mensagens obtido pelo combiner (>= 1.0).

    Metrica de defesa (R3): quanto a borda economizou de banda. 1 pacote no
    lugar de N leituras => taxa = N/n_pacotes.
    """
    if n_pacotes <= 0:
        raise ValueError("n_pacotes deve ser > 0")
    return n_leituras_cruas / n_pacotes


def combinar_lote(leituras: Iterable[LeituraCrua], tamanho_janela: int) -> list[PacoteAgregado]:
    """Aplica o combiner em janelas fixas de `tamanho_janela` leituras por veiculo.

    Agrupa por vehicle_id preservando a ordem de chegada e emite um pacote a
    cada `tamanho_janela` leituras (a ultima janela parcial tambem e emitida).
    """
    if tamanho_janela <= 0:
        raise ValueError("tamanho_janela deve ser > 0")
    por_veiculo: dict[str, list[LeituraCrua]] = {}
    for l in leituras:
        por_veiculo.setdefault(l.vehicle_id, []).append(l)

    pacotes: list[PacoteAgregado] = []
    for _vid, buffer in por_veiculo.items():
        for i in range(0, len(buffer), tamanho_janela):
            janela = buffer[i : i + tamanho_janela]
            pacotes.append(combinar(janela))
    return pacotes
