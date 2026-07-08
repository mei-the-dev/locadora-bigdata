# ============================================================================
# Testes: SCD Tipo 2 (Dim_Sensor/firmware) - historico point-in-time (R8).
# ============================================================================
from datetime import date

from fleetlib.scd2 import DATA_FIM_ABERTO, aplicar_mudanca, versao_vigente_em


def test_primeira_versao_e_inserida_como_corrente():
    versoes, prox = aplicar_mudanca([], "SENSOR-1", {"versao_firmware": "1.0"}, date(2026, 1, 1), proximo_sk=1)
    assert len(versoes) == 1
    assert versoes[0].is_current
    assert versoes[0].valid_to == DATA_FIM_ABERTO
    assert prox == 2


def test_atributos_iguais_sao_idempotentes():
    v1, prox1 = aplicar_mudanca([], "S1", {"fw": "1.0"}, date(2026, 1, 1), 1)
    v2, prox2 = aplicar_mudanca(v1, "S1", {"fw": "1.0"}, date(2026, 2, 1), prox1)
    assert v1 == v2  # sem nova versao
    assert prox1 == prox2


def test_mudanca_de_firmware_fecha_versao_e_abre_nova():
    v1, prox1 = aplicar_mudanca([], "S1", {"fw": "1.0"}, date(2026, 1, 1), 1)
    v2, prox2 = aplicar_mudanca(v1, "S1", {"fw": "2.0"}, date(2026, 6, 1), prox1)
    correntes = [v for v in v2 if v.is_current]
    fechadas = [v for v in v2 if not v.is_current]
    assert len(correntes) == 1 and correntes[0].atributos_dict()["fw"] == "2.0"
    assert len(fechadas) == 1 and fechadas[0].valid_to == date(2026, 6, 1)
    assert prox2 == 3


def test_point_in_time_recupera_firmware_correto():
    # Arrange - firmware 1.0 ate jun/2026, depois 2.0
    v1, p1 = aplicar_mudanca([], "S1", {"fw": "1.0"}, date(2026, 1, 1), 1)
    v2, _ = aplicar_mudanca(v1, "S1", {"fw": "2.0"}, date(2026, 6, 1), p1)
    # Act / Assert - reconstrucao do estado no instante do sinistro
    assert versao_vigente_em(v2, "S1", date(2026, 3, 15)).atributos_dict()["fw"] == "1.0"
    assert versao_vigente_em(v2, "S1", date(2026, 9, 1)).atributos_dict()["fw"] == "2.0"
    assert versao_vigente_em(v2, "S1", date(1999, 1, 1)) is None
