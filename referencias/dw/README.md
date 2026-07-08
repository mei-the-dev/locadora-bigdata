# Locadora de Veículos — Data Warehouse (PARTE II)

**MAE016 / EEL890 — Tóp. Eng. de Dados B: Big Data e Data Warehouse — 2026.1**
UFRJ · Instituto de Matemática · DMA — Prof. Milton Ramos Ramirez
Avaliação 02 — Modelagem de Data Warehouse — **PARTE II**

### Grupo
| Nome | DRE |
|------|-----|
| Izabela Lima da Silva | 124156557 |
| Caio Meirelles | 122071557 |

Projeto da Parte I (OLTP) do grupo: https://github.com/idevlimes/locadora-oltp

---

## O que é

Solução de **Data Warehouse integrado** para a associação de 6 locadoras de
veículos que compartilham pátios (Galeão, Santos Dumont, Rodoviária, Shopping
Rio Sul, Nova América, Barra Shopping). O DW unifica os dados dos sistemas
transacionais (OLTP) de quatro grupos da turma e entrega os Relatórios
Gerenciais Globais e a matriz de previsão de ocupação de pátio (Cadeia de
Markov).

## Modelo dimensional (esquema estrela)

Três tabelas de fato compartilhando dimensões conformadas:

- **Fato_Reserva** — grão: 1 reserva
- **Fato_Locacao** — grão: 1 locação (contrato)
- **Fato_Movimentacao** — grão: 1 deslocamento de veículo entre pátios (base da matriz de Markov)

Dimensões: **Dim_Tempo, Dim_Cliente, Dim_Veiculo, Dim_Empresa** e **Dim_Patio**
(dimensão de *papel múltiplo* — retirada, devolução, origem, destino).

Descrição completa e justificativa de cada campo: `docs/modelo-dimensional.pdf`.

## Fontes de dados integradas (4 OLTPs)

| Apelido no ETL | Grupo / repositório |
|----------------|---------------------|
| `propria` | idevlimes/locadora-oltp (grupo Izabela & Caio) |
| `gupessanha` | gupessanha/locadora-dw-parte1 |
| `tadeupires` | tadeupires21-sketch/locadora-db |
| `valviessejoao` | valviessejoao/mae016-bdd-dwh-projeto1 |

Cópias dos esquemas das fontes em `docs/esquemas-outros-grupos/`.

## Scripts SQL (ordem de execução)

| # | Arquivo | Papel |
|---|---------|-------|
| 1 | `sql/01_ddl_dw_estrela.sql` | Cria o esquema estrela do DW (dimensões + fatos) |
| 2 | `sql/02_extracao_staging.sql` | Cria a *staging area* e extrai as 4 fontes (com janelas de acionamento) |
| 3 | `sql/03_transformacao.sql` | Limpa, conforma e integra as fontes na staging |
| 4 | `sql/04_carga_dw.sql` | Carrega dimensões (surrogate keys) e fatos a partir da staging |
| 5 | `sql/05_relatorios_matriz.sql` | Relatórios Gerenciais (a–d) + matriz estocástica de Markov |

```bash
psql -d locadora_dw -f sql/01_ddl_dw_estrela.sql
psql -d locadora_dw -f sql/02_extracao_staging.sql
psql -d locadora_dw -f sql/03_transformacao.sql
psql -d locadora_dw -f sql/04_carga_dw.sql
psql -d locadora_dw -f sql/05_relatorios_matriz.sql
```

SGBD-alvo: **PostgreSQL** (compatível com ANSI SQL:1999+).

## Documentos (PDF)

- `docs/relatorio-etl-modelo.pdf` — comentários do processo ETL e do modelo dimensional, escolhas, problemas e **conclusão**.
- `docs/modelo-dimensional.pdf` — descrição do esquema estrela, ligação fontes→fatos/dimensões e justificativa de cada campo.
- `docs/folha-de-rosto.pdf` — folha de rosto do grupo.
- `docs/esquemas-outros-grupos/` — cópias dos esquemas das BD dos outros grupos.
