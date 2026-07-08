# ============================================================================
# batch/spark/jobs/lgpd_delete.py - Fase 9 (LGPD / direito ao esquecimento).
# DELETE transacional no Delta (Silver/Bronze) por vehicle_id ou por cliente -
# o registro some do object store apos o DELETE (MERGE/DELETE do Delta -
# Armbrust 2020). Complementa a mascara de PII na Gold (warehouse/lgpd.sql) e a
# retencao por TTL no Cassandra. Camera 360 + geo sao dados sensiveis.
# Uso: spark-submit lgpd_delete.py --vehicle-id VEH-003
# ============================================================================
"""Direito ao esquecimento: DELETE transacional no Delta (LGPD)."""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "/opt/fleet/spark")
sys.path.insert(0, "/opt/fleet")

from common import paths  # noqa: E402
from common.session import build_spark  # noqa: E402


def esquecer_veiculo(spark, vehicle_id: str) -> None:
    """Apaga toda a telemetria de um veiculo do Silver e do Bronze (Delta DELETE)."""
    from delta.tables import DeltaTable

    for dataset in ("telemetria",):
        for zona, caminho in (("silver", paths.silver(dataset)), ("bronze", paths.bronze(dataset))):
            if DeltaTable.isDeltaTable(spark, caminho):
                dt = DeltaTable.forPath(spark, caminho)
                antes = dt.toDF().where(f"vehicle_id = '{vehicle_id}'").count()
                dt.delete(f"vehicle_id = '{vehicle_id}'")
                print(f"[LGPD] {zona}/{dataset}: {antes} linhas apagadas de {vehicle_id}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vehicle-id", required=True)
    args = ap.parse_args()

    spark = build_spark("fleet-lgpd-delete")
    esquecer_veiculo(spark, args.vehicle_id)
    print(f"[LGPD] direito ao esquecimento aplicado a {args.vehicle_id} "
          f"(DESCRIBE HISTORY mostra a versao do DELETE).", flush=True)
    spark.stop()


if __name__ == "__main__":
    main()
