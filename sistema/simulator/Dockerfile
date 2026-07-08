# ============================================================================
# Simulador de frota - Camada 0 (Edge). Build context = raiz `sistema/` para
# copiar a fleetlib (nucleo puro) junto do codigo do simulador.
# ============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY simulator/requirements.txt /app/simulator/requirements.txt
RUN pip install --no-cache-dir -r /app/simulator/requirements.txt

COPY fleetlib /app/fleetlib
COPY simulator /app/simulator

CMD ["python", "/app/simulator/simulator.py"]
