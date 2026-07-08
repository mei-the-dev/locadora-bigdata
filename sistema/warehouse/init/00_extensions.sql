-- ============================================================================
-- 00_extensions.sql - habilita extensoes do PostgreSQL Gold antes do DDL.
-- pgvector: memoria vetorial do concierge/RAG (R9) no MESMO Postgres (cabe em
-- 16 GB, zero container extra) - plano secao 3.3. Roda 1x pelo initdb.d.
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS vector;
