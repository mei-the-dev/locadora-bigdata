# ============================================================================
# ai/mlops/train_score.py - [OPCIONAL] manutencao preditiva + MLOps.
# Featuriza sobre Fato_Telemetria_Diaria (Gold), gera o rotulo de risco via
# fleetlib.scoring.probabilidade_falha, treina um classificador (sklearn) e
# registra metricas/modelo no MLflow (se disponivel). Demonstra o pipeline de ML
# como DataFrame/feature -> modelo -> registro (Armbrust 2015; ementa III).
# Uso: python train_score.py
# ============================================================================
"""Treino de modelo de risco de manutenção (featurização sobre a Gold)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fleetlib.scoring import FeaturesConducao, probabilidade_falha  # noqa: E402

_SQL_FEATURES = """
SELECT v.id_veiculo_origem AS vehicle_id, t.km_rodados, t.velocidade_media,
       t.velocidade_maxima, t.num_eventos_conducao_brusca AS bruscos,
       t.consumo_medio_bateria AS consumo, t.score_conducao
FROM Fato_Telemetria_Diaria t
JOIN Dim_Veiculo v ON v.sk_veiculo = t.sk_veiculo
"""


def montar_dataset(linhas: list[dict], horas_desde_manut: float = 4000.0) -> tuple[list[list[float]], list[int]]:
    """Transforma linhas da Gold em (X, y). Rotulo = risco alto (prob>0.5).

    Funcao PURA (testavel): usa fleetlib.scoring.probabilidade_falha como
    ground-truth heuristico do rotulo binario.
    """
    X: list[list[float]] = []
    y: list[int] = []
    for r in linhas:
        feats = FeaturesConducao(
            km_rodados=float(r["km_rodados"] or 0),
            velocidade_media=float(r["velocidade_media"] or 0),
            velocidade_maxima=float(r["velocidade_maxima"] or 0),
            eventos_bruscos=int(r["bruscos"] or 0),
            consumo_bateria_pct=float(r["consumo"] or 0),
        )
        X.append([feats.km_rodados, feats.velocidade_maxima, float(feats.eventos_bruscos), feats.consumo_bateria_pct])
        prob = probabilidade_falha(feats, horas_desde_manut)
        y.append(1 if prob > 0.5 else 0)
    return X, y


def treinar() -> dict:
    """Le a Gold, treina o classificador e registra no MLflow (se disponivel)."""
    from app.common import db

    linhas = db.consultar(_SQL_FEATURES)
    if len(linhas) < 4:
        print("[MLOPS] dados insuficientes; rode a ELT (make elt) primeiro.", flush=True)
        return {"treinado": False, "n": len(linhas)}

    X, y = montar_dataset(linhas)
    metricas = _treinar_sklearn(X, y)
    _log_mlflow(metricas)
    print(f"[MLOPS] modelo treinado. metricas={metricas}", flush=True)
    return {"treinado": True, "n": len(linhas), **metricas}


def _treinar_sklearn(X: list[list[float]], y: list[int]) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score

    if len(set(y)) < 2:  # rotulo constante -> baseline trivial
        return {"acuracia": 1.0, "classes": len(set(y)), "baseline": True}
    modelo = LogisticRegression(max_iter=500).fit(X, y)
    acc = accuracy_score(y, modelo.predict(X))
    return {"acuracia": round(float(acc), 4), "classes": len(set(y)), "baseline": False}


def _log_mlflow(metricas: dict) -> None:
    try:
        import mlflow  # lazy/opcional

        mlflow.set_tracking_uri(os.getenv("MLFLOW_URI", "http://mlflow:5000"))
        mlflow.set_experiment("frota-manutencao-preditiva")
        with mlflow.start_run():
            for k, v in metricas.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v))
    except Exception:  # noqa: BLE001 - MLflow e opcional (perfil full)
        pass


if __name__ == "__main__":
    treinar()
