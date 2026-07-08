# ============================================================================
# Testes: checksum da ponte MQTT->Kafka (R2 sem perda de pacotes).
# ============================================================================
import pytest

from fleetlib.checksum import calcular_crc32, selar, verificar


def test_envelope_selado_e_valido():
    # Arrange / Act
    env = selar("V1", b"telemetria-avro-bytes")
    # Assert
    assert env.valido()
    assert env.partition_key == "V1"
    verificar(env)  # nao levanta


def test_crc32_deterministico_para_mesmo_payload():
    assert calcular_crc32(b"abc") == calcular_crc32(b"abc")


def test_crc32_muda_com_payload_diferente():
    assert calcular_crc32(b"abc") != calcular_crc32(b"abd")


def test_verificar_detecta_corrupcao():
    # Arrange - envelope com payload adulterado apos selagem
    from dataclasses import replace

    env = selar("V1", b"payload-original")
    corrompido = replace(env, payload=b"payload-adulterado")
    # Act / Assert
    assert not corrompido.valido()
    with pytest.raises(ValueError, match="checksum invalido"):
        verificar(corrompido)


def test_selar_exige_partition_key():
    with pytest.raises(ValueError, match="partition_key"):
        selar("", b"x")
