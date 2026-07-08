# Extensão Dimensional do Data Warehouse — Cenário Big Data (Avaliação 03)

**UFRJ — Instituto de Matemática — Departamento de Matemática Aplicada (DMA)**
**Disciplina:** MAE016.15912 / EEL890 — Tóp. Eng. de Dados B: Big Data e Data Warehouse — 2026.1
**Professor:** Milton Ramos Ramirez
**Grupo:**
- Izabela Lima da Silva — DRE 124156557
- Caio Meirelles — DRE 122071557

**Artefatos relacionados:** `01_ddl_dw_estrela.sql` (Star Schema Av.02) · `06_ddl_extensao.sql` (esta extensão)

---

## 1. Contexto e objetivo

Na Avaliação 02 o `dw_locadora` é um **Data Warehouse relacional em lote** (PostgreSQL single-node, janela D-1 via `pg_cron`): 5 dimensões conformadas (**Tempo, Cliente, Veículo, Pátio** — multipapel — e **Empresa**) e 3 fatos (**Reserva, Locação, Movimentação**), este último fonte da **matriz de Markov** de redistribuição de frota entre os 6 pátios.

Para o cenário da **frota de veículos autônomos e conectados** (Avaliação 03), o DW **deixa de ser um sistema isolado e passa a ser a camada GOLD de um Lakehouse** (Bronze → Silver → Gold em Delta Lake sobre MinIO). As novas tabelas Gold **não** são mais carregadas só por batch OLTP: são materializadas por **ELT** a partir do **Silver** (agregados produzidos pelo streaming Flink/Spark sobre a telemetria).

Este documento **estende, não redefine**. As 5 dimensões conformadas e os 3 fatos existentes permanecem intactos; adicionamos **4 dimensões** e **4 fatos** que fecham as lacunas identificadas na análise do modelo atual (grão temporal fino, telemetria, financeiro/cobrança, emergências, manutenção preditiva).

### Princípios de projeto mantidos

- **Surrogate keys inteiras** `sk_*` e **membro especial `sk = -1` "Não informado"** em toda dimensão.
- **Dimensões conformadas reutilizadas** por FK (não duplicadas): `Dim_Tempo`, `Dim_Cliente`, `Dim_Veiculo`, `Dim_Patio` (multipapel), `Dim_Empresa`.
- **Domínios fechados por `CHECK`**, linhagem por `sistema_origem`, **índices em todas as FKs** das fatos.
- **Aditividade documentada** (Kimball): cada medida é rotulada como aditiva, semi-aditiva ou não-aditiva.

---

## 2. Racional e trade-offs de cada nova tabela

### 2.1 Novas dimensões

#### `Dim_Tempo_Detalhe` (papel de "Dim_Hora", grão HORA/MINUTO)
- **Lacuna resolvida:** a `Dim_Tempo` atual tem grão **DIA** (`sk = AAAAMMDD`) — insuficiente para telemetria, sinistros e para condicionar a Markov por faixa horária.
- **Decisão:** dimensão **separada** de hora/minuto (`sk = HHMM`, 0..2359), **pré-carregada deterministicamente** com os 1440 minutos do dia por `generate_series` — mesma filosofia da `Dim_Tempo`. Atributos derivados: `faixa_horaria` (Madrugada/Manhã/Tarde/Noite) e `is_horario_pico`.
- **Trade-off:** separar `Dim_Data` + `Dim_Hora` evita explodir a cardinalidade de uma única dimensão de timestamp (365 × 1440 linhas/ano). A "hora do evento" combina-se com `sk_tempo` (o dia) nas fatos de transação. Para telemetria contínua no grão de janela de streaming, o timestamp de alta resolução é preservado no **Silver/Cassandra**; a Gold recebe agregados.
- **Uso:** `Fato_Sinistro` (hora da ocorrência — crítico para SLA de resposta), `Fato_Cobranca` (hora do faturamento) e **eixo de condicionamento da Markov estendida** (§5).

#### `Dim_TipoEvento` (panes / acidentes / colisão / violação)
- **Lacuna resolvida:** não havia classificação de eventos de emergência/manutenção.
- **Decisão:** dimensão compartilhada por `Fato_Sinistro` e `Fato_Manutencao`. `categoria_evento` é domínio fechado (`Pane, Acidente, Colisao, Violacao, Falha_Sensor, Bateria_Critica, Manutencao, Outro`); `gravidade_padrao` é atributo derivado; `exige_dossie` sinaliza o disparo do **dossiê regulatório** (R8).
- **Trade-off:** poderíamos ter fatos separados por natureza de evento; uma dimensão-tipo única mantém os fatos enxutos e permite drill-down por categoria/gravidade sem alterar o esquema.

#### `Dim_Sensor` (dispositivo de borda — **SCD Tipo 2**)
- **Lacuna resolvida:** não havia dimensão de sensor/dispositivo edge nem histórico de firmware.
- **Decisão:** **única dimensão versionada por Tipo 2** (`valid_from`, `valid_to`, `is_current`). Motivo: a `versao_firmware` muda no tempo e o **dossiê regulatório point-in-time** exige saber qual firmware o sensor rodava no instante do sinistro. SK estável por (chave natural + vigência).
- **Trade-off:** Tipo 2 custa mais linhas e MERGE mais complexo no ELT, mas é **indispensável para auditoria** e para ingestão incremental/streaming (lacuna 4 do modelo atual, que hoje é 100% Tipo 1 full-refresh). Aplicamos Tipo 2 **cirurgicamente** só onde a auditoria justifica (Sensor/firmware), evitando reescrever as dimensões conformadas existentes.

#### `Dim_FaixaConducao` (banda do score: Econômico / Moderado / Agressivo)
- **Lacuna resolvida:** o score de condução (derivado da telemetria) precisava de uma dimensão para *slice-and-dice*.
- **Decisão:** **band/bucket** do score contínuo (0..100). `fator_tarifa` liga a faixa à **cobrança** (modula `acrescimo_consumo`) — **cor semântica**, não decorativa: Econômico = 0,95 (desconto), Moderado = 1,00, Agressivo = 1,15 (sobretaxa). Pré-carregada com as 3 bandas + membro −1.
- **Trade-off:** discretizar o score facilita relatórios e a ligação com a tarifa; o score contínuo permanece como medida em `Fato_Telemetria_Diaria`.

### 2.2 Novas fatos

| Fato | Tipo | Grão | Medidas-chave (aditividade) |
|------|------|------|------------------------------|
| `Fato_Telemetria_Diaria` | **Snapshot periódico acumulado** | 1 veículo × 1 dia × empresa | `km_rodados`, `tempo_movimento_seg`, `num_eventos_conducao_brusca` (aditivas); `consumo_medio_*` (semi-aditivas); `velocidade_*`, `autonomia_media_km`, `score_conducao` (não-aditivas) |
| `Fato_Cobranca` | **Transação** | 1 locação faturada | `valor_base`, `acrescimo_km/tempo/consumo`, `multa_infracao`, `desconto`, `valor_final` — **todas aditivas ($)** |
| `Fato_Sinistro` | **Transação** | 1 ocorrência de emergência | `severidade` (discreta), `custo_estimado` (aditiva $), `tempo_resposta_seg` (aditiva/SLA) |
| `Fato_Manutencao` | **Transação** | 1 evento/previsão de manutenção | `custo` (aditiva $), `downtime_horas` (aditiva), `probabilidade_falha` (não-aditiva, só previsões) |

- **`Fato_Telemetria_Diaria`** — Escolhemos o **grão diário por veículo** (snapshot) porque a telemetria por evento (sub-segundo, altíssima cardinalidade) **não** cabe na Gold: ela vive em **Cassandra** e no Bronze/Silver. A Gold recebe o **agregado de janela** que alimenta score de condução e manutenção preditiva. Preserva a compatibilidade com a `Dim_Tempo` (dia) e evita inchar o DW ROLAP.
- **`Fato_Cobranca`** — Preenche a **lacuna financeira** (hoje todas as medidas são contagens/durações, zero $). É a base da **cobrança automática pós-uso** (R7), que exige **consistência forte/ACID** — daí residir no PostgreSQL Gold. Usa **surrogate de fato** `sk_cobranca` + **dimensão degenerada** `id_locacao` (UNIQUE) porque o grão é exatamente uma locação faturada.
- **`Fato_Sinistro`** — Base do **dossiê regulatório** (R8). `latitude/longitude` entram como **atributos degenerados** (podem ser promovidos a uma futura `Dim_Geo/Waypoint`). Combinado com `Dim_Sensor` (SCD2) e `Delta time-travel`, reconstrói o estado point-in-time do veículo.
- **`Fato_Manutencao`** — Suporta **manutenção preditiva**: `tipo_manutencao = 'Preditiva'` carrega `probabilidade_falha` estimada pelo modelo ML featurizado sobre `Fato_Telemetria_Diaria`. `downtime_horas` quantifica indisponibilidade da frota.

> **Padrão de chaves das fatos de transação:** usamos surrogate de fato IDENTITY + degenerada UNIQUE (em vez do PK composto agregado dos fatos Av.02) porque o grão é **um evento**, carregado incrementalmente pelo ELT — mais robusto para *late-arriving data* e replay do que reagrupar por todas as FKs.

---

## 3. Diagrama textual do esquema estendido (constelação / fact constellation)

Legenda: `[D]` dimensão · `[F]` fato · `(=)` dimensão conformada reutilizada · `(novo)`.

```
                         ┌───────────────────────────┐
                         │      [D] Dim_Tempo (=)     │  grão DIA (AAAAMMDD)
                         └───────────────────────────┘
        ┌────────────────────┬──────────┬───────────┬──────────────────┐
        │                    │          │           │                  │
        │        ┌───────────┴───┐  ┌───┴──────┐ ┌──┴─────────┐ ┌──────┴──────┐
        │        │ [D] Dim_Veiculo│  │[D] Cliente│ │[D] Dim_Patio│ │[D] Empresa │  (todas =)
        │        │      (=)       │  │   (=)     │ │ (=) multipapel│ │    (=)     │
        │        └──┬────┬───┬────┘  └──┬───┬────┘ └─┬──┬──┬──┬──┘ └──┬──┬──┬───┘
        │           │    │   │          │   │        │  │  │  │       │  │  │
   ┌────┴─────┐  ┌──┴────┴───┴───┐  ┌───┴───┴────┐ ┌─┴──┴──┴──┴──┐ ...(fatos Av.02:
   │[F] Reserva│  │  FATOS NOVOS  │  │[F] Locacao │ │[F] Movimenta│    Reserva,
   │   (Av.02) │  │  (Av.03)      │  │  (Av.02)   │ │  cao (Av.02)│    Locacao,
   └───────────┘  └───────────────┘  └────────────┘ └─────────────┘    Movimentacao)

  ── FATOS NOVOS (Av.03) e suas dimensões ──────────────────────────────────────

  [F] Fato_Telemetria_Diaria   grão: veículo × dia × empresa  (SNAPSHOT diário)
        FK → Dim_Veiculo(=), Dim_Tempo(=), Dim_Empresa(=), Dim_Patio(=),
             Dim_FaixaConducao(novo)

  [F] Fato_Cobranca            grão: 1 locação faturada        (TRANSAÇÃO $)
        FK → Dim_Cliente(=), Dim_Veiculo(=), Dim_Patio(=) [retirada+devolução],
             Dim_Tempo(=), Dim_Tempo_Detalhe(novo), Dim_Empresa(=),
             Dim_FaixaConducao(novo)   +  degenerada id_locacao

  [F] Fato_Sinistro            grão: 1 ocorrência de emergência (TRANSAÇÃO)
        FK → Dim_Veiculo(=), Dim_Cliente(=), Dim_Patio(=), Dim_Tempo(=),
             Dim_Tempo_Detalhe(novo), Dim_Empresa(=), Dim_TipoEvento(novo),
             Dim_Sensor(novo, SCD2)    +  degenerada id_ocorrencia + geo(lat/long)

  [F] Fato_Manutencao          grão: 1 evento/previsão manut.  (TRANSAÇÃO)
        FK → Dim_Veiculo(=), Dim_Patio(=), Dim_Tempo(=), Dim_Empresa(=),
             Dim_TipoEvento(novo), Dim_Sensor(novo)   +  degenerada id_manutencao

  ── NOVAS DIMENSÕES ───────────────────────────────────────────────────────────
  [D] Dim_Tempo_Detalhe (HHMM, faixa_horaria, is_horario_pico)   — pré-carga determinística
  [D] Dim_TipoEvento    (categoria, gravidade_padrao, exige_dossie)
  [D] Dim_Sensor        (tipo_sensor, versao_firmware, valid_from/to/is_current — SCD2)
  [D] Dim_FaixaConducao (faixa, score_min/max, fator_tarifa)     — pré-carga determinística
```

**Constelação resultante:** 7 fatos (3 Av.02 + 4 Av.03) compartilhando um núcleo de dimensões conformadas (Tempo, Cliente, Veículo, Pátio multipapel, Empresa) mais 4 dimensões novas. A conformação garante que "Veículo", "Pátio", "Tempo" e "Empresa" signifiquem o mesmo em qualquer relatório integrado das 6 locadoras.

---

## 4. Como o ELT / Lakehouse (Silver → Gold) carrega cada tabela nova

O DAG de orquestração (Airflow/Dagster) segue `bronze_ingest → silver_conform → gold_dimensional → gold_markov → gold_aggregates → refresh_serving`. A Gold é materializada em **Delta** (para ML/RAG/federação lerem direto) **e** servida em **PostgreSQL ROLAP** para o dashboard. Cada nova tabela:

| Tabela Gold | Fonte no Silver (Delta) | Transformação ELT (Spark SQL / Catalyst) | Cadência |
|-------------|--------------------------|-------------------------------------------|----------|
| `Dim_Tempo_Detalhe` | — (determinística) | Pré-carga por `generate_series` (já no DDL); imutável (SCD Tipo 0) | Uma vez |
| `Dim_FaixaConducao` | — (regra de negócio) | Seed das 3 bandas (já no DDL); parâmetro de tarifa | Sob demanda |
| `Dim_TipoEvento` | `silver.eventos` (catálogo de códigos, MongoDB → Silver) | Conformação de códigos heterogêneos → domínio fechado; deriva `gravidade_padrao`/`exige_dossie` | Diária |
| `Dim_Sensor` (**SCD2**) | `silver.dispositivos` (cadastro edge + firmware) | **MERGE Tipo 2**: fecha `valid_to`/`is_current=false` da versão antiga e insere a nova; SK estável | Incremental (por mudança de firmware) |
| `Fato_Telemetria_Diaria` | `silver.telemetria` (dedup por `vehicle_id+ts`, oriundo de Cassandra/Bronze) | **Agregação de janela por veículo/dia** (`GROUP BY vehicle_id, data`): SUM(km), AVG/MAX(velocidade), contagem de eventos bruscos, `score_conducao`; resolve `sk_faixa_conducao` pela banda | Diária (micro-batch) |
| `Fato_Cobranca` | `silver.locacoes_encerradas` + agregado de telemetria | Motor de cobrança: `valor_base` + acréscimos (km/tempo/consumo × `fator_tarifa`) + multas − desconto = `valor_final`; **exactly-once** (ação `txn` do Delta / idempotência por `id_locacao`) | A cada encerramento (near-real-time) |
| `Fato_Sinistro` | `silver.emergencias` (hot path Spark → Silver) | Resolve FKs (Veículo/Pátio/Tempo/Tempo_Detalhe/Empresa/TipoEvento/**Sensor point-in-time via SCD2**); grava geo degenerado; `flag_dossie` | Contínua (baixa latência) |
| `Fato_Manutencao` | `silver.manutencao` + saída do modelo ML | Eventos realizados (Corretiva/Preventiva) + previsões (`Preditiva`, `probabilidade_falha` do MLflow featurizado sobre `Fato_Telemetria_Diaria`) | Diária / evento |

**Padrões transversais:**
- **Resolução de SK** por JOIN nas chaves naturais com `COALESCE(..., -1)` (mesmo padrão do `04_carga_dw.sql`), agora estendido a *late-arriving dimensions* graças ao SCD2 de `Dim_Sensor`.
- **Idempotência/exactly-once:** rodar o job duas vezes mantém o estado (dedup por `id_locacao`/`id_ocorrencia`/`vehicle_id+ts`); a Gold é **derivável por replay ordenado** do log Kafka + Delta.
- **Cassandra → Gold:** telemetria bruta serve baixa latência por veículo; a Gold só recebe o **agregado** (`Fato_Telemetria_Diaria`). A "posição atual" continua derivável por `ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY ts DESC)`.
- **MongoDB ↔ Gold:** dossiês de emergência referenciam `Fato_Sinistro` (SK estável) + blobs (refs MinIO); cadastrais alimentam `Dim_Cliente/Veiculo`.
- **Redis ← Gold:** cache dos agregados quentes (ocupação por pátio, KPIs financeiros) revalidado best-effort.

---

## 5. Extensão da matriz de Markov

**Estado atual (Av.02):** matriz estocástica de **1ª ordem, homogênea no tempo**, construída em SQL batch sobre `Fato_Movimentacao`. Para cada pátio de origem *i*: `P(i→j) = mov(i,j) / Σⱼ mov(i,j)` (MLE por contagem de frequências sobre todo o histórico). Cada linha soma 1,0000. Limitações: não condiciona por tempo/categoria/estado e é recomputada em lote no grão diário.

**Extensões propostas (fecham a lacuna 9):**

1. **Markov condicional (heterogênea).** Estratificar a matriz por variáveis de contexto, gerando **uma matriz por célula de condição** em vez de uma global:
   - **Faixa horária** — via `Dim_Tempo_Detalhe.faixa_horaria` (Madrugada/Manhã/Tarde/Noite) e `is_horario_pico`. As transições entre pátios diferem muito entre pico e madrugada.
   - **Dia da semana** — via `Dim_Tempo.dia_semana`.
   - **Categoria de veículo** — via `Dim_Veiculo.categoria` (o "grupo").
   - **Estado de condução** — via `Dim_FaixaConducao`/`score_conducao`, para roteirizar preferencialmente veículos aptos.

   Formalmente: `P(i→j | h, c) = mov(i,j,h,c) / Σⱼ mov(i,j,h,c)`, onde *h* = faixa horária e *c* = categoria. A verificação de estocasticidade (soma das linhas = 1,0) passa a ser **por estrato**.

2. **De recomputação batch para atualização incremental sobre o Silver.** Em vez de recomputar toda a matriz na janela noturna, manter **contadores incrementais** de `mov(i,j,h,c)` atualizados em **janela deslizante** no Flink/Spark Structured Streaming sobre o Silver, com decaimento temporal (janelas recentes pesam mais). A matriz vira um **estado servido** (Redis/serving) consultável em tempo (quase) real para decidir o **reposicionamento do veículo autônomo vazio** — o veículo pode "voltar sozinho" ao pátio de maior demanda prevista.

3. **Complemento por grafo (opcional, Neo4j/GraphX).** A matriz dá a probabilidade de destino; o grafo de pátios/rotas/waypoints (arestas ponderadas por distância × ocupação prevista pela Markov) resolve o **caminho mínimo** do reposicionamento — Markov (para onde ir) + grafo (como chegar).

**Fonte de dados:** a Markov estendida continua alimentada por `Fato_Movimentacao`, agora **enriquecido no JOIN** com `Dim_Tempo_Detalhe` e `Dim_Veiculo.categoria` no momento da agregação Silver→Gold (`gold_markov`), sem alterar o grão do fato de movimentação.

---

## 6. Reconciliação de nomes com o plano de implementação

O `plano-implementacao.md` cita alguns nomes ligeiramente diferentes; a correspondência é direta e proposital (esta extensão é a materialização detalhada daquela seção §3.2/§4):

| Plano (§3.2 / §4) | Este artefato (`06_ddl_extensao.sql`) | Observação |
|-------------------|----------------------------------------|------------|
| `Fato_Telemetria` (grão de janela) | `Fato_Telemetria_Diaria` (grão dia) | Janela = 1 dia por veículo na Gold; grão fino permanece em Cassandra/Silver |
| `Fato_Emergencia` | `Fato_Sinistro` | Mesmo conceito (ocorrência de emergência/sinistro) |
| `Fato_Cobranca` | `Fato_Cobranca` | Idêntico |
| `Dim_Tipo_Evento` | `Dim_TipoEvento` | Mesma dimensão |
| `Dim_Sensor/Dispositivo_Edge` + `Dim_Firmware` | `Dim_Sensor` (SCD2, com `versao_firmware`) | Firmware modelado como atributo versionado Tipo 2 (evita dimensão extra) |
| `Dim_Hora` / `Dim_Data`+`Dim_Hora` | `Dim_Tempo_Detalhe` (papel de Dim_Hora) + `Dim_Tempo` (dia, já existente) | Data = `Dim_Tempo`; Hora = `Dim_Tempo_Detalhe` |
| — | `Dim_FaixaConducao`, `Fato_Manutencao` | Detalhamento adicional (score de condução e manutenção preditiva) |

`Fato_Viagem_Autonoma` e `Dim_Rota/Geo/Waypoint` citados no plano ficam como **evolução futura** (o trajeto autônomo pode ser um fato próprio; a geo entra hoje como atributos degenerados de `Fato_Sinistro`).

---

## 7. Síntese

A extensão adiciona **4 dimensões** (`Dim_Tempo_Detalhe`, `Dim_TipoEvento`, `Dim_Sensor` SCD2, `Dim_FaixaConducao`) e **4 fatos** (`Fato_Telemetria_Diaria`, `Fato_Cobranca`, `Fato_Sinistro`, `Fato_Manutencao`) ao `dw_locadora`, formando uma **constelação de 7 fatos** sobre um núcleo conformado. Resolve as lacunas de **grão temporal fino**, **telemetria agregada**, **medida financeira/cobrança**, **emergências/dossiê** e **manutenção preditiva**, mantém o padrão `sk_*` / membro −1 / FKs indexadas, introduz **SCD2 pontual** para auditoria point-in-time, e reposiciona o DW como **camada Gold de um Lakehouse** carregado por **ELT a partir do Silver** — inclusive com um caminho de evolução da **matriz de Markov** de estática/global para **condicional e incremental em streaming**.
