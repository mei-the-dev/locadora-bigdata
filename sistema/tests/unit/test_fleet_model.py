# ============================================================================
# Testes: modelo de simulacao por veiculo (determinismo + limites fisicos).
# ============================================================================
import random
import sys
from pathlib import Path

# torna importaveis os modulos do simulador (fora de pacote)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "simulator"))

from fleetlib.domain import EMPRESAS, PATIOS  # noqa: E402
from fleet_model import estado_inicial, passo, precisa_reposicionar  # noqa: E402


def _estado():
    rng = random.Random(1)
    return estado_inicial("VEH-001", EMPRESAS[0].nome, PATIOS[0], rng)


def test_passo_e_deterministico_para_mesma_semente():
    e = _estado()
    r1 = passo(e, 1000, random.Random(7))
    r2 = passo(e, 1000, random.Random(7))
    assert r1[1] == r2[1]  # mesma leitura crua
    assert r1[0] == r2[0]  # mesmo estado resultante


def test_passo_nao_muta_estado_original():
    e = _estado()
    v0 = e.velocidade
    passo(e, 1000, random.Random(3))
    assert e.velocidade == v0  # imutabilidade


def test_velocidade_e_bateria_ficam_nos_limites():
    e = _estado()
    rng = random.Random(99)
    for t in range(500):
        e, leitura = passo(e, t, rng)
        assert 0.0 <= leitura.velocidade <= 160.0
        assert 0.0 <= leitura.bateria <= 100.0


def test_bateria_descarrega_ao_longo_do_tempo():
    e = _estado()
    rng = random.Random(5)
    b0 = e.bateria
    for t in range(200):
        e, _ = passo(e, t, rng)
    assert e.bateria < b0


def test_precisa_reposicionar_quando_bateria_critica():
    from dataclasses import replace

    e = replace(_estado(), bateria=10.0)
    assert precisa_reposicionar(e) is True
    assert precisa_reposicionar(replace(e, bateria=80.0)) is False
