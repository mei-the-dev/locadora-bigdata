-- ============================================================================
-- 04_seed_gold.sql - carga DETERMINISTICA das dimensoes conformadas e de um
-- conjunto REPRESENTATIVO de fatos, para que dashboard, relatorios gerenciais
-- (A-D) e a matriz de Markov funcionem imediatamente apos `make up-core`, mesmo
-- antes do ELT streaming rodar. Coerente com fleetlib.domain e o seed do Mongo.
-- Executa 1x pelo initdb.d, APOS 01 (estrela) e 02 (extensao). SK explicitas.
-- Grupo: Izabela Lima da Silva (124156557) - Caio Meirelles (122071557)
-- ============================================================================
SET search_path TO dw_locadora;

-- ----------------------------------------------------------------------------
-- DIM_EMPRESA (membro -1 + 6 locadoras do consorcio)
-- ----------------------------------------------------------------------------
INSERT INTO Dim_Empresa (sk_empresa, id_empresa_origem, nome_empresa) VALUES
    (-1, 'N/A', 'Nao informado'),
    (1, 'EMP-AUTORIO',   'AutoRio Locadora'),
    (2, 'EMP-MOVEFROTA', 'MoveFrota'),
    (3, 'EMP-VELOZCAR',  'VelozCar'),
    (4, 'EMP-UNIDAS',    'UnidasFrota'),
    (5, 'EMP-CARIOCA',   'Carioca Rent'),
    (6, 'EMP-LITORAL',   'Litoral Autos');

-- ----------------------------------------------------------------------------
-- DIM_PATIO (membro -1 + 6 patios canonicos compartilhados)
-- ----------------------------------------------------------------------------
INSERT INTO Dim_Patio (sk_patio, id_patio_origem, sistema_origem, nome_patio, localizacao, empresa_dona) VALUES
    (-1, 'N/A', 'N/A', 'Nao informado', NULL, NULL),
    (1, 'PAT-GAL', 'conformado', 'Galeao',        'Aeroporto Internacional - Ilha do Governador', 'AutoRio Locadora'),
    (2, 'PAT-SDU', 'conformado', 'Santos Dumont', 'Centro - Orla da Baia de Guanabara',           'MoveFrota'),
    (3, 'PAT-BAR', 'conformado', 'Barra',         'Barra da Tijuca - Av. das Americas',           'VelozCar'),
    (4, 'PAT-COP', 'conformado', 'Copacabana',    'Zona Sul - Orla de Copacabana',                'AutoRio Locadora'),
    (5, 'PAT-CEN', 'conformado', 'Centro',        'Centro - Av. Presidente Vargas',               'UnidasFrota'),
    (6, 'PAT-NIT', 'conformado', 'Niteroi',       'Niteroi - Centro / Terminal',                  'MoveFrota');

-- ----------------------------------------------------------------------------
-- DIM_CLIENTE (membro -1 + 8 clientes; cidades de origem p/ relatorios C e D)
-- ----------------------------------------------------------------------------
INSERT INTO Dim_Cliente (sk_cliente, id_cliente_origem, sistema_origem, nome, cidade, estado, faixa_etaria) VALUES
    (-1, 'N/A', 'N/A', 'Nao informado', NULL, NULL, 'Nao informado'),
    (1, 'CLI-001', 'crm', 'Cliente 1', 'Rio de Janeiro',  'RJ', 'Jovem'),
    (2, 'CLI-002', 'crm', 'Cliente 2', 'Niteroi',         'RJ', 'Adulto'),
    (3, 'CLI-003', 'crm', 'Cliente 3', 'Sao Paulo',       'SP', 'Adulto'),
    (4, 'CLI-004', 'crm', 'Cliente 4', 'Belo Horizonte',  'MG', 'Senior'),
    (5, 'CLI-005', 'crm', 'Cliente 5', 'Vitoria',         'ES', 'Jovem'),
    (6, 'CLI-006', 'crm', 'Cliente 6', 'Campinas',        'SP', 'Adulto'),
    (7, 'CLI-007', 'crm', 'Cliente 7', 'Rio de Janeiro',  'RJ', 'Adulto'),
    (8, 'CLI-008', 'crm', 'Cliente 8', 'Niteroi',         'RJ', 'Senior');

-- ----------------------------------------------------------------------------
-- DIM_VEICULO (membro -1 + 12 veiculos autonomos; espelha o seed do MongoDB)
-- ----------------------------------------------------------------------------
INSERT INTO Dim_Veiculo (sk_veiculo, id_veiculo_origem, sistema_origem, categoria, marca, modelo, mecanizacao, empresa_origem) VALUES
    (-1, 'N/A', 'N/A', 'Nao informado', 'Nao informado', 'Nao informado', 'Nao informado', 'Nao informado'),
    (1,  'VEH-001', 'fleet', 'Economico',     'VW',        'VW Gol',          'Automatico', 'AutoRio Locadora'),
    (2,  'VEH-002', 'fleet', 'Intermediario', 'Hyundai',   'Hyundai HB20',    'Automatico', 'MoveFrota'),
    (3,  'VEH-003', 'fleet', 'SUV',           'Jeep',      'Jeep Compass',    'Automatico', 'VelozCar'),
    (4,  'VEH-004', 'fleet', 'Executivo',     'Honda',     'Honda Civic',     'Automatico', 'UnidasFrota'),
    (5,  'VEH-005', 'fleet', 'Utilitario',    'Fiat',      'Fiat Fiorino',    'Automatico', 'Carioca Rent'),
    (6,  'VEH-006', 'fleet', 'Economico',     'Fiat',      'Fiat Mobi',       'Automatico', 'Litoral Autos'),
    (7,  'VEH-007', 'fleet', 'Intermediario', 'Chevrolet', 'Chevrolet Onix',  'Automatico', 'AutoRio Locadora'),
    (8,  'VEH-008', 'fleet', 'SUV',           'VW',        'VW T-Cross',      'Automatico', 'MoveFrota'),
    (9,  'VEH-009', 'fleet', 'Executivo',     'Toyota',    'Toyota Corolla',  'Automatico', 'VelozCar'),
    (10, 'VEH-010', 'fleet', 'Utilitario',    'Renault',   'Renault Kangoo',  'Automatico', 'UnidasFrota'),
    (11, 'VEH-011', 'fleet', 'Economico',     'VW',        'VW Gol',          'Automatico', 'Carioca Rent'),
    (12, 'VEH-012', 'fleet', 'Intermediario', 'Hyundai',   'Hyundai HB20',    'Automatico', 'Litoral Autos');

-- ----------------------------------------------------------------------------
-- DIM_TEMPO (calendario deterministico cobrindo passado recente + futuro p/
-- reservas). sk = AAAAMMDD (compat. com 04_carga_dw.sql da Av.02).
-- ----------------------------------------------------------------------------
INSERT INTO Dim_Tempo (sk_tempo, data, dia, mes, nome_mes, trimestre, ano, semana_ano, dia_semana)
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
FROM generate_series(CURRENT_DATE - 60, CURRENT_DATE + 120, INTERVAL '1 day') AS g(d);

-- ----------------------------------------------------------------------------
-- DIM_TIPOEVENTO (membros reais alem do -1 ja semeado pela extensao)
-- ----------------------------------------------------------------------------
INSERT INTO Dim_TipoEvento (sk_tipo_evento, codigo_evento, sistema_origem, categoria_evento, descricao_evento, gravidade_padrao, exige_dossie) VALUES
    (1, 'EVT-COLISAO',  'safety', 'Colisao',         'Colisao detectada por acelerometro/camera', 'Alta',    TRUE),
    (2, 'EVT-PANE',     'obd',    'Pane',            'Falha mecanica/eletronica em via',          'Media',   FALSE),
    (3, 'EVT-BATCRIT',  'bms',    'Bateria_Critica', 'Bateria abaixo do limite critico',          'Alta',    TRUE),
    (4, 'EVT-VIOLACAO', 'traffic','Violacao',        'Excesso de velocidade / infracao',          'Media',   FALSE),
    (5, 'EVT-FALHASEN', 'diag',   'Falha_Sensor',    'Sensor de borda inoperante',                'Media',   FALSE),
    (6, 'EVT-MANUT',    'cmms',   'Manutencao',      'Manutencao programada/preditiva',           'Baixa',   FALSE);

-- ----------------------------------------------------------------------------
-- DIM_SENSOR (membros reais correntes; SCD2 - is_current=TRUE, vigencia aberta)
-- ----------------------------------------------------------------------------
INSERT INTO Dim_Sensor (sk_sensor, id_sensor_origem, sistema_origem, tipo_sensor, fabricante, unidade_medida, versao_firmware, valid_from, valid_to, is_current) VALUES
    (1, 'SEN-GPS-STD',  'fleet', 'GPS',        'Garmin',   'graus', '1.0.0', DATE '2026-01-15', DATE '9999-12-31', TRUE),
    (2, 'SEN-BAT-STD',  'fleet', 'Bateria',    'BYD',      '%',     '2.3.1', DATE '2026-01-15', DATE '9999-12-31', TRUE),
    (3, 'SEN-CAM-STD',  'fleet', 'Camera360',  'Mobileye', 'frame', '4.1.0', DATE '2026-01-15', DATE '9999-12-31', TRUE),
    (4, 'SEN-ACC-STD',  'fleet', 'Acelerometro','Bosch',   'g',     '1.2.0', DATE '2026-01-15', DATE '9999-12-31', TRUE);

-- ============================================================================
-- FATOS REPRESENTATIVOS
-- ============================================================================

-- ---- FATO_MOVIMENTACAO (base da matriz de Markov; cada origem soma 1.0) -----
-- (veiculo base do patio de origem, origem, destino, dia=ontem, empresa, qtd)
INSERT INTO Fato_Movimentacao (sk_veiculo, sk_patio_origem, sk_patio_destino, sk_tempo, sk_empresa, qtd_movimentacoes)
SELECT v, o, d, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE - 1), e, q
FROM (VALUES
    -- Galeao (origem 1) - veiculo 1 / empresa 1 : 5+3+2 = 10
    (1, 1, 1, 1, 5), (1, 1, 2, 1, 3), (1, 1, 3, 1, 2),
    -- Santos Dumont (2) - veiculo 2 / empresa 2 : 4+4+2 = 10
    (2, 2, 2, 2, 4), (2, 2, 1, 2, 4), (2, 2, 5, 2, 2),
    -- Barra (3) - veiculo 3 / empresa 3 : 6+2+2 = 10
    (3, 3, 3, 3, 6), (3, 3, 4, 3, 2), (3, 3, 1, 3, 2),
    -- Copacabana (4) - veiculo 4 / empresa 4 : 5+3+2 = 10
    (4, 4, 4, 4, 5), (4, 4, 3, 4, 3), (4, 4, 2, 4, 2),
    -- Centro (5) - veiculo 5 / empresa 5 : 4+3+3 = 10
    (5, 5, 5, 5, 4), (5, 5, 1, 5, 3), (5, 5, 6, 5, 3),
    -- Niteroi (6) - veiculo 6 / empresa 6 : 5+3+2 = 10
    (6, 6, 6, 6, 5), (6, 6, 2, 6, 3), (6, 6, 5, 6, 2)
) AS m(v, o, d, e, q);

-- ---- FATO_RESERVA (retiradas futuras p/ relatorio C) -----------------------
INSERT INTO Fato_Reserva (sk_cliente, sk_veiculo, sk_patio_retirada, sk_tempo, sk_empresa, qtd_reservas, dias_reserva)
SELECT c, v, p, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE + off), e, q, dias
FROM (VALUES
    (1, 3, 3, 7,  3, 2, 4),
    (2, 8, 2, 3,  2, 1, 3),
    (3, 4, 4, 14, 4, 3, 5),
    (5, 1, 1, 5,  1, 1, 2),
    (7, 9, 3, 10, 3, 2, 6)
) AS r(c, v, p, off, e, q, dias);

-- ---- FATO_LOCACAO (contratos em curso p/ relatorios B e D) ------------------
INSERT INTO Fato_Locacao (sk_cliente, sk_veiculo, sk_patio_retirada, sk_patio_devolucao, sk_tempo, sk_empresa, qtd_locacoes, dias_locacao)
SELECT c, v, pr, pd, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE - off), e, q, dias
FROM (VALUES
    (1, 1, 1, 2, 2, 1, 1, 4),
    (2, 3, 3, 3, 1, 3, 1, 3),
    (4, 4, 4, 3, 5, 4, 1, 7),
    (6, 6, 6, 5, 3, 6, 1, 2),
    (8, 9, 3, 1, 4, 3, 1, 5)
) AS l(c, v, pr, pd, off, e, q, dias);

-- ---- FATO_TELEMETRIA_DIARIA (snapshot de ontem por veiculo; score/faixa) ----
INSERT INTO Fato_Telemetria_Diaria
    (sk_veiculo, sk_tempo, sk_empresa, sk_patio, sk_faixa_conducao, km_rodados, velocidade_media,
     velocidade_maxima, consumo_medio_bateria, autonomia_media_km, num_eventos_conducao_brusca,
     tempo_movimento_seg, score_conducao)
SELECT v, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE - 1), e, p, fx, km, vmed, vmax, cons, aut, brusco, tmov, score
FROM (VALUES
    (1, 1, 1, 1, 180.5, 48.2, 92.0, 22.0, 210.0, 2, 12600, 88.5),
    (2, 2, 2, 2, 95.0,  52.0, 105.0, 18.0, 240.0, 1, 7200, 79.0),
    (3, 3, 3, 3, 240.0, 61.0, 138.0, 34.0, 180.0, 9, 15400, 41.0),
    (4, 4, 4, 1, 60.0,  40.0, 80.0, 12.0, 300.0, 0, 5400, 96.0),
    (5, 5, 5, 2, 130.0, 55.0, 120.0, 28.0, 160.0, 5, 9800, 58.0),
    (6, 6, 6, 3, 210.0, 50.0, 98.0, 24.0, 190.0, 3, 13000, 72.0)
) AS t(v, e, p, fx, km, vmed, vmax, cons, aut, brusco, tmov, score);

-- ---- FATO_COBRANCA (cobrancas pos-uso; id_locacao UNIQUE = exactly-once) ----
INSERT INTO Fato_Cobranca
    (id_locacao, sk_cliente, sk_veiculo, sk_patio_retirada, sk_patio_devolucao, sk_tempo, sk_tempo_detalhe,
     sk_empresa, sk_faixa_conducao, valor_base, acrescimo_km, acrescimo_tempo, acrescimo_consumo,
     multa_infracao, desconto, valor_final)
SELECT idl, c, v, pr, pd, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE - off), 1830, e, fx,
       vb, akm, atempo, acons, multa, desc_, vfinal
FROM (VALUES
    ('LOC-1001', 1, 1, 1, 2, 2, 1, 1, 359.60, 216.60, 0.00,   18.81, 0.00,  0.00, 594.01),
    ('LOC-1002', 2, 3, 3, 3, 1, 3, 2, 569.70, 288.00, 35.00,  39.10, 0.00,  0.00, 931.80),
    ('LOC-1003', 4, 4, 4, 3, 5, 4, 1, 1749.30, 72.00, 0.00,   10.26, 0.00, 50.00, 1781.56),
    ('LOC-1004', 6, 6, 6, 5, 3, 6, 2, 179.80, 252.00, 0.00,   21.60, 90.00, 0.00, 543.40)
) AS b(idl, c, v, pr, pd, off, e, fx, vb, akm, atempo, acons, multa, desc_, vfinal);

-- ---- FATO_SINISTRO (ocorrencias de emergencia; base do dossie R8) -----------
INSERT INTO Fato_Sinistro
    (id_ocorrencia, sk_veiculo, sk_cliente, sk_patio, sk_tempo, sk_tempo_detalhe, sk_empresa,
     sk_tipo_evento, sk_sensor, severidade, custo_estimado, tempo_resposta_seg, latitude, longitude, flag_dossie)
SELECT ido, v, c, p, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE - off), td, e, te, s, sev, custo, resp, lat, lon, dossie
FROM (VALUES
    ('OCC-9001', 3, 2, 3, 1, 1420, 3, 1, 4, 4, 8500.00, 240, -23.000, -43.365, TRUE),
    ('OCC-9002', 5, -1, 5, 2, 320,  5, 3, 2, 3, 1200.00, 180, -22.906, -43.185, TRUE),
    ('OCC-9003', 2, 8, 2, 1, 905,  2, 4, 1, 2, 300.00,  90, -22.910, -43.163, FALSE)
) AS s(ido, v, c, p, off, td, e, te, s, sev, custo, resp, lat, lon, dossie);

-- ---- FATO_MANUTENCAO (corretiva + preditiva com probabilidade_falha) --------
INSERT INTO Fato_Manutencao
    (id_manutencao, sk_veiculo, sk_patio, sk_tempo, sk_empresa, sk_tipo_evento, sk_sensor,
     tipo_manutencao, custo, downtime_horas, probabilidade_falha, flag_preditiva)
SELECT idm, v, p, (SELECT sk_tempo FROM Dim_Tempo WHERE data = CURRENT_DATE - off), e, te, sen, tipo, custo, down, prob, pred
FROM (VALUES
    ('MAN-7001', 3, 3, 2, 3, 6, 2, 'Corretiva',  2200.00, 8.0,  NULL,   FALSE),
    ('MAN-7002', 5, 5, 1, 5, 6, 4, 'Preditiva',   0.00,   0.0,  0.7300, TRUE),
    ('MAN-7003', 1, 1, 5, 1, 6, 1, 'Preventiva', 450.00,  2.5,  NULL,   FALSE)
) AS m(idm, v, p, off, e, te, sen, tipo, custo, down, prob, pred);

-- FIM 04_seed_gold.sql
