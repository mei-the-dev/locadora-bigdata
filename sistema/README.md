# Solução Big Data — Frota Autônoma Conectada (sistema executável)

**Avaliação 03 · MAE016.15912 / EEL890 — TED-B: Big Data & Data Warehouse · UFRJ/NCE**
**Professor:** Milton Ramos Ramirez · **2026.1**

## Grupo

| Nome completo | DRE |
|---|---|
| Izabela Lima da Silva | 124156557 |
| Caio Meirelles | 122071557 |

> Sistema executável (docker-compose, containers reais) que implementa a arquitetura
> descrita em [`docs/plano-implementacao.md`](../docs/plano-implementacao.md). O esquema
> estrela em PostgreSQL da Avaliação 02 deixa de ser um DW isolado e passa a ser a
> **camada GOLD** de um Lakehouse orientado a fluxo contínuo (Armbrust et al., 2021).

---

## Arquitetura (fluxo end-to-end)

```
Simulador (Avro + combiner de borda)         Camada 0 — Edge (Dean 2004: banda cara)
        │  MQTT
        ▼
Mosquitto ──ponte(checksum)──► Kafka/Redpanda   Camada 1 — log durável, partição vehicle_id
        │  (ordem estrita R1, sem perda R2)
        ├───────────────► Flink  (event-time, watermarks, estado por veículo)
        └───────────────► Spark  (hot path emergências + ELT Delta + Markov)
                                   │
        Delta Lake (MinIO)  Bronze → Silver → Gold          Camada 3 — Lakehouse Kappa
                                   │
   ┌───────────────┬───────────────┼─────────────────┬───────────────┐
   ▼               ▼               ▼                 ▼               ▼
Cassandra       MongoDB          Redis          Delta/MinIO      PostgreSQL   Camada 4 — poliglota
(telemetria)   (cadastrais/     (cache          (fonte da        (GOLD: DW
 AP/BASE        dossiês)         dashboard)      verdade)         estrela + pgvector)
                                   │
                                   ▼
        Streamlit + Cobrança + Emergências + Concierge (RAG local)   Camada 5 — serving/IA
```

Cada camada tem lastro teórico explícito (ver a tabela REQUISITOS × EMENTA × FUNDAMENTOS
no plano). Perfis Docker: **`core`** (caminho demonstrável, cabe em 16 GB) e **`full`**
(extras: Airflow, Neo4j, MLflow).

---

## Pré-requisitos

- Docker + Docker Compose v2 (`docker compose version`)
- ~16 GB de RAM para o perfil `core`
- Python 3.11+ (apenas para rodar os testes unitários de lógica pura, fora do Docker)

## Como rodar

```bash
cd sistema
make env          # cria .env a partir de .env.example
make config       # valida docker-compose (core e full)  [não sobe nada]
make up-core      # sobe o perfil core e espera ficar healthy
make seed         # aplica seed do Cassandra e refresca os cubos da Gold
make smoke        # teste de fumaça: operação básica em cada serviço
make demo         # roteiro cronometrado da defesa (~10 min)
make down         # derruba containers (mantém volumes)
make clean        # derruba tudo e remove volumes (reset completo)
```

Portas úteis: Streamlit `:8501` · Flink UI `:8081` · MinIO console `:9001` ·
Spark UI `:8080` · Postgres `:5432` · (full) Airflow `:8088` · Neo4j `:7474` · MLflow `:5000`.

### Pipeline ELT e comandos avançados

```bash
make elt              # bronze→silver→cassandra→hotpath→gold→markov→refresh (Spark)
make flink-analytics  # análise contínua (event-time/watermarks) no Flink
make rag-index        # constrói o índice vetorial pgvector (RAG persistente)
make federation       # query federada sobre 4 stores (Data Fabric)
make lgpd             # governança/LGPD na Gold (máscara PII + auditoria)
make e2e              # valida R1..R12 fim-a-fim no stack no ar
make mlops-train      # (full) treina o modelo de manutenção preditiva
make neo4j-seed       # (full) carrega o grafo de pátios/rotas
```

### Perfil `full` (extras — subir 1 por vez em 16 GB)

```bash
make up-full                                   # core + extras (cuidado com RAM)
# ou, seletivo:
docker compose --profile core --profile full up -d neo4j
docker compose --profile core --profile full up -d airflow
```

## Testes

```bash
make test         # testes UNITÁRIOS de lógica pura (fleetlib) — NÃO exige Docker
make lint         # py_compile de todo o Python
make test-int     # testes de integração (exigem o stack core no ar)
```

Os testes unitários cobrem a lógica determinística que sustenta os requisitos:
combiner de borda (R3), checksum da ponte (R2), conformação Silver, score de condução,
**matriz de Markov (linhas somam 1.0)**, **cobrança exactly-once (R7)**, **SCD2
point-in-time (R8)**, agregações do CUBO (Gray 1997), **RAG grounding + hot-swap (R9)**
e PLN por regras do concierge.

---

## Estrutura

```
sistema/
├── docker-compose.yml      # perfis core / full
├── Makefile · .env.example · pytest.ini
├── fleetlib/               # NÚCLEO de lógica pura (testável sem o stack)
│   ├── domain, edge, checksum, conform, scoring, markov,
│   ├── billing, scd2, aggregates, rag, nlp
├── simulator/              # Camada 0 — Edge (Avro + combiner) → MQTT
├── ingestion/              # mosquitto.conf + ponte MQTT→Kafka (checksum)
├── streaming/flink/        # análise contínua (event-time/watermarks)
├── batch/spark/            # bronze/silver/gold + hot path + Markov + cube
├── warehouse/              # Gold: DDL estrela (Av.02) + extensão + seed + views
│   └── init/               # scripts initdb do Postgres (00..07)
├── persistence/            # cassandra/init.cql · mongodb/init.js · redis
├── app/                    # dashboard (Streamlit) · cobrança · emergências
├── ai/                     # concierge (regras) · RAG (pgvector) · MLOps
├── orchestration/airflow/  # DAG ELT bronze→silver→gold→serving  (full)
├── graph/neo4j/            # grafo de pátios/rotas  (full)
├── scripts/                # wait_healthy · smoke · demo
└── tests/                  # unit (pura) · integration · e2e
```

## Notas de memória (16 GB)

Heaps e `mem_limit` são explícitos no compose e no `.env` (`CASSANDRA_MAX_HEAP=1G`,
Redpanda `--memory=1G`, Flink/Spark ~1.5 GB cada). O perfil `core` soma ≈ 8–9 GB com
folga para o SO/Docker. O `full` deve subir **um serviço extra por vez**.

## Fundamentos

O mapeamento completo requisito↔ementa↔referência (21 papers) está em
[`docs/plano-implementacao.md`](../docs/plano-implementacao.md) e
[`docs/fundamentos-conceitos.md`](../docs/fundamentos-conceitos.md).
