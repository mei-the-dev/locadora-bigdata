# ============================================================================
# Testes: RAG local (R9). Grounding (Lewis 2020) e hot-swap sem re-treino.
# ============================================================================
import pytest

from fleetlib.rag import IndiceVetorial, Passagem, cosseno, embed_hashing, gerar_resposta


def _corpus():
    return [
        Passagem("pol-cancel", "Politica de Cancelamento", "Reservas podem ser canceladas sem custo ate 24 horas antes da retirada.", "manual-frota"),
        Passagem("tar-suv", "Tarifa do Grupo SUV", "A diaria do grupo SUV custa R$ 189,90 mais R$ 1,20 por quilometro rodado.", "tabela-tarifas"),
        Passagem("emg-bat", "Emergencia de Bateria", "Em pane de bateria, o veiculo autonomo aciona reboque e envia o dossie a central.", "protocolo-emergencia"),
    ]


def test_embedding_deterministico():
    assert embed_hashing("teste de frota") == embed_hashing("teste de frota")


def test_cosseno_identico_e_um():
    v = embed_hashing("veiculo autonomo")
    assert cosseno(v, v) == pytest.approx(1.0)


def test_cosseno_dimensoes_diferentes_falha():
    with pytest.raises(ValueError):
        cosseno([1, 2], [1, 2, 3])


def test_retriever_recupera_passagem_mais_relevante():
    # Arrange
    idx = IndiceVetorial()
    idx.indexar_muitas(_corpus())
    # Act
    top = idx.buscar("quanto custa a diaria do SUV por km", k=1)
    # Assert
    assert top[0].passagem.doc_id == "tar-suv"


def test_resposta_e_ancorada_no_corpus_com_fonte():
    # Grounding: a resposta contem o trecho recuperado e cita a fonte.
    idx = IndiceVetorial()
    idx.indexar_muitas(_corpus())
    recuperadas = idx.buscar("posso cancelar minha reserva?", k=2)
    saida = gerar_resposta("posso cancelar minha reserva?", recuperadas)
    assert "canceladas sem custo" in saida["resposta"]
    assert saida["fontes"][0]["fonte"] == "manual-frota"
    assert saida["confianca"] > 0


def test_hotswap_muda_resposta_sem_retreino():
    # Arrange - indice sem a politica de cancelamento
    idx = IndiceVetorial()
    idx.indexar(_corpus()[1])  # so tarifa
    antes = idx.buscar("posso cancelar minha reserva?", k=1)[0].passagem.doc_id
    # Act - HOT-SWAP: injeta a politica de cancelamento (sem re-treinar nada)
    idx.indexar(_corpus()[0])
    depois = idx.buscar("posso cancelar minha reserva?", k=1)[0].passagem.doc_id
    # Assert - a melhor passagem muda para a recem-inserida
    assert antes != depois
    assert depois == "pol-cancel"


def test_remocao_do_indice_esquece_conhecimento():
    idx = IndiceVetorial()
    idx.indexar_muitas(_corpus())
    assert idx.remover("tar-suv") is True
    assert len(idx) == 2
    assert all(r.passagem.doc_id != "tar-suv" for r in idx.buscar("tarifa suv", k=3))


def test_resposta_vazia_quando_sem_corpus():
    saida = gerar_resposta("qualquer coisa", [])
    assert saida["confianca"] == 0.0
    assert saida["fontes"] == []
