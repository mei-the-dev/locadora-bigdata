# Solução Big Data — Frota Autônoma Conectada

**Avaliação 03 · Solução Big Data** — GRAD.2026-1 · MAE016.15912 · UFRJ/NCE
Proposta Executiva e defesa oral de uma arquitetura de Big Data para o monitoramento,
em tempo real, de uma frota de veículos autônomos e conectados operada por um consórcio
de seis locadoras.

---

**Disciplina:** GRAD.2026-1 · MAE016.15912 — TED-B: Big Data & Data Warehouse ·
**Professor:** Milton Ramos Ramirez

## Grupo (componentes)

| Nome completo | DRE |
|---|---|
| Izabela Lima da Silva | 124156557 |
| Caio Meirelles | 122071557 |

> ⚠️ Identificação do grupo completa. Lembrete do enunciado: arquivos sem identificação do
> grupo **não serão considerados** e o integrante que não postar nada no AVA (nem a folha de
> rosto) recebe nota **ZERO**.

**Trabalho anterior (Avaliação 02 — Data Warehouse):**
https://github.com/mei-the-dev/locadora-dw-parte2 — esta apresentação também cobre e
recapitula aquele modelo dimensional (esquema estrela em PostgreSQL, cadeias de Markov).

---

## Estrutura do repositório

```
.
├── README.md                       # este arquivo (estrutura + instruções)
├── folha-de-rosto.md               # folha de rosto (nomes completos + DRE)
├── apresentacao.html / .pdf        # slides da defesa (entregável no AVA)
├── proposta-executiva.html / .pdf  # Proposta Executiva (entregável no AVA)
├── docs/                           # desenvolvimento de apoio
│   ├── plano-implementacao.md      # plano completo (requisitos × ementa × fundamentos)
│   ├── revisao-teorica.md          # revisão teórica (4 partes da ementa, citada)
│   └── fundamentos-conceitos.md    # 119 conceitos consolidados das referências
├── referencias/
│   ├── dois.txt · books.txt        # bibliografia (DOIs dos papers + livros)
│   └── dw/                         # modelo de DW (Aval. 02) + extensão (06_ddl_extensao.sql)
└── sistema/                        # sistema executável (docker-compose, 115 testes)
    ├── docker-compose.yml · Makefile
    ├── fleetlib · simulator · ingestion · streaming · batch
    ├── persistence · warehouse · app · ai · graph · orchestration
    └── tests
```

> As **notas do apresentador** e o **guia de estudo** são material interno de estudo do
> grupo e não fazem parte da entrega (mantidos apenas localmente, via `.gitignore`).

## Entregáveis (conforme o enunciado)

1. **Proposta Executiva** (PDF) → `proposta-executiva.pdf` — postar no AVA@UFRJ.
2. **Slides da apresentação** (PDF) → `apresentacao.pdf` — postar no AVA@UFRJ.
   Contém: slide de abertura com os componentes (nome + DRE), slide de índice e slide
   final com as conclusões gerais.
3. **E-mail** para `milton@matematica.ufrj.br` com a **folha de rosto** (`folha-de-rosto.md`)
   e o **link deste repositório**: https://github.com/mei-the-dev/locadora-bigdata

## Como gerar os PDFs a partir das fontes HTML

Os dois documentos são HTML autossuficientes (sem dependências). Duas opções:

**A) Navegador (recomendado):** abrir o `.html` no Chrome → **Imprimir** → *Salvar como PDF*.
- `apresentacao.html`: layout **Paisagem**, margens **Nenhuma**, marcar **Gráficos de plano de fundo**.
- `proposta-executiva.html`: tamanho **A4**, marcar **Gráficos de plano de fundo**.

**B) Chrome headless (linha de comando):**
```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"   # macOS
"$CHROME" --headless=new --no-pdf-header-footer --virtual-time-budget=15000 \
  --print-to-pdf="apresentacao.pdf" "file://$PWD/apresentacao.html"
"$CHROME" --headless=new --no-pdf-header-footer --virtual-time-budget=15000 \
  --print-to-pdf="proposta-executiva.pdf" "file://$PWD/proposta-executiva.html"
```

## Navegação do deck (`apresentacao.html`)

Setas ← → / espaço / roda do mouse / swipe. Índice clicável na lateral direita.
Barra de progresso no topo. Respeita `prefers-reduced-motion`.

## Resumo da arquitetura proposta

Borda (Edge Computing, 2 fluxos) → **Kafka** (tópicos isolados, partição por veículo
para ordenação estrita) → processamento em **3 regimes** (Spark batch, Spark Streaming
para emergências, Flink para análise contínua) → **Lakehouse Kappa + Delta Lake**
(Bronze/Silver/Gold, ACID entre batch e streaming) → **persistência poliglota**
(Cassandra, MongoDB, Redis, Data Lake) → **serving** (dashboard em tempo real, motor de
cobrança dinâmica, resposta a emergências e concierge de viagem por IA com RAG).

Detalhes e justificativas completas (com referências citadas) em `proposta-executiva.html`.

## Casos de uso (demonstração de valor e rastreabilidade)

Três cenários mostram **onde cada entidade modelada aparece** — e quais apontam a
**extensão do modelo** (marcadas com ✚):

1. **Colisão em túnel** (crítico · resposta rápida) — `Fato_Sinistro` ✚, `Dim_Sensor` ✚
   (SCD-2), `Dim_TipoEvento` ✚, `Dim_Tempo_Detalhe` ✚. *Valor: ↓ tempo de resposta e de regulação.*
2. **Devolução com condução agressiva** (usual · financeiro) — `Fato_Cobranca` ✚,
   `Fato_Telemetria_Diaria` ✚, `Dim_FaixaConducao` ✚, `Dim_TipoEvento` ✚. *Valor: ↑ receita, ↓ contestações.*
3. **Pico no aeroporto + pane + concierge** (analítico · IA) — `Fato_Movimentacao`,
   `Fato_Manutencao` ✚, `Fato_Telemetria_Diaria` ✚, Markov condicional, RAG. *Valor: ↑ utilização, ↓ downtime, ↑ NPS.*

Matriz completa **entidade × caso**: slide 21 do deck e seção 15 da proposta.
