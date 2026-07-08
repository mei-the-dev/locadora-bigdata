# ============================================================================
# Testes: codec Avro schemaless (round-trip) + envelope com checksum.
# Requer fastavro; pulado automaticamente se ausente (mantem a suite pura leve).
# ============================================================================
import struct
from pathlib import Path

import pytest

fastavro = pytest.importorskip("fastavro")

from fleetlib import avro_io, checksum  # noqa: E402

_SCHEMAS = Path(__file__).resolve().parents[2] / "simulator" / "schemas"


def test_telemetria_round_trip():
    schema = avro_io.carregar_schema(_SCHEMAS / "telemetry.avsc")
    registro = {
        "vehicle_id": "VEH-001", "empresa": "AutoRio Locadora",
        "window_start_ts": 1000, "window_end_ts": 2000, "n_leituras": 10,
        "velocidade_media": 48.2, "velocidade_maxima": 92.0, "bateria_min": 71.0,
        "bateria_fim": 70.0, "autonomia_fim_km": 210.0, "temperatura_media": 31.5,
        "lat_fim": -22.9, "lon_fim": -43.2, "km_percorridos": 12.3, "eventos_bruscos": 2,
        "patio_base": "Galeao",
    }
    blob = avro_io.encode(schema, registro)
    assert avro_io.decode(schema, blob) == registro


def test_envelope_crc_prefixo_valida_na_ponte():
    # Simula o envelope produzido pelo simulador e verificado pela ponte.
    schema = avro_io.carregar_schema(_SCHEMAS / "emergency.avsc")
    registro = {
        "vehicle_id": "VEH-003", "empresa": "VelozCar", "event_ts": 123456,
        "id_ocorrencia": "OCC-000001", "categoria": "Colisao", "severidade": 5,
        "lat": -23.0, "lon": -43.3, "bateria": 42.0, "id_sensor": None,
        "detalhe": "Cenario injetado: Colisao",
    }
    blob = avro_io.encode(schema, registro)
    crc = checksum.calcular_crc32(blob)
    envelope_bytes = struct.pack(">I", crc) + blob

    # lado da ponte
    crc_lido = struct.unpack(">I", envelope_bytes[:4])[0]
    payload = envelope_bytes[4:]
    env = checksum.Envelope(partition_key="VEH-003", payload=payload, crc32=crc_lido)
    checksum.verificar(env)  # nao levanta
    assert avro_io.decode(schema, payload)["categoria"] == "Colisao"
