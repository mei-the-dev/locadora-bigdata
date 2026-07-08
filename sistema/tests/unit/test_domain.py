# ============================================================================
# Testes: constantes canonicas do dominio (dimensoes conformadas).
# ============================================================================
from fleetlib import domain


def test_seis_patios_e_seis_empresas():
    assert len(domain.PATIOS) == 6
    assert len(domain.EMPRESAS) == 6


def test_patio_ids_unicos():
    ids = domain.patio_ids()
    assert len(ids) == len(set(ids)) == 6


def test_patio_por_id_encontra_e_falha_graciosamente():
    assert domain.patio_por_id("PAT-GAL").nome == "Galeao"
    assert domain.patio_por_id("INEXISTENTE") is None


def test_rotas_canonicas_cobrem_todos_os_pares_ordenados():
    rotas = domain.rotas_canonicas()
    # 6 patios => 6*5 = 30 arestas dirigidas
    assert len(rotas) == 30
    for origem, destino, dist in rotas:
        assert origem != destino
        assert dist >= 0


def test_empresa_donas_dos_patios_sao_empresas_conhecidas():
    nomes = set(domain.empresa_nomes())
    for p in domain.PATIOS:
        assert p.empresa_dona in nomes
