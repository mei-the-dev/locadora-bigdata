# ============================================================================
# Dashboard Streamlit + camada de aplicacao (cobranca, dossie, concierge,
# refresh de serving). Build context = raiz `sistema/` (copia fleetlib/app/ai).
# ============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# libpq p/ psycopg2-binary ja vem no wheel; build-essential nao necessario.
COPY app/dashboard/requirements.txt /app/app/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/app/dashboard/requirements.txt

COPY fleetlib /app/fleetlib
COPY app /app/app
COPY ai /app/ai

EXPOSE 8501

CMD ["streamlit", "run", "/app/app/dashboard/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
