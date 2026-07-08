# ============================================================================
# fleetlib.rag - RAG local SEM LLM paga (R9).
# Embedding leve DETERMINISTICO (hashing de tokens em vetor de dimensao fixa) +
# similaridade de cosseno + retriever top-K (MIPS/HNSW conceptual). O gerador e
# por regras/template e ATERRA a resposta na passagem recuperada (proveniencia,
# menos alucinacao). Hot-swap do indice muda a resposta sem re-treino.
# Fundamento: Lewis 2020 (RAG, memoria nao-parametrica, hot-swap); Manu 2022
# (banco vetorial, MIPS/HNSW). O embedder real (sentence-transformers) e um
# plugin opcional; o default nao baixa modelo -> testavel offline.
# ============================================================================
"""RAG local: embedding deterministico, cosseno, retriever e geracao ancorada."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Callable, Sequence

DIM_PADRAO = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenizar(texto: str) -> list[str]:
    """Tokenizacao simples: minusculas + tokens alfanumericos."""
    return _TOKEN_RE.findall(texto.lower())


def embed_hashing(texto: str, dim: int = DIM_PADRAO) -> list[float]:
    """Embedding deterministico por hashing (bag-of-tokens L2-normalizado).

    Cada token e mapeado (via SHA-1) a uma posicao e a um sinal no vetor de
    dimensao `dim`. Sem dependencias externas e sem download de modelo -> roda
    em qualquer lugar e e reproduzivel (bom para testes de grounding/hot-swap).
    """
    vec = [0.0] * dim
    for tok in tokenizar(texto):
        h = hashlib.sha1(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sinal = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sinal
    return _l2_normalizar(vec)


def _l2_normalizar(vec: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vec))
    if norma == 0.0:
        return vec
    return [x / norma for x in vec]


def cosseno(a: Sequence[float], b: Sequence[float]) -> float:
    """Similaridade de cosseno entre dois vetores de mesma dimensao."""
    if len(a) != len(b):
        raise ValueError("vetores de dimensoes diferentes")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True)
class Passagem:
    """Um documento/trecho do corpus da frota (politica, tarifa, FAQ, dossie)."""

    doc_id: str
    titulo: str
    texto: str
    fonte: str  # proveniencia citavel


@dataclass(frozen=True)
class Recuperada:
    """Passagem recuperada com seu score de similaridade."""

    passagem: Passagem
    score: float


class IndiceVetorial:
    """Indice vetorial em memoria (analogo funcional a pgvector/HNSW).

    Suporta HOT-SWAP: adicionar/remover passagens muda as respostas sem
    re-treino do gerador (Lewis 2020). Embedder injetavel (default: hashing).
    """

    def __init__(
        self,
        embedder: Callable[[str], list[float]] = embed_hashing,
    ) -> None:
        self._embedder = embedder
        self._passagens: list[Passagem] = []
        self._vetores: list[list[float]] = []

    def indexar(self, passagem: Passagem) -> None:
        """Adiciona uma passagem ao indice (hot-swap incremental)."""
        self._passagens.append(passagem)
        self._vetores.append(self._embedder(f"{passagem.titulo}. {passagem.texto}"))

    def indexar_muitas(self, passagens: Sequence[Passagem]) -> None:
        for p in passagens:
            self.indexar(p)

    def remover(self, doc_id: str) -> bool:
        """Remove uma passagem por doc_id (hot-swap: 'esquece' conhecimento)."""
        for i, p in enumerate(self._passagens):
            if p.doc_id == doc_id:
                del self._passagens[i]
                del self._vetores[i]
                return True
        return False

    def buscar(self, consulta: str, k: int = 3) -> list[Recuperada]:
        """Top-K por similaridade de cosseno (MIPS) - Manu 2022."""
        if not self._passagens:
            return []
        q = self._embedder(consulta)
        pontuadas = [
            Recuperada(passagem=p, score=cosseno(q, v))
            for p, v in zip(self._passagens, self._vetores)
        ]
        pontuadas.sort(key=lambda r: r.score, reverse=True)
        return pontuadas[: max(k, 0)]

    def __len__(self) -> int:
        return len(self._passagens)


def gerar_resposta(consulta: str, recuperadas: Sequence[Recuperada]) -> dict:
    """Gerador por regras que ANCORA a resposta na melhor passagem (proveniencia).

    Retorna dict com 'resposta' (contendo o trecho recuperado - criterio do
    test_rag_grounding) e 'fontes' (citaveis). Sem LLM: a resposta e a passagem
    recuperada emoldurada, o que garante grounding e auditabilidade (Lewis 2020).
    """
    if not recuperadas:
        return {
            "resposta": "Nao encontrei essa informacao na base de conhecimento da frota.",
            "fontes": [],
            "confianca": 0.0,
        }
    melhor = recuperadas[0]
    fontes = [{"doc_id": r.passagem.doc_id, "fonte": r.passagem.fonte, "score": round(r.score, 4)} for r in recuperadas]
    resposta = (
        f"Segundo {melhor.passagem.titulo} (fonte: {melhor.passagem.fonte}): "
        f"{melhor.passagem.texto}"
    )
    return {"resposta": resposta, "fontes": fontes, "confianca": round(melhor.score, 4)}
