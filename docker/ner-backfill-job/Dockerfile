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
COPY scripts/ scripts/
RUN poetry install --no-interaction --no-ansi --without dev,docs

COPY docker/ner-backfill-job/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Cloud Run Job: long-running, resumível, sem porta HTTP. O shim escolhe o script
# pela env BACKFILL_SCRIPT (ausente → scripts/backfill_ner_corpus.py;
# reenrich_combined_window.py → re-enriquecimento; outro valor → exit 64), parseia
# AWS_BEDROCK_CONNECTION_URI → AWS_ACCESS_KEY_ID/SECRET/DEFAULT_REGION e então
# `exec`uta o script, repassando os args do Job ("$@").
ENTRYPOINT ["/app/entrypoint.sh"]
