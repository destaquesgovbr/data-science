FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential gcc \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock README.md ./

RUN poetry config virtualenvs.create false
RUN poetry install --no-root --no-interaction --no-ansi --without dev,docs

COPY src/ src/
COPY source/ source/
RUN poetry install --no-interaction --no-ansi --without dev,docs

COPY docker/canonicalization-job/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Cloud Run Job: long-running, resumível, sem porta HTTP. O shim parseia
# AWS_BEDROCK_CONNECTION_URI → AWS_ACCESS_KEY_ID/SECRET/DEFAULT_REGION e então
# `exec`uta o CLI de canonicalização, repassando os args do Job ("$@").
ENTRYPOINT ["/app/entrypoint.sh"]
