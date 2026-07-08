-- ============================================================================
-- UFRJ - Instituto de Matematica - Departamento de Matematica Aplicada (DMA)
-- MAE016 / EEL890 - Top. Eng. de Dados B: Big Data e Data Warehouse - 2026.1
-- Professor: Milton Ramos Ramirez
-- Avaliacao 03 - Big Data (frota de veiculos autonomos e conectados)
-- ----------------------------------------------------------------------------
-- GRUPO:
--   Izabela Lima da Silva    - DRE 124156557
--   Caio Meirelles           - DRE 122071557
-- ----------------------------------------------------------------------------
-- ARTEFATO: 06_ddl_extensao.sql
-- OBJETIVO: EXTENSAO dimensional do esquema estrela da Avaliacao 02. O DW passa
--           a ser a camada GOLD de um Lakehouse (Bronze->Silver->Gold em
--           Delta/MinIO). Estas tabelas sao carregadas por ELT a partir do
--           Silver (agregados do streaming Flink/Spark) e complementam os
--           3 fatos e 5 dimensoes conformadas ja existentes.
--
-- PRE-REQUISITO: executar APOS 01_ddl_dw_estrela.sql (mesmo schema dw_locadora;
--           reutiliza Dim_Tempo, Dim_Cliente, Dim_Veiculo, Dim_Patio,
--           Dim_Empresa e as views de role-playing de Dim_Patio).
-- SGBD-alvo: PostgreSQL (compativel com ANSI SQL:2003+ / IDENTITY do SQL:2003).
-- ============================================================================

SET search_path TO dw_locadora;

-- ============================================================================
-- NOVAS DIMENSOES
-- Padrao mantido do modelo atual: surrogate key inteira sk_*, membro especial
-- sk = -1 "Nao informado", dominio fechado por CHECK, linhagem por
-- sistema_origem quando aplicavel.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Dim_Tempo_Detalhe : dimensao de HORA/MINUTO (grao sub-diario).
--   A Dim_Tempo existente tem grao DIA (sk=AAAAMMDD) e nao atende telemetria,
--   sinistros nem a Markov condicionada por faixa horaria. Esta dimensao e o
--   eixo temporal fino, pre-carregada deterministicamente (1440 minutos do dia,
--   igual a Dim_Tempo por generate_series). sk = HHMM (0..2359); -1 sentinela.
--   Papel de "Dim_Hora"; usada por Fato_Sinistro, Fato_Cobranca e como chave de
--   condicionamento (faixa_horaria) da matriz de Markov estendida.
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Tempo_Detalhe (
    sk_tempo_detalhe INTEGER     PRIMARY KEY,          -- HHMM (ex.: 1830 = 18:30); -1 = Nao informado
    hora             SMALLINT    NOT NULL,
    minuto           SMALLINT    NOT NULL,
    hora_minuto      CHAR(5)     NOT NULL,             -- 'HH:MM' para leitura em relatorio
    faixa_horaria    VARCHAR(15) NOT NULL,             -- Madrugada|Manha|Tarde|Noite
    is_horario_pico  BOOLEAN     NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_dtd_hora   CHECK (hora   BETWEEN -1 AND 23),
    CONSTRAINT ck_dtd_minuto CHECK (minuto BETWEEN -1 AND 59),
    CONSTRAINT ck_dtd_faixa  CHECK (faixa_horaria IN
        ('Madrugada','Manha','Tarde','Noite','Nao_informado'))
);

-- ----------------------------------------------------------------------------
-- Dim_TipoEvento : natureza de ocorrencias operacionais (panes, acidentes,
--   colisoes, violacoes de transito, bateria critica...). Compartilhada por
--   Fato_Sinistro e Fato_Manutencao. gravidade_padrao e atributo derivado;
--   exige_dossie sinaliza eventos que disparam o dossie regulatorio (R8).
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_TipoEvento (
    sk_tipo_evento   INTEGER     PRIMARY KEY,
    codigo_evento    VARCHAR(40) NOT NULL,             -- chave natural da fonte
    sistema_origem   VARCHAR(40) NOT NULL,
    categoria_evento VARCHAR(30) NOT NULL,             -- dominio fechado abaixo
    descricao_evento VARCHAR(150),
    gravidade_padrao VARCHAR(15) NOT NULL DEFAULT 'Nao_informado',
    exige_dossie     BOOLEAN     NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_tev_categoria CHECK (categoria_evento IN
        ('Pane','Acidente','Colisao','Violacao','Falha_Sensor',
         'Bateria_Critica','Manutencao','Outro','Nao_informado')),
    CONSTRAINT ck_tev_gravidade CHECK (gravidade_padrao IN
        ('Baixa','Media','Alta','Critica','Nao_informado'))
);

-- ----------------------------------------------------------------------------
-- Dim_Sensor : dispositivo de borda (edge) que gera telemetria/deteccao.
--   DIMENSAO SCD TIPO 2: versao de firmware muda no tempo; valid_from/valid_to/
--   is_current permitem reconstruir, point-in-time, qual firmware o sensor
--   rodava no instante de um sinistro (auditoria/regulacao - lacuna 4 do
--   modelo atual). SK estavel por (natural key + vigencia).
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_Sensor (
    sk_sensor        INTEGER     PRIMARY KEY,
    id_sensor_origem VARCHAR(60) NOT NULL,             -- chave natural do dispositivo
    sistema_origem   VARCHAR(40) NOT NULL,
    tipo_sensor      VARCHAR(30) NOT NULL,             -- dominio fechado abaixo
    fabricante       VARCHAR(60),
    unidade_medida   VARCHAR(20),                      -- km/h, C, %, g, ...
    versao_firmware  VARCHAR(40),                      -- atributo versionado (SCD2)
    valid_from       DATE        NOT NULL DEFAULT DATE '1900-01-01',
    valid_to         DATE        NOT NULL DEFAULT DATE '9999-12-31',
    is_current       BOOLEAN     NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_sen_tipo CHECK (tipo_sensor IN
        ('GPS','Acelerometro','Camera360','Bateria','Temperatura',
         'LIDAR','Ultrassom','Combustivel','Outro','Nao_informado')),
    CONSTRAINT ck_sen_vigencia CHECK (valid_to >= valid_from)
);

-- ----------------------------------------------------------------------------
-- Dim_FaixaConducao : banda (bucket) do score de conducao. Atributo DERIVADO
--   do score continuo (0..100, maior = mais economico/suave). fator_tarifa
--   liga a faixa a cobranca (acrescimo por consumo) - uso semantico, nao so
--   descritivo. Referenciada por Fato_Telemetria_Diaria e Fato_Cobranca.
-- ----------------------------------------------------------------------------
CREATE TABLE Dim_FaixaConducao (
    sk_faixa_conducao INTEGER      PRIMARY KEY,
    faixa             VARCHAR(15)  NOT NULL,           -- Economico|Moderado|Agressivo
    score_min         NUMERIC(5,2),                    -- limite inferior da banda (nullable p/ -1)
    score_max         NUMERIC(5,2),                    -- limite superior da banda
    fator_tarifa      NUMERIC(4,3) NOT NULL DEFAULT 1.000,  -- multiplicador aplicado a acrescimo_consumo
    descricao         VARCHAR(120),
    CONSTRAINT ck_fc_faixa CHECK (faixa IN
        ('Economico','Moderado','Agressivo','Nao_informado')),
    CONSTRAINT ck_fc_ordem CHECK (score_min IS NULL OR score_max IS NULL
                                  OR score_min <= score_max),
    CONSTRAINT ck_fc_fator CHECK (fator_tarifa > 0)
);

-- ============================================================================
-- NOVAS TABELAS DE FATO
-- Reutilizam as dimensoes conformadas (Tempo, Cliente, Veiculo, Patio,
-- Empresa) e as novas dimensoes acima. FKs nao-chave recebem DEFAULT -1
-- (membro "Nao informado") para carga robusta sem violar integridade.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Fato_Telemetria_Diaria : SNAPSHOT PERIODICO ACUMULADO.
--   GRAO = 1 veiculo x 1 dia (x empresa). Consolida a telemetria de alta
--   cardinalidade (que vive em Cassandra e flui Bronze->Silver) em agregados
--   diarios por veiculo, calculados em janela pelo Spark/Flink. Alimenta o
--   score de conducao e a manutencao preditiva.
--   MEDIDAS: km_rodados (ADITIVA); tempo_movimento_seg (ADITIVA);
--     num_eventos_conducao_brusca (ADITIVA); consumo_medio_bateria e
--     consumo_medio_combustivel (SEMI-ADITIVAS - media ponderada por dia/km);
--     velocidade_media/maxima, autonomia_media_km, score_conducao
--     (NAO-ADITIVAS - somente media/max, nunca soma).
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Telemetria_Diaria (
    sk_veiculo                  INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_tempo                    INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),      -- dia do snapshot
    sk_empresa                  INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    sk_patio                    INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Patio(sk_patio),          -- base/ultima posicao no dia
    sk_faixa_conducao           INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_FaixaConducao(sk_faixa_conducao),
    km_rodados                  NUMERIC(10,2) NOT NULL DEFAULT 0,
    velocidade_media            NUMERIC(6,2),
    velocidade_maxima           NUMERIC(6,2),
    consumo_medio_bateria       NUMERIC(5,2),          -- % de bateria consumida no dia
    consumo_medio_combustivel   NUMERIC(7,2),          -- litros (frota hibrida)
    autonomia_media_km          NUMERIC(7,2),
    num_eventos_conducao_brusca INTEGER NOT NULL DEFAULT 0,   -- frenagem/aceleracao/curva bruscas
    tempo_movimento_seg         INTEGER NOT NULL DEFAULT 0,
    score_conducao              NUMERIC(5,2),          -- 0..100 (derivado)
    PRIMARY KEY (sk_veiculo, sk_tempo, sk_empresa),
    CONSTRAINT ck_ftel_km    CHECK (km_rodados >= 0),
    CONSTRAINT ck_ftel_vmed  CHECK (velocidade_media IS NULL OR velocidade_media >= 0),
    CONSTRAINT ck_ftel_vmax  CHECK (velocidade_maxima IS NULL OR velocidade_maxima >= 0),
    CONSTRAINT ck_ftel_evt   CHECK (num_eventos_conducao_brusca >= 0),
    CONSTRAINT ck_ftel_tmov  CHECK (tempo_movimento_seg >= 0),
    CONSTRAINT ck_ftel_score CHECK (score_conducao IS NULL OR score_conducao BETWEEN 0 AND 100)
);

-- ----------------------------------------------------------------------------
-- Fato_Cobranca : FATO DE TRANSACAO.
--   GRAO = 1 locacao faturada (cobranca automatica pos-uso). Materializa na Gold o
--   PAGAMENTO ja modelado na Av.02 (entidade Pagamento/valor no OLTP da Parte I,
--   esbocada como Fato_Pagamento) -- que o esquema estrela entregue nao trouxe como
--   fato -- e o enriquece com os ajustes dinamicos pos-uso (km/consumo/infracoes/score).
--   Surrogate key de fato (sk_cobranca) + degenerada id_locacao (UNIQUE).
--   MEDIDAS TODAS ADITIVAS ($): valor_base + acrescimo_km + acrescimo_tempo +
--     acrescimo_consumo + multa_infracao - desconto = valor_final.
--   sk_faixa_conducao registra a banda de conducao que modulou acrescimo_consumo.
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Cobranca (
    sk_cobranca        BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    id_locacao         VARCHAR(60) NOT NULL UNIQUE,    -- dimensao degenerada (grao)
    sk_cliente         INTEGER NOT NULL REFERENCES Dim_Cliente(sk_cliente),
    sk_veiculo         INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_patio_retirada  INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Patio(sk_patio),
    sk_patio_devolucao INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Patio(sk_patio),
    sk_tempo           INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),               -- data do faturamento
    sk_tempo_detalhe   INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Tempo_Detalhe(sk_tempo_detalhe), -- hora do faturamento
    sk_empresa         INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    sk_faixa_conducao  INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_FaixaConducao(sk_faixa_conducao),
    valor_base         NUMERIC(12,2) NOT NULL DEFAULT 0,
    acrescimo_km       NUMERIC(12,2) NOT NULL DEFAULT 0,
    acrescimo_tempo    NUMERIC(12,2) NOT NULL DEFAULT 0,
    acrescimo_consumo  NUMERIC(12,2) NOT NULL DEFAULT 0,
    multa_infracao     NUMERIC(12,2) NOT NULL DEFAULT 0,
    desconto           NUMERIC(12,2) NOT NULL DEFAULT 0,
    valor_final        NUMERIC(12,2) NOT NULL DEFAULT 0,
    CONSTRAINT ck_cob_base     CHECK (valor_base        >= 0),
    CONSTRAINT ck_cob_akm      CHECK (acrescimo_km      >= 0),
    CONSTRAINT ck_cob_atempo   CHECK (acrescimo_tempo   >= 0),
    CONSTRAINT ck_cob_aconsumo CHECK (acrescimo_consumo >= 0),
    CONSTRAINT ck_cob_multa    CHECK (multa_infracao    >= 0),
    CONSTRAINT ck_cob_desc     CHECK (desconto          >= 0),
    CONSTRAINT ck_cob_final    CHECK (valor_final       >= 0)
);

-- ----------------------------------------------------------------------------
-- Fato_Sinistro : FATO DE TRANSACAO.
--   GRAO = 1 ocorrencia de emergencia/sinistro (colisao, pane, bateria critica,
--   violacao). Base do dossie regulatorio point-in-time (R8). Surrogate de fato
--   + degenerada id_ocorrencia (UNIQUE). latitude/longitude sao atributos
--   degenerados (poderao ser conformados numa futura Dim_Geo/Waypoint).
--   MEDIDAS: severidade (1..5, discreta); custo_estimado ($ ADITIVA);
--     tempo_resposta_seg (ADITIVA para totais; media para SLA).
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Sinistro (
    sk_sinistro       BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    id_ocorrencia     VARCHAR(60) NOT NULL UNIQUE,     -- dimensao degenerada (grao)
    sk_veiculo        INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_cliente        INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Cliente(sk_cliente),  -- ocupante (se houver)
    sk_patio          INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Patio(sk_patio),      -- patio base/mais proximo
    sk_tempo          INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),                 -- data da ocorrencia
    sk_tempo_detalhe  INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Tempo_Detalhe(sk_tempo_detalhe), -- hora da ocorrencia
    sk_empresa        INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    sk_tipo_evento    INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_TipoEvento(sk_tipo_evento),
    sk_sensor         INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Sensor(sk_sensor),    -- sensor que detectou
    severidade        SMALLINT NOT NULL DEFAULT 1,
    custo_estimado    NUMERIC(12,2) NOT NULL DEFAULT 0,
    tempo_resposta_seg INTEGER,
    latitude          NUMERIC(9,6),                    -- geo degenerado (dossie)
    longitude         NUMERIC(9,6),
    flag_dossie       BOOLEAN NOT NULL DEFAULT FALSE,   -- dossie regulatorio gerado?
    CONSTRAINT ck_sin_sev    CHECK (severidade BETWEEN 1 AND 5),
    CONSTRAINT ck_sin_custo  CHECK (custo_estimado >= 0),
    CONSTRAINT ck_sin_resp   CHECK (tempo_resposta_seg IS NULL OR tempo_resposta_seg >= 0)
);

-- ----------------------------------------------------------------------------
-- Fato_Manutencao : FATO DE TRANSACAO (evento REALIZADO ou PREVISTO).
--   GRAO = 1 evento/previsao de manutencao de um veiculo. Ligado a manutencao
--   preditiva: tipo_manutencao='Preditiva' carrega probabilidade_falha estimada
--   pelo modelo ML (featurizado sobre Fato_Telemetria_Diaria). Surrogate de
--   fato + degenerada id_manutencao (UNIQUE).
--   MEDIDAS: custo ($ ADITIVA); downtime_horas (ADITIVA - indisponibilidade);
--     probabilidade_falha (0..1, NAO-ADITIVA - so em previsoes).
-- ----------------------------------------------------------------------------
CREATE TABLE Fato_Manutencao (
    sk_manutencao      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    id_manutencao      VARCHAR(60) NOT NULL UNIQUE,    -- dimensao degenerada (grao)
    sk_veiculo         INTEGER NOT NULL REFERENCES Dim_Veiculo(sk_veiculo),
    sk_patio           INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Patio(sk_patio),     -- patio/oficina
    sk_tempo           INTEGER NOT NULL REFERENCES Dim_Tempo(sk_tempo),                -- data prevista/realizada
    sk_empresa         INTEGER NOT NULL REFERENCES Dim_Empresa(sk_empresa),
    sk_tipo_evento     INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_TipoEvento(sk_tipo_evento),
    sk_sensor          INTEGER NOT NULL DEFAULT -1 REFERENCES Dim_Sensor(sk_sensor),   -- componente/sensor associado
    tipo_manutencao    VARCHAR(15) NOT NULL DEFAULT 'Corretiva',
    custo              NUMERIC(12,2) NOT NULL DEFAULT 0,
    downtime_horas     NUMERIC(8,2)  NOT NULL DEFAULT 0,
    probabilidade_falha NUMERIC(5,4),                  -- so em previsoes (Preditiva)
    flag_preditiva     BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_man_tipo  CHECK (tipo_manutencao IN ('Preventiva','Corretiva','Preditiva')),
    CONSTRAINT ck_man_custo CHECK (custo >= 0),
    CONSTRAINT ck_man_down  CHECK (downtime_horas >= 0),
    CONSTRAINT ck_man_prob  CHECK (probabilidade_falha IS NULL
                                   OR probabilidade_falha BETWEEN 0 AND 1)
);

-- ============================================================================
-- INDICES de apoio as consultas analiticas (FKs das novas fatos + lookups)
-- ============================================================================
-- Fato_Telemetria_Diaria
CREATE INDEX ix_ftel_veiculo    ON Fato_Telemetria_Diaria(sk_veiculo);
CREATE INDEX ix_ftel_tempo      ON Fato_Telemetria_Diaria(sk_tempo);
CREATE INDEX ix_ftel_empresa    ON Fato_Telemetria_Diaria(sk_empresa);
CREATE INDEX ix_ftel_faixa      ON Fato_Telemetria_Diaria(sk_faixa_conducao);
-- Fato_Cobranca
CREATE INDEX ix_cob_cliente     ON Fato_Cobranca(sk_cliente);
CREATE INDEX ix_cob_veiculo     ON Fato_Cobranca(sk_veiculo);
CREATE INDEX ix_cob_tempo       ON Fato_Cobranca(sk_tempo);
CREATE INDEX ix_cob_empresa     ON Fato_Cobranca(sk_empresa);
-- Fato_Sinistro
CREATE INDEX ix_sin_veiculo     ON Fato_Sinistro(sk_veiculo);
CREATE INDEX ix_sin_tempo       ON Fato_Sinistro(sk_tempo);
CREATE INDEX ix_sin_tipo_evento ON Fato_Sinistro(sk_tipo_evento);
CREATE INDEX ix_sin_empresa     ON Fato_Sinistro(sk_empresa);
-- Fato_Manutencao
CREATE INDEX ix_man_veiculo     ON Fato_Manutencao(sk_veiculo);
CREATE INDEX ix_man_tempo       ON Fato_Manutencao(sk_tempo);
CREATE INDEX ix_man_empresa     ON Fato_Manutencao(sk_empresa);
-- Lookup do SCD2 de Dim_Sensor por chave natural + versao corrente
CREATE INDEX ix_sensor_nat      ON Dim_Sensor(id_sensor_origem, is_current);

-- ============================================================================
-- MEMBROS ESPECIAIS "Nao informado" (sk = -1) e PRE-CARGA DETERMINISTICA
-- das NOVAS dimensoes de referencia (analogo a Dim_Tempo em 04). Estes seeds
-- tornam as FKs com DEFAULT -1 (para as novas dimensoes) validas.
-- NOTA: o membro -1 das dimensoes CONFORMADAS (Dim_Cliente/Veiculo/Patio/
-- Empresa) e semeado pelo 04_carga_dw.sql (full refresh); as FKs desta
-- extensao para essas dimensoes assumem que a carga ja o inseriu.
-- ============================================================================

-- Membro -1 das novas dimensoes -------------------------------------------
INSERT INTO Dim_Tempo_Detalhe (sk_tempo_detalhe, hora, minuto, hora_minuto, faixa_horaria, is_horario_pico)
VALUES (-1, -1, -1, '--:--', 'Nao_informado', FALSE);

INSERT INTO Dim_TipoEvento (sk_tipo_evento, codigo_evento, sistema_origem, categoria_evento, descricao_evento, gravidade_padrao, exige_dossie)
VALUES (-1, 'N/D', 'N/D', 'Nao_informado', 'Nao informado', 'Nao_informado', FALSE);

INSERT INTO Dim_Sensor (sk_sensor, id_sensor_origem, sistema_origem, tipo_sensor, fabricante, unidade_medida, versao_firmware, is_current)
VALUES (-1, 'N/D', 'N/D', 'Nao_informado', 'N/D', 'N/D', 'N/D', TRUE);

INSERT INTO Dim_FaixaConducao (sk_faixa_conducao, faixa, score_min, score_max, fator_tarifa, descricao)
VALUES (-1, 'Nao_informado', NULL, NULL, 1.000, 'Nao informado');

-- Bandas reais do score de conducao (0..100; maior = mais economico) -------
INSERT INTO Dim_FaixaConducao (sk_faixa_conducao, faixa, score_min, score_max, fator_tarifa, descricao) VALUES
    (1, 'Economico', 75.00, 100.00, 0.950, 'Conducao suave/economica - desconto no acrescimo de consumo'),
    (2, 'Moderado',  50.00,  74.99, 1.000, 'Conducao moderada - tarifa neutra'),
    (3, 'Agressivo',  0.00,  49.99, 1.150, 'Conducao agressiva - sobretaxa por consumo/eventos bruscos');

-- Pre-carga deterministica dos 1440 minutos do dia (grao HHMM) -------------
INSERT INTO Dim_Tempo_Detalhe (sk_tempo_detalhe, hora, minuto, hora_minuto, faixa_horaria, is_horario_pico)
SELECT
    (g / 60) * 100 + (g % 60)                                        AS sk_tempo_detalhe,
    (g / 60)                                                         AS hora,
    (g % 60)                                                         AS minuto,
    lpad((g / 60)::text, 2, '0') || ':' || lpad((g % 60)::text, 2, '0') AS hora_minuto,
    CASE
        WHEN (g / 60) BETWEEN 0  AND 5  THEN 'Madrugada'
        WHEN (g / 60) BETWEEN 6  AND 11 THEN 'Manha'
        WHEN (g / 60) BETWEEN 12 AND 17 THEN 'Tarde'
        ELSE 'Noite'
    END                                                              AS faixa_horaria,
    ((g / 60) IN (7, 8, 9, 17, 18, 19))                              AS is_horario_pico
FROM generate_series(0, 1439) AS g;

-- FIM 06_ddl_extensao.sql
