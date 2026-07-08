# ============================================================================
# Testes: PLN por regras do concierge (R9). Intencao + slots.
# ============================================================================
import pytest

from fleetlib.nlp import classificar


def test_emergencia_tem_prioridade_absoluta():
    r = classificar("socorro, o carro bateu e a bateria acabou")
    assert r.intencao == "emergencia"
    assert r.confianca == 1.0


@pytest.mark.parametrize(
    "fala,intencao",
    [
        ("quero reservar um carro para amanha", "reserva"),
        ("quanto custa a diaria de um SUV", "tarifa"),
        ("tem carro disponivel no Galeao?", "disponibilidade"),
        ("preciso devolver o carro hoje", "devolucao"),
        ("bom dia", "saudacao"),
        ("qual a cor do ceu", "desconhecida"),
    ],
)
def test_classifica_intencoes(fala, intencao):
    assert classificar(fala).intencao == intencao


def test_extrai_slots_categoria_patio_e_dias():
    r = classificar("quero alugar um Executivo no Santos Dumont por 5 dias")
    assert r.intencao == "reserva"
    assert r.slots.get("categoria") == "Executivo"
    assert r.slots.get("patio") == "Santos Dumont"
    assert r.slots.get("dias") == "5"


def test_funciona_sem_acento():
    assert classificar("quero fazer uma reserva").intencao == "reserva"
