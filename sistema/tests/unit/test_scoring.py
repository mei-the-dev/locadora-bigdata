# ============================================================================
# Testes: score de conducao e mapeamento para faixa/fator tarifario.
# ============================================================================
import pytest

from fleetlib.scoring import FeaturesConducao, calcular_score, faixa_do_score, probabilidade_falha


def test_conducao_suave_gera_score_alto():
    f = FeaturesConducao(km_rodados=200, velocidade_media=45, velocidade_maxima=80, eventos_bruscos=0, consumo_bateria_pct=20)
    assert calcular_score(f) >= 90


def test_conducao_agressiva_gera_score_baixo():
    f = FeaturesConducao(km_rodados=50, velocidade_media=90, velocidade_maxima=160, eventos_bruscos=30, consumo_bateria_pct=60)
    assert calcular_score(f) <= 40


def test_score_limitado_entre_0_e_100():
    horrivel = FeaturesConducao(km_rodados=10, velocidade_media=200, velocidade_maxima=250, eventos_bruscos=100, consumo_bateria_pct=100)
    assert calcular_score(horrivel) == 0.0
    perfeito = FeaturesConducao(km_rodados=1000, velocidade_media=30, velocidade_maxima=50, eventos_bruscos=0, consumo_bateria_pct=5)
    assert calcular_score(perfeito) == 100.0


def test_score_monotonico_em_eventos_bruscos():
    base = dict(km_rodados=100, velocidade_media=60, velocidade_maxima=90, consumo_bateria_pct=20)
    s0 = calcular_score(FeaturesConducao(eventos_bruscos=0, **base))
    s5 = calcular_score(FeaturesConducao(eventos_bruscos=5, **base))
    s10 = calcular_score(FeaturesConducao(eventos_bruscos=10, **base))
    assert s0 >= s5 >= s10


@pytest.mark.parametrize(
    "score,sk,faixa,fator",
    [(90, 1, "Economico", 0.950), (60, 2, "Moderado", 1.000), (20, 3, "Agressivo", 1.150), (75, 1, "Economico", 0.950), (-5, -1, "Nao_informado", 1.000)],
)
def test_faixa_do_score_bate_com_seed_do_ddl(score, sk, faixa, fator):
    assert faixa_do_score(score) == (sk, faixa, fator)


def test_probabilidade_falha_no_intervalo_0_1():
    f = FeaturesConducao(km_rodados=500, velocidade_media=80, velocidade_maxima=140, eventos_bruscos=20, consumo_bateria_pct=40)
    p = probabilidade_falha(f, horas_desde_manutencao=5000)
    assert 0.0 <= p <= 1.0
