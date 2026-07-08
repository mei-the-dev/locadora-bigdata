# Solução de Big Data — Frota Autônoma Conectada

> **Avaliação 03 · Solução Big Data** — GRAD.2026-1 · **MAE016.15912 / EEL890** — TED-B: Big Data & Data Warehouse · UFRJ / NCE · 2026.1

Proposta e defesa de uma arquitetura de **Big Data em tempo real** para o monitoramento de
uma frota de **veículos autônomos e conectados**, operada por um consórcio de seis locadoras.
Este repositório reúne os entregáveis da avaliação (proposta e slides), a **extensão do
modelo de Data Warehouse** da Avaliação 02 e uma **prova de conceito executável** do sistema.

---

## Grupo

| Nome completo | DRE |
|---|---|
| Izabela Lima da Silva | 124156557 |
| Caio Meirelles | 122071557 |

**Professor:** Milton Ramos Ramirez · **Disciplina:** MAE016.15912 / EEL890 (TED-B).

> Todos os arquivos entregáveis incluem a identificação do grupo (nomes completos e DRE),
> conforme exigido no enunciado. A **folha de rosto** está em [`folha-de-rosto.md`](folha-de-rosto.md).

---

## Contexto e problema

O consórcio automatizou a operação: pelo aplicativo, o cliente reserva o veículo e indica o
local; o **veículo autônomo sai sozinho do pátio**, navega no trânsito urbano, estaciona no
ponto pedido e, ao fim da locação, retorna para higienização. Cada veículo é instrumentado
(motor, chassi, câmeras 360°, sensores de impacto) com um computador de bordo capaz de
**Edge Computing**, gerando um fluxo contínuo de dados.

A solução baseada apenas em Data Warehouse **não é mais suficiente**; é preciso Big Data para
sustentar quatro necessidades — **acompanhamento** da frota, **cobrança automática**,
**apoio a emergências** e um **concierge de viagem** por IA — sob restrições severas:
**banda móvel finita**, **alta concorrência sem perda de pacotes** e **ordenação estrita**
dos eventos por veículo e *timestamp*, mesmo sob forte estresse de carga.

---

## Entregáveis (conforme o enunciado)

| # | Item exigido | Arquivo neste repositório |
|---|---|---|
| 1 | **Proposta Executiva** (PDF) | [`proposta-executiva.pdf`](proposta-executiva.pdf) — versão para a diretoria (valor de negócio) · [`proposta-executiva-tecnica.pdf`](proposta-executiva-tecnica.pdf) — versão técnica detalhada (arquitetura, decisões, robustez, figuras) |
| 2 | **Slides da defesa** (PDF) | [`apresentacao.pdf`](apresentacao.pdf) — capa com os componentes (nome + DRE), índice e slide final de conclusões |
| 3 | **Folha de rosto** + **README** da estrutura | [`folha-de-rosto.md`](folha-de-rosto.md) + este arquivo |
| — | **Outro desenvolvimento / extensão** | Extensão do DW (`referencias/dw/`), documentos de apoio (`docs/`) e sistema executável (`sistema/`) |

As fontes em HTML acompanham cada PDF (`*.html`), para regeneração e edição.

---

## O que a proposta contempla (checklist do enunciado)

- [x] **Pipeline completo** de ingestão → processamento → armazenamento → visualização
- [x] **Dashboard interativo** com painéis de reservas, locações, estado da frota,
      financeiro/cobranças, emergências, viagens em andamento e oficina — além de
      trânsito, engarrafamentos, meteorologia e eventos/alertas da cidade
- [x] **Explicação e justificativa de cada tecnologia:** MapReduce, Spark, Flink,
      Lambda × Kappa e NoSQL — com vantagens, desvantagens e por que **não** as alternativas
- [x] **Extra:** especificação funcional do **chatbot de voz** (concierge com PLN + RAG)
- [x] **Computação de borda** (dois fluxos: rotina agregada e evento crítico imediato)
- [x] **Ingestão resiliente** (Apache Kafka, tópicos isolados, tolerância a falhas)
- [x] **Três regimes de processamento** (Spark batch/MapReduce, Spark Streaming, Flink)
- [x] **Lambda × Kappa** comparados formalmente + **ACID entre lote e streaming** (Delta Lake)
- [x] **Persistência poliglota** (Cassandra, MongoDB, Redis) justificada pelo padrão de acesso
- [x] **Robustez:** tratamento de casos limítrofes (banda finita, sem perda, ordenação sob estresse)
- [x] **Custos de nuvem** e alavancas de economia

---

## Resumo da solução

Arquitetura **Kappa** materializada por um **Lakehouse** sobre **Delta Lake**:

```
Borda/Edge (Avro) → Kafka (telemetry.raw | alerts.critical)
   ├─ HOT   colisão      → Spark Streaming → despacho + dossiê de sinistro
   ├─ WARM  telemetria   → Flink (event-time/watermarks) → rotas, score de condução
   └─ COLD  histórico    → Spark batch → quilometragem, manutenção preditiva, Markov
Delta Lake (Bronze → Silver → Gold) → NoSQL (Cassandra · MongoDB · Redis) → Serving
   (Dashboard Streamlit · Motor de cobrança · Resposta a emergências · Concierge de IA)
```

**Continuidade com a Avaliação 02:** o esquema estrela do Data Warehouse **não é descartado** —
torna-se a camada **Gold** do Lakehouse. A extensão dimensional acrescenta 4 fatos
(Telemetria, Cobrança, Sinistro, Manutenção) e 4 dimensões (Tempo_Detalhe, Sensor SCD-2,
TipoEvento, FaixaCondução). A `Fato_Cobranca` dá continuidade ao `Pagamento` já modelado no
OLTP da Parte I, trazendo-o para a camada analítica e enriquecendo-o com ajustes dinâmicos.
O DDL da extensão (`referencias/dw/06_ddl_extensao.sql`) foi validado em PostgreSQL.

---

## Estrutura do repositório

```
.
├── README.md                          # este arquivo (estrutura + conformidade)
├── folha-de-rosto.md                  # folha de rosto (nomes completos + DRE)
│
├── proposta-executiva.pdf / .html     # Proposta Executiva — versão diretoria (valor)
├── proposta-executiva-tecnica.pdf/.html  # Proposta Executiva — versão técnica (arquitetura)
├── apresentacao.pdf / .html           # slides da defesa oral (25 slides)
│
├── docs/                              # desenvolvimento de apoio
│   ├── plano-implementacao.md         # plano completo (requisitos × ementa × fundamentos)
│   ├── revisao-teorica.md             # revisão teórica das 4 partes da ementa (citada)
│   └── fundamentos-conceitos.md       # conceitos consolidados das referências
│
├── referencias/
│   ├── dois.txt · books.txt           # bibliografia (DOIs dos papers + livros)
│   └── dw/                            # modelo de DW (Aval. 02) + extensão (Aval. 03)
│       ├── 01_ddl_dw_estrela.sql … 05_relatorios_matriz.sql   # DW original (Parte 2)
│       ├── 06_ddl_extensao.sql        # extensão dimensional (validada)
│       ├── extensao-dimensional.md    # racional da extensão
│       └── modelo-dimensional.pdf · relatorio-etl-modelo.pdf  # documentação da Aval. 02
│
└── sistema/                           # prova de conceito executável
    ├── docker-compose.yml · Makefile  # perfis core e full
    ├── fleetlib · simulator · ingestion · streaming · batch
    ├── persistence · warehouse · app · ai · graph · orchestration
    └── tests                          # 115 testes unitários
```

---

## Como usar

### Gerar os PDFs a partir das fontes HTML

Os documentos são HTML autossuficientes. Abrir o `.html` no navegador → **Imprimir → Salvar como PDF**:

- `apresentacao.html` — layout **Paisagem**, margens **Nenhuma**, marcar *Gráficos de plano de fundo*.
- `proposta-executiva*.html` — tamanho **A4**, marcar *Gráficos de plano de fundo*.

### Rodar a prova de conceito

```bash
cd sistema
docker compose --profile core up      # núcleo: Kafka, Flink, Spark, Cassandra, Mongo, Redis, MinIO, Postgres, Streamlit
# perfil completo (Airflow, banco vetorial, MLOps, grafo):
docker compose --profile full up
```

O DW e sua extensão podem ser criados em um PostgreSQL executando, em ordem,
`referencias/dw/01_ddl_dw_estrela.sql` e `referencias/dw/06_ddl_extensao.sql`.

---

## Nota sobre material de terceiros

Os artigos científicos (papers) e o enunciado da disciplina **não são redistribuídos** neste
repositório, por serem material de terceiros protegido por direitos autorais. A bibliografia
completa (com DOIs) está em [`referencias/dois.txt`](referencias/dois.txt) e
[`referencias/books.txt`](referencias/books.txt); as citações completas constam na proposta
técnica e no relatório acadêmico do grupo.
