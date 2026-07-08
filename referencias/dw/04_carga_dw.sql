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
-- ARTEFATO: 04_carga_dw.sql
-- OBJETIVO: L do ETL. Carrega DIMENSOES (gerando surrogate keys) e FATOS do
--           DW a partir das tabelas conformadas stg_t_* (03). A resolucao de
--           SK das fatos e feita por JOIN nas chaves naturais.
--           Executar APOS 03.
-- ============================================================================

SET search_path TO dw_locadora, staging;

-- Limpa o DW para recarga determinista (full refresh do escopo do trabalho).
TRUNCATE Fato_Reserva, Fato_Locacao, Fato_Movimentacao,
         Dim_Cliente, Dim_Veiculo, Dim_Patio, Dim_Empresa, Dim_Tempo
         RESTART IDENTITY;

-- ============================================================================
-- 1) DIM_EMPRESA  (sk via row_number; membro -1 = "Nao informado")
-- ============================================================================
INSERT INTO dw_locadora.Dim_Empresa (sk_empresa, id_empresa_origem, nome_empresa)
VALUES (-1, 'N/A', 'Nao informado');

INSERT INTO dw_locadora.Dim_Empresa (sk_empresa, id_empresa_origem, nome_empresa)
SELECT ROW_NUMBER() OVER (ORDER BY nome_empresa), nome_empresa, nome_empresa
FROM staging.stg_t_empresa;

-- ============================================================================
-- 2) DIM_PATIO  (6 patios canonicos; membro -1 = "Nao informado")
-- ============================================================================
INSERT INTO dw_locadora.Dim_Patio (sk_patio, id_patio_origem, sistema_origem, nome_patio, localizacao, empresa_dona)
VALUES (-1, 'N/A', 'N/A', 'Nao informado', NULL, NULL);

INSERT INTO dw_locadora.Dim_Patio (sk_patio, id_patio_origem, sistema_origem, nome_patio, localizacao, empresa_dona)
SELECT ROW_NUMBER() OVER (ORDER BY nome_patio),
       nome_patio,                 -- chave natural canonica = nome do patio
       'conformado',
       nome_patio, localizacao, empresa_dona
FROM staging.stg_t_patio;

-- ============================================================================
-- 3) DIM_CLIENTE
-- ============================================================================
INSERT INTO dw_locadora.Dim_Cliente (sk_cliente, id_cliente_origem, sistema_origem, nome, cidade, estado, faixa_etaria)
VALUES (-1, 'N/A', 'N/A', 'Nao informado', NULL, NULL, 'Nao informado');

INSERT INTO dw_locadora.Dim_Cliente (sk_cliente, id_cliente_origem, sistema_origem, nome, cidade, estado, faixa_etaria)
SELECT ROW_NUMBER() OVER (ORDER BY nk_cliente),
       id_origem, sistema_origem, nome, cidade, estado, faixa_etaria
FROM staging.stg_t_cliente;

-- ============================================================================
-- 4) DIM_VEICULO
-- ============================================================================
INSERT INTO dw_locadora.Dim_Veiculo (sk_veiculo, id_veiculo_origem, sistema_origem, categoria, marca, modelo, mecanizacao, empresa_origem)
VALUES (-1, 'N/A', 'N/A', 'Nao informado', 'Nao informado', 'Nao informado', 'Nao informado', 'Nao informado');

INSERT INTO dw_locadora.Dim_Veiculo (sk_veiculo, id_veiculo_origem, sistema_origem, categoria, marca, modelo, mecanizacao, empresa_origem)
SELECT ROW_NUMBER() OVER (ORDER BY nk_veiculo),
       id_origem, sistema_origem, categoria, marca, modelo, mecanizacao, empresa_origem
FROM staging.stg_t_veiculo;

-- ============================================================================
-- 5) DIM_TEMPO  (calendario gerado cobrindo todas as datas dos fatos)
-- ============================================================================
WITH limites AS (
    SELECT LEAST(
             (SELECT MIN(d) FROM (
                 SELECT MIN(data_inicio) d FROM staging.stg_reserva
                 UNION ALL SELECT MIN(data_retirada) FROM staging.stg_locacao
                 UNION ALL SELECT MIN(data_movimentacao) FROM staging.stg_movimentacao
             ) a)
           , CURRENT_DATE) AS dmin,
           GREATEST(
             (SELECT MAX(d) FROM (
                 SELECT MAX(data_fim) d FROM staging.stg_reserva
                 UNION ALL SELECT MAX(data_devolucao) FROM staging.stg_locacao
                 UNION ALL SELECT MAX(data_movimentacao) FROM staging.stg_movimentacao
             ) b)
           , CURRENT_DATE + 90) AS dmax            -- folga p/ reservas futuras
)
INSERT INTO dw_locadora.Dim_Tempo (sk_tempo, data, dia, mes, nome_mes, trimestre, ano, semana_ano, dia_semana)
SELECT
    (EXTRACT(YEAR FROM d)*10000 + EXTRACT(MONTH FROM d)*100 + EXTRACT(DAY FROM d))::int,
    d::date,
    EXTRACT(DAY     FROM d)::smallint,
    EXTRACT(MONTH   FROM d)::smallint,
    TRIM(TO_CHAR(d, 'TMMonth')),
    EXTRACT(QUARTER FROM d)::smallint,
    EXTRACT(YEAR    FROM d)::smallint,
    EXTRACT(WEEK    FROM d)::smallint,
    TRIM(TO_CHAR(d, 'TMDay'))
FROM limites, generate_series(limites.dmin, limites.dmax, INTERVAL '1 day') AS g(d);

-- ============================================================================
-- 6) FATOS  (resolucao de surrogate keys por JOIN nas chaves naturais)
-- Helpers de resolucao de patio: source(sistema,id) -> nome canonico -> sk.
-- ============================================================================

-- ---- FATO_RESERVA ----------------------------------------------------------
INSERT INTO dw_locadora.Fato_Reserva
    (sk_cliente, sk_veiculo, sk_patio_retirada, sk_tempo, sk_empresa, qtd_reservas, dias_reserva)
SELECT
    COALESCE(dc.sk_cliente, -1),
    COALESCE(dv.sk_veiculo, -1),
    COALESCE(dp.sk_patio,  -1),
    dt.sk_tempo,
    COALESCE(de.sk_empresa, -1),
    COUNT(*),
    AVG(NULLIF(r.data_fim - r.data_inicio, 0))::int
FROM staging.stg_reserva r
JOIN dw_locadora.Dim_Tempo dt
     ON dt.data = r.data_inicio
LEFT JOIN dw_locadora.Dim_Cliente dc
     ON dc.sistema_origem = r.sistema_origem AND dc.id_cliente_origem = r.id_cliente_origem
LEFT JOIN dw_locadora.Dim_Veiculo dv
     ON dv.sistema_origem = r.sistema_origem AND dv.id_veiculo_origem = r.id_veiculo_origem
LEFT JOIN staging.stg_t_patio_map pm
     ON pm.sistema_origem = r.sistema_origem AND pm.id_origem = r.id_patio_retirada_org
LEFT JOIN dw_locadora.Dim_Patio dp
     ON dp.nome_patio = pm.nome_canonico
LEFT JOIN dw_locadora.Dim_Empresa de
     ON de.nome_empresa = dv.empresa_origem
GROUP BY dc.sk_cliente, dv.sk_veiculo, dp.sk_patio, dt.sk_tempo, de.sk_empresa;

-- ---- FATO_LOCACAO ----------------------------------------------------------
INSERT INTO dw_locadora.Fato_Locacao
    (sk_cliente, sk_veiculo, sk_patio_retirada, sk_patio_devolucao, sk_tempo, sk_empresa, qtd_locacoes, dias_locacao)
SELECT
    COALESCE(dc.sk_cliente, -1),
    COALESCE(dv.sk_veiculo, -1),
    COALESCE(dpr.sk_patio, -1),
    COALESCE(dpd.sk_patio, -1),
    dt.sk_tempo,
    COALESCE(de.sk_empresa, -1),
    COUNT(*),
    COALESCE(AVG(NULLIF(l.data_devolucao - l.data_retirada, 0))::int, 1)
FROM staging.stg_locacao l
JOIN dw_locadora.Dim_Tempo dt
     ON dt.data = l.data_retirada
LEFT JOIN dw_locadora.Dim_Cliente dc
     ON dc.sistema_origem = l.sistema_origem AND dc.id_cliente_origem = l.id_cliente_origem
LEFT JOIN dw_locadora.Dim_Veiculo dv
     ON dv.sistema_origem = l.sistema_origem AND dv.id_veiculo_origem = l.id_veiculo_origem
LEFT JOIN staging.stg_t_patio_map pmr
     ON pmr.sistema_origem = l.sistema_origem AND pmr.id_origem = l.id_patio_retirada_org
LEFT JOIN dw_locadora.Dim_Patio dpr ON dpr.nome_patio = pmr.nome_canonico
LEFT JOIN staging.stg_t_patio_map pmd
     ON pmd.sistema_origem = l.sistema_origem AND pmd.id_origem = l.id_patio_devolucao_org
LEFT JOIN dw_locadora.Dim_Patio dpd ON dpd.nome_patio = pmd.nome_canonico
LEFT JOIN dw_locadora.Dim_Empresa de ON de.nome_empresa = dv.empresa_origem
GROUP BY dc.sk_cliente, dv.sk_veiculo, dpr.sk_patio, dpd.sk_patio, dt.sk_tempo, de.sk_empresa;

-- ---- FATO_MOVIMENTACAO  (base da matriz de Markov) -------------------------
INSERT INTO dw_locadora.Fato_Movimentacao
    (sk_veiculo, sk_patio_origem, sk_patio_destino, sk_tempo, sk_empresa, qtd_movimentacoes)
SELECT
    COALESCE(dv.sk_veiculo, -1),
    COALESCE(dpo.sk_patio, -1),
    COALESCE(dpd.sk_patio, -1),
    dt.sk_tempo,
    COALESCE(de.sk_empresa, -1),
    COUNT(*)
FROM staging.stg_movimentacao m
JOIN dw_locadora.Dim_Tempo dt
     ON dt.data = m.data_movimentacao
LEFT JOIN dw_locadora.Dim_Veiculo dv
     ON dv.sistema_origem = m.sistema_origem AND dv.id_veiculo_origem = m.id_veiculo_origem
LEFT JOIN staging.stg_t_patio_map pmo
     ON pmo.sistema_origem = m.sistema_origem AND pmo.id_origem = m.id_patio_origem
LEFT JOIN dw_locadora.Dim_Patio dpo ON dpo.nome_patio = pmo.nome_canonico
LEFT JOIN staging.stg_t_patio_map pmd
     ON pmd.sistema_origem = m.sistema_origem AND pmd.id_origem = m.id_patio_destino
LEFT JOIN dw_locadora.Dim_Patio dpd ON dpd.nome_patio = pmd.nome_canonico
LEFT JOIN dw_locadora.Dim_Empresa de ON de.nome_empresa = dv.empresa_origem
GROUP BY dv.sk_veiculo, dpo.sk_patio, dpd.sk_patio, dt.sk_tempo, de.sk_empresa;

-- FIM 04_carga_dw.sql
