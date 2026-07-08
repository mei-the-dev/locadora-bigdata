# ============================================================================
# MLflow (perfil full) - registro de modelos da manutencao preditiva.
# Backend SQLite + artefatos locais (leve, cabe no bonus de 16 GB).
# ============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /mlflow

RUN pip install --no-cache-dir mlflow==2.15.1

EXPOSE 5000

CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 \
     --backend-store-uri ${BACKEND_URI:-sqlite:////mlflow/mlflow.db} \
     --default-artifact-root ${ARTIFACT_ROOT:-/mlflow/artifacts}"]
