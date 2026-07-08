-- ============================================================================
-- UFRJ - Instituto de Matematica - Departamento de Matematica Aplicada (DMA)
-- MAE016 / EEL890 - Top. Eng. de Dados B: Big Data e Data Warehouse - 2026.1
-- Professor: Milton Ramos Ramirez
-- Avaliacao 02 - Modelagem de Data Warehouse - PARTE II
-- ----------------------------------------------------------------------------
-- GRUPO:
--   Izabela Lima da Silva    - DRE 124156557
--   Caio Meirelles  - DRE 122071557
-- ----------------------------------------------------------------------------
-- ARTEFATO: 02_extracao_staging.sql
-- OBJETIVO: (1) criar a STAGING AREA neutra (landing por conceito, nao por
--           fonte); (2) EXTRAIR as 4 fontes OLTP para a staging, preservando
--           a chave natural e a LINHAGEM (sistema_origem). Sem limpeza ainda
--           (isso e feito em 03). Acesso as fontes via postgres_fdw.
--
-- JANELAS DE ACIONAMENTO (agendamento das extracoes):
--   - Carga incremental DIARIA as 01:00 (janela de baixo trafego das lojas
--     fisicas e do APP). E o horario em que os OLTPs estao mais ociosos.
--   - Reprocessamento/carga histórica completa: SEMANAL, domingo 02:30.
--   - Sequencia do pipeline:  01:00 extracao (este script)
--                             02:00 transformacao (03_transformacao.sql)
--                             02:30 carga do DW    (04_carga_dw.sql)
--                             03:00 refresh de relatorios/cubos (05).
--   Exemplo de agendamento com pg_cron ao final deste arquivo.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0) STAGING AREA
-- ----------------------------------------------------------------------------
DROP SCHEMA IF EXISTS staging CASCADE;
CREATE SCHEMA staging;
SET search_path TO staging;

-- Landing tables: um registro por linha de origem. Tudo em texto/cru quando o
-- formato diverge entre fontes (ex.: transmissao). 'sistema_origem' identifica
-- a fonte e e parte da chave natural composta (mesmo id pode existir em 2 OLTPs).
CREATE TABLE stg_empresa (
    sistema_origem  VARCHAR(40),
    id_origem       VARCHAR(60),
    nome_empresa    VARCHAR(100)
);

CREATE TABLE stg_patio (
    sistema_origem  VARCHAR(40),
    id_origem       VARCHAR(60),
    nome_patio      VARCHAR(100),
    localizacao     VARCHAR(150),
    empresa_dona    VARCHAR(100),
    n_vagas         INTEGER
);

CREATE TABLE stg_cliente (
    sistema_origem    VARCHAR(40),
    id_origem         VARCHAR(60),
    nome              VARCHAR(120),
    cidade            VARCHAR(100),
    estado            VARCHAR(40),      -- cru: pode vir "RJ", "Rio de Janeiro"...
    data_nascimento   DATE,
    idade             INTEGER           -- algumas fontes guardam idade, nao nascimento
);

CREATE TABLE stg_veiculo (
    sistema_origem    VARCHAR(40),
    id_origem         VARCHAR(60),
    categoria         VARCHAR(50),      -- "grupo": Economico/SUV/...
    marca             VARCHAR(50),
    modelo            VARCHAR(60),
    transmissao_bruta VARCHAR(50),      -- cru: 'A','Aut.','AUTOMATICO','Manual',...
    placa             VARCHAR(20),
    empresa_origem    VARCHAR(100),
    id_patio_origem   VARCHAR(60)       -- patio onde o veiculo esta cadastrado
);

CREATE TABLE stg_reserva (
    sistema_origem         VARCHAR(40),
    id_origem              VARCHAR(60),
    id_cliente_origem      VARCHAR(60),
    id_patio_retirada_org  VARCHAR(60),
    categoria_veiculo      VARCHAR(50),
    id_veiculo_origem      VARCHAR(60),   -- quando a reserva ja aponta veiculo
    data_inicio            DATE,
    data_fim               DATE
);

CREATE TABLE stg_locacao (
    sistema_origem          VARCHAR(40),
    id_origem               VARCHAR(60),
    id_cliente_origem       VARCHAR(60),
    id_veiculo_origem       VARCHAR(60),
    id_patio_retirada_org   VARCHAR(60),
    id_patio_devolucao_org  VARCHAR(60),
    data_retirada           DATE,
    data_devolucao          DATE
);

CREATE TABLE stg_movimentacao (
    sistema_origem      VARCHAR(40),
    id_origem           VARCHAR(60),
    id_veiculo_origem   VARCHAR(60),
    id_patio_origem     VARCHAR(60),
    id_patio_destino    VARCHAR(60),
    data_movimentacao   DATE
);

-- ----------------------------------------------------------------------------
-- 1) CONEXAO COM AS FONTES (postgres_fdw)
-- Cada OLTP e um banco PostgreSQL independente. Criamos um foreign server por
-- fonte e importamos o schema remoto sob um schema local "src_<fonte>".
-- (Credenciais reais ficam fora do versionamento; aqui o padrao de uso.)
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- --- Fonte 0: PROPRIA (grupo Izabela & Caio - idevlimes/locadora-oltp) -------
CREATE SERVER IF NOT EXISTS src_propria_srv FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'oltp-propria.local', port '5432', dbname 'locadora_oltp');
CREATE USER MAPPING IF NOT EXISTS FOR CURRENT_USER SERVER src_propria_srv
    OPTIONS (user 'etl_reader', password 'CHANGE_ME');
CREATE SCHEMA IF NOT EXISTS src_propria;
IMPORT FOREIGN SCHEMA public FROM SERVER src_propria_srv INTO src_propria;

-- --- Fonte A: gupessanha/locadora-dw-parte1 ----------------------------------
CREATE SERVER IF NOT EXISTS src_gupessanha_srv FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'oltp-gupessanha.local', port '5432', dbname 'locadora');
CREATE USER MAPPING IF NOT EXISTS FOR CURRENT_USER SERVER src_gupessanha_srv
    OPTIONS (user 'etl_reader', password 'CHANGE_ME');
CREATE SCHEMA IF NOT EXISTS src_gupessanha;
IMPORT FOREIGN SCHEMA public FROM SERVER src_gupessanha_srv INTO src_gupessanha;

-- --- Fonte B: tadeupires21-sketch/locadora-db --------------------------------
CREATE SERVER IF NOT EXISTS src_tadeupires_srv FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'oltp-tadeupires.local', port '5432', dbname 'locadora_db');
CREATE USER MAPPING IF NOT EXISTS FOR CURRENT_USER SERVER src_tadeupires_srv
    OPTIONS (user 'etl_reader', password 'CHANGE_ME');
CREATE SCHEMA IF NOT EXISTS src_tadeupires;
IMPORT FOREIGN SCHEMA public FROM SERVER src_tadeupires_srv INTO src_tadeupires;

-- --- Fonte C: valviessejoao/mae016-bdd-dwh-projeto1 --------------------------
CREATE SERVER IF NOT EXISTS src_valviessejoao_srv FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'oltp-valviessejoao.local', port '5432', dbname 'locadora');
CREATE USER MAPPING IF NOT EXISTS FOR CURRENT_USER SERVER src_valviessejoao_srv
    OPTIONS (user 'etl_reader', password 'CHANGE_ME');
CREATE SCHEMA IF NOT EXISTS src_valviessejoao;
IMPORT FOREIGN SCHEMA public FROM SERVER src_valviessejoao_srv INTO src_valviessejoao;

-- ============================================================================
-- 2) EXTRACAO POR FONTE  (E do ETL: copia 1:1 para a staging, sem limpar)
-- O bloco de cada fonte e o UNICO ponto que conhece os nomes de tabela/coluna
-- daquela fonte. A heterogeneidade entre fontes e absorvida aqui (mapeamento
-- de nomes) e em 03 (conformacao de dominios/tipos).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 2.0  FONTE PROPRIA  (idevlimes/locadora-oltp)  -- esquema conhecido (Parte I)
--   cliente(id_cliente,nome,data_nascimento,cpf_cnpj,cnh,validade_cnh)
--   patio(id_patio,endereco,n_vagas)
--   veiculo(id_veiculo,id_patio,id_vaga,modelo,placa)
--   movimentacao(id_movimentacao,id_veiculo,id_patio_origem,id_patio_destino,data_movimentacao)
--   reserva(id_reserva,id_cliente,id_patio_retirada,categoria_veiculo,data_inicio,data_fim)
--   locacao(id_locacao,id_cliente,id_veiculo,id_patio_retirada,id_patio_devolucao,data_retirada,data_devolucao)
--   pagamento(id_pagamento,id_locacao,data_pagamento,valor)
-- OBS: nesta fonte NAO existem cidade/estado do cliente, nem marca/categoria/
--      mecanizacao/empresa do veiculo, nem tabela de empresa/grupo. Esses gaps
--      sao tratados em 03 (default 'Nao informado') e/ou supridos por outras
--      fontes. A empresa e derivada da identidade da fonte.
-- ----------------------------------------------------------------------------
INSERT INTO stg_empresa (sistema_origem, id_origem, nome_empresa)
VALUES ('propria', 'E_PROPRIA', 'Locadora Galeao (grupo Izabela & Caio)');

INSERT INTO stg_patio (sistema_origem, id_origem, nome_patio, localizacao, empresa_dona, n_vagas)
SELECT 'propria', p.id_patio::text, NULL, p.endereco, 'Locadora Galeao (grupo Izabela & Caio)', p.n_vagas
FROM src_propria.patio p;

INSERT INTO stg_cliente (sistema_origem, id_origem, nome, cidade, estado, data_nascimento, idade)
SELECT 'propria', c.id_cliente::text, c.nome, NULL, NULL, c.data_nascimento, NULL
FROM src_propria.cliente c;

INSERT INTO stg_veiculo (sistema_origem, id_origem, categoria, marca, modelo, transmissao_bruta, placa, empresa_origem, id_patio_origem)
SELECT 'propria', v.id_veiculo::text, NULL, NULL, v.modelo, NULL, v.placa,
       'Locadora Galeao (grupo Izabela & Caio)', v.id_patio::text
FROM src_propria.veiculo v;

INSERT INTO stg_reserva (sistema_origem, id_origem, id_cliente_origem, id_patio_retirada_org, categoria_veiculo, id_veiculo_origem, data_inicio, data_fim)
SELECT 'propria', r.id_reserva::text, r.id_cliente::text, r.id_patio_retirada::text,
       r.categoria_veiculo, NULL, r.data_inicio, r.data_fim
FROM src_propria.reserva r;

INSERT INTO stg_locacao (sistema_origem, id_origem, id_cliente_origem, id_veiculo_origem, id_patio_retirada_org, id_patio_devolucao_org, data_retirada, data_devolucao)
SELECT 'propria', l.id_locacao::text, l.id_cliente::text, l.id_veiculo::text,
       l.id_patio_retirada::text, l.id_patio_devolucao::text, l.data_retirada, l.data_devolucao
FROM src_propria.locacao l;

INSERT INTO stg_movimentacao (sistema_origem, id_origem, id_veiculo_origem, id_patio_origem, id_patio_destino, data_movimentacao)
SELECT 'propria', m.id_movimentacao::text, m.id_veiculo::text, m.id_patio_origem::text,
       m.id_patio_destino::text, m.data_movimentacao
FROM src_propria.movimentacao m;

-- ----------------------------------------------------------------------------
-- 2.A  FONTE gupessanha/locadora-dw-parte1
--   >>> CONFERIR os nomes exatos de tabelas/colunas em
--   >>> docs/esquemas-outros-grupos/gupessanha/schema.sql
--   Estrutura publicada (resumo): cliente, veiculo, grupo (categoria do
--   veiculo), patio, vaga, reserva, locacao, cobranca/pagamento, empresa.
--   Particularidades tipicas a conformar em 03: 'grupo' em tabela propria
--   (FK do veiculo) e cambio/transmissao com dominio textual proprio.
-- ----------------------------------------------------------------------------
INSERT INTO stg_empresa (sistema_origem, id_origem, nome_empresa)
SELECT 'gupessanha', e.id_empresa::text, e.nome
FROM src_gupessanha.empresa e;

INSERT INTO stg_patio (sistema_origem, id_origem, nome_patio, localizacao, empresa_dona, n_vagas)
SELECT 'gupessanha', p.id_patio::text, p.nome, p.localizacao, e.nome, p.n_vagas
FROM src_gupessanha.patio p
LEFT JOIN src_gupessanha.empresa e ON e.id_empresa = p.id_empresa;

INSERT INTO stg_cliente (sistema_origem, id_origem, nome, cidade, estado, data_nascimento, idade)
SELECT 'gupessanha', c.id_cliente::text, c.nome, c.cidade, c.estado, c.data_nascimento, NULL
FROM src_gupessanha.cliente c;

INSERT INTO stg_veiculo (sistema_origem, id_origem, categoria, marca, modelo, transmissao_bruta, placa, empresa_origem, id_patio_origem)
SELECT 'gupessanha', v.id_veiculo::text, g.nome, v.marca, v.modelo, v.transmissao, v.placa,
       e.nome, v.id_patio::text
FROM src_gupessanha.veiculo v
LEFT JOIN src_gupessanha.grupo   g ON g.id_grupo   = v.id_grupo
LEFT JOIN src_gupessanha.empresa e ON e.id_empresa = v.id_empresa;

INSERT INTO stg_reserva (sistema_origem, id_origem, id_cliente_origem, id_patio_retirada_org, categoria_veiculo, id_veiculo_origem, data_inicio, data_fim)
SELECT 'gupessanha', r.id_reserva::text, r.id_cliente::text, r.id_patio_retirada::text,
       g.nome, r.id_veiculo::text, r.data_inicio, r.data_fim
FROM src_gupessanha.reserva r
LEFT JOIN src_gupessanha.grupo g ON g.id_grupo = r.id_grupo;

INSERT INTO stg_locacao (sistema_origem, id_origem, id_cliente_origem, id_veiculo_origem, id_patio_retirada_org, id_patio_devolucao_org, data_retirada, data_devolucao)
SELECT 'gupessanha', l.id_locacao::text, l.id_cliente::text, l.id_veiculo::text,
       l.id_patio_retirada::text, l.id_patio_devolucao::text, l.data_retirada, l.data_devolucao
FROM src_gupessanha.locacao l;

INSERT INTO stg_movimentacao (sistema_origem, id_origem, id_veiculo_origem, id_patio_origem, id_patio_destino, data_movimentacao)
SELECT 'gupessanha', m.id_movimentacao::text, m.id_veiculo::text, m.id_patio_origem::text,
       m.id_patio_destino::text, m.data_movimentacao
FROM src_gupessanha.movimentacao m;

-- ----------------------------------------------------------------------------
-- 2.B  FONTE tadeupires21-sketch/locadora-db
--   >>> CONFERIR nomes exatos em docs/esquemas-outros-grupos/tadeupires/schema.sql
--   (mapeamento abaixo segue o modelo do dominio; ajustar identificadores.)
-- ----------------------------------------------------------------------------
INSERT INTO stg_empresa (sistema_origem, id_origem, nome_empresa)
SELECT 'tadeupires', e.id_empresa::text, e.nome_empresa
FROM src_tadeupires.empresa e;

INSERT INTO stg_patio (sistema_origem, id_origem, nome_patio, localizacao, empresa_dona, n_vagas)
SELECT 'tadeupires', p.id_patio::text, p.nome, p.endereco, e.nome_empresa, p.qtd_vagas
FROM src_tadeupires.patio p
LEFT JOIN src_tadeupires.empresa e ON e.id_empresa = p.id_empresa;

INSERT INTO stg_cliente (sistema_origem, id_origem, nome, cidade, estado, data_nascimento, idade)
SELECT 'tadeupires', c.id_cliente::text, c.nome, c.cidade, c.uf, c.data_nascimento, NULL
FROM src_tadeupires.cliente c;

INSERT INTO stg_veiculo (sistema_origem, id_origem, categoria, marca, modelo, transmissao_bruta, placa, empresa_origem, id_patio_origem)
SELECT 'tadeupires', v.id_veiculo::text, v.categoria, v.marca, v.modelo, v.cambio, v.placa,
       e.nome_empresa, v.id_patio::text
FROM src_tadeupires.veiculo v
LEFT JOIN src_tadeupires.empresa e ON e.id_empresa = v.id_empresa;

INSERT INTO stg_reserva (sistema_origem, id_origem, id_cliente_origem, id_patio_retirada_org, categoria_veiculo, id_veiculo_origem, data_inicio, data_fim)
SELECT 'tadeupires', r.id_reserva::text, r.id_cliente::text, r.id_patio::text,
       r.categoria, NULL, r.data_retirada, r.data_devolucao
FROM src_tadeupires.reserva r;

INSERT INTO stg_locacao (sistema_origem, id_origem, id_cliente_origem, id_veiculo_origem, id_patio_retirada_org, id_patio_devolucao_org, data_retirada, data_devolucao)
SELECT 'tadeupires', l.id_locacao::text, l.id_cliente::text, l.id_veiculo::text,
       l.id_patio_retirada::text, l.id_patio_devolucao::text, l.data_retirada, l.data_devolucao
FROM src_tadeupires.locacao l;

INSERT INTO stg_movimentacao (sistema_origem, id_origem, id_veiculo_origem, id_patio_origem, id_patio_destino, data_movimentacao)
SELECT 'tadeupires', m.id_movimentacao::text, m.id_veiculo::text, m.id_patio_origem::text,
       m.id_patio_destino::text, m.data_mov
FROM src_tadeupires.movimentacao m;

-- ----------------------------------------------------------------------------
-- 2.C  FONTE valviessejoao/mae016-bdd-dwh-projeto1
--   >>> CONFERIR nomes exatos em docs/esquemas-outros-grupos/valviessejoao/01_create_table.sql
-- ----------------------------------------------------------------------------
INSERT INTO stg_empresa (sistema_origem, id_origem, nome_empresa)
SELECT 'valviessejoao', e.id_empresa::text, e.nome
FROM src_valviessejoao.empresa e;

INSERT INTO stg_patio (sistema_origem, id_origem, nome_patio, localizacao, empresa_dona, n_vagas)
SELECT 'valviessejoao', p.id_patio::text, p.nome, p.localizacao, e.nome, p.numero_vagas
FROM src_valviessejoao.patio p
LEFT JOIN src_valviessejoao.empresa e ON e.id_empresa = p.id_empresa;

INSERT INTO stg_cliente (sistema_origem, id_origem, nome, cidade, estado, data_nascimento, idade)
SELECT 'valviessejoao', c.id_cliente::text, c.nome, c.cidade, c.estado, c.data_nascimento, NULL
FROM src_valviessejoao.cliente c;

INSERT INTO stg_veiculo (sistema_origem, id_origem, categoria, marca, modelo, transmissao_bruta, placa, empresa_origem, id_patio_origem)
SELECT 'valviessejoao', v.id_veiculo::text, v.categoria, v.marca, v.modelo, v.transmissao, v.placa,
       e.nome, v.id_patio::text
FROM src_valviessejoao.veiculo v
LEFT JOIN src_valviessejoao.empresa e ON e.id_empresa = v.id_empresa;

INSERT INTO stg_reserva (sistema_origem, id_origem, id_cliente_origem, id_patio_retirada_org, categoria_veiculo, id_veiculo_origem, data_inicio, data_fim)
SELECT 'valviessejoao', r.id_reserva::text, r.id_cliente::text, r.id_patio_retirada::text,
       r.categoria, r.id_veiculo::text, r.data_inicio, r.data_fim
FROM src_valviessejoao.reserva r;

INSERT INTO stg_locacao (sistema_origem, id_origem, id_cliente_origem, id_veiculo_origem, id_patio_retirada_org, id_patio_devolucao_org, data_retirada, data_devolucao)
SELECT 'valviessejoao', l.id_locacao::text, l.id_cliente::text, l.id_veiculo::text,
       l.id_patio_retirada::text, l.id_patio_devolucao::text, l.data_retirada, l.data_devolucao
FROM src_valviessejoao.locacao l;

INSERT INTO stg_movimentacao (sistema_origem, id_origem, id_veiculo_origem, id_patio_origem, id_patio_destino, data_movimentacao)
SELECT 'valviessejoao', m.id_movimentacao::text, m.id_veiculo::text, m.id_patio_origem::text,
       m.id_patio_destino::text, m.data_movimentacao
FROM src_valviessejoao.movimentacao m;

-- ============================================================================
-- 3) AGENDAMENTO (exemplo com pg_cron) - documenta as janelas de acionamento
-- ============================================================================
-- CREATE EXTENSION IF NOT EXISTS pg_cron;
-- SELECT cron.schedule('extracao_staging',  '0 1 * * *', $$ \i sql/02_extracao_staging.sql $$);
-- SELECT cron.schedule('transformacao',     '0 2 * * *', $$ \i sql/03_transformacao.sql   $$);
-- SELECT cron.schedule('carga_dw',          '30 2 * * *',$$ \i sql/04_carga_dw.sql         $$);
-- (em producao, cada etapa e um job orquestrado; aqui documentamos os horarios.)

-- FIM 02_extracao_staging.sql
