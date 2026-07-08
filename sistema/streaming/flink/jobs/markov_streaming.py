# ============================================================================
# streaming/flink/jobs/markov_streaming.py - [OPCIONAL] Markov condicional em
# janela deslizante (plano secao 3.6). Le o topico `trip` (viagens/repos.), conta
# transicoes (patio_origem -> patio_destino) por faixa horaria numa HOP window e
# emite contadores. A normalizacao para matriz estocastica (linha soma 1.0)
# reutiliza fleetlib.markov no gold_markov/serving - fecha a lacuna da Markov
# homogenea da Av.02 (Zaharia 2012 - iterativo/quase tempo real).
# Uso: flink run -py markov_streaming.py
# ============================================================================
"""Contagem de transições entre pátios em janela deslizante (Markov condicional)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/opt/flink")

from pyflink.table import EnvironmentSettings, TableEnvironment

_BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
_TOPIC_IN = os.getenv("KAFKA_TOPIC_VIAGEM", "trip")
_TOPIC_OUT = os.getenv("KAFKA_TOPIC_MARKOV", "markov_counts")


def _ddl_source() -> str:
    return f"""
    CREATE TABLE trips (
        vehicle_id STRING,
        empresa STRING,
        event_ts BIGINT,
        id_viagem STRING,
        patio_origem STRING,
        patio_destino STRING,
        vazio BOOLEAN,
        motivo STRING,
        distancia_km DOUBLE,
        event_time AS TO_TIMESTAMP_LTZ(event_ts, 3),
        WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = '{_TOPIC_IN}',
        'properties.bootstrap.servers' = '{_BROKER}',
        'properties.group.id' = 'flink-markov-streaming',
        'scan.startup.mode' = 'earliest-offset',
        'format' = 'avro'
    )
    """


def _ddl_sink() -> str:
    return f"""
    CREATE TABLE markov_counts (
        patio_origem STRING,
        patio_destino STRING,
        faixa_horaria STRING,
        window_start TIMESTAMP(3),
        window_end TIMESTAMP(3),
        movimentacoes BIGINT
    ) WITH (
        'connector' = 'kafka',
        'topic' = '{_TOPIC_OUT}',
        'properties.bootstrap.servers' = '{_BROKER}',
        'format' = 'json'
    )
    """


def _query() -> str:
    # Faixa horaria alinhada ao 06_ddl / fleetlib.conform (Madrugada/Manha/Tarde/Noite).
    return """
    SELECT
        patio_origem, patio_destino,
        CASE
            WHEN HOUR(window_start) BETWEEN 0 AND 5  THEN 'Madrugada'
            WHEN HOUR(window_start) BETWEEN 6 AND 11 THEN 'Manha'
            WHEN HOUR(window_start) BETWEEN 12 AND 17 THEN 'Tarde'
            ELSE 'Noite'
        END AS faixa_horaria,
        window_start, window_end,
        COUNT(*) AS movimentacoes
    FROM TABLE(
        HOP(TABLE trips, DESCRIPTOR(event_time), INTERVAL '30' SECONDS, INTERVAL '2' MINUTES)
    )
    GROUP BY patio_origem, patio_destino, window_start, window_end
    """


def main() -> None:
    env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
    env.execute_sql(_ddl_source())
    env.execute_sql(_ddl_sink())
    env.sql_query(_query()).execute_insert("markov_counts").wait()


if __name__ == "__main__":
    main()
