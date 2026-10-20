#!/bin/sh
# Entrypoint do Cloud Run Job de backfill do acervo (NER e re-enriquecimento).
#
# 1. Escolhe o script pela env BACKFILL_SCRIPT (allowlist fechada):
#      ausente ou vazia / backfill_ner_corpus.py -> scripts/backfill_ner_corpus.py
#        (default: o DAG `ner_backfill` não passa a env e segue igual)
#      reenrich_combined_window.py -> scripts/reenrich_combined_window.py
#        (DAG `enrichment_backfill`, por container override de env)
#    Qualquer outro valor (inclusive caminhos) sai com 64 (EX_USAGE) ANTES de
#    executar qualquer coisa.
# 2. Parseia AWS_BEDROCK_CONNECTION_URI (formato Airflow:
#      aws://ACCESS_KEY:SECRET_KEY@/?region_name=us-east-1
#    ) exportando AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
#    discretos (boto3 os lê do ambiente). Igual para os dois scripts.
# 3. `exec`uta o script escolhido repassando os args do Job ("$@", ex.:
#    --limit/--order/--workers no NER; --select/--date-from/--date-to/--limit/
#    --workers no re-enriquecimento).
#
# Se as creds discretas já vierem no ambiente (AWS_ACCESS_KEY_ID + SECRET), não
# sobrescreve. Usa Python (sempre presente na imagem) para URL-decode robusto.
set -e

case "${BACKFILL_SCRIPT:-}" in
    ""|backfill_ner_corpus.py)
        SCRIPT=scripts/backfill_ner_corpus.py ;;
    reenrich_combined_window.py)
        SCRIPT=scripts/reenrich_combined_window.py ;;
    *)
        printf 'ERRO: BACKFILL_SCRIPT inválido: "%s" (permitidos: backfill_ner_corpus.py [default], reenrich_combined_window.py)\n' \
            "$BACKFILL_SCRIPT" >&2
        exit 64 ;;
esac

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

exec "$PYBIN" "$SCRIPT" "$@"
