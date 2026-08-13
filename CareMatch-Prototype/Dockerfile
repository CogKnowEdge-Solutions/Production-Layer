# Cloud Run deployment for CareMatch API
# Stateless FastAPI backend with Postgres (Supabase) persistence.
# Build context is the CareMatch-Prototype/ directory.
FROM python:3.12-slim

WORKDIR /app/api

# Install BOTH requirement files. main.py imports engine, protocol, schema,
# llm_client, and guardrails from the sibling reasoning_engine/ package via
# a sys.path.insert of __file__.parent.parent / reasoning_engine -- so that
# source tree AND its dependencies must ship in this image, or the app
# crashes on startup with an ImportError.
COPY api/requirements.txt /tmp/api-requirements.txt
COPY reasoning_engine/requirements.txt /tmp/reasoning-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/reasoning-requirements.txt

COPY api /app/api
COPY reasoning_engine /app/reasoning_engine

# Cloud Run sets PORT env var (default 8080)
# App must listen on 0.0.0.0 to accept external traffic
EXPOSE 8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
