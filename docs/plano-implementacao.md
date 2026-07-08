# Plano de Implementação — Solução Big Data para Frota Autônoma Conectada

> **Disciplina:** MAE016.15912 / EEL890 — TED-B: Big Data & Data Warehouse — UFRJ/NCE — Prof. Milton Ramos Ramirez — 2026.1
> **Grupo:** Izabela Lima da Silva (124156557) · Caio Meirelles (122071557)
> **Avaliação:** 03 (final) — sistema executável (docker-compose, containers reais) + defesa
> **Documento:** `docs/superpowers/specs/plano-implementacao.md`

---

## 1. Objetivo, escopo e mapeamento REQUISITOS × EMENTA × FUNDAMENTOS

### 1.1 Objetivo

Construir e defender um sistema Big Data **executável** que atende ao cenário de um consórcio de 6 locadoras operando uma frota de veículos **autônomos e conectados**. O sistema ingere telemetria de alta cardinalidade sob banda móvel cara/finita, com **ordenação estrita por veículo e timestamp** e **sem perda de pacotes**, e entrega: dashboard (frota/emergências/financeiro), reserva, cobrança automática pós-uso, apoio a emergências (dossiê regulatório) e um concierge de viagem por IA (voz), **sem chave de LLM paga** (PLN por regras + RAG local).

A tese estruturante: **o esquema estrela em PostgreSQL da Avaliação 02 deixa de ser um DW isolado e passa a ser a camada GOLD de um Lakehouse orientado a fluxo contínuo** (Armbrust et al., 2021).

### 1.2 Escopo

**Núcleo (obrigatório, perfil `core`):** simulador Avro/MQTT → ponte → Kafka → Flink + Spark → Cassandra/MongoDB/Redis/Delta(MinIO) → PostgreSQL (Gold) → Streamlit + cobrança + emergências.

**Full (perfil `full`):** Airflow/Dagster (orquestração ELT), banco vetorial (RAG/concierge), Neo4j (roteirização/grafo), MLOps (score de condução/manutenção preditiva), governança/LGPD.

**Fora de escopo:** produção real em nuvem, HA multi-datacenter física, LLM paga, treino de LLM do zero. Esses tópicos aparecem como **argumento teórico de defesa** (ver §9), não como código.

### 1.3 Mapeamento REQUISITOS(enunciado) × EMENTA(4 partes) × FUNDAMENTOS(referências)

| # | Requisito do enunciado | Ementa (parte) | Camada/tecnologia | Fundamento citado |
|---|------------------------|----------------|-------------------|-------------------|
| R1 | Ordenação estrita por veículo e timestamp | III (tempo real, Kafka) | Kafka partição por `vehicle_id`; Flink event-time+watermarks | Dean & Ghemawat 2004 (partição por chave + ordem intra-partição); Kreps 2011 (ordem estrita na partição); Corbett 2012 (consistência externa / TrueTime); Carbone 2015 (watermarks) |
| R2 | Sem perda de pacotes | III (tolerância a falhas) | Kafka (log durável, replay) + Flink exactly-once (ABS) + Delta txn append/version | Ghemawat 2003 (log append-only, checksum); Kreps 2011 (at-least-once + retenção); Carbone 2015 + arXiv 1506.08603 (ABS/exactly-once); Armbrust 2020 (ação `txn` appId/version) |
| R3 | Banda móvel cara e finita | I/III (localidade, combiner) | Computação de borda (Edge) pré-agrega no veículo | Dean & Ghemawat 2004 (localidade; combiner) |
| R4 | Alta concorrência de escrita | IV (BASE, wide-column) | Cassandra (LSM, sloppy quorum) | Lakshman 2009 (LSM write-optimized); DeCandia 2007 (always-writeable, hinted handoff); Chang 2006 (LSM) |
| R5 | Dashboard frota/emergências/financeiro (OLAP) | II (BI 4.0, OLAP, cubo) | Streamlit sobre Gold (Postgres) + Redis cache | Chaudhuri & Dayal 1997 (OLAP separado do OLTP; roll-up/drill/slice); Gray 1997 (CUBE, ALL) |
| R6 | Reserva | II (star schema, fatos) | Fato_Reserva na Gold | Chaudhuri & Dayal 1997 (star schema, surrogate keys) |
| R7 | Cobrança automática pós-uso | II/III (consistência forte; exactly-once) | Fato_Cobrança (novo) + motor sobre Gold/Postgres | Cattell 2011 (ACID vs BASE — checkout precisa ACID); Zaharia 2013 (exactly-once, sem dupla contagem); Gilbert & Lynch 2002 (segmentação C/A) |
| R8 | Apoio a emergências (dossiê p/ regulação) | II/IV (time travel, forense) | Fato_Emergência + Delta time-travel + MongoDB dossiê | Armbrust 2020 (time travel/SIEM/forense); Corbett 2012 (snapshot read no passado); DeCandia 2007 (SLA p99.9) |
| R8b | Latência de emergência (cauda) | I (SLA p99.9) | Spark hot path + Redis; backup tasks | DeCandia 2007 (p99.9, estado como componente do SLA); Dean 2004 (backup tasks) |
| R9 | Concierge de viagem por IA (voz) | III/IV (RAG, vetorial) | PLN por regras + RAG local + banco vetorial | Lewis 2020 (RAG, memória não-paramétrica, hot-swap, sem re-treino); Manu 2022 (banco vetorial, MIPS/HNSW) |
| R10 | Câmeras 360° / vídeo / áudio (variedade) | III (V's; semiestruturado) | Bronze Delta (blobs) + MongoDB refs + inferência de schema | Ghemawat 2003 (append bruto); Armbrust 2015 (schema inference JSON/Avro) |
| R11 | Falha como norma (6 locadoras) | I (VLDB distribuído) | Réplicas Kafka/Cassandra; docker-compose reconstituível | Ghemawat 2003 (falha é norma); Corbett 2012 (failover Paxos); Cattell 2011 (shared-nothing) |
| R12 | Previsão de ocupação / redistribuição | II/III (Markov, iterativo) | Matriz Markov (batch Spark/SQL) → serving | Zaharia 2012 (iterativo em memória — Markov/PageRank); modelo DW Av.02 |
| R13 | Roteirização do veículo vazio | III (grafo/GraphX) | Neo4j (grafo de pátios/rotas) | Ementa III (Neo4j p/ raciocínio); Cattell 2011 (grafo) |
| R14 | ELT de alta performance + orquestração | II (ETL→ELT, Airflow) | Airflow/Dagster + Spark SQL/Catalyst | Armbrust 2015 (Catalyst, DataFrame); Chaudhuri & Dayal 1997 (ETL back-end, refresh incremental) |
| R15 | Persistência poliglota | IV (CAP, poliglota) | Cassandra/MongoDB/Redis/Delta/Postgres | Cattell 2011 (taxonomia NoSQL); Gilbert & Lynch 2002 (segmentação CAP); DeCandia 2007 |

**Conclusão do mapeamento:** cada camada da arquitetura tem lastro teórico explícito e cobre as 4 partes da ementa. As lacunas do DW da Av.02 (batch D-1, grão diário, sem streaming, sem NoSQL, sem IA/RAG/grafo) são o motivo de existir deste trabalho e são endereçadas em §3.

---

## 2. Arquitetura de referência detalhada por camada

Fluxo global:
`Simulador (Avro) → MQTT (Mosquitto) → ponte MQTT→Kafka → Kafka (partição vehicle_id) → {Flink: análise contínua | Spark: hot path + ELT Delta} → {Cassandra, MongoDB, Redis, Delta/MinIO, Postgres-Gold, Neo4j, Vetorial} → {Streamlit, cobrança, emergências, concierge} — orquestrado por Airflow/Dagster.`

### Camada 0 — Borda (Edge)

- **Escolha:** simulador Python com pré-agregação no "computador de bordo" (combiner) + serialização **Avro** + schema registry.
- **Porquê:** largura de banda de rede é recurso escasso; mover computação para perto dos dados e usar combiner reduz drasticamente o tráfego (Dean & Ghemawat 2004). Avro por eficiência + evolução de schema; batching amortiza RPC (Kreps 2011).
- **Alternativa descartada:** enviar cada leitura crua em JSON — inviável sob "banda cara e finita" e sem contrato de schema.

### Camada 1 — Ingestão (broker + barramento)

- **Escolha:** **Mosquitto (MQTT)** na ponta + ponte para **Kafka** (Redpanda opcional como Kafka-compatível mais leve). Tópicos isolados por tipo de evento; partição por `vehicle_id`.
- **Porquê:** MQTT é o protocolo de campo IoT (leve, pub/sub); Kafka é o log de commit distribuído que desacopla produtor de consumidores online/offline, com ordem estrita intra-partição, retenção temporal, replay por offset e zero-copy (Kreps 2011; Ghemawat 2003 — log como linha do tempo lógica). Manu 2022 valida "log as data" sobre Kafka como backbone.
- **Alternativa descartada:** RabbitMQ (sem retenção/replay de log e sem ordenação particionada nativa para reprocessamento batch); ligar simulador direto no Kafka (perde a camada de campo IoT realista).

### Camada 2 — Processamento (stream + batch)

- **Flink (análise contínua):** janelas event-time + watermarks, estado por `vehicle_id`, rotas/score.
  - **Porquê:** dataflow unificado stream/batch; event/ingestion/processing-time; watermarks tratam desordem da rede móvel; estado chaveado com StateBackend e exactly-once via ABS/checkpoints; fontes replayable (Kafka) fecham a garantia (Carbone 2015; arXiv 1506.08603; arXiv 2008.00842 — 2ª geração out-of-order).
  - **Alternativa descartada:** Kafka Streams (menos flexível em janelamento/estado) e Storm (garantias mais fracas, 1ª/2ª geração inferior).
- **Spark (hot path de emergências + ELT Delta + batch/Markov):** micro-batch determinístico, RDD/DataFrame, Catalyst.
  - **Porquê:** recuperação por linhagem (barata, sem replicação), reuso em memória para algoritmos iterativos (Markov/score), exactly-once por discretização determinística, DataFrame+Catalyst para ELT de alta performance e federação poliglota (Zaharia 2012/2013; Armbrust 2015).
  - **Alternativa descartada:** só Flink para tudo (batch iterativo e ELT declarativo são o forte do Spark; usar a ferramenta certa por carga aproxima Lambda/Kappa prático).
- **Decisão Lambda vs Kappa:** **Kappa-pragmático** — Kafka durável + Flink unificam o caminho de tempo real; Spark cobre hot path e batch Delta. Justificativa: crítica ao Lambda (dupla implementação, latência, imprecisão) em Carbone 2015; unificação por stream durável.

### Camada 3 — Armazenamento (Lakehouse)

- **Escolha:** **MinIO (S3) + Delta Lake**, camadas **Bronze → Silver → Gold**.
  - **Porquê:** object store é key-value barato mas sem atomicidade cross-key, consistência eventual e LIST caro → Delta adiciona log transacional no próprio store, ACID serializável, estatísticas min/max (data skipping), time travel, MERGE/DELETE (compliance) e escrita exactly-once via ação `txn` (Armbrust 2020, 2021). MinIO é literalmente a tecnologia de object store desacoplado de compute (Manu 2022; Ghemawat 2003 — plano de metadados vs dados, ancestral HDFS).
  - **Alternativa descartada:** Parquet cru (herda todos os problemas de object store — corrupção em escrita parcial); HDFS dedicado (peso operacional desnecessário em 16 GB).

### Camada 4 — Persistência poliglota (serving)

| Store | Modelo | Uso | Lado do CAP | Fundamento |
|-------|--------|-----|-------------|------------|
| **Cassandra** | wide-column | telemetria (série temporal alta cardinalidade) | AP / BASE | Lakshman 2009; Chang 2006; DeCandia 2007; Cattell 2011 |
| **MongoDB** | documento | cadastrais + dossiês de emergência (aninhados, heterogêneos) | consistência por documento | Cattell 2011 (document store) |
| **Redis** | key-value | cache "ao vivo" do dashboard (estado quente) | best-effort / staleness limitado | Cattell 2011 (cache de RDBMS); Gilbert & Lynch 2002 (Akamai); Manu 2022 (delta consistency) |
| **Delta/MinIO** | Lakehouse | fonte da verdade recuperável | forte (log serializável) | Armbrust 2020/2021 |
| **PostgreSQL** | relacional (star) | **Gold** — DW dimensional, cobrança, Markov | ACID | Chaudhuri & Dayal 1997; Cattell 2011 (NewSQL/relacional) |
| **Neo4j** *(full)* | grafo | roteirização/raciocínio do veículo vazio | — | ementa III (Neo4j) |
| **Vetorial** *(full)* | vetorial | memória do concierge/RAG (embeddings) | row-level ACID / delta | Lewis 2020; Manu 2022 |

- **Porquê poliglota:** o CAP e a segmentação de consistência (dados diferentes, garantias diferentes) fundamentam usar o store certo por forma de acesso — telemetria AP vs cobrança/dossiê fortemente consistente vs cache best-effort (Gilbert & Lynch 2002; DeCandia 2007; Cattell 2011).
- **Chave de partição/clustering:** `vehicle_id` de ponta a ponta (Kafka → Spark/Flink → Cassandra), clustering por `timestamp` — co-localiza joins/agregações por veículo (sem shuffle) e entrega leituras já ordenadas cronologicamente (Zaharia 2012 — partitioner; Lakshman 2009 — clustering temporal; Corbett 2012 — directory/localidade).

### Camada 5 — Serving/aplicação e IA

- **Streamlit dashboard** (OLAP sobre Gold, cache Redis), **motor de cobrança**, **resposta a emergências** (Delta time-travel + dossiê MongoDB), **concierge** (PLN por regras + RAG local sobre banco vetorial).
- **Porquê IA sem LLM paga:** RAG aterra a geração em documentos recuperáveis (menos alucinação, proveniência, hot-swap sem re-treino) — ideal para dossiê auditável e para base de frota em mudança (Lewis 2020); banco vetorial serve o MIPS/HNSW que liga o corpus ao gerador (Manu 2022).
- **Alternativa descartada:** chatbot com API de LLM externa (proibido: sem chave paga; e menos auditável para regulação).

---

## 3. Incorporação explícita dos tópicos MODERNOS da ementa (o que falta ao desenho atual)

Marcação: **[NÚCLEO]** vai ao código do `core`; **[OPCIONAL]** entra no perfil `full` (implementado se houver folga; senão vira ponto de defesa argumentado).

### 3.1 ELT + Orquestração — **[NÚCLEO parcial]**

- **Airflow** (ou Dagster) orquestra os DAGs de ELT: `bronze_ingest → silver_conform → gold_dimensional → gold_markov → gold_aggregates → refresh_serving`.
- Substitui o `pg_cron` da Av.02 (insuficiente). ELT de alta performance = transformações declarativas Spark SQL/Catalyst com pushdown (Armbrust 2015; Chaudhuri & Dayal 1997 — ETL back-end evolui para ELT).
- **Decisão:** **Airflow** por ser o padrão de indústria e o mais citado na ementa; Dagster fica como alternativa (asset-oriented). No `core`, um DAG mínimo executável; no `full`, o pipeline completo agendado.

### 3.2 DW como camada GOLD do Lakehouse + extensão dimensional — **[NÚCLEO]**

O star schema `dw_locadora` vira a **Gold**. Extensões projetadas (detalhe em §4):
- **Novos fatos:** `Fato_Telemetria` (grão sub-segundo por evento), `Fato_Emergencia`, `Fato_Viagem_Autonoma`, `Fato_Cobranca` (materializa na Gold o `Pagamento` do OLTP, que a estrela da Av.02 não trouxe como fato, e o enriquece com ajustes dinâmicos).
- **Novas dimensões:** `Dim_Sensor/Dispositivo_Edge`, `Dim_Firmware`, `Dim_Rota/Geo/Waypoint`, `Dim_Tipo_Evento` (severidade). Separar `Dim_Data` + `Dim_Hora` (grão sub-diário) ou usar timestamp de alta resolução.
- **SCD Tipo 2** nas dimensões que exigem auditoria (Veículo/Firmware/Cliente): `valid_from/valid_to/is_current`, SK estáveis — indispensável para ingestão incremental/streaming e para o dossiê regulatório point-in-time (hoje tudo é Tipo 1 full-refresh).
- **CUBE/agregados:** cubo frota × tempo × pátio × empresa com `ALL` para a visão executiva (Gray 1997), materializado como summary tables na Gold (Chaudhuri & Dayal 1997 — views materializadas; roll-up só de função distributiva/algébrica).

### 3.3 RAG + Banco Vetorial — **[OPCIONAL, alvo de implementar]**

- **Escolha:** **pgvector** no `core` (mesmo Postgres, zero container extra, cabe em 16 GB) e **Milvus/Weaviate** como alternativa citada no `full`.
- Corpus: políticas da frota, manuais, FAQ, tarifas, dossiês. Embeddings locais (sentence-transformers) → índice HNSW → MIPS top-K → gerador por regras.
- Memória de agente = embeddings persistidos; hot-swap do índice atualiza conhecimento sem re-treino (Lewis 2020; Manu 2022).

### 3.4 Agente de IA + MLOps — **[OPCIONAL]**

- Pipeline de **score de condução** e **manutenção preditiva**: featurização Spark (DataFrame/MLlib) sobre Gold/Silver → modelo (sklearn/Spark ML) → registro de modelo (MLflow) → serving do score no dashboard.
- Agente concierge com memória (vetorial) + ferramentas (consulta Gold, disponibilidade, reserva). MLOps mínimo: versionamento de modelo, métricas, reprodutibilidade (Armbrust 2015 — DataFrames como pipeline de ML; ementa III).

### 3.5 Grafo (Neo4j) — **[OPCIONAL]**

- Grafo de pátios/rotas/waypoints para **roteirização do veículo vazio** e raciocínio do agente. Nós = pátios/veículos; arestas = rotas com peso (distância/ocupação prevista pela Markov). Complementa a matriz estocástica com caminho mínimo/raciocínio (ementa III — Neo4j/GraphX).

### 3.6 Markov condicional em streaming — **[OPCIONAL]**

- Evoluir a matriz estática/1ª ordem/homogênea (Av.02) para **condicional** (dia-da-semana/faixa-horária/categoria) e atualizada em **janela deslizante** no Flink, servindo reposicionamento em tempo (quase) real (fecha a lacuna 9 do modelo atual; Zaharia 2012 — iterativo).

### 3.7 NewSQL e Data Mesh/Fabric — **[MENÇÃO / defesa]**

- **NewSQL:** o PostgreSQL da Gold é o polo SQL+ACID; posicionamos Spanner/VoltDB como a categoria que unifica escala NoSQL + consistência SQL (Corbett 2012; Cattell 2011) — argumento de defesa, não container.
- **Data Mesh:** cada uma das 6 locadoras como produto de dados sobre o object store aberto compartilhado (Armbrust 2021). **Data Fabric:** Spark SQL federa Delta+Cassandra+Mongo+Postgres via Data Source API com pushdown (Armbrust 2015) — demonstrável com uma query federada.

### 3.8 Governança/LGPD — **[OPCIONAL]**

- Máscara de PII, retenção por família de coluna (Cassandra GC por timestamp), MERGE/DELETE Delta (direito ao esquecimento), audit log (Armbrust 2020; Chang 2006). Câmera 360° + geolocalização = dados sensíveis.

---

## 4. Modelo de dados — Gold × Lakehouse × NoSQL

### 4.1 Fluxo de maturação (medalhão)

```
Bronze (Delta/MinIO)         Silver (Delta/MinIO)              Gold (Delta + Postgres)
- telemetria bruta append    - deduplicada (vehicle_id+ts)     - star schema dimensional
- Avro/JSON semiestruturado  - conformada (domínios, UF,       - Fato_* + Dim_* (SCD2)
- 1 registro = 1 evento cru    câmbio→{Auto,Manual})           - agregados/CUBE (summary)
- imutável, checksum         - enriquecida (joins históricos)  - matriz de Markov
```

- **Bronze** = zona bruta imutável append-only; dedup por chave `vehicle_id+timestamp` na transição Silver (Ghemawat 2003 — registros auto-validáveis; consistência relaxada). Escritas exactly-once via ação `txn` do Delta (Armbrust 2020).
- **Silver** = limpeza/conformação (equivale às etapas 02/03 do ETL Av.02) em Spark SQL declarativo com pushdown (Armbrust 2015).
- **Gold** = a extensão do star schema. Materializada em **Delta** (para ML/RAG/federação lerem direto) **e** servida em **PostgreSQL ROLAP** para o dashboard OLAP (Chaudhuri & Dayal 1997; Armbrust 2021).

### 4.2 Conexão Gold ↔ NoSQL

- **Cassandra → Gold:** telemetria bruta vive em Cassandra (serving de baixa latência por veículo) **e** flui para Bronze/Silver; a Gold recebe **agregados** de telemetria (`Fato_Telemetria` no grão de janela, não por evento) via batch Spark. A "posição atual" (destino da última movimentação) continua derivável (ROW_NUMBER OVER PARTITION BY vehicle_id ORDER BY ts DESC).
- **MongoDB ↔ Gold:** cadastrais alimentam `Dim_Cliente/Veiculo`; dossiês de emergência referenciam `Fato_Emergencia` (SK) + blobs (refs para MinIO). SCD2 nas dimensões garante SK estável para o link.
- **Redis ← Gold:** cache dos agregados quentes (ocupação por pátio, KPIs) recomputados pelo Flink/Spark; revalidação best-effort (Cattell 2011; Manu 2022 delta consistency).
- **Delta = fonte da verdade:** todo estado (Cassandra/Mongo/Redis/Postgres-Gold) é **derivável por replay ordenado** do log Kafka + Delta (Ghemawat 2003; Kreps 2011).

### 4.3 Chaves estáveis (mudança-chave vs Av.02)

Abandona-se o `TRUNCATE ... RESTART IDENTITY` + `ROW_NUMBER` (SK não persistente). Adota-se **SK persistente + SCD2** para viabilizar ingestão incremental/streaming e point-in-time do dossiê (Corbett 2012 — snapshot read no passado; Armbrust 2020 — time travel).

---

## 5. Estrutura de repositório e serviços docker-compose

### 5.1 Árvore de pastas

```
fleet-bigdata/
├── docker-compose.yml              # perfis: core, full
├── .env.example                    # heaps, portas, credenciais MinIO
├── Makefile                        # up-core, up-full, seed, demo, test, down
├── README.md
├── docs/superpowers/specs/plano-implementacao.md
├── simulator/                      # Camada 0 — Edge
│   ├── Dockerfile
│   ├── simulator.py                # gera telemetria, pré-agrega (combiner), Avro
│   ├── schemas/telemetry.avsc      # + emergency.avsc, trip.avsc
│   └── edge_aggregator.py
├── ingestion/
│   ├── mqtt/mosquitto.conf
│   └── bridge/mqtt_to_kafka.py     # ponte + validação/checksum
├── streaming/flink/
│   ├── jobs/continuous_analytics.py   # janelas, watermarks, rotas, score
│   ├── jobs/markov_streaming.py       # [OPCIONAL] Markov condicional
│   └── Dockerfile
├── batch/spark/
│   ├── jobs/hotpath_emergency.py
│   ├── jobs/bronze_ingest.py
│   ├── jobs/silver_conform.py
│   ├── jobs/gold_dimensional.py
│   ├── jobs/gold_markov.py
│   └── jobs/gold_aggregates_cube.py
├── warehouse/                      # Gold (evolui os 5 scripts da Av.02)
│   ├── 01_ddl_dw_estrela.sql       # + novos fatos/dims, SCD2
│   ├── 02_extracao_staging.sql
│   ├── 03_transformacao.sql
│   ├── 04_carga_dw.sql
│   ├── 05_relatorios_matriz.sql
│   └── 06_agregados_cube.sql
├── orchestration/airflow/
│   └── dags/elt_lakehouse.py       # bronze→silver→gold→serving
├── persistence/
│   ├── cassandra/init.cql          # telemetria: PK(vehicle_id), CK(ts)
│   ├── mongodb/init.js             # cadastrais + dossiês
│   └── redis/                      # cache (sem schema)
├── ai/
│   ├── concierge/rules_nlp.py      # PLN por regras
│   ├── rag/index_builder.py        # embeddings → pgvector/Milvus
│   ├── rag/retriever.py            # MIPS/HNSW top-K
│   └── mlops/train_score.py        # [OPCIONAL] score/manutenção + MLflow
├── graph/neo4j/init.cypher         # [OPCIONAL] pátios/rotas
├── app/
│   ├── dashboard/streamlit_app.py  # frota/emergências/financeiro
│   ├── billing/billing_engine.py   # cobrança pós-uso
│   └── emergency/dossier.py        # Delta time-travel → dossiê
└── tests/
    ├── unit/                       # transforms, conformação, agregados
    ├── integration/                # smoke por serviço
    └── e2e/demo_flow.py            # roteiro de defesa automatizado
```

### 5.2 Serviços docker-compose (perfis)

| Serviço | Imagem base | Perfil | Heap/limite alvo | Papel |
|---------|-------------|--------|------------------|-------|
| `mosquitto` | eclipse-mosquitto | core | ~64 MB | broker MQTT |
| `redpanda`/`kafka` | redpanda / bitnami-kafka | core | ~1 GB | barramento de log |
| `mqtt-bridge` | python-slim | core | ~128 MB | ponte MQTT→Kafka |
| `simulator` | python-slim | core | ~128 MB | frota Avro |
| `flink-jm`+`flink-tm` | flink | core | ~1.5 GB total | análise contínua |
| `spark` | bitnami-spark | core | ~1.5 GB | hot path + ELT |
| `minio` | minio | core | ~512 MB | object store S3 |
| `cassandra` | cassandra | core | `MAX_HEAP=1G` | telemetria |
| `mongodb` | mongo | core | ~512 MB | cadastrais/dossiê |
| `redis` | redis | core | ~128 MB | cache |
| `postgres-gold` | pgvector/pgvector | core | ~512 MB | Gold + pgvector |
| `streamlit` | python-slim | core | ~256 MB | dashboard |
| `airflow` | apache/airflow | full | ~1 GB | orquestração ELT |
| `milvus`+`etcd`+`minio-milvus` | milvusdb | full | ~1.5 GB | vetorial (alt. pgvector) |
| `neo4j` | neo4j | full | ~1 GB | grafo/rotas |
| `mlflow` | python-slim | full | ~256 MB | registro de modelo |

`core` cabe em 16 GB (soma dos limites ≈ 8–9 GB com folga de OS/Docker). `full` sobe serviços sob demanda um por vez (ver §8).

---

## 6. Plano faseado de construção (9 fases)

Princípio: **ordem que sempre deixa algo demonstrável** (Ghemawat 2003 — sistema reconstituível; cada fase é um checkpoint).

### Fase 0 — Fundação e esqueleto executável
- **Objetivo:** repositório, docker-compose (perfil core), Makefile, `.env`, healthchecks.
- **Entregáveis:** `docker-compose.yml`, `make up-core` sobe todos os containers `core` saudáveis.
- **Tecnologias:** Docker Compose, MinIO, Kafka, Postgres, Cassandra, Mongo, Redis.
- **Critério de aceite:** todos os serviços `core` em `healthy`.
- **Teste:** `make smoke` (script que faz ping em cada porta/health endpoint) → todos verdes.

### Fase 1 — Borda + ingestão (simulador → MQTT → Kafka)
- **Objetivo:** telemetria fluindo com Avro, partição por `vehicle_id`, ordem estrita.
- **Entregáveis:** `simulator.py` (com combiner de borda), `mqtt_to_kafka.py`, schemas Avro.
- **Tecnologias:** MQTT, Kafka, Avro, schema registry.
- **Critério de aceite:** tópico `telemetry` recebendo N eventos/s; todas as msgs de um `vehicle_id` na mesma partição, em ordem.
- **Teste:** `kafka-console-consumer` mostra ordem monotônica de `timestamp` por partição (verifica R1); contador produzido == consumido (verifica R2 na ingestão). Fundamento: Kreps 2011; Dean 2004.

### Fase 2 — Lakehouse Bronze/Silver (Spark ELT + Delta/MinIO)
- **Objetivo:** ingestão Kafka→Bronze append, dedup/conformação→Silver.
- **Entregáveis:** `bronze_ingest.py`, `silver_conform.py`, tabelas Delta.
- **Tecnologias:** Spark Structured Streaming, Delta, MinIO.
- **Critério de aceite:** Bronze cresce append-only; Silver sem duplicatas por `vehicle_id+ts`; reprocesso idempotente (mesmo estado).
- **Teste:** rodar job duas vezes → contagem Silver estável (idempotência, Zaharia 2013); `DESCRIBE HISTORY delta` mostra versões e ação `txn` (Armbrust 2020).

### Fase 3 — Persistência poliglota (telemetria/cadastrais/cache)
- **Objetivo:** telemetria em Cassandra, cadastrais/dossiês em Mongo, cache em Redis.
- **Entregáveis:** `cassandra/init.cql` (PK vehicle_id, CK ts), `mongodb/init.js`, sinks Spark/Flink.
- **Tecnologias:** Cassandra, MongoDB, Redis.
- **Critério de aceite:** leitura de janela temporal por veículo já ordenada; cache serve KPI em <50 ms.
- **Teste:** `SELECT * FROM telemetry WHERE vehicle_id=? AND ts>? AND ts<?` retorna cronológico (Lakshman 2009); `integration/test_cassandra_order.py`.

### Fase 4 — Análise contínua (Flink: janelas, watermarks, rotas/score)
- **Objetivo:** processamento event-time por veículo com estado.
- **Entregáveis:** `continuous_analytics.py` (assigner/trigger, low-watermark, estado por chave).
- **Tecnologias:** Flink (event-time, StateBackend, checkpoints/ABS).
- **Critério de aceite:** janelas fecham por event-time apesar de eventos fora de ordem; recuperação após kill do TaskManager sem perda/duplicação.
- **Teste:** injetar evento atrasado → janela correta (Carbone 2015); `docker kill flink-tm` → job recupera do último snapshot (arXiv 1506.08603). Verifica R1/R2.

### Fase 5 — Gold dimensional + Markov (a extensão do DW)
- **Objetivo:** Silver→Gold star schema estendido (novos fatos/dims, SCD2) + matriz de Markov + agregados/CUBE.
- **Entregáveis:** `gold_dimensional.py`, `01_ddl` estendido, `gold_markov.py`, `06_agregados_cube.sql`.
- **Tecnologias:** Spark SQL/Catalyst, PostgreSQL (ROLAP), Delta.
- **Critério de aceite:** cada linha da matriz de Markov soma 1.0000 (query de conferência); cubo com subtotais `ALL`; SK estáveis entre cargas.
- **Teste:** `test_markov_stochastic.py` (soma linhas ≈ 1.0); `test_scd2.py` (histórico preservado); roll-up frota→empresa→pátio→veículo confere (Gray 1997; Chaudhuri & Dayal 1997).

### Fase 6 — Aplicação: dashboard + cobrança + emergências
- **Objetivo:** as três necessidades operacionais do enunciado.
- **Entregáveis:** `streamlit_app.py` (OLAP sobre Gold + Redis), `billing_engine.py`, `dossier.py` (Delta time-travel).
- **Tecnologias:** Streamlit, Postgres, Delta time-travel, Mongo.
- **Critério de aceite:** dashboard mostra frota/emergências/financeiro; cobrança sem dupla contagem; dossiê reconstrói estado point-in-time do veículo.
- **Teste:** `test_billing_exactly_once.py` (reprocesso não duplica valor — Zaharia 2013); `test_dossier_timetravel.py` (`VERSION AS OF` reconstrói t — Armbrust 2020; Corbett 2012). Latência p99 de emergência medida por percentil (DeCandia 2007).

### Fase 7 — Orquestração ELT (Airflow)
- **Objetivo:** substituir cron por DAG orquestrado bronze→silver→gold→serving.
- **Entregáveis:** `dags/elt_lakehouse.py`.
- **Tecnologias:** Airflow (perfil full).
- **Critério de aceite:** DAG executa fim-a-fim; falha de tarefa re-executa (replay do offset Kafka).
- **Teste:** `airflow dags test elt_lakehouse` verde; matar tarefa → retry recupera (Kreps 2011 — rewind por offset).

### Fase 8 — IA: RAG/concierge + (opcional) MLOps/grafo
- **Objetivo:** concierge por regras + RAG local (pgvector/Milvus); score/manutenção; Neo4j.
- **Entregáveis:** `index_builder.py`, `retriever.py`, `rules_nlp.py`, `train_score.py`, `neo4j/init.cypher`.
- **Tecnologias:** sentence-transformers, pgvector/Milvus, MLflow, Neo4j.
- **Critério de aceite:** concierge responde com passagem recuperada citável (proveniência); hot-swap do índice muda a resposta sem re-treino; roteirização do veículo vazio via grafo+Markov.
- **Teste:** `test_rag_grounding.py` (resposta contém trecho do corpus — Lewis 2020); `test_hotswap.py` (trocar índice muda resposta); score do modelo registrado no MLflow.

### Fase 9 — Endurecimento, governança e ensaio de defesa
- **Objetivo:** LGPD (máscara/retenção/audit), federação Data Fabric, roteiro de demo, medição de percentis.
- **Entregáveis:** query federada Spark (Delta+Cassandra+Mongo+Postgres), políticas de retenção, `demo_flow.py`.
- **Critério de aceite:** query federada roda com pushdown; MERGE/DELETE atende esquecimento; demo roda em ~10 min.
- **Teste:** `test_federation.py`; `test_lgpd_delete.py` (registro sumido após DELETE Delta); ensaio cronometrado da defesa.

---

## 7. Estratégia de testes, dados sintéticos e roteiro de demo

### 7.1 Pirâmide de testes

- **Unit (pytest):** transforms de conformação (câmbio→{Auto,Manual}, UF, faixa etária), cálculo da matriz de Markov (linhas somam 1), agregados distributivos/algébricos vs holísticos (Gray 1997), geração de SK/SCD2. Padrão AAA. Alvo ≥80% nas libs de transformação.
- **Integração/smoke:** um teste por serviço (`healthy` + operação básica): Kafka produz/consome ordenado; Cassandra ordena por CK; Delta versiona; Flink recupera de snapshot; Postgres Gold responde OLAP.
- **E2E:** `demo_flow.py` percorre simulador→dashboard→cobrança→dossiê→concierge, validando os requisitos R1–R9.

### 7.2 Dados sintéticos (simulador)

- 6 empresas, 6 pátios canônicos, N veículos autônomos; telemetria (GPS, velocidade, bateria/autonomia, temperatura, sensores) em event-time com **desordem controlada** (atrasos aleatórios para exercitar watermarks) e **cenários injetáveis**: emergência (colisão/bateria crítica), viagem autônoma vazia, pico de concorrência. Combiner de borda pré-agrega para simular economia de banda (Dean 2004).
- Seeds determinísticos → reprodutibilidade (idempotência de reprocesso).

### 7.3 Roteiro de demo (defesa, ~10–12 min)

1. `make up-core` — containers saudáveis (fala: falha é a norma; sistema reconstituível — Ghemawat 2003).
2. Sobe simulador → mostra Kafka particionado por veículo, ordem estrita (R1 — Kreps 2011).
3. `docker kill` num TaskManager Flink → recupera sem perda (R2 — ABS, arXiv 1506.08603).
4. Dashboard ao vivo: frota (Redis cache), drill-down OLAP frota→pátio (Chaudhuri & Dayal 1997), cubo executivo (Gray 1997).
5. Injeta emergência → dossiê point-in-time por Delta time-travel (R8 — Armbrust 2020).
6. Encerra locação → cobrança pós-uso exactly-once (R7 — Zaharia 2013).
7. Concierge por voz (mock local): pergunta → RAG recupera política/tarifa e responde com fonte citável (R9 — Lewis 2020).
8. (full) Airflow DAG + roteirização Neo4j + score MLOps.
9. Query federada Data Fabric sobre 4 stores (Armbrust 2015) — fecha a convergência DW×BigData×AI (Parte I).

---

## 8. Riscos e mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| **16 GB RAM insuficiente com todos os containers** | OOM, containers mortos | Perfis `core`/`full`; subir `full` **um serviço por vez**; limites `mem_limit` e heaps explícitos (`CASSANDRA_MAX_HEAP=1G`, `SPARK_DRIVER_MEMORY`, Flink TM slots reduzidos, JVM `-Xmx`) |
| **Cassandra + Flink + Spark JVMs pesadas** | contenção de memória | Heaps fixos no `.env`; Redpanda no lugar de Kafka+ZooKeeper (menor pegada); Milvus→pgvector no `core` (elimina etcd+minio extra) |
| **Milvus/Neo4j/Airflow pesados** | não sobem juntos | `[OPCIONAL]` no `full`; degradam para argumento de defesa se não couberem |
| **Complexidade do Flink exactly-once** | tempo de dev | Começar com at-least-once + dedup idempotente no Delta (Armbrust 2020); ABS como incremento |
| **Escopo grande p/ 2 pessoas** | não terminar | Núcleo sempre demonstrável a cada fase (§6); `full` é bônus |
| **SCD2 + streaming (SK estável)** | inconsistência | SK persistente por chave natural composta `sistema_origem#id`; testes de histórico |
| **Perda de dados na ponte MQTT→Kafka** | viola R2 | Validação/checksum na ponte (Ghemawat 2003); Kafka acked; replay por offset |
| **LGPD (vídeo/geo sensíveis)** | ponto fraco na defesa | Máscara/retenção/audit no `full`; ao menos citar e mostrar MERGE/DELETE Delta |

---

## 9. Cada componente como "ponto de defesa" (≈15 componentes)

| # | Componente | Requisito atendido | Fundamento (defesa) | Ementa |
|---|-----------|--------------------|--------------------|--------|
| 1 | **Simulador Avro + Edge combiner** | R3 banda cara | Dean 2004 (combiner/localidade); Kreps 2011 (Avro/batch) | I, III |
| 2 | **Mosquitto (MQTT)** | camada de campo IoT | pub/sub de borda | III |
| 3 | **Kafka (partição vehicle_id)** | R1 ordem, R2 sem perda | Kreps 2011; Ghemawat 2003 (log); Manu 2022 (log as data) | III |
| 4 | **Flink (event-time/watermarks)** | R1, análise contínua | Carbone 2015; arXiv 2008.00842; 1506.08603 (ABS) | III |
| 5 | **Spark (hot path + ELT + Markov)** | R8b, R12, R14 | Zaharia 2012/2013; Armbrust 2015 (Catalyst) | II, III |
| 6 | **MinIO + Delta (Bronze/Silver/Gold)** | R2, fonte da verdade | Armbrust 2020/2021; Ghemawat 2003 | II, III |
| 7 | **Cassandra (telemetria)** | R4 concorrência, R1 clustering | Lakshman 2009; Chang 2006; DeCandia 2007 | IV |
| 8 | **MongoDB (cadastrais/dossiê)** | R8, R10 variedade | Cattell 2011 (document store) | IV |
| 9 | **Redis (cache ao vivo)** | R5 latência dashboard | Cattell 2011; Gilbert & Lynch 2002; Manu 2022 (delta) | IV |
| 10 | **PostgreSQL Gold (star + SCD2 + CUBE)** | R5, R6, R7 | Chaudhuri & Dayal 1997; Gray 1997; Cattell 2011 (NewSQL) | II, IV |
| 11 | **Airflow (ELT orquestrado)** | R14 | Armbrust 2015; Chaudhuri & Dayal 1997 (ETL→ELT) | II |
| 12 | **Banco vetorial + RAG (concierge)** | R9 | Lewis 2020; Manu 2022 (MIPS/HNSW) | III, IV |
| 13 | **Neo4j (roteirização)** | R13 veículo vazio | ementa III (Neo4j/GraphX) | III |
| 14 | **MLOps (score/manutenção)** | agente + MLOps | Armbrust 2015 (DataFrame ML) | II, III |
| 15 | **Motor de cobrança + Dossiê (time-travel)** | R7, R8 | Zaharia 2013 (exactly-once); Armbrust 2020; Corbett 2012 | II, IV |
| + | **Query federada (Data Fabric) / Data Mesh** | convergência | Armbrust 2015/2021 | I, III |

**Fecho de defesa:** o sistema demonstra as 4 partes da ementa em containers reais — Parte I (VLDB distribuído, localidade, TrueTime/consistência externa emulada por watermarks, SLA p99.9), Parte II (star schema → Gold do Lakehouse, ELT+orquestração, CUBE/OLAP, BI 4.0), Parte III (Kafka/Flink/Spark, Kappa, RAG/agentes, grafo, Data Mesh/Fabric) e Parte IV (persistência poliglota, CAP/BASE, NoSQL clássicos, vetorial, NewSQL) — todos com lastro nos 21 fundamentos citados.

---

*Documento pronto para `docs/superpowers/specs/plano-implementacao.md`. Núcleo `core` cabe em 16 GB e é sempre demonstrável; `full` é bônus argumentável na defesa.*