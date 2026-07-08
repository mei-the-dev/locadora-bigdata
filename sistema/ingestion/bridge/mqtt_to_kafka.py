# ============================================================================
# ingestion/bridge/mqtt_to_kafka.py - ponte da Camada 1.
# Consome do MQTT (Mosquitto), VALIDA o checksum CRC32 do envelope (R2 sem perda
# - Ghemawat 2003) e PRODUZ para o Kafka/Redpanda com key = vehicle_id, o que
# garante ordem estrita intra-particao (R1 - Kreps 2011). acks=all torna a
# escrita duravel; contadores produzido/consumido evidenciam a ausencia de perda.
# ============================================================================
"""Ponte MQTT -> Kafka: valida checksum e reparticiona por vehicle_id."""

from __future__ import annotations

import os
import signal
import struct
import sys

import paho.mqtt.client as mqtt
from confluent_kafka import Producer

from fleetlib import checksum

# Mapa topico-base MQTT -> topico Kafka (topicos isolados por tipo de evento).
_MQTT_TEL = os.getenv("MQTT_TOPIC_TELEMETRIA", "frota/telemetria")
_MQTT_EMG = os.getenv("MQTT_TOPIC_EMERGENCIA", "frota/emergencia")
_MQTT_TRIP = os.getenv("MQTT_TOPIC_VIAGEM", "frota/viagem")
_MAPA_KAFKA = {
    _MQTT_TEL: os.getenv("KAFKA_TOPIC_TELEMETRIA", "telemetry"),
    _MQTT_EMG: os.getenv("KAFKA_TOPIC_EMERGENCIA", "emergency"),
    _MQTT_TRIP: os.getenv("KAFKA_TOPIC_VIAGEM", "trip"),
}
_KAFKA_BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
_MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
_MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))


class Ponte:
    """Encapsula o estado da ponte (produtor Kafka + contadores)."""

    def __init__(self) -> None:
        self.producer = Producer(
            {
                "bootstrap.servers": _KAFKA_BROKER,
                "acks": "all",  # durabilidade (R2)
                "enable.idempotence": True,  # evita duplicatas do produtor
                "linger.ms": 20,  # batch amortiza RPC (Kreps 2011)
                "compression.type": "lz4",
            }
        )
        self.recebidos = 0
        self.produzidos = 0
        self.descartados = 0

    def _topico_kafka(self, topico_mqtt: str) -> tuple[str, str] | None:
        """Resolve (topico_kafka, vehicle_id) a partir do topico MQTT recebido."""
        for base, kafka_topic in _MAPA_KAFKA.items():
            if topico_mqtt.startswith(base + "/"):
                vehicle_id = topico_mqtt[len(base) + 1 :]
                return kafka_topic, vehicle_id
        return None

    def on_message(self, _client, _userdata, msg) -> None:
        """Callback MQTT: valida checksum e produz para o Kafka."""
        self.recebidos += 1
        destino = self._topico_kafka(msg.topic)
        if destino is None or len(msg.payload) < 4:
            self.descartados += 1
            return
        kafka_topic, vehicle_id = destino

        crc = struct.unpack(">I", msg.payload[:4])[0]
        avro_bytes = msg.payload[4:]
        envelope = checksum.Envelope(partition_key=vehicle_id, payload=avro_bytes, crc32=crc)
        try:
            checksum.verificar(envelope)  # fail-fast se corrompido
        except ValueError as exc:
            self.descartados += 1
            print(f"[BRIDGE] descartado (checksum): {exc}", file=sys.stderr, flush=True)
            return

        # key = vehicle_id -> particao Kafka (ordem estrita intra-particao, R1)
        self.producer.produce(kafka_topic, key=vehicle_id.encode(), value=avro_bytes,
                              on_delivery=self._entregue)
        self.producer.poll(0)

    def _entregue(self, err, _msg) -> None:
        if err is None:
            self.produzidos += 1
        else:
            self.descartados += 1
            print(f"[BRIDGE] falha de entrega Kafka: {err}", file=sys.stderr, flush=True)

    def rodar(self) -> None:
        client = mqtt.Client(client_id="fleet-mqtt-bridge")
        client.on_message = self.on_message
        client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=30)
        for base in _MAPA_KAFKA:
            client.subscribe(f"{base}/#", qos=1)
        print(f"[BRIDGE] MQTT {_MQTT_HOST}:{_MQTT_PORT} -> Kafka {_KAFKA_BROKER}", flush=True)

        parar = {"flag": False}

        def _sig(_s, _f):
            parar["flag"] = True

        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)

        client.loop_start()
        try:
            import time

            while not parar["flag"]:
                time.sleep(5)
                self.producer.poll(0)
                print(f"[BRIDGE] recebidos={self.recebidos} produzidos={self.produzidos} "
                      f"descartados={self.descartados}", flush=True)
        finally:
            self.producer.flush(10)
            client.loop_stop()
            client.disconnect()
            print(f"[BRIDGE] final: recebidos={self.recebidos} produzidos={self.produzidos} "
                  f"descartados={self.descartados}", flush=True)


if __name__ == "__main__":
    Ponte().rodar()
