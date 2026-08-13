# Cloud Run deployment for CareMatch API
# Stateless FastAPI backend with Postgres (Supabase) persistence

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API source
COPY api/ .

# Cloud Run sets PORT env var (default 8080)
# App must listen on 0.0.0.0 to accept external traffic
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
