# ============================================================================
# Imagem Airflow (perfil full) com o CLI do Docker, para que as tarefas do DAG
# disparem os jobs Spark nos containers irmaos (`docker exec fleet-spark ...`)
# via socket montado. Padrao de orquestrador de containers irmaos.
# ============================================================================
FROM apache/airflow:2.9.3-python3.11

USER root
# CLI estatico do Docker (apenas o cliente; o daemon e o do host, via socket).
RUN set -eux; \
    curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.1.1.tgz -o /tmp/d.tgz; \
    tar -xzf /tmp/d.tgz -C /tmp; \
    install -m 0755 /tmp/docker/docker /usr/local/bin/docker; \
    rm -rf /tmp/docker /tmp/d.tgz
USER airflow
