FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/app.py ./app.py

RUN useradd --create-home --uid 1000 carematch-ui && \
    mkdir -p /home/carematch-ui/.streamlit && \
    chown -R carematch-ui:carematch-ui /app /home/carematch-ui

USER carematch-ui

# Create Streamlit config
RUN printf '[client]\nmaxCacheMessageSize = 200\n[server]\nheadless = true\nrunOnSave = false\nenableXsrfProtection = false\n[browser]\ngatherUsageStats = false\n' > /home/carematch-ui/.streamlit/config.toml

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
