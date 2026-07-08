# ============================================================================
# ai/rag/retriever.py - recuperador MIPS/HNSW sobre o pgvector (persistente).
# Embute a consulta (mesmo embedder do index_builder) e recupera top-K por
# distancia de cosseno com o operador `<=>` do pgvector (indice HNSW). E o
# caminho PERSISTENTE do RAG (o concierge in-memory usa fleetlib.rag); ambos
# compartilham o embedding hashing (Manu 2022 - MIPS; Lewis 2020 - grounding).
# Uso: python retriever.py "quanto custa o SUV"
# ============================================================================
"""Recuperador top-K sobre pgvector (cosseno/HNSW)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.common import db  # noqa: E402
from fleetlib.rag import DIM_PADRAO, embed_hashing  # noqa: E402

_SQL = """
SELECT doc_id, titulo, texto, fonte,
       1 - (embedding <=> %s::vector) AS score
FROM rag_corpus
WHERE embedding IS NOT NULL
ORDER BY embedding <=> %s::vector
LIMIT %s
"""


def _literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def buscar(consulta: str, k: int = 3) -> list[dict]:
    """Retorna as top-K passagens do pgvector (doc_id, titulo, texto, fonte, score)."""
    vec = _literal(embed_hashing(consulta, DIM_PADRAO))
    return db.consultar(_SQL, (vec, vec, k))


if __name__ == "__main__":
    pergunta = " ".join(sys.argv[1:]) or "quanto custa alugar um SUV"
    import json

    print(json.dumps(buscar(pergunta), indent=2, ensure_ascii=False, default=str))
