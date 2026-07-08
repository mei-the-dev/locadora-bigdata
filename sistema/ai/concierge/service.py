# ============================================================================
# ai/concierge/service.py - concierge de viagem por IA (R9), SEM LLM paga.
# Combina PLN por regras (fleetlib.nlp) + RAG local (fleetlib.rag) sobre o corpus
# da frota (Postgres rag_corpus, com fallback para o JSON local). Para intencoes
# operacionais (tarifa, disponibilidade) enriquece a resposta com dados da Gold.
# A resposta e SEMPRE ancorada numa passagem citavel (proveniencia - Lewis 2020).
# ============================================================================
"""Concierge: PLN por regras + RAG local ancorado, com dados da Gold."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fleetlib.nlp import classificar
from fleetlib.rag import IndiceVetorial, Passagem, gerar_resposta

_CORPUS_JSON = Path(__file__).resolve().parents[1] / "rag" / "corpus" / "frota_corpus.json"


def _carregar_corpus() -> list[Passagem]:
    """Carrega o corpus do Postgres (rag_corpus); fallback para o JSON local."""
    try:
        from app.common import db  # lazy

        linhas = db.consultar("SELECT doc_id, titulo, texto, fonte FROM rag_corpus")
        if linhas:
            return [Passagem(r["doc_id"], r["titulo"], r["texto"], r["fonte"]) for r in linhas]
    except Exception:  # noqa: BLE001 - degrada para o corpus local
        pass
    dados = json.loads(_CORPUS_JSON.read_text(encoding="utf-8"))
    return [Passagem(d["doc_id"], d["titulo"], d["texto"], d["fonte"]) for d in dados]


class Concierge:
    """Agente concierge com memoria vetorial (indice) recarregavel (hot-swap)."""

    def __init__(self) -> None:
        self.indice = IndiceVetorial()
        self.indice.indexar_muitas(_carregar_corpus())

    def responder(self, fala: str) -> dict:
        """Responde a fala do cliente: intencao + resposta ancorada + acao."""
        intencao = classificar(fala)
        recuperadas = self.indice.buscar(fala, k=3)
        base = gerar_resposta(fala, recuperadas)
        base["intencao"] = intencao.intencao
        base["slots"] = intencao.slots

        # enriquecimento operacional por intencao (consulta a Gold, best-effort)
        if intencao.intencao == "disponibilidade":
            base["disponibilidade"] = self._disponibilidade(intencao.slots.get("patio"))
        elif intencao.intencao == "emergencia":
            base["acao"] = "Acionando protocolo de emergencia e central de operacoes."
        return base

    def _disponibilidade(self, patio: str | None) -> list[dict]:
        try:
            from app.common import db  # lazy

            sql = ("SELECT patio_atual AS patio, categoria, COUNT(*) AS qtd "
                   "FROM v_posicao_atual {where} GROUP BY patio_atual, categoria ORDER BY 3 DESC")
            if patio:
                return db.consultar(sql.format(where="WHERE patio_atual = %s"), (patio,))
            return db.consultar(sql.format(where=""))
        except Exception:  # noqa: BLE001
            return []


_SINGLETON: Concierge | None = None


def responder(fala: str) -> dict:
    """Ponto de entrada simples (reusa uma instancia por processo)."""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = Concierge()
    return _SINGLETON.responder(fala)


if __name__ == "__main__":  # concierge_cli.py delega aqui
    import sys

    pergunta = " ".join(sys.argv[1:]) or "quanto custa alugar um SUV por dia?"
    print(json.dumps(responder(pergunta), indent=2, ensure_ascii=False))
