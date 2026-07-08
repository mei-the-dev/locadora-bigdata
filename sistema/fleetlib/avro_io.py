# ============================================================================
# fleetlib.avro_io - codec Avro schemaless compartilhado (simulador e ponte).
# fastavro e importado de forma PREGUICOSA: `import fleetlib` continua funcionando
# sem fastavro (mantem os testes puros offline). Avro escolhido por eficiencia e
# evolucao de schema sob banda cara (Kreps 2011).
# ============================================================================
"""Encode/decode Avro schemaless (fastavro carregado sob demanda)."""

from __future__ import annotations

import io
import json
from pathlib import Path


def carregar_schema(caminho: str | Path) -> dict:
    """Carrega e faz o parse de um schema Avro (.avsc) para dict."""
    from fastavro import parse_schema  # lazy

    with open(caminho, "r", encoding="utf-8") as fh:
        return parse_schema(json.load(fh))


def encode(schema: dict, registro: dict) -> bytes:
    """Serializa um registro em Avro schemaless (bytes compactos)."""
    from fastavro import schemaless_writer  # lazy

    buf = io.BytesIO()
    schemaless_writer(buf, schema, registro)
    return buf.getvalue()


def decode(schema: dict, blob: bytes) -> dict:
    """Desserializa bytes Avro schemaless em dict (valida integridade de schema)."""
    from fastavro import schemaless_reader  # lazy

    return schemaless_reader(io.BytesIO(blob), schema)
