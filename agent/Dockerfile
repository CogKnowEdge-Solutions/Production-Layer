FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent

EXPOSE 8100

CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8100"]
