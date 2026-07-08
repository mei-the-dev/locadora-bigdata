# ============================================================================
# fleetlib.checksum - integridade da ponte MQTT->Kafka (R2 sem perda).
# A ponte anexa um checksum ao payload; o consumidor valida antes de aceitar.
# Fundamento: Ghemawat 2003 (registros auto-validaveis por checksum no GFS;
# deteccao de corrupcao na borda do armazenamento). Logica PURA -> testavel.
# ============================================================================
"""Checksum CRC32 para validar integridade de mensagens na ponte."""

from __future__ import annotations

import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Envelope:
    """Envelope de transporte: payload bruto + checksum + chave de particao."""

    partition_key: str  # vehicle_id -> particao Kafka (ordem estrita R1)
    payload: bytes
    crc32: int

    def valido(self) -> bool:
        """True se o CRC32 recomputado bate com o anexado."""
        return calcular_crc32(self.payload) == self.crc32


def calcular_crc32(payload: bytes) -> int:
    """CRC32 nao-negativo (0..2^32-1) do payload."""
    return zlib.crc32(payload) & 0xFFFFFFFF


def selar(partition_key: str, payload: bytes) -> Envelope:
    """Cria um envelope selado com o CRC32 do payload."""
    if not partition_key:
        raise ValueError("partition_key (vehicle_id) e obrigatorio para R1")
    return Envelope(partition_key=partition_key, payload=payload, crc32=calcular_crc32(payload))


def verificar(envelope: Envelope) -> None:
    """Valida o envelope; levanta ValueError se corrompido (fail-fast).

    Raises:
        ValueError: quando o CRC32 nao confere (mensagem descartada/reenfileirada).
    """
    if not envelope.valido():
        esperado = calcular_crc32(envelope.payload)
        raise ValueError(
            f"checksum invalido para vehicle_id={envelope.partition_key}: "
            f"esperado={esperado} recebido={envelope.crc32}"
        )
