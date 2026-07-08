# ============================================================================
# streaming/flink/jobs/continuous_analytics.py - Fase 4 (analise continua).
# PyFlink Table API sobre o topico Kafka `telemetry` (Avro):
#   - EVENT-TIME + WATERMARK explicito (trata desordem da rede movel - R1)
#   - janela TUMBLE por vehicle_id (estado chaveado)
#   - score de conducao via UDF Python que reutiliza fleetlib.scoring (mesma
#     logica testada por unidade)
#   - sink de janela para print (visibilidade na demo) e Kafka JSON
#     (`vehicle_window_score`) para o serving/dashboard.
# Watermarks + fonte replayable (Kafka) + checkpoints = exactly-once (Carbone
# 2015; arXiv 1506.08603 - ABS). Recuperacao apos `docker kill` do TaskManager.
# Uso: flink run -py continuous_analytics.py
# ============================================================================
"""Job Flink de analise contínua: janelas event-time + score por veículo."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/opt/flink")  # torna fleetlib importavel no cluster

from pyflink.table import EnvironmentSettings, TableEnvironment
from pyflink.table.expressions import col
from pyflink.table.udf import udf

_BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
_TOPIC_IN = os.getenv("KAFKA_TOPIC_TELEMETRIA", "telemetry")
_TOPIC_OUT = os.getenv("KAFKA_TOPIC_ANALYTICS", "vehicle_window_score")
_JANELA = os.getenv("FLINK_WINDOW_SECONDS", "30")


@udf(result_type="DOUBLE")
def driving_score(km, vel_media, vel_max, bruscos, consumo_pct):
    """UDF: score de conducao (0..100) reutilizando a logica testada da fleetlib."""
    from fleetlib.scoring import FeaturesConducao, calcular_score

    f = FeaturesConducao(
        km_rodados=float(km or 0.0),
        velocidade_media=float(vel_media or 0.0),
        velocidade_maxima=float(vel_max or 0.0),
        eventos_bruscos=int(bruscos or 0),
        consumo_bateria_pct=float(consumo_pct or 0.0),
    )
    return calcular_score(f)


def _ddl_source() -> str:
    return f"""
    CREATE TABLE telemetry (
        vehicle_id STRING,
        empresa STRING,
        window_start_ts BIGINT,
        window_end_ts BIGINT,
        n_leituras INT,
        velocidade_media DOUBLE,
        velocidade_maxima DOUBLE,
        bateria_min DOUBLE,
        bateria_fim DOUBLE,
        autonomia_fim_km DOUBLE,
        temperatura_media DOUBLE,
        lat_fim DOUBLE,
        lon_fim DOUBLE,
        km_percorridos DOUBLE,
        eventos_bruscos INT,
        patio_base STRING,
        event_time AS TO_TIMESTAMP_LTZ(window_end_ts, 3),
        WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = '{_TOPIC_IN}',
        'properties.bootstrap.servers' = '{_BROKER}',
        'properties.group.id' = 'flink-continuous-analytics',
        'scan.startup.mode' = 'earliest-offset',
        'format' = 'avro'
    )
    """


def _ddl_sink_kafka() -> str:
    return f"""
    CREATE TABLE vehicle_window_score (
        vehicle_id STRING,
        empresa STRING,
        window_start TIMESTAMP(3),
        window_end TIMESTAMP(3),
        km DOUBLE,
        vel_media DOUBLE,
        vel_max DOUBLE,
        bruscos BIGINT,
        consumo_pct DOUBLE,
        score DOUBLE
    ) WITH (
        'connector' = 'kafka',
        'topic' = '{_TOPIC_OUT}',
        'properties.bootstrap.servers' = '{_BROKER}',
        'format' = 'json'
    )
    """


def _ddl_sink_print() -> str:
    return """
    CREATE TABLE janela_print (
        vehicle_id STRING, empresa STRING,
        window_start TIMESTAMP(3), window_end TIMESTAMP(3),
        km DOUBLE, vel_media DOUBLE, vel_max DOUBLE,
        bruscos BIGINT, consumo_pct DOUBLE, score DOUBLE
    ) WITH ('connector' = 'print')
    """


def _query_janela() -> str:
    return f"""
    SELECT
        vehicle_id, empresa, window_start, window_end,
        SUM(km_percorridos)                                       AS km,
        AVG(velocidade_media)                                     AS vel_media,
        MAX(velocidade_maxima)                                    AS vel_max,
        SUM(CAST(eventos_bruscos AS BIGINT))                      AS bruscos,
        GREATEST(MAX(bateria_fim) - MIN(bateria_fim), CAST(0.0 AS DOUBLE)) AS consumo_pct
    FROM TABLE(
        TUMBLE(TABLE telemetry, DESCRIPTOR(event_time), INTERVAL '{_JANELA}' SECONDS)
    )
    GROUP BY vehicle_id, empresa, window_start, window_end
    """


def main() -> None:
    env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
    env.get_config().set("parallelism.default", "2")
    env.create_temporary_function("driving_score", driving_score)

    env.execute_sql(_ddl_source())
    env.execute_sql(_ddl_sink_kafka())
    env.execute_sql(_ddl_sink_print())

    janela = env.sql_query(_query_janela())
    env.create_temporary_view("janela", janela)

    # aplica o score da fleetlib e distribui para os dois sinks
    resultado = env.sql_query(
        """
        SELECT vehicle_id, empresa, window_start, window_end, km, vel_media,
               vel_max, bruscos, consumo_pct,
               driving_score(km, vel_media, vel_max, bruscos, consumo_pct) AS score
        FROM janela
        """
    )
    stmt = env.create_statement_set()
    stmt.add_insert("vehicle_window_score", resultado)
    stmt.add_insert("janela_print", resultado)
    stmt.execute()


if __name__ == "__main__":
    main()
