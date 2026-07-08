# ============================================================================
# Testes: motor de cobranca (R7). Determinismo + exactly-once (Zaharia 2013).
# ============================================================================
from decimal import Decimal

import pytest

from fleetlib.billing import Cobranca, LivroCobranca, LocacaoFaturavel, calcular_cobranca


def _loc(id_="L1", cat="SUV", dias=3, km="100", horas="0", consumo="20", score=60.0, multa="0", desc="0"):
    return LocacaoFaturavel(
        id_locacao=id_, categoria=cat, dias_contratados=dias, km_rodados=Decimal(km),
        horas_extra=Decimal(horas), consumo_bateria_pct=Decimal(consumo), score_conducao=score,
        multa_infracao=Decimal(multa), desconto=Decimal(desc),
    )


def test_cobranca_soma_componentes_aditivos():
    # Arrange - SUV 189.90/dia x3 + 100km x1.20 + 0 hora + consumo 20% x0.90 (fator 1.0 Moderado)
    loc = _loc()
    # Act
    c = calcular_cobranca(loc)
    # Assert
    assert c.valor_base == Decimal("569.70")
    assert c.acrescimo_km == Decimal("120.00")
    assert c.acrescimo_consumo == Decimal("18.00")
    esperado = c.valor_base + c.acrescimo_km + c.acrescimo_tempo + c.acrescimo_consumo + c.multa_infracao - c.desconto
    assert c.valor_final == esperado


def test_faixa_agressiva_aumenta_acrescimo_consumo():
    suave = calcular_cobranca(_loc(score=90.0))  # Economico 0.95
    agressiva = calcular_cobranca(_loc(score=20.0))  # Agressivo 1.15
    assert agressiva.acrescimo_consumo > suave.acrescimo_consumo
    assert suave.sk_faixa_conducao == 1 and agressiva.sk_faixa_conducao == 3


def test_valor_final_nunca_negativo():
    c = calcular_cobranca(_loc(dias=1, km="0", consumo="0", desc="10000"))
    assert c.valor_final >= 0


def test_categoria_desconhecida_falha():
    with pytest.raises(ValueError, match="categoria desconhecida"):
        calcular_cobranca(_loc(cat="Foguete"))


def test_livro_exactly_once_nao_duplica_reprocesso():
    # Arrange
    livro = LivroCobranca()
    c = calcular_cobranca(_loc(id_="L-42"))
    # Act - registra a MESMA locacao 3 vezes (replay/reprocesso)
    r1 = livro.registrar(c)
    r2 = livro.registrar(c)
    r3 = livro.registrar(calcular_cobranca(_loc(id_="L-42")))
    # Assert - so a 1a insere; total nao dobra
    assert r1 is True and r2 is False and r3 is False
    assert len(livro) == 1
    assert livro.total_faturado() == c.valor_final


def test_livro_soma_locacoes_distintas():
    livro = LivroCobranca()
    livro.registrar(calcular_cobranca(_loc(id_="A", cat="Economico")))
    livro.registrar(calcular_cobranca(_loc(id_="B", cat="Executivo")))
    assert len(livro) == 2
    assert livro.total_faturado() > 0
