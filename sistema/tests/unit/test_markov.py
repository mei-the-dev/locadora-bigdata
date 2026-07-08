# ============================================================================
# Testes: matriz de Markov (criterio de aceite da Fase 5 - linhas somam 1.0).
# ============================================================================
import pytest

from fleetlib import markov


def test_cada_linha_da_matriz_soma_um():
    # Arrange
    movs = [("Galeao", "Galeao"), ("Galeao", "Barra"), ("Galeao", "Barra"), ("Barra", "Centro"), ("Barra", "Galeao")]
    # Act
    m = markov.matriz_transicao(markov.contar_movimentos(movs))
    somas = markov.soma_linhas(m)
    # Assert
    for origem, soma in somas.items():
        assert markov.linha_estocastica(soma), f"linha {origem} soma {soma} != 1.0"


def test_probabilidade_proporcional_a_contagem():
    # Galeao->Barra 3x, Galeao->Centro 1x => P=0.75 e 0.25
    m = markov.matriz_transicao(markov.contar_movimentos([("G", "B")] * 3 + [("G", "C")]))
    assert m["G"]["B"] == pytest.approx(0.75)
    assert m["G"]["C"] == pytest.approx(0.25)


def test_matriz_condicional_por_faixa_horaria():
    # (contexto=faixa_horaria, origem, destino)
    movs = [
        ("Pico", "G", "C"), ("Pico", "G", "C"), ("Pico", "G", "B"),
        ("Madrugada", "G", "G"), ("Madrugada", "G", "B"),
    ]
    mc = markov.matriz_condicional(movs)
    assert markov.linha_estocastica(sum(mc["Pico"]["G"].values()))
    assert markov.linha_estocastica(sum(mc["Madrugada"]["G"].values()))
    # No pico, destino Centro domina; de madrugada, retorno ao proprio patio aparece.
    assert mc["Pico"]["G"]["C"] > mc["Pico"]["G"]["B"]
    assert "G" in mc["Madrugada"]["G"]


def test_distribuicao_estacionaria_soma_um():
    m = markov.matriz_transicao(markov.contar_movimentos([("A", "B"), ("B", "A"), ("A", "A"), ("B", "B")]))
    pi = markov.distribuicao_estacionaria(m)
    assert sum(pi.values()) == pytest.approx(1.0, abs=1e-4)


def test_matriz_vazia_nao_quebra():
    assert markov.matriz_transicao({}) == {}
    assert markov.distribuicao_estacionaria({}) == {}
