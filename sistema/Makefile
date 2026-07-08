# ============================================================================
# Makefile - Solucao Big Data para Frota Autonoma Conectada (Avaliacao 03)
# Grupo: Izabela Lima da Silva (124156557) - Caio Meirelles (122071557)
# Alvos principais:  up-core  seed  demo  test  down  (ver `make help`)
# ============================================================================
SHELL := /bin/bash
COMPOSE := docker compose
PY := python3

# Perfis
CORE := --profile core
FULL := --profile core --profile full

.DEFAULT_GOAL := help

.PHONY: help
help: ## Lista os alvos disponiveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Setup ------------------------------------------------------------------
.PHONY: env
env: ## Cria .env a partir de .env.example (se ainda nao existir)
	@test -f .env || (cp .env.example .env && echo "Criado .env a partir de .env.example")

.PHONY: config
config: ## Valida o docker-compose (config) para os perfis core e full
	$(COMPOSE) $(CORE) config >/dev/null && echo "core config OK"
	$(COMPOSE) $(FULL) config >/dev/null && echo "full config OK"

# --- Ciclo de vida do stack -------------------------------------------------
.PHONY: up-core
up-core: env ## Sobe o perfil CORE (caminho end-to-end, cabe em 16 GB)
	$(COMPOSE) $(CORE) up -d --build
	@echo "Aguardando servicos ficarem saudaveis..."
	@$(MAKE) --no-print-directory wait-core

.PHONY: up-full
up-full: env ## Sobe CORE + FULL (extras: Airflow, Neo4j, MLflow)
	$(COMPOSE) $(FULL) up -d --build

.PHONY: wait-core
wait-core: ## Espera os servicos core ficarem healthy (timeout ~3 min)
	@bash scripts/wait_healthy.sh

.PHONY: seed
seed: ## Aplica seeds que nao rodam no initdb (Cassandra) e refresca cubos
	@echo "[seed] Cassandra keyspace/tabelas..."
	$(COMPOSE) $(CORE) exec -T cassandra cqlsh -f /init.cql || echo "cassandra ainda subindo; repita apos healthy"
	@echo "[seed] Refresh dos cubos materializados (Gold)..."
	$(COMPOSE) $(CORE) exec -T postgres-gold psql -U $${POSTGRES_USER:-dw} -d $${POSTGRES_DB:-dw} \
	  -c "REFRESH MATERIALIZED VIEW dw_locadora.mv_cubo_frota; REFRESH MATERIALIZED VIEW dw_locadora.mv_cubo_financeiro;" || true

.PHONY: smoke
smoke: ## Ping em cada servico core (health/porta) - Fase 0
	@bash scripts/smoke.sh

.PHONY: demo
demo: ## Roteiro de demonstracao da defesa (~10 min)
	@bash scripts/demo.sh

.PHONY: down
down: ## Derruba os containers (mantem volumes)
	$(COMPOSE) $(FULL) down

.PHONY: clean
clean: ## Derruba tudo E remove volumes (reset completo)
	$(COMPOSE) $(FULL) down -v

.PHONY: logs
logs: ## Segue os logs de todos os servicos core
	$(COMPOSE) $(CORE) logs -f --tail=100

# --- Jobs de processamento (submissao manual p/ a demo) ---------------------
.PHONY: spark-bronze
spark-bronze: ## Ingestao Kafka -> Bronze (Delta/MinIO) via Spark
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/bronze_ingest.py

.PHONY: spark-silver
spark-silver: ## Conformacao Bronze -> Silver via Spark
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/silver_conform.py

.PHONY: spark-cassandra
spark-cassandra: ## Sink Silver -> Cassandra (telemetria + posicao_atual)
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/sink_cassandra.py

.PHONY: spark-hotpath
spark-hotpath: ## Hot path de emergencias Kafka -> Cassandra (availableNow)
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/hotpath_emergency.py --mode availableNow

.PHONY: spark-gold
spark-gold: ## Silver -> Gold: Fato_Telemetria_Diaria + Fato_Movimentacao (Markov)
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/gold_dimensional.py
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/gold_markov.py

.PHONY: elt
elt: spark-bronze spark-silver spark-cassandra spark-hotpath spark-gold refresh ## Pipeline ELT completo (bronze->silver->gold->serving)

.PHONY: refresh
refresh: ## Refresca cubos e aquece o cache Redis (serving)
	$(COMPOSE) $(CORE) exec -T streamlit python /app/app/common/refresh_serving.py

.PHONY: flink-analytics
flink-analytics: ## Submete o job de analise continua no Flink
	$(COMPOSE) $(CORE) exec -T flink-jobmanager flink run -py /opt/flink/jobs/continuous_analytics.py

# --- IA / grafo (perfil full ou dentro do container streamlit) --------------
.PHONY: rag-index
rag-index: ## Constroi/atualiza o indice vetorial (pgvector) do RAG
	$(COMPOSE) $(CORE) exec -T streamlit python /app/ai/rag/index_builder.py

.PHONY: mlops-train
mlops-train: ## Treina o modelo de manutencao preditiva (full: registra no MLflow)
	$(COMPOSE) $(CORE) exec -T streamlit python /app/ai/mlops/train_score.py

.PHONY: neo4j-seed
neo4j-seed: ## Carrega o grafo de patios/rotas no Neo4j (perfil full)
	$(COMPOSE) $(FULL) exec -T neo4j cypher-shell -u neo4j -p frotaneo4j -f /init.cypher

# --- Governanca / Data Fabric (Fase 9) --------------------------------------
.PHONY: federation
federation: ## Query federada Spark sobre 4 stores (Data Fabric)
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/federated_query.py

.PHONY: lgpd
lgpd: ## Aplica governanca LGPD na Gold (mascara PII + audit + anonimizacao)
	$(COMPOSE) $(CORE) exec -T postgres-gold psql -U $${POSTGRES_USER:-dw} -d $${POSTGRES_DB:-dw} \
	  -f /warehouse/lgpd.sql
	@echo "Direito ao esquecimento no Delta: make lgpd-delete VEH=VEH-003"

.PHONY: lgpd-delete
lgpd-delete: ## Direito ao esquecimento: DELETE Delta por veiculo (VEH=VEH-003)
	$(COMPOSE) $(CORE) exec -T spark bash /opt/fleet/spark/submit.sh jobs/lgpd_delete.py --vehicle-id $(VEH)

.PHONY: e2e
e2e: ## Fluxo fim-a-fim da defesa (valida R1..R12 no stack no ar)
	$(COMPOSE) $(CORE) exec -T streamlit python /app/tests/e2e/demo_flow.py

# --- Testes -----------------------------------------------------------------
.PHONY: test
test: ## Testes unitarios de logica pura (fleetlib) - nao exige o stack
	@test -d .venv || $(PY) -m venv .venv
	@. .venv/bin/activate && pip install -q pytest && python -m pytest tests/unit -q

.PHONY: test-int
test-int: ## Testes de integracao (exigem stack core no ar)
	@. .venv/bin/activate && python -m pytest tests/integration -q -m integration

.PHONY: lint
lint: ## Compilacao/lint estatico de todo o Python
	$(PY) -m compileall -q fleetlib simulator ingestion batch streaming ai app tests scripts && echo "py_compile OK"
