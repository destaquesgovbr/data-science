#!/usr/bin/env python3
"""
Re-enriquecimento da chamada COMBINADA (tema + resumo + sentimento) numa janela
de datas, SEM NER e SEM publicar evento. Fase 2.5 (DS-1).

Backfills:
  - B2: `--select null-theme --date-from 2026-09-25 --date-to 2026-10-06`:
    artigos que ficaram sem tema quando o Claude 3 Haiku teve EOL no Bedrock
    (25/09 até o INF-1/infra#215, aplicado em 06/10 00:19Z = 05/10 21:19 BRT).
  - B5 (decisão D3): `--select mock`: os ~4.600 artigos com summary '[MOCK]…'
    (tema também falso; ver issue #3).
  - DS-2: `--select null-summary --date-from 2026-06-01 --date-to <hoje BRT>`:
    os ~6.935 artigos com tema e summary NULL. O re-scrape do scraper
    (`_update_existing_articles`, desde o d406fee de 01/06) grava summary = NULL
    e content_embedding = NULL. Só depois do deploy do SC-1 (senão o re-scrape
    apaga de novo). Ver "Modo null-summary" abaixo. Antes do B3 (embeddings):
    uma última passada a partir do dia seguinte ao deploy do SC-1 e um --dry-run
    com selecionados=0 (trava na "Ordem operacional" do README do worker).

Fluxo por artigo (espelha o caminho de sucesso de handler.enrich_article, menos
o NER e o evento):
    result = classifier.classify_single(article)       # modelo = ENRICHMENT_MODEL_ID
    update_news_enrichment(db, [result], code_to_id)   # tema + resumo
    _upsert_ai_features(uid, {"sentiment": ...})       # NUNCA entities
    quota_governor.record_usage(...)                   # ledger por modelo

Garantias:
  - NUNCA chama extract_entities: não toca o pool do Sonnet e não sobrescreve
    entidades canonicalizadas (o merge `features || {...}` só leva `sentiment`).
  - NUNCA publica dgb.news.enriched: reenviar o evento para artigos antigos
    geraria push e federation de notícias velhas.
  - Governador de cota: para gracioso quando o consumo do dia do modelo
    (account-wide, ledger llm_daily_usage) bate `fração × cota`. Resumível: a
    seleção exclui o que já foi feito (tema gravado / summary sem [MOCK]).
    Use a cota REAL da AWS em BEDROCK_DAILY_TOKEN_QUOTA; a fração
    (BACKFILL_QUOTA_FRACTION, default 0.8) é aplicada aqui, uma única vez.
  - Modelo indisponível (EOL / id inexistente) aborta o run (código de saída 1).
  - Janela por dia BRT (America/Sao_Paulo); --date-to é EXCLUSIVO.
  - `null-theme` EXIGE --date-to, e ele não pode passar de hoje (BRT): sem teto,
    o ORDER BY published_at DESC pegaria primeiro artigos novos que o worker ao
    vivo ainda vai processar. Gravar o tema deles aqui (sem NER e sem publicar)
    faria o worker devolver `skipped` e o artigo ficaria sem dgb.news.enriched.
  - --dry-run só seleciona e lista: não chama o Bedrock nem escreve nada.

Modo null-summary (DS-2): só o resumo, com o prompt ENXUTO do
BedrockLLMClient.summarize_single (as regras de resumo da combinada, sem a
taxonomia: prompt de no máximo ~3 mil caracteres; a combinada manda ~18,9k
tokens de entrada). Por artigo:
    result = llm_client.summarize_single(article)       # modelo = ENRICHMENT_MODEL_ID
    UPDATE news SET summary = %s, updated_at = NOW()
     WHERE unique_id = %s AND summary IS NULL           # UPDATE_SUMMARY_SQL
    quota_governor.record_usage(...)                    # ledger por modelo
  - NUNCA regrava tema, NUNCA chama o NER, NUNCA publica, NUNCA grava
    news_features e NÃO toca content_embedding (o B3 gera depois, a partir do
    resumo).
  - Sentimento ausente em news_features NÃO é gerado aqui (fora do escopo): só
    é contado e reportado (sem_sentimento=N) na seleção e no resumo final.
  - Selecionados que JÁ têm content_embedding (feito sem o resumo, a partir do
    content) são contados e reportados (com_embedding=N) na seleção e no resumo
    final. O embedding deles não é tocado aqui, e o B3 (só content_embedding IS
    NULL) não o refaz: exigem um passo separado, aprovado, depois do DS-2 (ver o
    README do worker).
  - Resumo vazio/inválido não grava e conta `summary_failed`: o artigo segue
    selecionável no próximo run. Resumo gravado por outro processo no meio do
    run não é sobrescrito (guarda IS NULL → `summary_present`).
  - Mesma regra do null-theme para a janela: --date-to obrigatório, ≤ hoje BRT.

Modo --theme-only (DS-1, tema 26 "Defesa Civil e Gestão de Desastres"): a mesma
chamada combinada, mas grava SÓ os ids de tema. As seleções de tema implicam o modo
(--theme-only é opcional, aceito por compatibilidade) e a campanha da auditoria
`tema26-llm-d1` (--campaign aceita outra `tema26-llm-*`). Flags do contrato do DAG
enrichment_backfill (22/10): --select theme-code --theme-code <c> | --select
theme26-candidates, --date-from obrigatório, --date-to opcional, --limit, --workers,
[--dry-run] e, no theme26-candidates, --term-fields. Seleções:
  - `--select theme-code --theme-code <código>`: artigos com qualquer nível de tema
    (l1/l2/l3/mais específico) na subárvore do código. Escopo mínimo do plano:
    `--theme-code 19`.
  - `--select theme26-candidates`: L1 19, mais artigos em 04 / 05.02.01 / 15.02.03
    (--extra-codes) do MDR ou com termo-chave ("defesa civil", "calamidade",
    "situação de emergência", "estado de emergência", "desastre", com e sem acento:
    não há `unaccent` no banco). O termo é buscado só no TÍTULO por padrão;
    `--term-fields title-content` inclui o conteúdo (escopo da D1, decidido em 22/10:
    1.586 candidatos antes da 034). `--extra-codes ''` deixa só o bloco do 19.
Por artigo:
    old = ids de tema atuais (lidos ANTES da chamada)
    result = classifier.classify_single(article)        # modelo = ENRICHMENT_MODEL_ID
    chain = resolve_theme_chain(result, parents)         # cadeia coerente l1→l2→l3
    guarda do 26: artigo fora da subárvore do 19 só muda se chain.l1 == '26' (kept)
    numa transação:
      UPDATE news SET theme_* = novo WHERE unique_id = … AND theme_* IS NOT DISTINCT
        FROM old                                         # guarda: 0 linhas → theme_changed
      INSERT INTO news_theme_changes (campaign, unique_id, old_*_code, new_*_code,
        source = 'llm:<model_id>', note) ON CONFLICT (campaign, unique_id) DO UPDATE
        … WHERE reverted_at IS NOT NULL RETURNING 1     # sem linha → already_audited
    quota_governor.record_usage(...)
  - NUNCA grava resumo, sentimento (news_features), NER, content_embedding nem
    publica evento. O resumo e o sentimento da resposta são descartados.
  - Cadeia de tema: vale o código VÁLIDO (existente na taxonomia do banco) mais
    profundo da resposta ou do prefixo dela um nível acima, com l1/l2 derivados dele;
    ele pode estar no máximo MAX_LEVEL_DROP (1) nível acima do mais profundo que o
    LLM pediu. Ex.: pediu 26.01.09 (inexistente) → 26.01, mesmo sem o campo do L2;
    pediu 19.03.03 e só o 19 existe → resposta inválida (`invalid_theme`: não grava
    nem audita; o artigo volta no próximo run).
  - Guarda do tema 26: o artigo do bloco do 19 (algum dos 4 níveis na subárvore do
    19) sempre recebe a nova classificação. O de fora (04 / 05.02.01 / 15.02.03) só
    tem o tema gravado se o novo L1 for o 26; senão `kept`: sem UPDATE, audita
    old = new com a sugestão do LLM na note ("kept: o LLM sugeriu …").
  - Sem mudança (`unchanged`) e `kept`: sem UPDATE, mas audita (old = new), depois de
    conferir com SELECT … FOR UPDATE que o tema ainda é o lido.
  - Idempotência: todo artigo auditado na campanha e NÃO revertido sai da seleção (o
    run é idempotente e retomável, inclusive para os que continuam no 19 e os kept).
    O revertido pelo rollback da 034 (reverted_at) volta a ser candidato, e a nova
    gravação reaproveita a linha dele (UNIQUE (campaign, unique_id)). Um run
    concorrente que já auditou o artigo faz este desfazer o UPDATE (`already_audited`).
  - Preflight (também no --dry-run): a tabela news_theme_changes (migração 034 do
    data-platform) tem de existir com as 12 colunas do contrato (campaign, unique_id,
    os 8 códigos, source, changed_at) e UNIQUE (campaign, unique_id) sem predicado, e
    a campanha não pode ter registros de fonte que não seja `llm:*` (ex.: a campanha
    da própria 034). Colunas a mais são aceitas; note e reverted_at são usadas quando
    existem. Sem isso, o script sai com 1 e mensagem clara.
  - `theme26-candidates` exige 26/26.01/26.02 no banco e na taxonomia do classificador.
  - --date-to é opcional e sem teto: só entram artigos que JÁ têm tema, e o worker
    ao vivo devolve `skipped` para eles. Artigo que perdeu o tema no meio do run
    (`no_theme`) não é tocado.
  - Depois do run: sync do Typesense e MERGE do BigQuery a partir da auditoria.
  - Cache da taxonomia: este script lê a taxonomia do banco ao iniciar. O
    enrichment-worker também, mas UMA VEZ POR INSTÂNCIA e sem TTL: depois da 034 só
    uma revisão nova (redeploy, workflow_dispatch do "Deploy Enrichment Worker")
    limpa o cache das instâncias quentes. Ver o README do worker.

Env obrigatórias: DATABASE_URL, ENRICHMENT_MODEL_ID (sem fallback para o default
legado nem para BEDROCK_MODEL_ID), creds AWS (AWS_BEDROCK_CONNECTION_URI ou
AWS_ACCESS_KEY_ID/SECRET). Opcionais: BEDROCK_DAILY_TOKEN_QUOTA (JSON
{model_id: tokens/dia}), BACKFILL_QUOTA_FRACTION.

Uso (sempre --dry-run → --limit 10 → completo, cada etapa com OK):
    ENRICHMENT_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \\
    PYTHONPATH=src .venv/bin/python scripts/reenrich_combined_window.py \\
        --select null-theme --date-from 2026-09-25 --date-to 2026-10-06 \\
        [--limit 500] [--workers 1] [--dry-run]
    # DS-2 (depois do deploy do SC-1):
    ... --select null-summary --date-from 2026-06-01 --date-to <hoje BRT> [...]
    # DS-1 (D1, depois da 034 e do redeploy do worker; campanha tema26-llm-d1):
    ... --select theme26-candidates --term-fields title-content \\
        --date-from 2018-01-01 [--limit 10] [--workers 2] [--dry-run]
    ... --select theme-code --theme-code 19 --date-from 2018-01-01 [...]
"""
import argparse
import datetime
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from news_enrichment.enrichment_job import update_news_enrichment  # noqa: E402
from news_enrichment.llm_client import is_model_unavailable_error  # noqa: E402
from news_enrichment.quota_governor import (  # noqa: E402
    budget_exhausted,
    parse_daily_quota_env,
    record_usage,
)
from news_enrichment.worker import handler  # noqa: E402

SELECT_CHOICES = ("null-theme", "mock", "null-summary", "theme-code", "theme26-candidates")
# Seleções que disputam artigos com o worker ao vivo: exigem --date-to <= hoje BRT.
SELECTS_REQUIRING_DATE_TO = frozenset({"null-theme", "null-summary"})
# Seleções de tema (DS-1): só com --theme-only e --campaign; --date-to opcional.
THEME_SELECTS = frozenset({"theme-code", "theme26-candidates"})
# Janela de exemplo por seleção (mensagem de erro sem --date-to).
_EXAMPLE_WINDOW = {
    "null-theme": "no B2: --date-from 2026-09-25 --date-to 2026-10-06",
    "null-summary": "no DS-2: --date-from 2026-06-01 --date-to <hoje BRT>",
}
BRT = ZoneInfo("America/Sao_Paulo")
MOCK_SUMMARY_PATTERN = "[MOCK]%"
# Checa o budget a cada N artigos (tolera pequena ultrapassagem; margem ~fração).
BUDGET_CHECK_EVERY = 5
DRY_RUN_SAMPLE = 20
_ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0}

# Limites da janela: meia-noite do dia em BRT, convertida para timestamptz.
_BRT_DAY_START = "(%({param})s::date::timestamp AT TIME ZONE 'America/Sao_Paulo')"

# null-summary: grava SÓ o resumo, e só se ainda estiver NULL (não sobrescreve um
# resumo gravado no meio do run). Tema e content_embedding ficam intactos.
UPDATE_SUMMARY_SQL = """
    UPDATE news
    SET summary = %s, updated_at = NOW()
    WHERE unique_id = %s AND summary IS NULL
"""

# null-summary: quantos dos uids não têm sentimento em news_features (só reportado;
# este modo não gera sentimento).
MISSING_SENTIMENT_SQL = """
    SELECT COUNT(*)
    FROM news n
    LEFT JOIN news_features nf ON nf.unique_id = n.unique_id
    WHERE n.unique_id = ANY(%s)
      AND (nf.features -> 'sentiment' ->> 'label') IS NULL
"""

# null-summary: quantos dos uids JÁ têm content_embedding (feito sem o resumo, a
# partir do content). Só reportado: o embedding não é tocado aqui e o B3 só pega
# content_embedding IS NULL, então esses artigos exigem um passo separado.
WITH_EMBEDDING_SQL = """
    SELECT COUNT(*)
    FROM news n
    WHERE n.unique_id = ANY(%s)
      AND n.content_embedding IS NOT NULL
"""

# ---------------------------------------------------------------------------
# --theme-only (DS-1, tema 26)
# ---------------------------------------------------------------------------

THEME26_BASE_CODE = "19"
# Códigos que a migração 034 cria e que o theme26-candidates exige.
THEME26_TARGET_CODES = ("26", "26.01", "26.02")
# Bloco extra: só entra com MDR ou termo-chave. Configurável por --extra-codes.
DEFAULT_EXTRA_CODES = ("04", "05.02.01", "15.02.03")
THEME26_AGENCY_KEYS = ("mdr",)
# Sem `unaccent` no banco: as grafias sem acento entram também. ILIKE: sem caixa.
THEME26_TERMS = (
    "defesa civil",
    "calamidade",
    "situação de emergência",
    "situacao de emergencia",
    "estado de emergência",
    "estado de emergencia",
    "desastre",
)
# Onde procurar os termos. Padrão: só o título (no conteúdo, "calamidade" pega
# "calamidade fiscal" e "desastre" pega usos figurados; ~1,4x os candidatos).
TERM_FIELDS = {"title": ("n.title",), "title-content": ("n.title", "n.content")}
DEFAULT_TERM_FIELDS = "title"

# Regra da cadeia de tema: o código válido mais profundo pode estar no máximo este
# número de níveis acima do mais profundo que o LLM pediu (ver resolve_theme_chain).
MAX_LEVEL_DROP = 1

AUDIT_TABLE = "news_theme_changes"
# Contrato do plano (22/10), o da migração 034 do data-platform: o preflight exige estas
# 12 colunas; as demais da 034 (id, note, reverted_at) são aceitas e, quando existem,
# usadas (note na gravação; reverted_at na idempotência e no reaproveitamento da linha).
AUDIT_REQUIRED_COLUMNS = (
    "campaign",
    "unique_id",
    "old_l1_code",
    "old_l2_code",
    "old_l3_code",
    "old_most_specific_code",
    "new_l1_code",
    "new_l2_code",
    "new_l3_code",
    "new_most_specific_code",
    "source",
    "changed_at",
)
LLM_SOURCE_PREFIX = "llm:"
_AUDIT_CODE_COLUMNS = AUDIT_REQUIRED_COLUMNS[2:10]  # old_*_code, new_*_code

# Campanha da reclassificação por LLM (contrato de 22/10). As seleções de tema a usam
# por padrão; --campaign aceita outra tema26-llm-* (ex.: tema26-llm-d1b), porque o
# rollback da 034 e o MERGE do BigQuery só leem tema26-* e tema26-034/tema26-rollback
# são da própria migração. Até 50 caracteres (VARCHAR(50) na 034).
DEFAULT_THEME_CAMPAIGN = "tema26-llm-d1"
LLM_CAMPAIGN_PREFIX = "tema26-llm-"
_CODE_RE = re.compile(r"^\d{2}(?:\.\d{2}){0,2}$")
_CAMPAIGN_RE = re.compile(r"^tema26-llm-[a-z0-9][a-z0-9._-]{0,38}$")

# Guarda do tema 26: artigo fora da subárvore do 19 (em nenhum dos 4 níveis) só tem o
# tema gravado se o novo L1 for o 26; senão é auditado como 'kept' e mantém o tema.
THEME26_CODE = THEME26_TARGET_CODES[0]
NOTE_OK = "ok: reclassificado pelo LLM"
NOTE_UNCHANGED = "unchanged: o LLM manteve o tema"


@dataclass(frozen=True)
class AuditSchema:
    """Colunas opcionais da auditoria presentes no banco (o preflight as detecta).

    has_note: grava a `note` (ok / unchanged / kept: <sugestão>).
    has_reverted_at: só a linha NÃO revertida tira o artigo da seleção, e a gravação
    reaproveita a linha revertida pelo rollback da 034 (UNIQUE (campaign, unique_id)).
    Sem reverted_at, nenhuma linha é revertida: todo auditado sai da seleção.
    """

    has_note: bool = True
    has_reverted_at: bool = True

    @classmethod
    def from_columns(cls, columns) -> "AuditSchema":
        columns = set(columns)
        return cls(has_note="note" in columns, has_reverted_at="reverted_at" in columns)


CONTRACT_AUDIT = AuditSchema()

_THEME_ID_COLUMNS = ("theme_l1_id", "theme_l2_id", "theme_l3_id", "most_specific_theme_id")
_OLD_KEYS = ("old_l1", "old_l2", "old_l3", "old_most_specific")
_NEW_KEYS = ("new_l1", "new_l2", "new_l3", "new_most_specific")

# EXISTS (não JOIN): um artigo com vários níveis na subárvore sai uma vez só.
_THEMES_OF_ARTICLE = (
    "SELECT 1 FROM themes t\n"
    "            WHERE t.id IN (n.theme_l1_id, n.theme_l2_id, n.theme_l3_id,"
    " n.most_specific_theme_id)"
)


def _not_audited_sql(has_reverted_at: bool) -> str:
    """Idempotência: sai da seleção o artigo já auditado na campanha e NÃO revertido
    (o rollback da 034 marca reverted_at; o revertido volta a ser candidato)."""
    active = " AND c.reverted_at IS NULL" if has_reverted_at else ""
    return f"""NOT EXISTS (
            SELECT 1 FROM news_theme_changes c
            WHERE c.campaign = %(campaign)s AND c.unique_id = n.unique_id{active}
        )"""


READ_THEME_IDS_SQL = """
    SELECT theme_l1_id, theme_l2_id, theme_l3_id, most_specific_theme_id
    FROM news
    WHERE unique_id = %s
"""

# Guarda: o tema atual ainda é o lido antes da chamada (NULL-safe).
_OLD_THEME_GUARD = "\n      AND ".join(
    f"{col} IS NOT DISTINCT FROM %({key})s" for col, key in zip(_THEME_ID_COLUMNS, _OLD_KEYS)
)

# Só os ids de tema: nunca summary, content_embedding nem news_features.
UPDATE_THEME_SQL = f"""
    UPDATE news
    SET theme_l1_id = %(new_l1)s,
        theme_l2_id = %(new_l2)s,
        theme_l3_id = %(new_l3)s,
        most_specific_theme_id = %(new_most_specific)s,
        updated_at = NOW()
    WHERE unique_id = %(unique_id)s
      AND {_OLD_THEME_GUARD}
"""

# Sem mudança: confere e trava a linha antes de auditar (old = new).
LOCK_UNCHANGED_SQL = f"""
    SELECT 1 FROM news
    WHERE unique_id = %(unique_id)s
      AND {_OLD_THEME_GUARD}
    FOR UPDATE
"""


def build_insert_audit_sql(audit: AuditSchema = CONTRACT_AUDIT) -> str:
    """INSERT de uma linha na auditoria, com RETURNING 1.

    UNIQUE (campaign, unique_id): uma linha por artigo na campanha.
      - Com reverted_at: ON CONFLICT DO UPDATE só sobre a linha REVERTIDA (o rollback
        da 034 a marcou): reaproveita a linha com os códigos novos e reverted_at = NULL.
      - Sem reverted_at: ON CONFLICT DO NOTHING.
    Conflito com linha ativa (run concorrente já auditou) não devolve linha: quem
    chama desfaz o UPDATE (already_audited).
    """
    columns = ["campaign", "unique_id", *_AUDIT_CODE_COLUMNS, "source"]
    if audit.has_note:
        columns.append("note")
    if audit.has_reverted_at:
        sets = [f"{col} = EXCLUDED.{col}" for col in columns[2:]]
        sets += ["changed_at = NOW()", "reverted_at = NULL"]
        conflict = (
            "ON CONFLICT (campaign, unique_id) DO UPDATE SET\n        "
            + ",\n        ".join(sets)
            + "\n    WHERE news_theme_changes.reverted_at IS NOT NULL"
        )
    else:
        conflict = "ON CONFLICT (campaign, unique_id) DO NOTHING"
    placeholders = ", ".join(["%s"] * len(columns))
    return f"""
    INSERT INTO news_theme_changes ({", ".join(columns)})
    VALUES ({placeholders})
    {conflict}
    RETURNING 1
"""


AUDIT_COLUMNS_SQL = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = %s AND table_schema = current_schema()
"""

# UNIQUE (constraint ou índice) exatamente em (campaign, unique_id), sem predicado:
# é o que torna a idempotência por campanha segura sob concorrência.
AUDIT_UNIQUE_SQL = """
    SELECT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = to_regclass(%s)
          AND i.indisunique
          AND i.indpred IS NULL
          AND i.indnkeyatts = 2
          AND (
              SELECT array_agg(a.attname::text ORDER BY a.attname::text)
              FROM pg_attribute a
              WHERE a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey::int2[])
          ) = ARRAY['campaign', 'unique_id']
    )
"""

# Fontes que não são do LLM já gravadas na campanha (ex.: a da migração 034).
CAMPAIGN_FOREIGN_SOURCES_SQL = """
    SELECT DISTINCT source FROM news_theme_changes
    WHERE campaign = %s AND source NOT LIKE %s
    ORDER BY source
    LIMIT 5
"""


def _theme_select_sql(
    select: str, with_date_to: bool, term_fields: str, has_reverted_at: bool = True
) -> str:
    """WHERE das seleções de tema (theme-code | theme26-candidates).

    theme-code:          (subárvore) AND NOT EXISTS(campanha) AND janela
    theme26-candidates:  ((subárvore do 19) OR (extra AND (MDR OR termos)))
                         AND NOT EXISTS(campanha) AND janela
    NOT EXISTS(campanha): auditado na campanha e não revertido (ver _not_audited_sql).
    """
    if term_fields not in TERM_FIELDS:
        raise ValueError(f"term_fields inválido: {term_fields!r} (use {', '.join(TERM_FIELDS)})")
    subtree = f"""EXISTS (
            {_THEMES_OF_ARTICLE}
              AND (t.code = %(theme_code)s OR t.code LIKE %(theme_prefix)s)
        )"""
    if select == "theme-code":
        predicate = subtree
    else:
        terms = " OR ".join(
            f"{field} ILIKE ANY(%(term_patterns)s::text[])" for field in TERM_FIELDS[term_fields]
        )
        predicate = f"""(
        {subtree}
        OR (
            EXISTS (
                {_THEMES_OF_ARTICLE}
                  AND (t.code = ANY(%(extra_codes)s::text[])
                       OR t.code LIKE ANY(%(extra_prefixes)s::text[]))
            )
            AND (n.agency_key = ANY(%(agency_keys)s::text[]) OR {terms})
        )
    )"""
    upper = ""
    if with_date_to:
        upper = f"AND n.published_at < {_BRT_DAY_START.format(param='date_to')}"
    return f"""
        SELECT n.unique_id
        FROM news n
        WHERE {predicate}
          AND {_not_audited_sql(has_reverted_at)}
          AND n.published_at >= {_BRT_DAY_START.format(param='date_from')}
          {upper}
        ORDER BY n.published_at DESC
        LIMIT %(limit)s
    """


def build_select_sql(
    select: str,
    with_date_to: bool,
    term_fields: str = DEFAULT_TERM_FIELDS,
    audit_has_reverted_at: bool = True,
) -> str:
    """SELECT da janela: `null-theme` (tema NULL), `mock` (summary '[MOCK]%'),
    `null-summary` (tema gravado e summary NULL), `theme-code` (subárvore de um
    código) ou `theme26-candidates` (ver o docstring do módulo).

    Parâmetros nomeados (ver build_select_params). Ordem: mais recentes primeiro.
    `null-theme`/`null-summary` sem teto (with_date_to=False) são recusados: ver o
    docstring do módulo. `term_fields` e `audit_has_reverted_at` (a auditoria tem a
    coluna reverted_at) só valem para as seleções de tema.
    """
    if select in SELECTS_REQUIRING_DATE_TO and not with_date_to:
        raise ValueError(f"--select {select} exige --date-to (teto da janela)")
    if select in THEME_SELECTS:
        return _theme_select_sql(select, with_date_to, term_fields, audit_has_reverted_at)
    if select == "null-theme":
        predicate = "n.most_specific_theme_id IS NULL"
    elif select == "mock":
        predicate = "n.summary LIKE %(mock_pattern)s"
    elif select == "null-summary":
        predicate = "n.most_specific_theme_id IS NOT NULL AND n.summary IS NULL"
    else:
        raise ValueError(f"seleção inválida: {select!r} (use {', '.join(SELECT_CHOICES)})")

    upper = ""
    if with_date_to:
        upper = f"AND n.published_at < {_BRT_DAY_START.format(param='date_to')}"
    return f"""
        SELECT n.unique_id
        FROM news n
        WHERE {predicate}
          AND n.published_at >= {_BRT_DAY_START.format(param='date_from')}
          {upper}
        ORDER BY n.published_at DESC
        LIMIT %(limit)s
    """


def build_select_params(
    select: str,
    date_from: str,
    date_to,
    limit: int,
    *,
    theme_code=None,
    campaign=None,
    extra_codes=DEFAULT_EXTRA_CODES,
) -> dict:
    """Parâmetros nomeados do SELECT. Seleções de tema exigem `campaign` (exclusão
    dos já auditados); `theme-code` exige `theme_code`; `extra_codes` só vale para o
    theme26-candidates (vazio = só o bloco do 19)."""
    params = {"date_from": date_from, "limit": limit}
    if date_to:
        params["date_to"] = date_to
    if select == "mock":
        params["mock_pattern"] = MOCK_SUMMARY_PATTERN
    if select in THEME_SELECTS:
        if not campaign:
            raise ValueError(f"--select {select} exige a campanha (--campaign)")
        if select == "theme-code" and not theme_code:
            raise ValueError("--select theme-code exige o código (--theme-code)")
        base = theme_code if select == "theme-code" else THEME26_BASE_CODE
        params["theme_code"] = base
        params["theme_prefix"] = f"{base}.%"
        params["campaign"] = campaign
        if select == "theme26-candidates":
            extras = list(extra_codes or ())
            params["extra_codes"] = extras
            params["extra_prefixes"] = [f"{code}.%" for code in extras]
            params["agency_keys"] = list(THEME26_AGENCY_KEYS)
            params["term_patterns"] = [f"%{term}%" for term in THEME26_TERMS]
    return params


def _get_conn():
    """Conexão psycopg2 (separada para selecionar uids / ler e gravar o ledger)."""
    return psycopg2.connect(handler._get_database_url())


def get_window_uids(
    select: str,
    date_from: str,
    date_to,
    limit: int,
    *,
    theme_code=None,
    campaign=None,
    term_fields: str = DEFAULT_TERM_FIELDS,
    extra_codes=DEFAULT_EXTRA_CODES,
    audit_has_reverted_at: bool = True,
) -> list:
    sql = build_select_sql(
        select,
        with_date_to=bool(date_to),
        term_fields=term_fields,
        audit_has_reverted_at=audit_has_reverted_at,
    )
    params = build_select_params(
        select,
        date_from,
        date_to,
        limit,
        theme_code=theme_code,
        campaign=campaign,
        extra_codes=extra_codes,
    )
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def process_one(uid: str):
    """Re-enriquece um artigo. Retorna (uid, status, usage).

    status: ok | missing | classification_failed | model_unavailable |
    update_failed | error:<Exceção>. usage = tokens da chamada combinada.
    NUNCA chama extract_entities e NUNCA publica evento.
    """
    article = handler.fetch_article(uid)
    if not article:
        return uid, "missing", dict(_ZERO_USAGE)

    try:
        result = handler._get_classifier().classify_single(article, return_format="dict")
    except Exception as e:  # noqa: BLE001 — um artigo ruim não derruba o run
        return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)

    usage = (result or {}).get("_usage") or dict(_ZERO_USAGE)
    if handler.is_combined_failure(result):
        error = handler.combined_failure_error(result)
        status = (
            "model_unavailable" if is_model_unavailable_error(error) else "classification_failed"
        )
        print(f"  {uid}: {status} ({error})")
        return uid, status, usage

    result["unique_id"] = uid
    try:
        stats = update_news_enrichment(
            handler._get_database_url(), [result], handler._get_code_to_id()
        )
        if not stats.get("updated"):
            return uid, "update_failed", usage
        # Só o sentimento: entidades ficam como estão (sem NER neste script).
        handler._upsert_ai_features(uid, {"sentiment": result.get("sentiment")})
    except Exception as e:  # noqa: BLE001 — tokens já gastos: devolve o usage
        return uid, f"error:{type(e).__name__}", usage
    return uid, "ok", usage


def _count_uids(sql: str, uids: list) -> int:
    """Executa um COUNT(*) parametrizado pela lista de uids (só leitura)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, (list(uids),))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def count_missing_sentiment(uids: list) -> int:
    """Quantos dos uids não têm sentimento em news_features (null-summary só reporta)."""
    return _count_uids(MISSING_SENTIMENT_SQL, uids)


def count_with_embedding(uids: list) -> int:
    """Quantos dos uids já têm content_embedding (null-summary só reporta)."""
    return _count_uids(WITH_EMBEDDING_SQL, uids)


def update_summary_only(uid: str, summary: str) -> bool:
    """Grava SÓ o resumo (UPDATE_SUMMARY_SQL). True se gravou; False se o artigo
    já tinha resumo (guarda IS NULL) ou não existe."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(UPDATE_SUMMARY_SQL, (summary, uid))
        written = cur.rowcount == 1
        conn.commit()
        return written
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_one_summary(uid: str):
    """Gera e grava SÓ o resumo (--select null-summary). Retorna (uid, status, usage).

    status: ok | missing | summary_failed | model_unavailable | summary_present |
    error:<Exceção>. usage = tokens da chamada só-resumo (todas as tentativas).
    NUNCA chama a combinada nem o NER, NUNCA grava news_features (nem sentimento),
    NUNCA publica evento.
    """
    article = handler.fetch_article(uid)
    if not article:
        return uid, "missing", dict(_ZERO_USAGE)

    try:
        result = handler._get_classifier().llm_client.summarize_single(article)
    except Exception as e:  # noqa: BLE001 — um artigo ruim não derruba o run
        return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)

    result = result or {}
    usage = result.get("_usage") or dict(_ZERO_USAGE)
    error = result.get("_error")
    summary = result.get("summary")
    if error or not isinstance(summary, str) or not summary.strip():
        # Não grava: o artigo segue com summary NULL e selecionável no próximo run.
        status = "model_unavailable" if is_model_unavailable_error(error) else "summary_failed"
        print(f"  {uid}: {status} ({error or 'resumo vazio ou inválido'})")
        return uid, status, usage

    try:
        written = update_summary_only(uid, summary.strip())
    except Exception as e:  # noqa: BLE001 — tokens já gastos: devolve o usage
        return uid, f"error:{type(e).__name__}", usage
    return uid, ("ok" if written else "summary_present"), usage


# ---------------------------------------------------------------------------
# --theme-only
# ---------------------------------------------------------------------------

# Campos da resposta, em ordem de preferência no empate de profundidade.
_CHAIN_FIELDS = (
    "theme_1_level_3_code",
    "most_specific_theme_code",
    "theme_1_level_2_code",
    "theme_1_level_1_code",
)


def build_theme_parents(taxonomy: dict) -> dict:
    """{código: código do pai} a partir da árvore de load_taxonomy_from_postgres
    (L1 → None). Só os códigos existentes na taxonomia entram."""
    parents: dict = {}
    for l1, l1_data in (taxonomy or {}).items():
        parents[l1] = None
        for l2, l2_data in ((l1_data or {}).get("subcategories") or {}).items():
            parents[l2] = l1
            for l3 in (l2_data or {}).get("subcategories") or {}:
                parents[l3] = l2
    return parents


def _code_depth(code: str) -> int:
    return code.count(".") + 1


def resolve_theme_chain(result: dict, parents: dict):
    """Cadeia coerente (l1, l2, l3, mais específico) a partir da resposta, ou None.

    Regra (MAX_LEVEL_DROP = 1):
      1. Considera os códigos bem formados dos campos l3, mais específico, l2 e l1
         (texto que não é código, como um rótulo, é ignorado) e, depois deles, o
         prefixo de cada um até MAX_LEVEL_DROP nível acima (26.01.09 → 26.01): o nível
         válido acima de um código inexistente, mesmo que o LLM não tenha preenchido
         o campo desse nível.
      2. Vale o código VÁLIDO (presente em `parents`, i.e. na taxonomia do banco)
         mais profundo; no empate, a ordem acima (o código explícito vence o
         prefixo). l1/l2 vêm da taxonomia, não da resposta (ex.: l1 '04' com l3
         '26.01.03' vira 26 → 26.01 → 26.01.03).
      3. Ele pode estar no máximo MAX_LEVEL_DROP nível acima do código mais profundo
         que o LLM pediu. Pediu 26.01.09 (inexistente) → 26.01; pediu 26.07
         (inexistente) → 26. Mas pediu 19.03.03 e só o 19 existe → None: rebaixar
         um artigo para só o L1 quando o LLM escolheu um L3 perde a informação e,
         no tema 26, mandaria Defesa Civil para "Defesa e Forças Armadas".
      4. Nenhum código válido → None.
    None = resposta inválida: quem chama não grava nem audita (o artigo volta no
    próximo run).
    """
    codes = []
    for field in _CHAIN_FIELDS:
        value = (result or {}).get(field)
        if isinstance(value, str) and _CODE_RE.match(value.strip()):
            codes.append(value.strip())
    candidates = list(codes)
    for code in codes:
        for _ in range(MAX_LEVEL_DROP):
            if "." not in code:
                break
            code = code.rsplit(".", 1)[0]
            candidates.append(code)
    valid = [code for code in candidates if code in parents]
    if not valid:
        return None
    requested = max(_code_depth(code) for code in codes)
    best = max(valid, key=_code_depth)  # o primeiro entre os mais profundos
    chain = [best]
    while parents.get(chain[-1]):
        chain.append(parents[chain[-1]])
    chain.reverse()
    if len(chain) < requested - MAX_LEVEL_DROP:
        return None
    l1, l2, l3 = (chain + [None, None])[:3]
    return (l1, l2, l3, best)


def check_audit_table(campaign: str):
    """Preflight da auditoria. Devolve (erro, AuditSchema): erro None se está ok.

    Exige a tabela da migração 034 com as 12 colunas do contrato
    (AUDIT_REQUIRED_COLUMNS), UNIQUE (campaign, unique_id) sem predicado e a campanha
    sem registros de fonte que não seja `llm:*` (reusar a campanha da 034 tiraria da
    seleção os artigos que ela auditou e que continuam no 19). Colunas a mais são
    aceitas; id, note e reverted_at, se existirem, entram no AuditSchema.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(AUDIT_COLUMNS_SQL, (AUDIT_TABLE,))
        columns = {row[0] for row in cur.fetchall()}
        if not columns:
            return (
                f"tabela {AUDIT_TABLE} ausente: rode antes a migração 034 do "
                "data-platform (tema 26), que a cria",
                None,
            )
        missing = [col for col in AUDIT_REQUIRED_COLUMNS if col not in columns]
        if missing:
            return (
                f"{AUDIT_TABLE} sem as colunas {', '.join(missing)} (contrato da migração 034)",
                None,
            )
        cur.execute(AUDIT_UNIQUE_SQL, (AUDIT_TABLE,))
        row = cur.fetchone()
        if not (row and row[0]):
            return (
                f"{AUDIT_TABLE} sem UNIQUE (campaign, unique_id) (contrato da migração "
                "034): sem ele a idempotência por campanha não é segura",
                None,
            )
        cur.execute(CAMPAIGN_FOREIGN_SOURCES_SQL, (campaign, f"{LLM_SOURCE_PREFIX}%"))
        foreign = [row[0] for row in cur.fetchall()]
        if foreign:
            return (
                f"a campanha {campaign!r} já tem registros de outra fonte "
                f"({', '.join(foreign)}): use uma campanha própria do LLM "
                f"(ex.: {DEFAULT_THEME_CAMPAIGN})",
                None,
            )
        return None, AuditSchema.from_columns(columns)
    finally:
        conn.close()


def _read_theme_ids(uid: str):
    """(l1, l2, l3, mais específico) atuais do artigo, ou None se ele não existe."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(READ_THEME_IDS_SQL, (uid,))
        row = cur.fetchone()
        return tuple(row) if row else None
    finally:
        conn.close()


def _write_theme_change(
    uid,
    campaign,
    source,
    old_ids,
    new_ids,
    id_to_code,
    *,
    status: str,
    note: str,
    audit: AuditSchema = CONTRACT_AUDIT,
) -> str:
    """UPDATE guardado + INSERT na auditoria, na MESMA transação.

    new_ids == old_ids (unchanged / kept): sem UPDATE; confere com SELECT … FOR UPDATE
    que o tema ainda é o lido e audita old = new. Senão, UPDATE com a guarda do tema
    lido. Devolve `status` se gravou; theme_changed se outro processo mudou o tema;
    already_audited se a campanha já tem linha ativa do artigo (run concorrente): nos
    dois casos desfaz tudo. Exceção desfaz tudo e sobe para quem chama.
    """
    params = {"unique_id": uid}
    params.update(zip(_OLD_KEYS, old_ids))
    params.update(zip(_NEW_KEYS, new_ids))
    old_codes = [id_to_code.get(i) if i is not None else None for i in old_ids]
    new_codes = [id_to_code.get(i) if i is not None else None for i in new_ids]
    values = (campaign, uid, *old_codes, *new_codes, source)
    if audit.has_note:
        values += (note,)

    conn = _get_conn()
    try:
        cur = conn.cursor()
        if tuple(new_ids) == tuple(old_ids):
            cur.execute(LOCK_UNCHANGED_SQL, params)
            if cur.fetchone() is None:
                conn.rollback()
                return "theme_changed"
        else:
            cur.execute(UPDATE_THEME_SQL, params)
            if cur.rowcount != 1:
                conn.rollback()
                return "theme_changed"
        cur.execute(build_insert_audit_sql(audit), values)
        if cur.fetchone() is None:
            conn.rollback()
            return "already_audited"
        conn.commit()
        return status
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _in_theme26_base(codes) -> bool:
    """O artigo tem algum dos 4 níveis na subárvore do 19 (o bloco do 19)?"""
    prefix = f"{THEME26_BASE_CODE}."
    return any(code == THEME26_BASE_CODE or code.startswith(prefix) for code in codes if code)


def _kept_note(chain) -> str:
    suggested = " > ".join(code for code in chain[:3] if code)
    return (
        f"kept: o LLM sugeriu {suggested}; artigo fora do {THEME26_BASE_CODE} só muda "
        f"para o {THEME26_CODE}"
    )


def make_theme_only_process(
    *,
    campaign: str,
    source: str,
    code_to_id: dict,
    parents: dict,
    audit: AuditSchema = CONTRACT_AUDIT,
):
    """Fábrica do `process(uid) -> (uid, status, usage)` do --theme-only.

    status: ok | unchanged | kept | theme_changed | already_audited | invalid_theme |
    no_theme | unknown_old_theme | missing | classification_failed |
    model_unavailable | error:<Exceção>. Só ok/unchanged/kept gravam auditoria (e saem
    da seleção).
    Guarda do tema 26: artigo fora da subárvore do 19 (nenhum dos 4 níveis no 19) só
    tem o tema gravado se o novo L1 for o 26; senão é `kept`: mantém o tema e audita
    old = new, com a sugestão do LLM na note. O artigo do 19 sempre recebe a nova
    classificação.
    NUNCA grava resumo, sentimento, NER nem publica evento.
    """
    id_to_code = {theme_id: code for code, theme_id in code_to_id.items()}

    def process(uid: str):
        article = handler.fetch_article(uid)
        if not article:
            return uid, "missing", dict(_ZERO_USAGE)
        # Lido ANTES da chamada: a guarda pega mudança feita durante ela.
        try:
            old_ids = _read_theme_ids(uid)
        except Exception as e:  # noqa: BLE001
            return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)
        if old_ids is None:
            return uid, "missing", dict(_ZERO_USAGE)
        if all(i is None for i in old_ids):
            # Sem tema, o artigo é do worker ao vivo (NER + evento).
            return uid, "no_theme", dict(_ZERO_USAGE)
        if any(i is not None and i not in id_to_code for i in old_ids):
            return uid, "unknown_old_theme", dict(_ZERO_USAGE)

        try:
            result = handler._get_classifier().classify_single(article, return_format="dict")
        except Exception as e:  # noqa: BLE001 — um artigo ruim não derruba o run
            return uid, f"error:{type(e).__name__}", dict(_ZERO_USAGE)

        usage = (result or {}).get("_usage") or dict(_ZERO_USAGE)
        if handler.is_combined_failure(result):
            error = handler.combined_failure_error(result)
            status = (
                "model_unavailable"
                if is_model_unavailable_error(error)
                else "classification_failed"
            )
            print(f"  {uid}: {status} ({error})")
            return uid, status, usage

        chain = resolve_theme_chain(result, parents)
        if chain is None or any(code is not None and code not in code_to_id for code in chain):
            answer = " ".join(f"{field}={result.get(field)!r}" for field in _CHAIN_FIELDS)
            print(f"  {uid}: invalid_theme ({answer})")
            return uid, "invalid_theme", usage
        new_ids = tuple(code_to_id[code] if code else None for code in chain)
        old_codes = [id_to_code.get(i) if i is not None else None for i in old_ids]

        if new_ids == tuple(old_ids):
            status, note, target = "unchanged", NOTE_UNCHANGED, new_ids
        elif not _in_theme26_base(old_codes) and chain[0] != THEME26_CODE:
            status, note, target = "kept", _kept_note(chain), tuple(old_ids)
        else:
            status, note, target = "ok", NOTE_OK, new_ids

        try:
            status = _write_theme_change(
                uid,
                campaign,
                source,
                old_ids,
                target,
                id_to_code,
                status=status,
                note=note,
                audit=audit,
            )
        except Exception as e:  # noqa: BLE001 — tokens já gastos: devolve o usage
            print(f"  {uid}: error ({type(e).__name__}: {e})")
            return uid, f"error:{type(e).__name__}", usage
        return uid, status, usage

    return process


def _record_usage_for(conn, model_id: str, usage: dict) -> None:
    """Grava o usage de uma chamada no ledger (se não-zero)."""
    if not usage:
        return
    in_tok = usage.get("input_tokens") or 0
    out_tok = usage.get("output_tokens") or 0
    if in_tok or out_tok:
        record_usage(conn, model_id, in_tok, out_tok)


def run_reenrich(
    uids: list,
    *,
    model_id: str,
    daily_quota,
    quota_fraction: float,
    workers: int,
    process=process_one,
) -> dict:
    """Processa uids com governador de cota. Resumível e capado.

    `process(uid) -> (uid, status, usage)`: process_one (chamada combinada) ou
    process_one_summary (null-summary). Para em budget_exhausted (parada graciosa)
    ou no primeiro modelo indisponível. Sem cota (None/<=0) → modo sem-teto
    (apenas grava o ledger).
    """
    stats: dict = {"budget_exhausted": False, "model_unavailable": False}
    has_quota = bool(daily_quota and daily_quota > 0)
    if not has_quota:
        print(f"AVISO: sem cota diária para {model_id!r} — modo sem-teto.")

    ledger_conn = _get_conn()
    try:
        t0 = time.time()
        done = 0

        def _consume(status: str, usage: dict) -> None:
            nonlocal done
            _record_usage_for(ledger_conn, model_id, usage)
            key = status.split(":")[0]
            stats[key] = stats.get(key, 0) + 1
            if status == "model_unavailable":
                stats["model_unavailable"] = True
            done += 1
            if done % 25 == 0 or done == len(uids):
                print(f"  {done}/{len(uids)}  {_pretty(stats)}  ({time.time() - t0:.0f}s)")

        if workers <= 1:
            for i, uid in enumerate(uids):
                if (
                    has_quota
                    and i % BUDGET_CHECK_EVERY == 0
                    and budget_exhausted(ledger_conn, model_id, daily_quota, quota_fraction)
                ):
                    print(f"budget exhausted — parando gracioso em {i}/{len(uids)}.")
                    stats["budget_exhausted"] = True
                    break
                _, status, usage = process(uid)
                _consume(status, usage)
                if stats["model_unavailable"]:
                    print("modelo indisponível (EOL/inexistente) — abortando.")
                    break
        else:
            # Lotes de chunk_size para o governador poder parar entre lotes (um
            # `break` no as_completed não cancela futures já submetidas).
            chunk_size = max(workers * 2, BUDGET_CHECK_EVERY)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for chunk_start in range(0, len(uids), chunk_size):
                    if has_quota and budget_exhausted(
                        ledger_conn, model_id, daily_quota, quota_fraction
                    ):
                        print(f"budget exhausted — parando no lote {chunk_start}/{len(uids)}.")
                        stats["budget_exhausted"] = True
                        break
                    chunk_end = chunk_start + chunk_size
                    chunk = uids[chunk_start:chunk_end]
                    futs = [ex.submit(process, uid) for uid in chunk]
                    for fut in as_completed(futs):
                        _, status, usage = fut.result()
                        _consume(status, usage)
                    if stats["model_unavailable"]:
                        print("modelo indisponível (EOL/inexistente) — abortando.")
                        break

        print(f"FIM: {_pretty(stats)}  total={done}  {time.time() - t0:.0f}s")
        return stats
    finally:
        try:
            ledger_conn.close()
        except Exception:  # noqa: BLE001
            pass


def _pretty(stats: dict) -> dict:
    return {
        k: v for k, v in stats.items() if k not in ("budget_exhausted", "model_unavailable") or v
    }


def _missing_sentiment_line(missing: int, selected: int) -> str:
    return (
        f"sem_sentimento={missing} dos {selected} selecionados (fora do escopo do "
        "null-summary: o sentimento não é gerado aqui)"
    )


def _with_embedding_line(with_embedding: int, selected: int) -> str:
    return (
        f"com_embedding={with_embedding} dos {selected} selecionados (embedding feito "
        "sem o resumo; não é tocado aqui e o B3 só pega content_embedding IS NULL: "
        "exigem passo separado, ver o README do worker)"
    )


def _summary_only_gaps(missing_sentiment: int, with_embedding: int, selected: int) -> None:
    print(_missing_sentiment_line(missing_sentiment, selected))
    print(_with_embedding_line(with_embedding, selected))


def _today_brt() -> datetime.date:
    """Data de hoje no fuso BRT (America/Sao_Paulo)."""
    return datetime.datetime.now(BRT).date()


def _iso_date(value: str) -> str:
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"data inválida {value!r} (use AAAA-MM-DD)") from e


def _theme_code_arg(value: str) -> str:
    if not _CODE_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"código de tema inválido {value!r} (use NN, NN.NN ou NN.NN.NN)"
        )
    return value


def _extra_codes_arg(value: str) -> tuple:
    """Lista de códigos separados por vírgula; vazio = nenhum código extra."""
    if not value.strip():
        return ()
    codes = tuple(part.strip() for part in value.split(","))
    for code in codes:
        if not _CODE_RE.match(code):
            raise argparse.ArgumentTypeError(
                f"--extra-codes: código inválido {code!r} (use NN, NN.NN ou NN.NN.NN, "
                "separados por vírgula; vazio = nenhum)"
            )
    return codes


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--select",
        choices=SELECT_CHOICES,
        required=True,
        help="null-theme: tema NULL na janela; mock: summary LIKE '[MOCK]%%' na janela; "
        "null-summary: tema gravado e summary NULL na janela (só o resumo, prompt enxuto); "
        "theme-code: subárvore de --theme-code; theme26-candidates: candidatos ao tema 26 "
        f"(as duas últimas gravam só o tema, na campanha {DEFAULT_THEME_CAMPAIGN} por padrão)",
    )
    ap.add_argument(
        "--theme-code",
        type=_theme_code_arg,
        default=None,
        help="código da subárvore (só com --select theme-code), ex.: 19",
    )
    ap.add_argument(
        "--theme-only",
        action="store_true",
        help="grava SÓ os ids de tema, com guarda e auditoria em news_theme_changes. "
        "Implícito nas seleções de tema (aceito por compatibilidade com o DAG); proibido "
        "nas demais",
    )
    ap.add_argument(
        "--campaign",
        default=None,
        help=f"campanha da auditoria nas seleções de tema (padrão {DEFAULT_THEME_CAMPAIGN}); "
        f"só {LLM_CAMPAIGN_PREFIX}* ([a-z0-9._-], até 50 caracteres); os auditados nela e "
        "não revertidos saem da seleção",
    )
    ap.add_argument(
        "--term-fields",
        choices=tuple(TERM_FIELDS),
        default=None,
        help=f"theme26-candidates: onde buscar os termos (padrão {DEFAULT_TERM_FIELDS}: "
        "só o título; title-content inclui o conteúdo)",
    )
    ap.add_argument(
        "--extra-codes",
        type=_extra_codes_arg,
        default=None,
        help="theme26-candidates: códigos do bloco extra, separados por vírgula "
        f"(padrão {','.join(DEFAULT_EXTRA_CODES)}; '' = nenhum, só o bloco do 19)",
    )
    ap.add_argument(
        "--date-from", type=_iso_date, required=True, help="dia BRT inicial (inclusivo)"
    )
    ap.add_argument(
        "--date-to",
        type=_iso_date,
        default=None,
        help="dia BRT final (EXCLUSIVO). Obrigatório com --select null-theme e "
        "null-summary, e no máximo hoje (BRT); opcional com --select mock",
    )
    ap.add_argument("--limit", type=int, default=500, help="teto de artigos neste run")
    ap.add_argument("--workers", type=int, default=1, help="concorrência de chamadas Bedrock")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="só seleciona e lista; não chama o Bedrock nem escreve nada",
    )
    return ap


def _theme_campaign(args) -> str | None:
    """Campanha da auditoria: a de --campaign ou a padrão, só nas seleções de tema."""
    if args.select not in THEME_SELECTS:
        return None
    return DEFAULT_THEME_CAMPAIGN if args.campaign is None else args.campaign


def _theme_args_error(args) -> str | None:
    """Combinações de argumentos das seleções de tema (checadas antes de tocar o banco).

    As seleções de tema implicam o modo só-tema (--theme-only é opcional) e a campanha
    padrão: o DAG enrichment_backfill passa só --select/--theme-code/--term-fields,
    --date-from/--date-to, --limit/--workers/[--dry-run].
    """
    theme_select = args.select in THEME_SELECTS
    if args.theme_only and not theme_select:
        return (
            f"--theme-only só vale com --select {' ou '.join(sorted(THEME_SELECTS))} "
            f"(não com {args.select})"
        )
    if args.campaign is not None and not theme_select:
        return (
            f"--campaign só vale com --select {' ou '.join(sorted(THEME_SELECTS))} "
            f"(não com {args.select})"
        )
    campaign = _theme_campaign(args)
    if campaign is not None and not _CAMPAIGN_RE.match(campaign):
        return (
            f"--campaign inválida {campaign!r}: use {LLM_CAMPAIGN_PREFIX}<id> ([a-z0-9._-], "
            "até 50 caracteres; ex.: tema26-llm-d1). O rollback da 034 e o MERGE do "
            "BigQuery só leem tema26-*, e tema26-034/tema26-rollback são da migração"
        )
    if args.select == "theme-code" and not args.theme_code:
        return "--select theme-code exige --theme-code (ex.: 19)"
    if args.theme_code and args.select != "theme-code":
        return "--theme-code só vale com --select theme-code"
    if args.select != "theme26-candidates":
        for flag, value in (
            ("--term-fields", args.term_fields),
            ("--extra-codes", args.extra_codes),
        ):
            if value is not None:
                return f"{flag} só vale com --select theme26-candidates"
    return None


def _theme_taxonomy_error(args, code_to_id: dict, extra_codes) -> str | None:
    """Os códigos pedidos existem no banco (mapa código→id lido agora)?"""
    if args.select == "theme-code" and args.theme_code not in code_to_id:
        return f"--theme-code {args.theme_code} não existe na tabela themes"
    if args.select == "theme26-candidates":
        missing = [code for code in THEME26_TARGET_CODES if code not in code_to_id]
        if missing:
            return (
                f"tema 26 ausente da tabela themes (faltam {', '.join(missing)}): rode "
                "antes a migração 034 do data-platform"
            )
        unknown = [code for code in extra_codes if code not in code_to_id]
        if unknown:
            return f"--extra-codes com códigos inexistentes em themes: {', '.join(unknown)}"
    return None


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    theme_error = _theme_args_error(args)
    if theme_error:
        print(f"ERRO: {theme_error}", file=sys.stderr)
        return 1
    # As seleções de tema implicam o modo só-tema e a campanha (padrão tema26-llm-d1).
    theme_only = args.select in THEME_SELECTS
    campaign = _theme_campaign(args)
    audit = CONTRACT_AUDIT
    term_fields = args.term_fields or DEFAULT_TERM_FIELDS
    extra_codes = DEFAULT_EXTRA_CODES if args.extra_codes is None else args.extra_codes

    if not os.environ.get("DATABASE_URL"):
        print("ERRO: DATABASE_URL nao definida", file=sys.stderr)
        return 1

    model_id = os.environ.get("ENRICHMENT_MODEL_ID")
    if not model_id:
        print(
            "ERRO: ENRICHMENT_MODEL_ID nao definida (obrigatória; sem fallback para o "
            "default legado nem para BEDROCK_MODEL_ID)",
            file=sys.stderr,
        )
        return 1

    if args.date_to and args.date_to <= args.date_from:
        print("ERRO: --date-to (exclusivo) deve ser posterior a --date-from", file=sys.stderr)
        return 1

    if args.select in SELECTS_REQUIRING_DATE_TO:
        # Artigos novos sem tema são do worker ao vivo (que roda o NER e publica).
        today = _today_brt().isoformat()
        if not args.date_to:
            print(
                f"ERRO: --select {args.select} exige --date-to (exclusivo, no máximo hoje "
                f"BRT = {today}); {_EXAMPLE_WINDOW[args.select]}",
                file=sys.stderr,
            )
            return 1
        if args.date_to > today:
            print(
                f"ERRO: --date-to {args.date_to} passa de hoje BRT ({today}): a janela "
                "incluiria artigos que o worker ao vivo ainda vai processar",
                file=sys.stderr,
            )
            return 1

    quota_cfg = parse_daily_quota_env()
    daily_quota = quota_cfg["quota"].get(model_id)
    quota_fraction = quota_cfg["fraction"]

    print(
        f"ENRICHMENT_MODEL_ID={model_id!r}  select={args.select}  "
        f"janela=[{args.date_from}, {args.date_to or '…'}) BRT  dry_run={args.dry_run}  "
        f"cota={daily_quota}  fração={quota_fraction}"
    )

    if theme_only:
        # Preflight ANTES da seleção (também no --dry-run): a seleção depende da
        # tabela de auditoria, e a escrita, do contrato dela.
        audit_error, audit = check_audit_table(campaign)
        if audit_error:
            print(f"ERRO: {audit_error}", file=sys.stderr)
            return 1
        code_to_id = handler._get_code_to_id()
        taxonomy_error = _theme_taxonomy_error(args, code_to_id, extra_codes)
        if taxonomy_error:
            print(f"ERRO: {taxonomy_error}", file=sys.stderr)
            return 1
        detail = (
            f"  campanha={campaign}  auditoria: note={'sim' if audit.has_note else 'não'}"
            f" reverted_at={'sim' if audit.has_reverted_at else 'não'}"
        )
        if args.select == "theme-code":
            detail += f"  theme_code={args.theme_code}"
        else:
            detail += (
                f"  term_fields={term_fields}  extra_codes={','.join(extra_codes) or '(nenhum)'}"
            )
        print(f"--theme-only{detail}")

    summary_only = args.select == "null-summary"
    uids = get_window_uids(
        args.select,
        args.date_from,
        args.date_to,
        args.limit,
        theme_code=args.theme_code,
        campaign=campaign,
        term_fields=term_fields,
        extra_codes=extra_codes,
        audit_has_reverted_at=audit.has_reverted_at,
    )
    print(f"selecionados={len(uids)} (limit={args.limit})")
    if not uids:
        print("nada pendente — concluido.")
        return 0

    if summary_only:
        missing_sentiment = count_missing_sentiment(uids)
        with_embedding = count_with_embedding(uids)
        _summary_only_gaps(missing_sentiment, with_embedding, len(uids))

    if args.dry_run:
        for uid in uids[:DRY_RUN_SAMPLE]:
            print(f"  {uid}")
        if len(uids) > DRY_RUN_SAMPLE:
            print(f"  … e mais {len(uids) - DRY_RUN_SAMPLE}")
        print("dry-run: nada foi classificado nem escrito.")
        return 0

    # Aquece os caches do handler antes das threads e confere o modelo em uso.
    classifier = handler._get_classifier()
    classifier_model = classifier.llm_client.model_id
    if classifier_model != model_id:
        print(
            f"ERRO: classificador usa {classifier_model!r}, esperado {model_id!r}",
            file=sys.stderr,
        )
        return 1

    if theme_only:
        parents = build_theme_parents(classifier.llm_client.taxonomy)
        if args.select == "theme26-candidates":
            missing = [code for code in THEME26_TARGET_CODES if code not in parents]
            if missing:
                print(
                    f"ERRO: a taxonomia do classificador não tem o tema 26 (faltam "
                    f"{', '.join(missing)})",
                    file=sys.stderr,
                )
                return 1
        process = make_theme_only_process(
            campaign=campaign,
            source=f"{LLM_SOURCE_PREFIX}{model_id}",
            code_to_id=code_to_id,
            parents=parents,
            audit=audit,
        )
    elif summary_only:
        process = process_one_summary
    else:
        handler._get_code_to_id()  # aquece o mapa código→id (process_one grava tema)
        process = process_one

    stats = run_reenrich(
        uids,
        model_id=model_id,
        daily_quota=daily_quota,
        quota_fraction=quota_fraction,
        workers=args.workers,
        process=process,
    )
    if summary_only:
        _summary_only_gaps(missing_sentiment, with_embedding, len(uids))
    if theme_only:
        print(
            "lembrete: sync do Typesense e MERGE do BigQuery a partir da auditoria "
            f"(campanha {campaign})"
        )
    return 1 if stats["model_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
