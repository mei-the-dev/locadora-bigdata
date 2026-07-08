# ============================================================================
# Testes: conformacao Silver (dominios fechados, dedup idempotente).
# ============================================================================
import pytest

from fleetlib import conform


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Automatico", "Automatico"),
        ("automatica", "Automatico"),
        ("AUTO", "Automatico"),
        ("cvt", "Automatico"),
        ("Manual", "Manual"),
        ("mecanico", "Manual"),
        ("MT", "Manual"),
        ("xpto", "Nao_informado"),
        (None, "Nao_informado"),
    ],
)
def test_conformar_cambio_dominio_fechado(entrada, esperado):
    assert conform.conformar_cambio(entrada) == esperado


@pytest.mark.parametrize("uf,esperado", [("rj", "RJ"), ("SP", "SP"), ("zz", "Nao_informado"), (None, "Nao_informado")])
def test_conformar_uf(uf, esperado):
    assert conform.conformar_uf(uf) == esperado


@pytest.mark.parametrize(
    "idade,faixa",
    [(17, "Nao_informado"), (18, "Jovem"), (29, "Jovem"), (30, "Adulto"), (59, "Adulto"), (60, "Senior"), (None, "Nao_informado")],
)
def test_faixa_etaria(idade, faixa):
    assert conform.faixa_etaria(idade) == faixa


@pytest.mark.parametrize(
    "hora,faixa", [(0, "Madrugada"), (5, "Madrugada"), (6, "Manha"), (11, "Manha"), (12, "Tarde"), (17, "Tarde"), (18, "Noite"), (23, "Noite")]
)
def test_faixa_horaria_alinha_com_06_ddl(hora, faixa):
    assert conform.faixa_horaria(hora) == faixa


@pytest.mark.parametrize("hora,pico", [(8, True), (18, True), (10, False), (0, False)])
def test_is_horario_pico(hora, pico):
    assert conform.is_horario_pico(hora) is pico


def test_dedup_remove_duplicatas_por_vehicle_ts_mantendo_ordem():
    # Arrange - duplicata exata (mesmo vehicle_id + event_ts)
    regs = [
        {"vehicle_id": "V1", "event_ts": 100, "v": 1},
        {"vehicle_id": "V1", "event_ts": 100, "v": 2},  # duplicata
        {"vehicle_id": "V1", "event_ts": 200, "v": 3},
        {"vehicle_id": "V2", "event_ts": 100, "v": 4},
    ]
    # Act
    out = conform.deduplicar(regs)
    # Assert - 3 unicos, 1a ocorrencia preservada
    assert len(out) == 3
    assert out[0]["v"] == 1  # manteve a primeira, nao a segunda


def test_dedup_idempotente_rerun_estavel():
    # Reprocessar o resultado nao muda nada (Zaharia 2013).
    regs = [{"vehicle_id": "V1", "event_ts": 1}, {"vehicle_id": "V1", "event_ts": 1}]
    once = conform.deduplicar(regs)
    twice = conform.deduplicar(once)
    assert once == twice == [{"vehicle_id": "V1", "event_ts": 1}]


def test_sk_tempo_formato_aaaammdd():
    assert conform.sk_tempo(2026, 7, 8) == 20260708


def test_sk_tempo_detalhe_formato_hhmm():
    assert conform.sk_tempo_detalhe(18, 30) == 1830
    assert conform.sk_tempo_detalhe(25, 0) == -1
