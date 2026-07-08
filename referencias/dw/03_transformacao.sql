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
-- ARTEFATO: 03_transformacao.sql
-- OBJETIVO: T do ETL. Limpa e CONFORMA as fontes heterogeneas dentro da
--           staging, gerando tabelas stg_t_* prontas para carga. Trata:
--           (1) cambio/transmissao -> dominio fechado {Automatico, Manual};
--           (2) UF do cliente -> sigla de 2 letras;
--           (3) faixa etaria derivada da idade/nascimento;
--           (4) CONFORMACAO DOS 6 PATIOS compartilhados em nomes canonicos;
--           (5) chaves naturais com linhagem (sistema_origem + id_origem).
--           Executar APOS 02 e ANTES de 04.
-- ============================================================================

SET search_path TO staging;

DROP TABLE IF EXISTS stg_t_empresa, stg_t_patio_map, stg_t_patio,
                     stg_t_cliente, stg_t_veiculo CASCADE;

-- ----------------------------------------------------------------------------
-- 1) EMPRESA conformada (chave natural = nome canonico da locadora)
-- ----------------------------------------------------------------------------
CREATE TABLE stg_t_empresa AS
SELECT DISTINCT
       TRIM(nome_empresa)                       AS nome_empresa,
       MIN(sistema_origem)                      AS sistema_origem
FROM stg_empresa
WHERE nome_empresa IS NOT NULL
GROUP BY TRIM(nome_empresa);

-- ----------------------------------------------------------------------------
-- 2) PATIO: conformacao dos SEIS patios compartilhados.
--    Cada fonte referencia os mesmos 6 patios fisicos com ids proprios. Aqui
--    cada (sistema_origem,id_origem) e mapeado para um NOME CANONICO, pela
--    deteccao de palavras-chave no nome/endereco. Dim_Patio tera ~6 linhas.
-- ----------------------------------------------------------------------------
CREATE TABLE stg_t_patio_map AS
SELECT
    p.sistema_origem,
    p.id_origem,
    CASE
      WHEN COALESCE(p.nome_patio,p.localizacao) ILIKE '%galea%'                         THEN 'Aeroporto do Galeao'
      WHEN COALESCE(p.nome_patio,p.localizacao) ILIKE '%santos%dumont%'
        OR COALESCE(p.nome_patio,p.localizacao) ILIKE '%sdu%'                           THEN 'Aeroporto Santos Dumont'
      WHEN COALESCE(p.nome_patio,p.localizacao) ILIKE '%rodovi%'                        THEN 'Rodoviaria'
      WHEN COALESCE(p.nome_patio,p.localizacao) ILIKE '%rio sul%'                       THEN 'Shopping Rio Sul'
      WHEN COALESCE(p.nome_patio,p.localizacao) ILIKE '%nova am%'                       THEN 'Nova America'
      WHEN COALESCE(p.nome_patio,p.localizacao) ILIKE '%barra%'                         THEN 'Barra Shopping'
      ELSE COALESCE(NULLIF(TRIM(p.nome_patio),''), 'Patio '||p.sistema_origem||'-'||p.id_origem)
    END                                                                                 AS nome_canonico,
    p.localizacao,
    p.empresa_dona,
    p.n_vagas
FROM stg_patio p;

-- Dim_Patio canonica (uma linha por patio fisico)
CREATE TABLE stg_t_patio AS
SELECT
    nome_canonico                                   AS nome_patio,
    MAX(localizacao)                                AS localizacao,
    MAX(empresa_dona)                               AS empresa_dona,
    MAX(n_vagas)                                    AS n_vagas
FROM stg_t_patio_map
GROUP BY nome_canonico;

-- ----------------------------------------------------------------------------
-- 3) CLIENTE conformado
--    UF -> 2 letras; faixa etaria derivada (idade direta ou via nascimento).
-- ----------------------------------------------------------------------------
CREATE TABLE stg_t_cliente AS
SELECT
    sistema_origem,
    id_origem,
    sistema_origem || '#' || id_origem              AS nk_cliente,
    NULLIF(TRIM(nome),'')                           AS nome,
    NULLIF(TRIM(cidade),'')                         AS cidade,
    CASE
      WHEN estado IS NULL OR TRIM(estado) = ''                  THEN NULL
      WHEN CHAR_LENGTH(TRIM(estado)) = 2                        THEN UPPER(TRIM(estado))
      WHEN estado ILIKE 'rio de janeiro%'                       THEN 'RJ'
      WHEN estado ILIKE 'sao paulo%' OR estado ILIKE 'são paulo%' THEN 'SP'
      WHEN estado ILIKE 'minas gerais%'                         THEN 'MG'
      WHEN estado ILIKE 'espirito santo%' OR estado ILIKE 'espírito santo%' THEN 'ES'
      ELSE UPPER(LEFT(TRIM(estado),2))
    END                                             AS estado,
    CASE
      WHEN COALESCE(idade, DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))) IS NULL
                                                              THEN 'Nao informado'
      WHEN COALESCE(idade, DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))) < 25
                                                              THEN 'Jovem (ate 24 anos)'
      WHEN COALESCE(idade, DATE_PART('year', AGE(CURRENT_DATE, data_nascimento))) <= 50
                                                              THEN 'Adulto (25 a 50 anos)'
      ELSE 'Senior (acima de 50 anos)'
    END                                             AS faixa_etaria
FROM stg_cliente;

-- ----------------------------------------------------------------------------
-- 4) VEICULO conformado
--    transmissao -> {Automatico, Manual, Nao informado}; demais defaults.
-- ----------------------------------------------------------------------------
CREATE TABLE stg_t_veiculo AS
SELECT
    sistema_origem,
    id_origem,
    sistema_origem || '#' || id_origem              AS nk_veiculo,
    COALESCE(NULLIF(TRIM(categoria),''),'Nao informado')   AS categoria,
    COALESCE(NULLIF(TRIM(marca),''),'Nao informado')       AS marca,
    COALESCE(NULLIF(TRIM(modelo),''),'Nao informado')      AS modelo,
    CASE
      WHEN transmissao_bruta IS NULL OR TRIM(transmissao_bruta)='' THEN 'Nao informado'
      WHEN UPPER(TRIM(transmissao_bruta)) LIKE 'AUT%'
        OR UPPER(TRIM(transmissao_bruta)) IN ('A','AT')            THEN 'Automatico'
      WHEN UPPER(TRIM(transmissao_bruta)) LIKE 'MAN%'
        OR UPPER(TRIM(transmissao_bruta)) IN ('M','MT')            THEN 'Manual'
      ELSE 'Nao informado'
    END                                             AS mecanizacao,
    COALESCE(NULLIF(TRIM(empresa_origem),''),'Nao informado') AS empresa_origem,
    placa
FROM stg_veiculo;

-- ----------------------------------------------------------------------------
-- 5) Conferencias rapidas de qualidade (devem retornar 0 linhas problematicas)
-- ----------------------------------------------------------------------------
-- Veiculos sem patio canonico resolvivel:
-- SELECT * FROM stg_veiculo v WHERE NOT EXISTS
--   (SELECT 1 FROM stg_t_patio_map m WHERE m.sistema_origem=v.sistema_origem AND m.id_origem=v.id_patio_origem);

-- FIM 03_transformacao.sql
