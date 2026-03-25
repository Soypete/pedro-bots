FROM python:3.12-slim

WORKDIR /app

# Install all PyPI deps from pyproject.toml
COPY pyproject.toml ./
COPY local-packages/ ./local-packages/

RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir ./local-packages/middleware_py-*.whl

# Copy source
COPY src/ /app/src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "main"]
