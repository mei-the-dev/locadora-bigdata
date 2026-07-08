# ============================================================================
# orchestration/airflow/dags/elt_lakehouse.py - Fase 7 (orquestracao ELT, R14).
# Substitui o pg_cron da Av.02 por um DAG orquestrado bronze -> silver ->
# {cassandra, hotpath} -> gold -> markov -> refresh_serving. Cada tarefa dispara
# o job correspondente no container `spark`/`streamlit` via `docker exec` (Airflow
# como orquestrador de containers irmaos). Falha de tarefa re-executa (replay do
# offset Kafka - Kreps 2011). ELT declarativo Spark SQL/Catalyst (Armbrust 2015).
# ============================================================================
"""DAG Airflow do ELT do Lakehouse (bronze→silver→gold→serving)."""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

_DEFAULT_ARGS = {
    "owner": "frota-bigdata",
    "retries": 2,  # re-execucao (rewind por offset Kafka)
    "retry_delay": timedelta(seconds=30),
}


def _spark(job: str, extra: str = "") -> str:
    return f"docker exec fleet-spark bash /opt/fleet/spark/submit.sh jobs/{job} {extra}".strip()


with DAG(
    dag_id="elt_lakehouse",
    description="ELT do Lakehouse: bronze -> silver -> gold -> serving",
    default_args=_DEFAULT_ARGS,
    schedule="@hourly",
    start_date=pendulum.datetime(2026, 1, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    tags=["frota", "lakehouse", "elt"],
) as dag:

    bronze = BashOperator(
        task_id="bronze_ingest",
        bash_command=_spark("bronze_ingest.py", "--mode availableNow"),
    )
    silver = BashOperator(
        task_id="silver_conform",
        bash_command=_spark("silver_conform.py"),
    )
    sink_cassandra = BashOperator(
        task_id="sink_cassandra",
        bash_command=_spark("sink_cassandra.py"),
    )
    hotpath = BashOperator(
        task_id="hotpath_emergency",
        bash_command=_spark("hotpath_emergency.py", "--mode availableNow"),
    )
    gold_dim = BashOperator(
        task_id="gold_dimensional",
        bash_command=_spark("gold_dimensional.py"),
    )
    gold_markov = BashOperator(
        task_id="gold_markov",
        bash_command=_spark("gold_markov.py"),
    )
    refresh = BashOperator(
        task_id="refresh_serving",
        bash_command="docker exec fleet-streamlit python /app/app/common/refresh_serving.py",
    )

    # DAG: bronze -> silver -> {cassandra, hotpath, gold_dim} -> gold_markov -> refresh
    bronze >> silver >> [sink_cassandra, hotpath, gold_dim]
    gold_dim >> gold_markov >> refresh
