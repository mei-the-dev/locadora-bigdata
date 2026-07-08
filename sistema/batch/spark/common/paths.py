# ============================================================================
# batch/spark/common/paths.py - caminhos e schemas Avro do Lakehouse.
# Camadas medalhao Bronze -> Silver -> Gold em s3a://<bucket>/... e leitura dos
# .avsc do simulador para o from_avro do Spark.
# ============================================================================
"""Caminhos Delta (Bronze/Silver/Gold) e carga dos schemas Avro."""

from __future__ import annotations

import json
import os
from pathlib import Path

_BUCKET = os.getenv("MINIO_BUCKET", "lakehouse")
_BASE = f"s3a://{_BUCKET}"

# Schemas Avro (montados no container Spark ou empacotados junto)
_SCHEMA_DIR = Path(os.getenv("AVRO_SCHEMA_DIR", "/opt/fleet/spark/schemas"))


def bronze(dataset: str) -> str:
    """Zona bruta append-only (imutavel)."""
    return f"{_BASE}/bronze/{dataset}"


def silver(dataset: str) -> str:
    """Zona conformada/deduplicada."""
    return f"{_BASE}/silver/{dataset}"


def gold(dataset: str) -> str:
    """Zona dimensional (materializacao Delta da Gold, alem do Postgres ROLAP)."""
    return f"{_BASE}/gold/{dataset}"


def checkpoint(nome: str) -> str:
    """Diretorio de checkpoint do Structured Streaming (exactly-once)."""
    return f"{_BASE}/_checkpoints/{nome}"


def avro_schema_json(nome: str) -> str:
    """Le o .avsc (telemetry/emergency/trip) como string JSON para from_avro."""
    with open(_SCHEMA_DIR / f"{nome}.avsc", "r", encoding="utf-8") as fh:
        return json.dumps(json.load(fh))
