# ============================================================================
# app/emergency/dossier.py - dossie regulatorio point-in-time (R8).
# Reconstroi o estado do veiculo NO INSTANTE do sinistro combinando:
#   - Fato_Sinistro (contexto forense na Gold)
#   - Dim_Sensor SCD Tipo 2: qual firmware o sensor rodava naquela data
#     (valid_from <= data < valid_to) - o ponto central do R8
#   - telemetria imediatamente anterior (Cassandra, opcional) - estado leading-up
#   - time travel do Delta/Silver (opcional, deltalake) - snapshot imutavel
#   - cadastral do veiculo (MongoDB)
# Fundamento: Armbrust 2020 (time travel / forense); Corbett 2012 (snapshot read
# no passado). Salva o dossie no MongoDB (upsert idempotente).
# Uso: python dossier.py OCC-9001
# ============================================================================
"""Montagem do dossiê regulatório point-in-time de um sinistro."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.common import db, mongo  # noqa: E402

_SQL_SINISTRO = """
SELECT s.id_ocorrencia, v.id_veiculo_origem AS vehicle_id, v.categoria, v.modelo,
       e.nome_empresa AS empresa, te.categoria_evento, te.gravidade_padrao, te.exige_dossie,
       s.severidade, s.custo_estimado, s.tempo_resposta_seg, s.latitude, s.longitude,
       tm.data AS data_ocorrencia, td.hora_minuto AS hora_ocorrencia,
       sen.id_sensor_origem AS sensor_nk, sen.tipo_sensor, sen.versao_firmware AS firmware_registrado
FROM Fato_Sinistro s
JOIN Dim_Veiculo v ON v.sk_veiculo = s.sk_veiculo
JOIN Dim_Empresa e ON e.sk_empresa = s.sk_empresa
JOIN Dim_TipoEvento te ON te.sk_tipo_evento = s.sk_tipo_evento
JOIN Dim_Tempo tm ON tm.sk_tempo = s.sk_tempo
LEFT JOIN Dim_Tempo_Detalhe td ON td.sk_tempo_detalhe = s.sk_tempo_detalhe
LEFT JOIN Dim_Sensor sen ON sen.sk_sensor = s.sk_sensor
WHERE s.id_ocorrencia = %s
"""

# Reconstrucao point-in-time do firmware do sensor via SCD2 (na data do sinistro).
_SQL_FIRMWARE_PIT = """
SELECT versao_firmware, valid_from, valid_to, is_current
FROM Dim_Sensor
WHERE id_sensor_origem = %s
  AND valid_from <= %s AND %s < valid_to
"""


def _firmware_point_in_time(sensor_nk: str, data_ocorrencia) -> dict | None:
    if not sensor_nk:
        return None
    linhas = db.consultar(_SQL_FIRMWARE_PIT, (sensor_nk, data_ocorrencia, data_ocorrencia))
    if not linhas:
        return None
    r = linhas[0]
    return {
        "versao_firmware_vigente": r["versao_firmware"],
        "valid_from": str(r["valid_from"]),
        "valid_to": str(r["valid_to"]),
        "is_current": r["is_current"],
    }


def _telemetria_leading_up(vehicle_id: str, limite: int = 5) -> list[dict]:
    """Ultimas leituras do veiculo antes do evento (Cassandra, opcional)."""
    try:
        from cassandra.cluster import Cluster  # lazy/opcional
    except Exception:  # noqa: BLE001
        return []
    try:
        cluster = Cluster([os.getenv("CASSANDRA_HOST", "cassandra")],
                          port=int(os.getenv("CASSANDRA_PORT", "9042")))
        sess = cluster.connect(os.getenv("CASSANDRA_KEYSPACE", "frota"))
        rows = sess.execute(
            "SELECT event_ts, velocidade_media, velocidade_maxima, bateria_fim, "
            "autonomia_fim_km FROM telemetria_por_veiculo WHERE vehicle_id=%s LIMIT %s",
            (vehicle_id, limite),
        )
        out = [dict(r._asdict()) for r in rows]
        cluster.shutdown()
        return out
    except Exception:  # noqa: BLE001 - telemetria e enriquecimento, nao bloqueia o dossie
        return []


def _delta_time_travel(vehicle_id: str) -> dict:
    """Metadados de time travel do Silver (deltalake, opcional)."""
    try:
        from deltalake import DeltaTable  # lazy/opcional

        bucket = os.getenv("MINIO_BUCKET", "lakehouse")
        storage = {
            "AWS_ENDPOINT_URL": os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            "AWS_ACCESS_KEY_ID": os.getenv("MINIO_ROOT_USER", "fleetadmin"),
            "AWS_SECRET_ACCESS_KEY": os.getenv("MINIO_ROOT_PASSWORD", "fleetsecret123"),
            "AWS_ALLOW_HTTP": "true",
            "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
        }
        dt = DeltaTable(f"s3://{bucket}/silver/telemetria", storage_options=storage)
        return {"delta_versao_atual": dt.version(), "delta_disponivel": True,
                "nota": "VERSION AS OF permite reconstruir o snapshot imutavel (Armbrust 2020)"}
    except Exception:  # noqa: BLE001
        return {"delta_disponivel": False,
                "nota": "time travel disponivel apos a ingestao Delta (VERSION AS OF)"}


def montar_dossie(id_ocorrencia: str) -> dict:
    """Monta o dossie point-in-time e o persiste no MongoDB. Retorna o dossie."""
    sinistros = db.consultar(_SQL_SINISTRO, (id_ocorrencia,))
    if not sinistros:
        raise ValueError(f"sinistro nao encontrado: {id_ocorrencia}")
    s = sinistros[0]
    vehicle_id = s["vehicle_id"]

    dossie = {
        "id_ocorrencia": id_ocorrencia,
        "gerado_por": "app/emergency/dossier.py",
        "sinistro": {k: (str(v) if not isinstance(v, (int, float, bool, type(None))) else v)
                     for k, v in s.items()},
        "firmware_point_in_time": _firmware_point_in_time(s.get("sensor_nk"), s["data_ocorrencia"]),
        "telemetria_anterior": _telemetria_leading_up(vehicle_id),
        "time_travel": _delta_time_travel(vehicle_id),
        "cadastral": _cadastral(vehicle_id),
    }
    mongo.salvar_dossie(dossie)
    return dossie


def _cadastral(vehicle_id: str) -> dict | None:
    try:
        return mongo.veiculo(vehicle_id)
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python dossier.py <id_ocorrencia>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(montar_dossie(sys.argv[1]), indent=2, ensure_ascii=False, default=str))
