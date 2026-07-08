// ============================================================================
// Cassandra - telemetria de alta cardinalidade (Camada 4, lado AP/BASE do CAP).
// PK = vehicle_id (particao) / CK = event_ts DESC (clustering temporal).
// Fundamento: Lakshman 2009 (LSM write-optimized, clustering por tempo);
// DeCandia 2007 (always-writeable); Chang 2006 (LSM). Alta concorrencia de
// escrita (R4) e leitura por janela ja ORDENADA por veiculo (R1).
// Executado uma vez pelo docker-entrypoint-initdb.d na 1a subida.
// ============================================================================

CREATE KEYSPACE IF NOT EXISTS frota
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE frota;

// ----------------------------------------------------------------------------
// telemetria_por_veiculo : serie temporal por veiculo (pacotes agregados da
// borda). Particao = vehicle_id -> co-localiza toda a historia de um veiculo;
// clustering por event_ts DESC -> leituras retornam da mais recente p/ a mais
// antiga sem ORDER BY custoso (R1 clustering). TTL opcional por retencao (LGPD).
// ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetria_por_veiculo (
    vehicle_id        text,
    event_ts          bigint,          // epoch ms (event-time)
    empresa           text,
    velocidade_media  double,
    velocidade_maxima double,
    bateria_min       double,
    bateria_fim       double,
    autonomia_fim_km  double,
    temperatura_media double,
    lat_fim           double,
    lon_fim           double,
    km_percorridos    double,
    eventos_bruscos   int,
    n_leituras        int,
    PRIMARY KEY ((vehicle_id), event_ts)
) WITH CLUSTERING ORDER BY (event_ts DESC)
  AND comment = 'Pacotes agregados de telemetria por veiculo (clustering temporal desc)';

// ----------------------------------------------------------------------------
// posicao_atual : ultima posicao conhecida por veiculo (upsert; grao 1 linha
// por veiculo). Serve o dashboard/reposicionamento sem varrer a serie.
// ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posicao_atual (
    vehicle_id  text PRIMARY KEY,
    event_ts    bigint,
    patio_base  text,
    lat         double,
    lon         double,
    bateria     double,
    autonomia_km double
);

// ----------------------------------------------------------------------------
// eventos_emergencia : ocorrencias criticas por veiculo (hot path). Clustering
// temporal DESC para recuperar o evento mais recente rapidamente (SLA p99.9).
// ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos_emergencia (
    vehicle_id     text,
    event_ts       bigint,
    id_ocorrencia  text,
    categoria      text,          // Colisao|Pane|Bateria_Critica|...
    severidade     int,           // 1..5
    lat            double,
    lon            double,
    detalhe        text,
    PRIMARY KEY ((vehicle_id), event_ts)
) WITH CLUSTERING ORDER BY (event_ts DESC);
