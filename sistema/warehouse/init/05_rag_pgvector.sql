-- ============================================================================
-- 05_rag_pgvector.sql - memoria vetorial do concierge/RAG (R9) no Postgres Gold.
-- Tabela de corpus + coluna vector(256) (dim = fleetlib.rag.DIM_PADRAO) + indice
-- HNSW por cosseno (MIPS - Manu 2022). As embeddings sao preenchidas por
-- ai/rag/index_builder.py (hot-swap sem re-treino - Lewis 2020). O texto e
-- semeado aqui para que a base exista mesmo sem rodar o index builder.
-- ============================================================================
SET search_path TO dw_locadora;

CREATE TABLE IF NOT EXISTS rag_corpus (
    doc_id     VARCHAR(60) PRIMARY KEY,
    titulo     VARCHAR(200) NOT NULL,
    texto      TEXT         NOT NULL,
    fonte      VARCHAR(120) NOT NULL,
    embedding  vector(256)              -- preenchida pelo index_builder
);

-- Indice HNSW por distancia de cosseno (so indexa linhas com embedding != NULL).
CREATE INDEX IF NOT EXISTS ix_rag_hnsw
    ON rag_corpus USING hnsw (embedding vector_cosine_ops);

-- Seed do corpus (politicas, tarifas, FAQ, protocolos) - proveniencia citavel.
INSERT INTO rag_corpus (doc_id, titulo, texto, fonte) VALUES
 ('pol-cancel', 'Politica de Cancelamento',
  'Reservas podem ser canceladas sem custo ate 24 horas antes da retirada. Apos esse prazo aplica-se taxa de 20 por cento sobre a diaria.',
  'manual-frota'),
 ('tar-suv', 'Tarifa do Grupo SUV',
  'A diaria do grupo SUV custa R$ 189,90 mais R$ 1,20 por quilometro rodado. Horas extras custam R$ 35,00.',
  'tabela-tarifas'),
 ('tar-eco', 'Tarifa do Grupo Economico',
  'A diaria do grupo Economico custa R$ 89,90 mais R$ 1,20 por quilometro rodado.',
  'tabela-tarifas'),
 ('emg-bat', 'Protocolo de Emergencia de Bateria',
  'Em pane de bateria critica, o veiculo autonomo reduz a velocidade, encosta em local seguro, aciona o reboque e envia o dossie regulatorio a central de operacoes.',
  'protocolo-emergencia'),
 ('emg-colisao', 'Protocolo de Colisao',
  'Em colisao detectada por acelerometro e camera 360, o veiculo aciona alerta a central, preserva o log de sensores para o dossie e aguarda instrucao remota.',
  'protocolo-emergencia'),
 ('faq-devolucao', 'FAQ Devolucao em Outro Patio',
  'O veiculo pode ser devolvido em qualquer um dos seis patios do consorcio. A cobranca de reposicionamento e calculada pela matriz de redistribuicao da frota.',
  'faq-clientes'),
 ('pol-conducao', 'Politica de Score de Conducao',
  'A conducao economica (score acima de 75) recebe desconto de 5 por cento no acrescimo de consumo. A conducao agressiva (score abaixo de 50) tem sobretaxa de 15 por cento.',
  'manual-frota')
ON CONFLICT (doc_id) DO NOTHING;
