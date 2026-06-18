#!/bin/sh
# Entrypoint do Cloud Run Job de canonicalização.
#
# Parseia AWS_BEDROCK_CONNECTION_URI (formato Airflow:
#   aws://ACCESS_KEY:SECRET_KEY@/?region_name=us-east-1
# ) exportando AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
# discretos (boto3 os lê do ambiente), e então `exec`uta o CLI da canonicalização
# repassando os args do Job ("$@", ex.: --since/--limit).
#
# Se as creds discretas já vierem no ambiente (AWS_ACCESS_KEY_ID + SECRET), não
# sobrescreve. Usa Python (sempre presente na imagem) para URL-decode robusto.
set -e

# Resolve o interpretador (a imagem tem `python`; host de teste pode ter só `python3`).
if command -v python >/dev/null 2>&1; then PYBIN=python; else PYBIN=python3; fi

if [ -n "$AWS_BEDROCK_CONNECTION_URI" ] && \
   { [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; }; then
    eval "$("$PYBIN" - <<'PYEOF'
import os
from urllib.parse import parse_qs, unquote, urlparse


def _sh_quote(v: str) -> str:
    return "'" + v.replace("'", "'\\''") + "'"


uri = os.environ.get("AWS_BEDROCK_CONNECTION_URI", "")
parsed = urlparse(uri)
access = unquote(parsed.username) if parsed.username else ""
secret = unquote(parsed.password) if parsed.password else ""
qs = parse_qs(parsed.query)
region = qs.get("region_name", [os.environ.get("AWS_DEFAULT_REGION", "us-east-1")])[0]
if access:
    print(f"export AWS_ACCESS_KEY_ID={_sh_quote(access)}")
if secret:
    print(f"export AWS_SECRET_ACCESS_KEY={_sh_quote(secret)}")
if region:
    print(f"export AWS_DEFAULT_REGION={_sh_quote(region)}")
PYEOF
)"
fi

exec "$PYBIN" -m news_enrichment.canonicalization_job "$@"
