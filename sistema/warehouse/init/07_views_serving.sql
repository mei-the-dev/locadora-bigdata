-- ============================================================================
-- 07_views_serving.sql - views de SERVING para o dashboard (OLAP sobre a Gold).
-- Encapsulam a logica dos Relatorios Gerenciais A-D e da matriz de Markov
-- (warehouse/05_relatorios_matriz.sql) em objetos consumiveis pelo Streamlit.
-- ============================================================================
SET search_path TO dw_locadora;

-- ----------------------------------------------------------------------------
-- v_posicao_atual : posicao atual = destino da ultima movimentacao (Relatorio A).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_posicao_atual AS
WITH ultima AS (
    SELECT sk_veiculo, sk_patio_destino,
           ROW_NUMBER() OVER (PARTITION BY sk_veiculo ORDER BY sk_tempo DESC) AS rn
    FROM Fato_Movimentacao
)
SELECT v.sk_veiculo, v.id_veiculo_origem AS vehicle_id, v.categoria, v.marca, v.modelo,
       v.empresa_origem, p.nome_patio AS patio_atual, p.empresa_dona,
       CASE WHEN v.empresa_origem = p.empresa_dona
            THEN 'Frota propria do patio' ELSE 'Frota de empresa associada' END AS origem
FROM ultima u
JOIN Dim_Veiculo v ON v.sk_veiculo = u.sk_veiculo
JOIN Dim_Patio   p ON p.sk_patio   = u.sk_patio_destino
WHERE u.rn = 1;

-- ----------------------------------------------------------------------------
-- v_markov : matriz estocastica P(i->j) (cada linha soma 1.0). Base do
-- reposicionamento do veiculo vazio (R12).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_markov AS
WITH total_saidas AS (
    SELECT sk_patio_origem, SUM(qtd_movimentacoes) AS total
    FROM Fato_Movimentacao GROUP BY sk_patio_origem
)
SELECT po.nome_patio AS patio_origem, pd.nome_patio AS patio_destino,
       SUM(f.qtd_movimentacoes) AS movimentacoes,
       ROUND(SUM(f.qtd_movimentacoes)::numeric / ts.total, 4)     AS p_ij,
       ROUND(SUM(f.qtd_movimentacoes)::numeric / ts.total * 100, 2) AS p_ij_pct
FROM Fato_Movimentacao f
JOIN Dim_Patio po ON po.sk_patio = f.sk_patio_origem
JOIN Dim_Patio pd ON pd.sk_patio = f.sk_patio_destino
JOIN total_saidas ts ON ts.sk_patio_origem = f.sk_patio_origem
GROUP BY po.nome_patio, pd.nome_patio, ts.total
ORDER BY patio_origem, p_ij DESC;

-- ----------------------------------------------------------------------------
-- v_kpi_frota : KPIs de topo do dashboard (cacheados no Redis).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_kpi_frota AS
SELECT
    (SELECT COUNT(*) FROM Dim_Veiculo WHERE sk_veiculo > 0)                          AS total_veiculos,
    (SELECT COUNT(*) FROM Fato_Locacao)                                              AS locacoes_ativas,
    (SELECT COUNT(*) FROM Fato_Reserva)                                              AS reservas_futuras,
    (SELECT COUNT(*) FROM Fato_Sinistro)                                             AS sinistros_total,
    (SELECT COUNT(*) FROM Fato_Sinistro WHERE flag_dossie)                           AS dossies_gerados,
    (SELECT ROUND(AVG(score_conducao), 1) FROM Fato_Telemetria_Diaria)              AS score_medio_frota,
    (SELECT COALESCE(SUM(valor_final), 0) FROM Fato_Cobranca)                         AS faturamento_total;

-- ----------------------------------------------------------------------------
-- v_emergencias : sinistros com contexto (tipo, gravidade, sensor, dossie).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_emergencias AS
SELECT s.id_ocorrencia, v.id_veiculo_origem AS vehicle_id, v.categoria,
       e.nome_empresa AS empresa, te.categoria_evento, te.gravidade_padrao,
       s.severidade, s.custo_estimado, s.tempo_resposta_seg,
       td.hora_minuto AS hora, tm.data AS data_ocorrencia,
       s.latitude, s.longitude, s.flag_dossie,
       sen.tipo_sensor AS sensor_detector, sen.versao_firmware
FROM Fato_Sinistro s
JOIN Dim_Veiculo v      ON v.sk_veiculo = s.sk_veiculo
JOIN Dim_Empresa e      ON e.sk_empresa = s.sk_empresa
JOIN Dim_TipoEvento te  ON te.sk_tipo_evento = s.sk_tipo_evento
JOIN Dim_Tempo tm       ON tm.sk_tempo = s.sk_tempo
LEFT JOIN Dim_Tempo_Detalhe td ON td.sk_tempo_detalhe = s.sk_tempo_detalhe
LEFT JOIN Dim_Sensor sen ON sen.sk_sensor = s.sk_sensor
ORDER BY tm.data DESC, s.severidade DESC;

-- ----------------------------------------------------------------------------
-- v_faturamento_dia : receita diaria (medida aditiva de Fato_Cobranca).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_faturamento_dia AS
SELECT tm.data, e.nome_empresa AS empresa,
       COUNT(*) AS n_cobrancas,
       SUM(c.valor_final) AS faturamento,
       SUM(c.multa_infracao) AS multas
FROM Fato_Cobranca c
JOIN Dim_Tempo tm  ON tm.sk_tempo = c.sk_tempo
JOIN Dim_Empresa e ON e.sk_empresa = c.sk_empresa
GROUP BY tm.data, e.nome_empresa
ORDER BY tm.data DESC;

-- ----------------------------------------------------------------------------
-- v_score_frota : score de conducao por veiculo (dia mais recente).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_score_frota AS
SELECT v.id_veiculo_origem AS vehicle_id, v.categoria, e.nome_empresa AS empresa,
       fc.faixa AS faixa_conducao, t.score_conducao, t.km_rodados,
       t.velocidade_maxima, t.num_eventos_conducao_brusca, tm.data
FROM Fato_Telemetria_Diaria t
JOIN Dim_Veiculo v ON v.sk_veiculo = t.sk_veiculo
JOIN Dim_Empresa e ON e.sk_empresa = t.sk_empresa
JOIN Dim_FaixaConducao fc ON fc.sk_faixa_conducao = t.sk_faixa_conducao
JOIN Dim_Tempo tm ON tm.sk_tempo = t.sk_tempo
ORDER BY t.score_conducao ASC;
