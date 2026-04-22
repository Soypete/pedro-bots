FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY local-packages/pedro_agentware /app/pedro_agentware

RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -e /app/pedro_agentware

COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "main"]