# ============================================================================
# ai/rag/index_builder.py - constroi/atualiza o indice vetorial no pgvector.
# Le o corpus (rag_corpus), calcula embeddings (fleetlib.rag.embed_hashing por
# padrao; sentence-transformers se disponivel e habilitado) e grava a coluna
# vector(256). HOT-SWAP: re-executar atualiza a memoria do agente SEM re-treino
# do gerador (Lewis 2020). Indice HNSW/cosseno servido pelo pgvector (Manu 2022).
# Uso: python index_builder.py
# ============================================================================
"""Construtor do índice vetorial (embeddings → pgvector), com hot-swap."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.common import db  # noqa: E402
from fleetlib.rag import DIM_PADRAO, embed_hashing  # noqa: E402


def _embedder():
    """Escolhe o embedder: hashing (default, offline) ou sentence-transformers."""
    if os.getenv("RAG_USE_ST", "0") == "1":
        try:
            from sentence_transformers import SentenceTransformer  # lazy/opcional

            modelo = SentenceTransformer(os.getenv("RAG_ST_MODEL", "all-MiniLM-L6-v2"))
            # projecao para DIM_PADRAO nao e feita aqui; ajustar a coluna se usar ST.
            return lambda t: modelo.encode(t).tolist()
        except Exception:  # noqa: BLE001
            pass
    return lambda t: embed_hashing(t, DIM_PADRAO)


def _vetor_literal(vec: list[float]) -> str:
    """Formata a lista como literal de vector do pgvector: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def construir() -> int:
    """Calcula e grava embeddings de todo o corpus. Retorna nº de linhas indexadas."""
    embedder = _embedder()
    corpus = db.consultar("SELECT doc_id, titulo, texto FROM rag_corpus")
    n = 0
    for row in corpus:
        vec = embedder(f"{row['titulo']}. {row['texto']}")
        db.executar(
            "UPDATE rag_corpus SET embedding = %s::vector WHERE doc_id = %s",
            (_vetor_literal(vec), row["doc_id"]),
        )
        n += 1
    print(f"[RAG] indice atualizado: {n} passagens embutidas (dim={DIM_PADRAO}).", flush=True)
    return n


if __name__ == "__main__":
    construir()
