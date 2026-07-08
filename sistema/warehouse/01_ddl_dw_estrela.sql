-- ============================================================================
-- UFRJ - Instituto de Matematica - Departamento de Matematica Aplicada (DMA)
-- MAE016 / EEL890 - Top. Eng. de Dados B: Big Data e Data Warehouse - 2026.1
-- Professor: Milton Ramos Ramirez
-- Avaliacao 02 - Modelagem de Data Warehouse - PARTE II
-- ----------------------------------------------------------------------------
-- GRUPO:
--   Izabela Lima da Silva    - DRE 124156557
--   Caio Meirelles  - DRE 122071557
-- Repositorio (Parte I OLTP): https://github.com/idevlimes/locadora-oltp
-- ----------------------------------------------------------------------------
-- ARTEFATO: 01_ddl_dw_estrela.sql
-- OBJETIVO: Criacao do esquema ESTRELA (Star Schema) do Data Warehouse.
--           Dimensoes conformadas + tabelas de fato. SGBD-alvo: PostgreSQL
--           (compativel com ANSI SQL:1999+). Executar ANTES da carga (03).
-- ============================================================================

DROP SCHEMA IF EXISTS dw_locadora CASCADE;
CREATE SCHEMA dw_locadora;
SET search_path TO dw_locadora;

-- ============================================================================
-- DIMENSOES CONFORMADAS
-- As dimensoes sao compartilhadas pelas tres tabelas de fato (conformed
-- dimensions), garantindo que "Veiculo", "Patio", "Tempo" e "Empresa"
-- signifiquem a mesma coisa em qualquer relatorio integrado das 6 locadoras.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Dim_Tempo : dimensao de calendario (pre-carregada de forma deterministica).
--   Suporta: "tempo de retirada futura" (semana/mes que vem), agregacoes por
--   mes/trimestre/ano e o eixo temporal das movimentacoes (Markov).
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Tempo (
    sk_tempo     INTEGER     PRIMARY KEY,          -- chave no formato AAAAMMDD
    data         DATE        NOT NULL UNIQUE,
    dia          SMALLINT    NOT NULL,
    mes          SMALLINT    NOT NULL,
    nome_mes     VARCHAR(15) NOT NULL,
    trimestre    SMALLINT    NOT NULL,
    ano          SMALLINT    NOT NULL,
    semana_ano   SMALLINT    NOT NULL,             -- p/ "reservas para a semana que vem"
    dia_semana   VARCHAR(15) NOT NULL
);

-- ----------------------------------------------------------------------------
-- Dim_Cliente : quem aluga. cidade/estado sustentam o relatorio de reservas
--   "pelas cidades de origem dos clientes". faixa_etaria e atributo derivado
--   (conformado a partir da data de nascimento / idade das fontes).
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Cliente (
    sk_cliente        INTEGER     PRIMARY KEY,
    id_cliente_origem VARCHAR(60) NOT NULL,        -- chave natural da fonte
    sistema_origem    VARCHAR(40) NOT NULL,        -- de qual OLTP veio (linhagem)
    nome              VARCHAR(120),
    cidade            VARCHAR(100),
    estado            CHAR(2),
    faixa_etaria      VARCHAR(30)                   -- Jovem / Adulto / Senior
);

-- ----------------------------------------------------------------------------
-- Dim_Veiculo : a frota. "categoria" e o GRUPO do veiculo (Economico, SUV...);
--   "mecanizacao" = cambio conformado (Automatico/Manual); "empresa_origem"
--   identifica a locadora dona do ativo (alimenta o relatorio de "origem").
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Veiculo (
    sk_veiculo        INTEGER     PRIMARY KEY,
    id_veiculo_origem VARCHAR(60) NOT NULL,
    sistema_origem    VARCHAR(40) NOT NULL,
    categoria         VARCHAR(50),                  -- "grupo" do veiculo
    marca             VARCHAR(50),
    modelo            VARCHAR(60),
    mecanizacao       VARCHAR(20),                  -- dominio fechado: Automatico|Manual
    empresa_origem    VARCHAR(100)                  -- locadora proprietaria do veiculo
);

-- ----------------------------------------------------------------------------
-- Dim_Patio : os 6 patios compartilhados. Dimensao de PAPEL MULTIPLO
--   (role-playing): a MESMA tabela fisica e referenciada como patio de
--   Retirada, Devolucao, Origem e Destino nas tabelas de fato. As VIEWS
--   abaixo dao nomes de papel para deixar as consultas legiveis.
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Patio (
    sk_patio        INTEGER     PRIMARY KEY,
    id_patio_origem VARCHAR(60) NOT NULL,
    sistema_origem  VARCHAR(40) NOT NULL,
    nome_patio      VARCHAR(100),                   -- Galeao, Santos Dumont, ...
    localizacao     VARCHAR(150),
    empresa_dona    VARCHAR(100)                    -- locadora dona do patio
);

-- ----------------------------------------------------------------------------
-- Dim_Empresa : as 6 locadoras associadas. Permite o recorte "global x por
--   empresa" exigido dos Relatorios Gerenciais.
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Empresa (
    sk_empresa        INTEGER     PRIMARY KEY,
    id_empresa_origem VARCHAR(60) NOT NULL,
    nome_empresa      VARCHAR(100) NOT NULL
);

-- ============================================================================
-- TABELAS DE FATO
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Fato_Reserva : grao = 1 reserva efetuada.
--   Responde "Controle de reservas": por grupo de veiculo, patio de retirada,
--   tempo de retirada futura e cidade de origem do cliente.
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Reserva (
    sk_cliente        INTEGER NOT NULL REFERENCES Dim_Cliente(sk_cliente),
    sk_veiculo        INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_patio_retirada INTEGER NOT NULL REFERENCES Dim_Patio(sk_patio),
    sk_tempo          INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),
    sk_empresa        INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    qtd_reservas      INTEGER NOT NULL DEFAULT 1,
    dias_reserva      INTEGER,                      -- duracao prevista (data_fim-data_inicio)
    PRIMARY KEY (sk_cliente, sk_veiculo, sk_patio_retirada, sk_tempo, sk_empresa)
);

-- ----------------------------------------------------------------------------
-- Fato_Locacao : grao = 1 locacao (contrato de aluguel).
--   Responde "Controle das locacoes" e "grupos mais alugados x origem do
--   cliente". dias_locacao + data de retirada permitem calcular o tempo
--   restante para devolucao em tempo de consulta.
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Locacao (
    sk_cliente         INTEGER NOT NULL REFERENCES Dim_Cliente(sk_cliente),
    sk_veiculo         INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_patio_retirada  INTEGER NOT NULL REFERENCES Dim_Patio(sk_patio),
    sk_patio_devolucao INTEGER NOT NULL REFERENCES Dim_Patio(sk_patio),
    sk_tempo           INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),  -- retirada
    sk_empresa         INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    qtd_locacoes       INTEGER NOT NULL DEFAULT 1,
    dias_locacao       INTEGER NOT NULL,
    PRIMARY KEY (sk_cliente, sk_veiculo, sk_patio_retirada, sk_patio_devolucao, sk_tempo, sk_empresa)
);

-- ----------------------------------------------------------------------------
-- Fato_Movimentacao : grao = 1 deslocamento de veiculo entre patios.
--   E a FONTE da matriz estocastica da Cadeia de Markov: contabiliza, por
--   patio de origem, quantos veiculos retornam/seguem para cada destino.
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Movimentacao (
    sk_veiculo        INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_patio_origem   INTEGER NOT NULL REFERENCES Dim_Patio(sk_patio),
    sk_patio_destino  INTEGER NOT NULL REFERENCES Dim_Patio(sk_patio),
    sk_tempo          INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),
    sk_empresa        INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    qtd_movimentacoes INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (sk_veiculo, sk_patio_origem, sk_patio_destino, sk_tempo, sk_empresa)
);

-- ============================================================================
-- VIEWS DE PAPEL (role-playing) sobre Dim_Patio - apenas conveniencia/leitura
-- ============================================================================
CREATE VIEW Dim_Patio_Retirada  AS SELECT * FROM Dim_Patio;
CREATE VIEW Dim_Patio_Devolucao AS SELECT * FROM Dim_Patio;
CREATE VIEW Dim_Patio_Origem    AS SELECT * FROM Dim_Patio;
CREATE VIEW Dim_Patio_Destino   AS SELECT * FROM Dim_Patio;

-- ============================================================================
-- INDICES de apoio as consultas analiticas (FKs das fatos)
-- ============================================================================
CREATE INDEX ix_freserva_tempo    ON Fato_Reserva(sk_tempo);
CREATE INDEX ix_freserva_veiculo  ON Fato_Reserva(sk_veiculo);
CREATE INDEX ix_freserva_patio    ON Fato_Reserva(sk_patio_retirada);
CREATE INDEX ix_flocacao_tempo    ON Fato_Locacao(sk_tempo);
CREATE INDEX ix_flocacao_veiculo  ON Fato_Locacao(sk_veiculo);
CREATE INDEX ix_fmov_origem       ON Fato_Movimentacao(sk_patio_origem);
CREATE INDEX ix_fmov_destino      ON Fato_Movimentacao(sk_patio_destino);

-- FIM 01_ddl_dw_estrela.sql
