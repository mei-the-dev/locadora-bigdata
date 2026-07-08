# ============================================================================
# fleetlib.nlp - PLN por REGRAS do concierge de viagem (R9, sem LLM paga).
# Classifica a intencao da fala do cliente (reserva, tarifa, disponibilidade,
# emergencia, devolucao, saudacao) e extrai slots (categoria, patio, cidade).
# Combina com o RAG (fleetlib.rag) para responder com proveniencia. Ementa III
# (PLN/agentes); Lewis 2020 (geracao ancorada). Logica pura -> testavel.
# ============================================================================
"""Classificacao de intencao e extracao de slots por regras (concierge)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .domain import CATEGORIAS, PATIOS

INTENCOES = (
    "reserva",
    "tarifa",
    "disponibilidade",
    "emergencia",
    "devolucao",
    "saudacao",
    "desconhecida",
)

# Palavras-gatilho por intencao (sem acento, minusculas).
_GATILHOS: dict[str, tuple[str, ...]] = {
    "emergencia": ("socorro", "acidente", "colisao", "bateu", "pane", "emergencia", "bateria acabou", "parou"),
    "reserva": ("reservar", "reserva", "alugar", "quero um carro", "quero alugar", "agendar"),
    "tarifa": ("preco", "tarifa", "quanto custa", "valor", "cobranca", "diaria", "custa"),
    "disponibilidade": ("disponivel", "tem carro", "disponibilidade", "tem vaga", "tem algum"),
    "devolucao": ("devolver", "devolucao", "entregar o carro", "encerrar"),
    "saudacao": ("ola", "oi", "bom dia", "boa tarde", "boa noite", "e ai"),
}


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


@dataclass(frozen=True)
class Intencao:
    """Resultado do classificador: intencao + slots extraidos + confianca."""

    intencao: str
    slots: dict[str, str] = field(default_factory=dict)
    confianca: float = 0.0


def classificar(fala: str) -> Intencao:
    """Classifica a intencao da fala por casamento de gatilhos + extrai slots.

    Ordem de prioridade: emergencia (critica) vence as demais. A confianca e o
    numero de gatilhos casados normalizado (>=1 gatilho -> intencao definida).
    """
    txt = _sem_acento(fala)
    melhor_intencao = "desconhecida"
    melhor_hits = 0

    # emergencia tem prioridade absoluta (seguranca).
    for gat in _GATILHOS["emergencia"]:
        if gat in txt:
            return Intencao(intencao="emergencia", slots=_extrair_slots(txt), confianca=1.0)

    for intencao, gatilhos in _GATILHOS.items():
        if intencao == "emergencia":
            continue
        hits = sum(1 for g in gatilhos if g in txt)
        if hits > melhor_hits:
            melhor_hits = hits
            melhor_intencao = intencao

    confianca = min(1.0, melhor_hits / 2.0) if melhor_hits else 0.0
    slots = _extrair_slots(txt) if melhor_intencao != "desconhecida" else {}
    return Intencao(intencao=melhor_intencao, slots=slots, confianca=round(confianca, 3))


def _extrair_slots(txt_sem_acento: str) -> dict[str, str]:
    """Extrai categoria de veiculo e patio mencionados (slots do dominio)."""
    slots: dict[str, str] = {}
    for cat in CATEGORIAS:
        if _sem_acento(cat) in txt_sem_acento:
            slots["categoria"] = cat
            break
    for patio in PATIOS:
        if _sem_acento(patio.nome) in txt_sem_acento:
            slots["patio"] = patio.nome
            break
    m = re.search(r"(\d+)\s*(dia|dias)", txt_sem_acento)
    if m:
        slots["dias"] = m.group(1)
    return slots
