# ============================================================================
# Ponte MQTT -> Kafka (Camada 1). Build context = raiz `sistema/` (copia fleetlib).
# ============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY ingestion/bridge/requirements.txt /app/ingestion/bridge/requirements.txt
RUN pip install --no-cache-dir -r /app/ingestion/bridge/requirements.txt

COPY fleetlib /app/fleetlib
COPY ingestion/bridge /app/ingestion/bridge

CMD ["python", "/app/ingestion/bridge/mqtt_to_kafka.py"]
