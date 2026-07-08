# ============================================================================
# Testes: concierge (service) - integra PLN por regras + RAG local sobre o
# corpus (fallback JSON, sem DB). Valida grounding + intencao fim-a-fim (R9).
# ============================================================================
from ai.concierge.service import Concierge


def test_responde_tarifa_com_passagem_ancorada():
    c = Concierge()
    r = c.responder("quanto custa a diaria do SUV?")
    assert r["intencao"] == "tarifa"
    assert "189,90" in r["resposta"]  # trecho recuperado do corpus (grounding)
    assert r["fontes"][0]["fonte"] == "tabela-tarifas"


def test_emergencia_dispara_acao():
    c = Concierge()
    r = c.responder("socorro, o carro bateu")
    assert r["intencao"] == "emergencia"
    assert "protocolo" in r.get("acao", "").lower()


def test_cancelamento_recupera_politica():
    c = Concierge()
    r = c.responder("posso cancelar minha reserva sem custo?")
    assert "canceladas sem custo" in r["resposta"]
    assert r["confianca"] > 0


def test_corpus_carregado_do_fallback_json():
    # Sem Postgres disponivel no teste, o corpus vem do JSON local.
    c = Concierge()
    assert len(c.indice) >= 7
