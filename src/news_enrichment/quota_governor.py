"""
Governador de cota de tokens do Bedrock (ledger account-wide por modelo).

Peça central da orquestração do backfill: os jobs se auto-limitam a uma fração
(default 80%) da cota diária de tokens de cada modelo, deixando o restante para o
worker ao vivo. Todos os chamadores (jobs + worker) gravam o consumo no ledger
Postgres `llm_daily_usage`; só os JOBS leem o ledger para decidir parar.

Contrato fixo (NÃO alterar — espelha a migração 023 do data-platform):
    llm_daily_usage(
        day DATE,
        model_id TEXT,
        input_tokens BIGINT NOT NULL DEFAULT 0,
        output_tokens BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY (day, model_id)
    )

Princípios:
  - `record_usage` é RESILIENTE: qualquer falha de DB é logada e NÃO levanta — a
    contabilidade nunca pode derrubar o pipeline.
  - `tokens_used_today` em falha → 0 (conservador: não bloqueia por erro de leitura).
  - `budget_exhausted` sem cota definida (None/<=0) → False (modo sem-teto).
  - Funções puras/testáveis: a conexão é injetada; nenhum I/O implícito.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_QUOTA_FRACTION = 0.8

# UPSERT atômico no ledger (ON CONFLICT ... += EXCLUDED). Tolerante a corrida:
# dois processos podem somar concorrentemente sem perder contagem.
_RECORD_SQL = """
INSERT INTO llm_daily_usage (day, model_id, input_tokens, output_tokens)
VALUES (CURRENT_DATE, %s, %s, %s)
ON CONFLICT (day, model_id) DO UPDATE SET
    input_tokens = llm_daily_usage.input_tokens + EXCLUDED.input_tokens,
    output_tokens = llm_daily_usage.output_tokens + EXCLUDED.output_tokens
"""

_USED_TODAY_SQL = """
SELECT COALESCE(SUM(input_tokens + output_tokens), 0)
FROM llm_daily_usage
WHERE day = CURRENT_DATE AND model_id = %s
"""


def record_usage(
    conn,
    model_id: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
) -> None:
    """Acumula tokens no ledger do dia para o modelo (UPSERT atômico).

    RESILIENTE: nunca levanta — falha de DB é logada e ignorada. A contabilidade
    de tokens jamais deve derrubar o pipeline de enriquecimento.

    Args:
        conn: conexão psycopg2 (ou compatível). None → no-op defensivo.
        model_id: id do modelo Bedrock (ex.: us.anthropic.claude-sonnet-4-6).
        input_tokens: tokens de entrada da chamada (None → 0).
        output_tokens: tokens de saída da chamada (None → 0).
    """
    if conn is None or not model_id:
        return
    in_tok = int(input_tokens or 0)
    out_tok = int(output_tokens or 0)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(_RECORD_SQL, (model_id, in_tok, out_tok))
            conn.commit()
        finally:
            cursor.close()
    except Exception as e:  # noqa: BLE001 — contabilidade nunca derruba o pipeline
        logger.warning("record_usage falhou para modelo %s: %s", model_id, e)
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass


def tokens_used_today(conn, model_id: str) -> int:
    """SUM(input+output) consumido HOJE (account-wide) para o modelo.

    Em falha de leitura → 0 (conservador: não bloqueia o pipeline por erro de DB;
    a margem da fração + retry diário absorvem qualquer subcontagem transitória).
    """
    if conn is None or not model_id:
        return 0
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(_USED_TODAY_SQL, (model_id,))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            cursor.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("tokens_used_today falhou para modelo %s: %s", model_id, e)
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return 0


def budget_exhausted(
    conn,
    model_id: str,
    daily_quota: Optional[int],
    fraction: float = DEFAULT_QUOTA_FRACTION,
) -> bool:
    """True se o consumo do dia atingiu `fraction × daily_quota` para o modelo.

    Sem cota definida (None ou <= 0) → False (modo sem-teto). É o callsite que
    deve logar o warning de "sem cota" — esta função apenas decide.

    Args:
        conn: conexão psycopg2.
        model_id: id do modelo Bedrock.
        daily_quota: cota diária de tokens (input+output) do modelo; None → sem-teto.
        fraction: fração da cota reservada ao backfill (default 0.8).
    """
    if not daily_quota or daily_quota <= 0:
        return False
    used = tokens_used_today(conn, model_id)
    ceiling = fraction * daily_quota
    exhausted = used >= ceiling
    if exhausted:
        logger.info(
            "budget exhausted para %s: usado=%d >= teto=%.0f (cota=%d × fração=%.2f)",
            model_id,
            used,
            ceiling,
            daily_quota,
            fraction,
        )
    return exhausted


def parse_daily_quota_env() -> dict:
    """Lê a config de cota das envs do job.

    Envs:
      - BEDROCK_DAILY_TOKEN_QUOTA: JSON {model_id: tokens_por_dia}. Malformado/ausente
        → {} (modo sem-teto para todos os modelos).
      - BACKFILL_QUOTA_FRACTION: float (default 0.8). Malformado → default.

    Returns:
        {"quota": {model_id: int}, "fraction": float}
    """
    quota: dict = {}
    raw = os.environ.get("BEDROCK_DAILY_TOKEN_QUOTA", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    try:
                        quota[str(k)] = int(v)
                    except (TypeError, ValueError):
                        logger.warning("cota inválida para %r: %r (ignorada)", k, v)
            else:
                logger.warning("BEDROCK_DAILY_TOKEN_QUOTA não é um objeto JSON")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("BEDROCK_DAILY_TOKEN_QUOTA malformado: %s", e)

    fraction = DEFAULT_QUOTA_FRACTION
    raw_frac = os.environ.get("BACKFILL_QUOTA_FRACTION", "").strip()
    if raw_frac:
        try:
            fraction = float(raw_frac)
        except (TypeError, ValueError):
            logger.warning(
                "BACKFILL_QUOTA_FRACTION malformado: %r (usando %.2f)",
                raw_frac,
                DEFAULT_QUOTA_FRACTION,
            )

    return {"quota": quota, "fraction": fraction}
