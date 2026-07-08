#!/usr/bin/env bash
# ============================================================================
# demo.sh - roteiro cronometrado da defesa (~10-12 min). Cada passo imprime a
# narrativa (o "porque" com fundamento) e executa a evidencia. Mapeado ao plano
# secao 7.3. Pausas com ENTER para conduzir a banca.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
COMPOSE="docker compose --profile core"
PGSQL="$COMPOSE exec -T postgres-gold psql -U ${POSTGRES_USER:-dw} -d ${POSTGRES_DB:-dw}"

pausa() { echo; read -rp ">>> ENTER para o proximo passo..." _; echo; }
titulo() { echo; echo "============================================================"; echo "$1"; echo "============================================================"; }

titulo "1) Fundacao reconstituivel (Ghemawat 2003: falha e a norma)"
$COMPOSE ps
pausa

titulo "2) Ingestao: Kafka particionado por vehicle_id, ordem estrita (R1 - Kreps 2011)"
echo "Ultimas mensagens do topico telemetry (chave = vehicle_id):"
$COMPOSE exec -T redpanda rpk topic consume telemetry --num 5 -o end 2>/dev/null || true
pausa

titulo "3) Tolerancia a falha do Flink (R2 - ABS/checkpoints, arXiv 1506.08603)"
echo "Matando um TaskManager; o job recupera do ultimo snapshot:"
$COMPOSE kill flink-taskmanager || true
sleep 3
$COMPOSE up -d flink-taskmanager
pausa

titulo "4) Dashboard OLAP: KPIs (cache Redis) + drill-down + cubo (Gray 1997)"
echo "KPIs da frota (v_kpi_frota):"
$PGSQL -c "SELECT * FROM dw_locadora.v_kpi_frota;"
echo "Cubo executivo (subtotais ALL):"
$PGSQL -c "SELECT empresa, patio, faixa_conducao, km_total, score_medio FROM dw_locadora.mv_cubo_frota WHERE patio='ALL' ORDER BY empresa LIMIT 10;"
echo "Abra o dashboard: http://localhost:${STREAMLIT_PORT:-8501}"
pausa

titulo "5) Emergencia -> dossie point-in-time (R8 - Delta time-travel, Armbrust 2020)"
$PGSQL -c "SELECT id_ocorrencia, vehicle_id, categoria_evento, severidade, flag_dossie FROM dw_locadora.v_emergencias LIMIT 5;"
echo "Reconstrucao point-in-time via: python app/emergency/dossier.py <id_ocorrencia>"
pausa

titulo "6) Cobranca pos-uso exactly-once (R7 - Zaharia 2013)"
$PGSQL -c "SELECT id_locacao, valor_base, acrescimo_km, acrescimo_consumo, valor_final FROM dw_locadora.Fato_Cobranca ORDER BY id_locacao;"
echo "Reprocessar a mesma locacao NAO duplica (UNIQUE id_locacao)."
pausa

titulo "7) Concierge por IA + RAG local (R9 - Lewis 2020, sem LLM paga)"
echo "Exemplo: 'quanto custa alugar um SUV por dia?'"
$COMPOSE exec -T streamlit python /app/ai/concierge/concierge_cli.py "quanto custa alugar um SUV por dia?" 2>/dev/null \
  || python ai/concierge/concierge_cli.py "quanto custa alugar um SUV por dia?" 2>/dev/null || true
pausa

titulo "8) Matriz de Markov: reposicionamento do veiculo vazio (R12)"
$PGSQL -c "SELECT patio_origem, patio_destino, p_ij_pct FROM dw_locadora.v_markov ORDER BY patio_origem, p_ij DESC LIMIT 12;"
echo
echo "Fim da demonstracao do perfil core. (Extras full: Airflow, Neo4j, MLflow.)"
