# CareMatch API. Build context is the carematch/ PARENT directory so the
# sibling reasoning_engine/ package ships in the same image, preserving the
# relative structure api/main.py depends on (sys.path.insert to
# ../reasoning_engine). Zero code changes needed.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt /tmp/api-requirements.txt
COPY reasoning_engine/requirements.txt /tmp/reasoning-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/reasoning-requirements.txt

COPY api /app/api
COPY reasoning_engine /app/reasoning_engine

# main.py computes REASONING_ENGINE_PATH from __file__'s parent.parent, so
# running from /app/api resolves it to /app/reasoning_engine.
WORKDIR /app/api

# "real" is the image default so a bare `docker run` (no compose override)
# can never silently land in free testing mode.
ENV LLM_MODE=real
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
