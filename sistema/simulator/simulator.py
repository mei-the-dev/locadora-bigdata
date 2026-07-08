# ============================================================================
# simulator/simulator.py - Camada 0 (Borda). Simula a frota autonoma:
#  - gera leituras cruas por veiculo (fleet_model)
#  - PRE-AGREGA na borda (combiner - fleetlib.edge) a cada FLEET_EDGE_WINDOW
#    leituras -> reduz banda (R3)
#  - serializa em Avro (fleetlib.avro_io) e sela com checksum CRC32
#    (fleetlib.checksum, R2) num envelope
#  - publica no MQTT (Mosquitto) em topico por vehicle_id (ordem estrita R1)
#  - injeta cenarios: emergencia (colisao/bateria critica) e viagem/
#    reposicionamento do veiculo vazio.
# Determinismo por FLEET_SEED (reprodutibilidade / idempotencia a jusante).
# ============================================================================
"""Simulador de frota autonoma conectada (Avro + combiner de borda -> MQTT)."""

from __future__ import annotations

import random
import struct
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from fleetlib import avro_io, checksum
from fleetlib.domain import EMPRESAS, PATIOS
from fleetlib.edge import combinar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SimConfig, carregar  # noqa: E402
from fleet_model import (  # noqa: E402
    EstadoVeiculo,
    destino_reposicionamento,
    estado_inicial,
    passo,
    precisa_reposicionar,
)

_SCHEMAS = Path(__file__).resolve().parent / "schemas"


def _agora_ms() -> int:
    return int(time.time() * 1000)


def montar_veiculos(cfg: SimConfig, rng: random.Random) -> list[EstadoVeiculo]:
    """Cria N veiculos VEH-001.. distribuidos entre as 6 empresas/patios.

    A distribuicao espelha o seed do Gold/Mongo (VEH-i -> empresa i%6, patio i%6).
    """
    veiculos = []
    for i in range(cfg.num_veiculos):
        empresa = EMPRESAS[i % len(EMPRESAS)].nome
        patio = PATIOS[i % len(PATIOS)]
        vid = f"VEH-{i + 1:03d}"
        veiculos.append(estado_inicial(vid, empresa, patio, rng))
    return veiculos


class Simulador:
    """Orquestra o loop de simulacao e a publicacao MQTT."""

    def __init__(self, cfg: SimConfig) -> None:
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.veiculos = montar_veiculos(cfg, self.rng)
        self.buffers: dict[str, list] = {v.vehicle_id: [] for v in self.veiculos}
        self.sch_tel = avro_io.carregar_schema(_SCHEMAS / "telemetry.avsc")
        self.sch_emg = avro_io.carregar_schema(_SCHEMAS / "emergency.avsc")
        self.sch_trip = avro_io.carregar_schema(_SCHEMAS / "trip.avsc")
        self.client = mqtt.Client(client_id="fleet-simulator")
        self._seq = 0

    # -- publicacao ---------------------------------------------------------
    def _publicar(self, topico_base: str, vehicle_id: str, schema: dict, registro: dict) -> None:
        """Publica um registro Avro selado (crc32 + avro) em topico/<vehicle_id>."""
        blob = avro_io.encode(schema, registro)
        crc = checksum.calcular_crc32(blob)
        envelope = struct.pack(">I", crc) + blob  # 4 bytes crc32 + payload avro
        self.client.publish(f"{topico_base}/{vehicle_id}", envelope, qos=1)

    # -- geracao de eventos -------------------------------------------------
    def _emitir_telemetria(self, estado: EstadoVeiculo) -> None:
        pacote = combinar(self.buffers[estado.vehicle_id])
        registro = pacote.as_dict()
        registro["empresa"] = estado.empresa
        registro["patio_base"] = estado.patio.nome
        self._publicar(self.cfg.topico_telemetria, estado.vehicle_id, self.sch_tel, registro)
        self.buffers[estado.vehicle_id] = []

    def _emitir_emergencia(self, estado: EstadoVeiculo) -> None:
        self._seq += 1
        critica = estado.bateria <= 15.0
        categoria = "Bateria_Critica" if critica else self.rng.choice(["Colisao", "Pane", "Violacao"])
        severidade = 5 if categoria == "Colisao" else (4 if critica else self.rng.randint(2, 3))
        registro = {
            "vehicle_id": estado.vehicle_id, "empresa": estado.empresa, "event_ts": _agora_ms(),
            "id_ocorrencia": f"OCC-{self._seq:06d}", "categoria": categoria, "severidade": severidade,
            "lat": estado.lat, "lon": estado.lon, "bateria": estado.bateria,
            "id_sensor": None, "detalhe": f"Cenario injetado: {categoria}",
        }
        self._publicar(self.cfg.topico_emergencia, estado.vehicle_id, self.sch_emg, registro)
        print(f"[EMERGENCIA] {estado.vehicle_id} {categoria} sev={severidade}", flush=True)

    def _emitir_viagem_vazia(self, estado: EstadoVeiculo) -> EstadoVeiculo:
        self._seq += 1
        destino = destino_reposicionamento(estado, self.rng)
        registro = {
            "vehicle_id": estado.vehicle_id, "empresa": estado.empresa, "event_ts": _agora_ms(),
            "id_viagem": f"TRIP-{self._seq:06d}", "patio_origem": estado.patio.nome,
            "patio_destino": destino.nome, "vazio": True, "motivo": "Reposicionamento",
            "distancia_km": 0.0,
        }
        self._publicar(self.cfg.topico_viagem, estado.vehicle_id, self.sch_trip, registro)
        print(f"[VIAGEM VAZIA] {estado.vehicle_id} {estado.patio.nome}->{destino.nome}", flush=True)
        # reposiciona e recarrega (volta sozinho ao patio)
        from dataclasses import replace

        return replace(estado, patio_base=destino.id, bateria=100.0, autonomia_km=320.0,
                       lat=destino.lat, lon=destino.lon)

    # -- loop ---------------------------------------------------------------
    def rodar(self) -> None:
        self.client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=30)
        self.client.loop_start()
        print(f"Simulador: {len(self.veiculos)} veiculos, seed={self.cfg.seed}, "
              f"janela={self.cfg.edge_window}, broker={self.cfg.mqtt_host}", flush=True)
        try:
            while True:
                base_ts = _agora_ms()
                for idx, estado in enumerate(self.veiculos):
                    # desordem controlada: jitter no event_ts (exercita watermarks)
                    jitter = self.rng.randint(0, self.cfg.desordem_max_ms)
                    ts = base_ts - jitter
                    novo, leitura = passo(estado, ts, self.rng)
                    self.buffers[novo.vehicle_id].append(leitura)

                    # combiner: fecha a janela e emite pacote agregado
                    if len(self.buffers[novo.vehicle_id]) >= self.cfg.edge_window:
                        self._emitir_telemetria(novo)

                    # cenarios injetaveis
                    if self.rng.random() < self.cfg.prob_emergencia:
                        self._emitir_emergencia(novo)
                    if precisa_reposicionar(novo):
                        novo = self._emitir_viagem_vazia(novo)

                    self.veiculos[idx] = novo
                time.sleep(self.cfg.emit_interval_s)
        except KeyboardInterrupt:
            print("Simulador encerrado.", flush=True)
        finally:
            self.client.loop_stop()
            self.client.disconnect()


def main() -> None:
    Simulador(carregar()).rodar()


if __name__ == "__main__":
    main()
