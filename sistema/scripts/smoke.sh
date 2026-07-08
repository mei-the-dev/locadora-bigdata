#!/usr/bin/env bash
# ============================================================================
# smoke.sh - teste de fumaca (Fase 0): operacao basica em cada servico core.
# Cada linha valida um requisito de infraestrutura. Verde em todos = fundacao OK.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose --profile core"
ok=0; falhas=0
check() { # nome  comando...
  local nome="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  [OK]   $nome"; ok=$((ok+1));
  else echo "  [FAIL] $nome"; falhas=$((falhas+1)); fi
}

echo "== SMOKE TEST (perfil core) =="

check "Mosquitto (MQTT) publica/consome" \
  $COMPOSE exec -T mosquitto sh -c "mosquitto_pub -t frota/smoke -m ping"

check "Redpanda cluster saudavel" \
  $COMPOSE exec -T redpanda rpk cluster health

check "Kafka topicos existem (telemetry)" \
  bash -c "$COMPOSE exec -T redpanda rpk topic list | grep -q telemetry"

check "MinIO responde (bucket lakehouse)" \
  $COMPOSE exec -T minio mc ls local/

check "Cassandra keyspace frota" \
  $COMPOSE exec -T cassandra cqlsh -e "USE frota; DESCRIBE TABLES;"

check "MongoDB responde (ping)" \
  $COMPOSE exec -T mongodb mongosh --quiet --eval "db.adminCommand({ping:1})"

check "Redis PONG" \
  $COMPOSE exec -T redis redis-cli ping

check "Postgres Gold responde (schema dw_locadora)" \
  $COMPOSE exec -T postgres-gold psql -U "${POSTGRES_USER:-dw}" -d "${POSTGRES_DB:-dw}" -c "SELECT COUNT(*) FROM dw_locadora.Dim_Veiculo;"

check "Postgres Gold - matriz de Markov (linhas somam 1.0)" \
  $COMPOSE exec -T postgres-gold psql -U "${POSTGRES_USER:-dw}" -d "${POSTGRES_DB:-dw}" -Atc \
    "SELECT bool_and(ABS(s-1.0)<0.001) FROM (SELECT SUM(p_ij) s FROM dw_locadora.v_markov GROUP BY patio_origem) q;"

check "Flink JobManager UI (overview)" \
  $COMPOSE exec -T flink-jobmanager curl -fsS http://localhost:8081/overview

echo "== Resultado: ${ok} OK, ${falhas} FALHAS =="
exit $(( falhas > 0 ? 1 : 0 ))
