# ============================================================================
# Testes: combiner de borda (Camada 0). Verifica R3 (economia de banda) e a
# ordenacao estrita por veiculo/timestamp ainda na borda (R1).
# ============================================================================
import pytest

from fleetlib.edge import LeituraCrua, combinar, combinar_lote, taxa_compressao


def _leitura(vid, ts, vel, bat, brusco=False, lat=-22.9, lon=-43.2):
    return LeituraCrua(
        vehicle_id=vid, event_ts=ts, velocidade=vel, bateria=bat,
        autonomia_km=bat * 3.0, temperatura=30.0, lat=lat, lon=lon, evento_brusco=brusco,
    )


def test_combiner_reduz_n_leituras_a_um_pacote():
    # Arrange
    leituras = [_leitura("V1", 1000 + i, 40 + i, 90 - i) for i in range(10)]
    # Act
    pacote = combinar(leituras)
    # Assert
    assert pacote.n_leituras == 10
    assert pacote.vehicle_id == "V1"
    assert pacote.velocidade_maxima == 49
    assert pacote.bateria_min == 81


def test_combiner_ordena_por_timestamp_mesmo_com_entrada_desordenada():
    # Arrange - leituras fora de ordem (desordem da rede movel)
    leituras = [_leitura("V1", 3000, 50, 70), _leitura("V1", 1000, 40, 90), _leitura("V1", 2000, 45, 80)]
    # Act
    pacote = combinar(leituras)
    # Assert - janela usa menor/maior ts; bateria_fim = ultima cronologica
    assert pacote.window_start_ts == 1000
    assert pacote.window_end_ts == 3000
    assert pacote.bateria_fim == 70


def test_combiner_conta_eventos_bruscos():
    # Arrange
    leituras = [_leitura("V1", 1, 40, 90, brusco=True), _leitura("V1", 2, 40, 90, brusco=False), _leitura("V1", 3, 40, 90, brusco=True)]
    # Act
    pacote = combinar(leituras)
    # Assert
    assert pacote.eventos_bruscos == 2


def test_combiner_rejeita_multiplos_veiculos():
    # Arrange
    leituras = [_leitura("V1", 1, 40, 90), _leitura("V2", 2, 40, 90)]
    # Act / Assert
    with pytest.raises(ValueError, match="por veiculo"):
        combinar(leituras)


def test_combiner_rejeita_lista_vazia():
    with pytest.raises(ValueError):
        combinar([])


def test_combinar_lote_agrupa_por_veiculo_e_janela():
    # Arrange - 2 veiculos, janelas de 3
    leituras = [_leitura("V1", i, 40, 90) for i in range(6)] + [_leitura("V2", i, 30, 80) for i in range(4)]
    # Act
    pacotes = combinar_lote(leituras, tamanho_janela=3)
    # Assert - V1: 6/3 = 2 pacotes; V2: 4 -> ceil = 2 pacotes (3 + 1)
    ids = sorted(p.vehicle_id for p in pacotes)
    assert ids == ["V1", "V1", "V2", "V2"]


def test_taxa_compressao_reflete_economia_de_banda():
    # Arrange / Act
    taxa = taxa_compressao(n_leituras_cruas=100, n_pacotes=10)
    # Assert - 1 pacote a cada 10 leituras => 10x menos mensagens
    assert taxa == pytest.approx(10.0)


def test_pacote_km_percorridos_nao_negativo():
    leituras = [_leitura("V1", 1, 40, 90, lat=-22.9, lon=-43.2), _leitura("V1", 2, 42, 89, lat=-22.91, lon=-43.21)]
    pacote = combinar(leituras)
    assert pacote.km_percorridos >= 0
