#!/usr/bin/env bash
# ============================================================================
# wait_healthy.sh - espera os servicos core com healthcheck ficarem 'healthy'.
# Usado por `make up-core`. Timeout defensivo (~3 min) para nao travar a demo.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --profile core"
# Servicos que possuem healthcheck definido no compose.
SERVICOS=(mosquitto redpanda minio cassandra mongodb redis postgres-gold flink-jobmanager)
TIMEOUT=${WAIT_TIMEOUT:-180}
INTERVALO=5
decorrido=0

echo "Aguardando health de: ${SERVICOS[*]} (timeout ${TIMEOUT}s)"
while (( decorrido < TIMEOUT )); do
  pendentes=()
  for s in "${SERVICOS[@]}"; do
    cid=$($COMPOSE ps -q "$s" 2>/dev/null)
    if [[ -z "$cid" ]]; then pendentes+=("$s(?)"); continue; fi
    estado=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null)
    [[ "$estado" == "healthy" || "$estado" == "running" ]] || pendentes+=("$s($estado)")
  done
  if (( ${#pendentes[@]} == 0 )); then
    echo "OK - todos os servicos core saudaveis (${decorrido}s)."
    exit 0
  fi
  echo "  ... pendentes: ${pendentes[*]}  (${decorrido}s)"
  sleep "$INTERVALO"; decorrido=$(( decorrido + INTERVALO ))
done

echo "TIMEOUT: servicos ainda nao saudaveis: ${pendentes[*]}" >&2
exit 1
