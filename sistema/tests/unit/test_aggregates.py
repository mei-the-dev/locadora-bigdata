# ============================================================================
# Testes: agregacoes do CUBO (Gray 1997) - classes distributiva/algebrica/
# holistica e subtotais ALL.
# ============================================================================
import pytest

from fleetlib import aggregates as agg


def test_distributivas_fazem_rollup_direto():
    parciais = [[1, 2, 3], [4, 5]]
    total_direto = agg.soma(v for grupo in parciais for v in grupo)
    total_por_partes = agg.soma(agg.soma(g) for g in parciais)
    assert total_direto == total_por_partes == 15


def test_media_algebrica_via_componentes():
    # AVG global reconstruido de (soma, contagem) parciais, sem revisitar base.
    grupo_a = [10, 20, 30]  # soma 60, n 3
    grupo_b = [40, 40]  # soma 80, n 2
    global_direto = agg.media(grupo_a + grupo_b)
    global_rollup = agg.rollup_media([(agg.soma(grupo_a), len(grupo_a)), (agg.soma(grupo_b), len(grupo_b))])
    assert global_direto == pytest.approx(global_rollup)


def test_holistica_mediana_precisa_dos_dados_base():
    assert agg.mediana([1, 2, 3, 4, 5]) == 3
    assert agg.distintos(["G", "G", "B", "C"]) == 3


def test_cubo_2d_gera_subtotais_all():
    # Arrange - (empresa, patio, km)
    fatos = [("AutoRio", "Galeao", 100.0), ("AutoRio", "Barra", 50.0), ("MoveFrota", "Galeao", 30.0)]
    # Act
    cubo = agg.cubo_2d(fatos)
    # Assert - grande total e subtotais
    assert cubo[(agg.ALL, agg.ALL)] == pytest.approx(180.0)
    assert cubo[("AutoRio", agg.ALL)] == pytest.approx(150.0)
    assert cubo[(agg.ALL, "Galeao")] == pytest.approx(130.0)
    assert cubo[("AutoRio", "Galeao")] == pytest.approx(100.0)


def test_agregacoes_vazias_nao_quebram():
    assert agg.media([]) == 0.0
    assert agg.maximo([]) == 0.0
    assert agg.mediana([]) == 0.0
