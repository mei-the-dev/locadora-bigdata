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
-- ARTEFATO: 05_relatorios_matriz.sql
-- OBJETIVO: Relatorios Gerenciais Globais (a, b, c, d do enunciado) +
--           Matriz estocastica de movimentacao entre patios (Cadeia de Markov).
--           Consome o esquema estrela criado em 01 e carregado em 03/04.
-- ============================================================================

SET search_path TO dw_locadora;

-- ============================================================================
-- RELATORIO A - CONTROLE DE PATIO
-- "Quantitativo de veiculos no patio por GRUPO e ORIGEM (frota da empresa dona
--  do patio x frota das outras associadas), com detalhe por marca/modelo/
--  mecanizacao."
-- A posicao ATUAL de cada veiculo e o destino de sua ultima movimentacao
-- registrada (Fato_Movimentacao).
-- ============================================================================
WITH ultima_posicao AS (
    SELECT
        sk_veiculo,
        sk_patio_destino,
        ROW_NUMBER() OVER (PARTITION BY sk_veiculo ORDER BY sk_tempo DESC) AS rn
    FROM Fato_Movimentacao
)
SELECT
    p.nome_patio                                              AS patio,
    v.categoria                                              AS grupo,
    v.marca,
    v.modelo,
    v.mecanizacao,
    CASE WHEN v.empresa_origem = p.empresa_dona
         THEN 'Frota propria do patio'
         ELSE 'Frota de empresa associada' END               AS origem,
    COUNT(*)                                                 AS qtd_veiculos
FROM ultima_posicao up
JOIN Dim_Veiculo v ON v.sk_veiculo = up.sk_veiculo
JOIN Dim_Patio   p ON p.sk_patio   = up.sk_patio_destino
WHERE up.rn = 1
GROUP BY
    p.nome_patio, v.categoria, v.marca, v.modelo, v.mecanizacao,
    CASE WHEN v.empresa_origem = p.empresa_dona
         THEN 'Frota propria do patio'
         ELSE 'Frota de empresa associada' END
ORDER BY p.nome_patio, grupo, origem;

-- ============================================================================
-- RELATORIO B - CONTROLE DAS LOCACOES
-- "Quantitativo de veiculos alugados por GRUPO, tempo de locacao e tempo
--  restante para devolucao (quando ficarao disponiveis)."
-- Previsao de devolucao = data de retirada + dias_locacao.
-- ============================================================================
SELECT
    v.categoria                                          AS grupo,
    COUNT(*)                                             AS qtd_locacoes,
    SUM(f.dias_locacao)                                  AS total_dias_locacao,
    ROUND(AVG(f.dias_locacao), 1)                        AS media_dias_locacao,
    (t.data + f.dias_locacao * INTERVAL '1 day')::date   AS previsao_devolucao,
    GREATEST(
        ((t.data + f.dias_locacao * INTERVAL '1 day')::date - CURRENT_DATE), 0
    )                                                    AS dias_restantes
FROM Fato_Locacao f
JOIN Dim_Veiculo  v ON v.sk_veiculo = f.sk_veiculo
JOIN Dim_Tempo    t ON t.sk_tempo   = f.sk_tempo
GROUP BY v.categoria, t.data, f.dias_locacao
ORDER BY grupo, previsao_devolucao;

-- Variante agregada: veiculos que ficarao disponiveis nos proximos 7 dias.
SELECT
    v.categoria AS grupo,
    COUNT(*)    AS veiculos_disponiveis_em_7d
FROM Fato_Locacao f
JOIN Dim_Veiculo v ON v.sk_veiculo = f.sk_veiculo
JOIN Dim_Tempo   t ON t.sk_tempo   = f.sk_tempo
WHERE (t.data + f.dias_locacao * INTERVAL '1 day')::date
      BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
GROUP BY v.categoria
ORDER BY grupo;

-- ============================================================================
-- RELATORIO C - CONTROLE DE RESERVAS
-- "Quantas reservas por GRUPO de veiculo e PATIO de retirada, por tempo de
--  retirada futura (semana/mes que vem), e/ou duracao das locacoes, e pelas
--  CIDADES DE ORIGEM dos clientes."
-- ============================================================================
SELECT
    v.categoria                 AS grupo,
    p.nome_patio                AS patio_retirada,
    c.cidade                    AS cidade_cliente,
    c.estado                    AS uf_cliente,
    t.ano,
    t.mes,
    t.semana_ano,
    SUM(f.qtd_reservas)         AS total_reservas,
    ROUND(AVG(f.dias_reserva), 1) AS media_dias_reserva
FROM Fato_Reserva f
JOIN Dim_Veiculo v ON v.sk_veiculo        = f.sk_veiculo
JOIN Dim_Patio   p ON p.sk_patio          = f.sk_patio_retirada
JOIN Dim_Cliente c ON c.sk_cliente        = f.sk_cliente
JOIN Dim_Tempo   t ON t.sk_tempo          = f.sk_tempo
WHERE t.data >= CURRENT_DATE                       -- somente retiradas futuras
GROUP BY v.categoria, p.nome_patio, c.cidade, c.estado, t.ano, t.mes, t.semana_ano
ORDER BY total_reservas DESC;

-- ============================================================================
-- RELATORIO D - GRUPOS DE VEICULOS MAIS ALUGADOS x ORIGEM DOS CLIENTES
-- ============================================================================
SELECT
    v.categoria          AS grupo,
    c.estado             AS uf_cliente,
    c.cidade             AS cidade_cliente,
    SUM(f.qtd_locacoes)  AS total_locacoes
FROM Fato_Locacao f
JOIN Dim_Veiculo  v ON v.sk_veiculo = f.sk_veiculo
JOIN Dim_Cliente  c ON c.sk_cliente = f.sk_cliente
GROUP BY v.categoria, c.estado, c.cidade
ORDER BY total_locacoes DESC;

-- Ranking simples dos grupos mais alugados (visao global):
SELECT
    v.categoria         AS grupo,
    SUM(f.qtd_locacoes) AS total_locacoes,
    RANK() OVER (ORDER BY SUM(f.qtd_locacoes) DESC) AS posicao
FROM Fato_Locacao f
JOIN Dim_Veiculo v ON v.sk_veiculo = f.sk_veiculo
GROUP BY v.categoria
ORDER BY total_locacoes DESC;

-- ============================================================================
-- MATRIZ ESTOCASTICA DE MOVIMENTACAO ENTRE PATIOS (CADEIA DE MARKOV)
-- Para cada patio de ORIGEM i, percentual de veiculos entregues em cada
-- patio de DESTINO j:   P(i -> j) = mov(i,j) / SUM_j mov(i, j)
-- A diagonal (i = j) e o percentual que RETORNA ao mesmo patio de retirada.
-- Cada linha da matriz soma 100% (matriz estocastica por linhas).
-- ============================================================================
WITH total_saidas AS (
    SELECT sk_patio_origem, SUM(qtd_movimentacoes) AS total
    FROM Fato_Movimentacao
    GROUP BY sk_patio_origem
)
SELECT
    po.nome_patio                                              AS patio_origem_i,
    pd.nome_patio                                              AS patio_destino_j,
    SUM(f.qtd_movimentacoes)                                  AS movimentacoes,
    ts.total                                                  AS total_saidas_origem,
    ROUND(SUM(f.qtd_movimentacoes)::numeric / ts.total, 4)    AS p_ij,
    ROUND(SUM(f.qtd_movimentacoes)::numeric / ts.total * 100, 2) AS p_ij_pct
FROM Fato_Movimentacao f
JOIN Dim_Patio    po ON po.sk_patio = f.sk_patio_origem
JOIN Dim_Patio    pd ON pd.sk_patio = f.sk_patio_destino
JOIN total_saidas ts ON ts.sk_patio_origem = f.sk_patio_origem
GROUP BY po.nome_patio, pd.nome_patio, ts.total
ORDER BY patio_origem_i, p_ij DESC;

-- Conferencia: cada linha (patio de origem) deve somar 1.0000
WITH total_saidas AS (
    SELECT sk_patio_origem, SUM(qtd_movimentacoes) AS total
    FROM Fato_Movimentacao GROUP BY sk_patio_origem
)
SELECT
    po.nome_patio AS patio_origem,
    ROUND(SUM(f.qtd_movimentacoes::numeric / ts.total), 4) AS soma_linha
FROM Fato_Movimentacao f
JOIN Dim_Patio    po ON po.sk_patio = f.sk_patio_origem
JOIN total_saidas ts ON ts.sk_patio_origem = f.sk_patio_origem
GROUP BY po.nome_patio
ORDER BY patio_origem;

-- FIM 05_relatorios_matriz.sql
