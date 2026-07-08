-- ============================================================================
-- 06_agregados_cube.sql - CUBO executivo (Gray 1997) materializado na Gold.
-- Operador CUBE/GROUPING SETS com subtotais ALL (GROUPING() marca a linha de
-- subtotal). Roll-up de funcoes DISTRIBUTIVAS (SUM/COUNT) e ALGEBRICAS (AVG).
-- Materializado como views (summary tables - Chaudhuri & Dayal 1997), o
-- dashboard le daqui (com cache Redis por cima).
-- ============================================================================
SET search_path TO dw_locadora;

-- ----------------------------------------------------------------------------
-- Cubo operacional da frota: km e score por (empresa x patio x faixa_conducao)
-- com todos os subtotais. GROUPING()=1 indica o membro 'ALL' daquela dimensao.
-- ----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_cubo_frota;
CREATE MATERIALIZED VIEW mv_cubo_frota AS
SELECT
    CASE WHEN GROUPING(e.nome_empresa) = 1 THEN 'ALL' ELSE e.nome_empresa END AS empresa,
    CASE WHEN GROUPING(p.nome_patio)   = 1 THEN 'ALL' ELSE p.nome_patio   END AS patio,
    CASE WHEN GROUPING(fc.faixa)       = 1 THEN 'ALL' ELSE fc.faixa       END AS faixa_conducao,
    SUM(t.km_rodados)                        AS km_total,           -- distributiva
    COUNT(*)                                 AS n_snapshots,        -- distributiva
    ROUND(AVG(t.score_conducao), 2)          AS score_medio,        -- algebrica
    SUM(t.num_eventos_conducao_brusca)       AS eventos_bruscos     -- distributiva
FROM Fato_Telemetria_Diaria t
JOIN Dim_Empresa e       ON e.sk_empresa = t.sk_empresa
JOIN Dim_Patio   p       ON p.sk_patio   = t.sk_patio
JOIN Dim_FaixaConducao fc ON fc.sk_faixa_conducao = t.sk_faixa_conducao
GROUP BY CUBE (e.nome_empresa, p.nome_patio, fc.faixa);

-- ----------------------------------------------------------------------------
-- Cubo financeiro: faturamento por (empresa x mes) com subtotais ALL.
-- Todas as medidas de Fato_Cobranca sao aditivas ($).
-- ----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_cubo_financeiro;
CREATE MATERIALIZED VIEW mv_cubo_financeiro AS
SELECT
    CASE WHEN GROUPING(e.nome_empresa) = 1 THEN 'ALL' ELSE e.nome_empresa END AS empresa,
    CASE WHEN GROUPING(tm.ano, tm.mes) = 1 THEN 'ALL'
         ELSE tm.ano || '-' || LPAD(tm.mes::text, 2, '0') END                 AS ano_mes,
    COUNT(*)                          AS n_cobrancas,
    SUM(c.valor_base)                 AS total_base,
    SUM(c.acrescimo_km)               AS total_km,
    SUM(c.acrescimo_consumo)          AS total_consumo,
    SUM(c.multa_infracao)             AS total_multa,
    SUM(c.valor_final)                AS total_faturado
FROM Fato_Cobranca c
JOIN Dim_Empresa e ON e.sk_empresa = c.sk_empresa
JOIN Dim_Tempo   tm ON tm.sk_tempo  = c.sk_tempo
GROUP BY CUBE (e.nome_empresa, (tm.ano, tm.mes));

-- Refresh helper (chamado pelo ELT / gold_aggregates ou `make seed`).
-- SELECT * exemplos ficam nos relatorios (warehouse/05_relatorios_matriz.sql).
