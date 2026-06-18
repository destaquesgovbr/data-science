"""
Job de canonicalização de entidades (Fase 3) — orquestrador CLI.

Cross-artigo, por FORMA distinta (não per-article): a mesma `Finep` recorre em
milhares de artigos, então resolvemos cada forma distinta UMA vez e fazemos
backfill do `canonical_id` nas menções via lookup determinístico.

Etapas:
  A (gather):  coleta (normalize(forma_canonica|text), type, sample unique_id)
               distintos de news_features sobre a janela, excluindo formas já
               resolvidas/needs_review em entity_registry_seen e já presentes em
               entity_alias; upsert em entity_registry_seen (status pending).
  B (resolve): para cada forma pending (até --limit): gazetteer_lookup → senão
               llm_canonicalize → link_wikidata → apply_gates → escreve
               entity_registry(+reuse) / entity_alias; atualiza seen. Grava o raw
               em news_llm_raw (task='canon').
  C (backfill): para cada artigo da janela, set entity.canonical_id a partir de
               entity_alias[normalize(forma_canonica|text), type] quando resolvido;
               UPDATE news_features SET features = jsonb_set(...) (idempotente).

Resumível via entity_registry_seen. Bedrock e Wikidata mockados nos testes;
nenhuma chamada real, nenhum reprocessamento contra dados reais.
"""

import argparse
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import Json

from .canonicalization import (
    CANON_PROMPT_VERSION,
    _ENTITY_REUSE_THRESHOLDS,
    _add_usage,
    _is_acronym_variant,
    _jaccard,
    _name_tokens,
    _zero_usage,
    add_alias,
    apply_gates,
    find_existing_by_wikidata,
    find_existing_entity_by_name,
    find_existing_org_by_name,
    gazetteer_lookup,
    get_canon_model_id,
    list_candidates,
    llm_canonicalize,
    merge_entities,
    mint_internal_id,
    normalize,
    upsert_entity,
)
from .quota_governor import budget_exhausted, parse_daily_quota_env, record_usage

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30
DEFAULT_LIMIT = 100
WIKIDATA_URL_PREFIX = "https://www.wikidata.org/wiki/"
SOURCE_CANON = "canon"
# Checa o budget a cada N formas resolvidas (tolera pequena ultrapassagem).
BUDGET_CHECK_EVERY = 5


# =============================================================================
# Step A — gather distinct forms into entity_registry_seen
# =============================================================================

# Distinct (forma, type, sample unique_id) de news_features sobre a janela.
# COALESCE(forma_canonica, text) é a forma de superfície a canonicalizar.
_GATHER_SQL = """
WITH mentions AS (
    SELECT
        nf.unique_id,
        COALESCE(e->>'forma_canonica', e->>'text') AS surface,
        e->>'type' AS type
    FROM news_features nf
    JOIN news n ON n.unique_id = nf.unique_id
    CROSS JOIN LATERAL jsonb_array_elements(nf.features->'entities') AS e
    WHERE n.published_at >= %s AND n.published_at < %s
      AND nf.features ? 'entities'
)
SELECT surface, type, MIN(unique_id) AS sample_unique_id
FROM mentions
WHERE surface IS NOT NULL AND surface <> '' AND type IS NOT NULL
GROUP BY surface, type
"""


def gather_forms(conn, since: datetime, until: datetime) -> List[dict]:
    """Step A: coleta formas distintas e faz upsert em entity_registry_seen.

    Exclui formas já resolvidas/needs_review (seen) e já presentes em entity_alias.

    Returns:
        Lista de {surface_norm, type, sample_unique_id} efetivamente staged
        (status pending) nesta passada.
    """
    cursor = conn.cursor()
    staged: List[dict] = []
    try:
        cursor.execute(_GATHER_SQL, (since, until))
        rows = cursor.fetchall()

        # Dedup por (surface_norm, type) preservando o primeiro sample.
        seen_keys: Dict[tuple, dict] = {}
        for surface, etype, sample_uid in rows:
            surface_norm = normalize(surface)
            if not surface_norm:
                continue
            key = (surface_norm, etype)
            if key not in seen_keys:
                seen_keys[key] = {
                    "surface_norm": surface_norm,
                    "type": etype,
                    "sample_unique_id": sample_uid,
                }

        for key, item in seen_keys.items():
            surface_norm, etype = key
            # Já resolvido / em review? pula.
            if _seen_is_terminal(conn, surface_norm, etype):
                continue
            # Já resolvido deterministicamente em entity_alias? pula.
            if gazetteer_lookup(conn, surface_norm, etype) is not None:
                continue
            _upsert_seen_pending(conn, surface_norm, etype, item["sample_unique_id"])
            staged.append(item)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
    logger.info("Step A: %d formas staged (pending)", len(staged))
    return staged


def _seen_is_terminal(conn, surface_norm: str, type: str) -> bool:  # noqa: A002
    """True se a forma já está resolvida ou em needs_review em entity_registry_seen."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT status FROM entity_registry_seen WHERE surface_norm = %s AND type = %s",
            (surface_norm, type),
        )
        row = cursor.fetchone()
        return bool(row and row[0] in ("resolved", "needs_review"))
    finally:
        cursor.close()


def _upsert_seen_pending(conn, surface_norm: str, type: str, sample_unique_id: Optional[str]) -> None:  # noqa: A002
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO entity_registry_seen
                (surface_norm, type, status, sample_unique_id, attempts,
                 first_seen_at, updated_at)
            VALUES (%s, %s, 'pending', %s, 0, NOW(), NOW())
            ON CONFLICT (surface_norm, type) DO UPDATE SET
                sample_unique_id = COALESCE(
                    entity_registry_seen.sample_unique_id, EXCLUDED.sample_unique_id
                ),
                updated_at = NOW()
            """,
            (surface_norm, type, sample_unique_id),
        )
    finally:
        cursor.close()


# =============================================================================
# Step B — resolve pending forms
# =============================================================================


def fetch_pending(conn, limit: int) -> List[dict]:
    """Busca formas pending de entity_registry_seen (até limit)."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT surface_norm, type, sample_unique_id, attempts
            FROM entity_registry_seen
            WHERE status = 'pending'
            ORDER BY first_seen_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()


def _fetch_sample_context(conn, unique_id: Optional[str]) -> str:
    """Lê um trecho de news.content do artigo de amostra (para contexto do LLM)."""
    if not unique_id:
        return ""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT content FROM news WHERE unique_id = %s", (unique_id,))
        row = cursor.fetchone()
        return (row[0] or "") if row else ""
    finally:
        cursor.close()


def _update_seen(
    conn,
    surface_norm: str,
    type: str,  # noqa: A002
    status: str,
    entity_id: Optional[str],
    attempts: int,
    last_error: Optional[str] = None,
) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE entity_registry_seen
            SET status = %s, entity_id = %s, attempts = %s,
                last_error = %s, updated_at = NOW()
            WHERE surface_norm = %s AND type = %s
            """,
            (status, entity_id, attempts, last_error, surface_norm, type),
        )
    finally:
        cursor.close()


def _store_canon_raw(conn, unique_id: Optional[str], form: str, model_id: str, raw_obj: dict) -> None:
    """Grava o raw da canonicalização em news_llm_raw (task='canon'). Não fatal."""
    if not unique_id:
        return
    prompt_hash = hashlib.sha256(form.encode("utf-8")).hexdigest()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO news_llm_raw
                (unique_id, task, model_id, prompt_version, prompt_hash, raw_response)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                unique_id,
                "canon",
                model_id,
                CANON_PROMPT_VERSION,
                prompt_hash,
                Json(raw_obj),
            ),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao gravar canon raw para %s: %s", unique_id, e)
    finally:
        cursor.close()


def resolve_form(
    conn,
    form_norm: str,
    type: str,  # noqa: A002
    sample_unique_id: Optional[str],
    attempts: int,
    *,
    bedrock_client,
    wikidata_client,
    model_id: str,
    dry_run: bool = False,
) -> dict:
    """Resolve UMA forma pending: gazetteer → LLM → wikidata → gates → persistência.

    Returns:
        dict {action, status, entity_id, ...} (decisão final).
    """
    # 1) Gazetteer short-circuit (zero LLM, zero tokens).
    hit = gazetteer_lookup(conn, form_norm, type)
    if hit is not None:
        if not dry_run:
            _update_seen(conn, form_norm, type, "resolved", hit, attempts)
        return {
            "action": "gazetteer",
            "status": "resolved",
            "entity_id": hit,
            "usage": _zero_usage(),
        }

    # 1.5) PER fast-path: pre-check Wikidata sem Bedrock.
    # Funcionários públicos brasileiros raramente têm entrada Wikidata → needs_review direto.
    if type == "PER" and wikidata_client is not None:
        pre_candidates = wikidata_client.search(form_norm)
        if not pre_candidates:
            if not dry_run:
                _update_seen(conn, form_norm, type, "needs_review", None, attempts + 1)
            return {"action": "needs_review", "status": "needs_review",
                    "entity_id": None, "usage": _zero_usage()}

    # 2) LLM canonicalize (Sonnet).
    sample_context = _fetch_sample_context(conn, sample_unique_id)
    canon_result = llm_canonicalize(form_norm, sample_context, model_id, bedrock_client)

    # raw para news_llm_raw (objeto, não string).
    if not dry_run:
        _store_canon_raw(conn, sample_unique_id, form_norm, model_id, canon_result)

    # 3) Wikidata candidates (sem tokens Bedrock — só HTTP Wikidata).
    candidates: List[dict] = []
    if not canon_result.get("not_an_entity"):
        candidates = list_candidates(
            wikidata_client,
            canon_result.get("canonical_name") or form_norm,
            canon_result.get("type") or type,
            canon_result.get("wikidata_query") or form_norm,
        )

    # 4) Gates (pode fazer 1 chamada extra de escalada).
    decision = apply_gates(
        form=form_norm,
        canon=canon_result,
        candidates=candidates,
        sample_context=sample_context,
        model_id=model_id,
        bedrock_client=bedrock_client,
    )

    # Total de tokens desta forma = canonicalização + (eventual) escalada.
    total_usage = _add_usage(
        dict(canon_result.get("usage") or _zero_usage()), decision.get("usage")
    )
    decision["usage"] = total_usage

    if dry_run:
        return decision

    # 5) Persistência conforme a decisão.
    _persist_decision(conn, form_norm, type, attempts, decision)
    return decision


def _persist_decision(conn, form_norm: str, type: str, attempts: int, decision: dict) -> None:  # noqa: A002
    """Escreve entity_registry/entity_alias e atualiza seen conforme a decisão."""
    action = decision["action"]
    canon_result = decision.get("canon") or {}
    resolved_type = canon_result.get("type") or type
    canonical_name = canon_result.get("canonical_name") or form_norm
    aliases = canon_result.get("aliases") or [form_norm]
    confidence = canon_result.get("confidence")

    if action == "drop":
        # não-entidade: resolved, entity_id NULL, sem alias.
        _update_seen(conn, form_norm, type, "resolved", None, attempts + 1)
        return

    if action == "needs_review":
        _update_seen(conn, form_norm, type, "needs_review", None, attempts + 1)
        return

    # action ∈ {link, internal}: determina entity_id (com reuso) e persiste.
    qid = decision.get("qid")
    link = decision.get("link") or {}
    provenance = decision.get("provenance")
    is_br_gov_org = bool(canon_result.get("is_br_gov_org"))

    entity_id = None
    wikidata_id = None
    wikidata_url = None
    description = None
    extra: dict = {}

    if action == "link" and qid:
        # (a) reuso por QID exato.
        existing = find_existing_by_wikidata(conn, qid)
        if existing is not None:
            entity_id = existing
        else:
            entity_id = qid
        wikidata_id = qid
        wikidata_url = f"{WIKIDATA_URL_PREFIX}{qid}"
        description = link.get("description")
        if link.get("country"):
            extra["country"] = link.get("country")
        if link.get("instance_of"):
            extra["instance_of"] = link.get("instance_of")
    else:
        # internal (sem QID): reuso por nome para tipos com threshold definido
        # (previne duplicatas dgb_). ORG: threshold 0.62 (histórico); outros:
        # conforme _ENTITY_REUSE_THRESHOLDS.
        threshold = _ENTITY_REUSE_THRESHOLDS.get(resolved_type)
        if threshold is not None:
            existing = find_existing_entity_by_name(conn, canonical_name, resolved_type, threshold)
            if existing is not None:
                entity_id = existing
        if entity_id is None:
            entity_id = mint_internal_id(canonical_name)

    # upsert da entidade (idempotente; não re-chaveia linha existente).
    upsert_entity(
        conn,
        entity_id=entity_id,
        canonical_name=canonical_name,
        type=resolved_type,
        aliases=aliases,
        wikidata_id=wikidata_id,
        wikidata_url=wikidata_url,
        description=description,
        confidence=confidence,
        provenance=provenance,
        extra=extra,
    )

    # alias para a forma resolvida (skip+record em ambiguidade cross-entity).
    if decision.get("write_alias"):
        add_alias(conn, form_norm, resolved_type, entity_id, SOURCE_CANON, confidence)
        # também grava aliases adicionais do LLM (não-ambíguos).
        for alias in aliases:
            alias_norm = normalize(alias)
            if alias_norm and alias_norm != form_norm:
                add_alias(conn, alias_norm, resolved_type, entity_id, SOURCE_CANON, confidence)

    _update_seen(conn, form_norm, type, "resolved", entity_id, attempts + 1)


def _resolve_pending_parallel(
    conn,
    limit: int,
    *,
    bedrock_client,
    wikidata_client,
    model_id: str,
    dry_run: bool,
    daily_quota: Optional[int],
    quota_fraction: float,
    n_workers: int,
    database_url: str,
) -> dict:
    """Variante paralela de resolve_pending com ThreadedConnectionPool.

    Cada worker-thread recebe conexão própria do pool. O budget é checado entre
    lotes (chunk_size = max(n_workers, BUDGET_CHECK_EVERY)); usage é gravado no
    ledger pela thread principal após cada lote para serializar o UPSERT atômico.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from psycopg2.pool import ThreadedConnectionPool

    pending = fetch_pending(conn, limit)
    stats = {
        "resolved": 0, "needs_review": 0, "dropped": 0, "errors": 0,
        "total": len(pending), "budget_exhausted": False,
    }
    has_quota = bool(daily_quota and daily_quota > 0)
    if not has_quota:
        logger.warning("Sem cota diária para %s — modo sem-teto.", model_id)

    pool = ThreadedConnectionPool(1, n_workers + 1, database_url)

    def _run_item(item):
        wconn = pool.getconn()
        try:
            decision = resolve_form(
                wconn,
                item["surface_norm"],
                item["type"],
                item.get("sample_unique_id"),
                item.get("attempts") or 0,
                bedrock_client=bedrock_client,
                wikidata_client=wikidata_client,
                model_id=model_id,
                dry_run=dry_run,
            )
            if not dry_run:
                wconn.commit()
            return decision, None
        except Exception as exc:  # noqa: BLE001
            try:
                wconn.rollback()
                _update_seen(
                    wconn, item["surface_norm"], item["type"], "pending", None,
                    (item.get("attempts") or 0) + 1, str(exc)[:500],
                )
                wconn.commit()
            except Exception:  # noqa: BLE001
                try:
                    wconn.rollback()
                except Exception:  # noqa: BLE001
                    pass
            return None, exc
        finally:
            pool.putconn(wconn)

    try:
        chunk_size = max(n_workers, BUDGET_CHECK_EVERY)
        i = 0
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            while i < len(pending):
                if has_quota and budget_exhausted(conn, model_id, daily_quota, quota_fraction):
                    logger.info(
                        "Budget exhausted para %s — parando no lote %d/%d.",
                        model_id, i, len(pending),
                    )
                    stats["budget_exhausted"] = True
                    break

                batch = pending[i : i + chunk_size]
                i += len(batch)

                futs = {ex.submit(_run_item, item): item for item in batch}
                for fut in as_completed(futs):
                    item = futs[fut]
                    decision, exc = fut.result()
                    if exc is not None:
                        stats["errors"] += 1
                        logger.error(
                            "Erro ao resolver (%r, %s): %s",
                            item["surface_norm"], item["type"], exc,
                        )
                        continue
                    action = decision.get("action")
                    if action == "drop":
                        stats["dropped"] += 1
                    elif decision.get("status") == "needs_review":
                        stats["needs_review"] += 1
                    else:
                        stats["resolved"] += 1
                    if not dry_run:
                        usage = decision.get("usage") or _zero_usage()
                        if usage.get("input_tokens") or usage.get("output_tokens"):
                            record_usage(conn, model_id, usage["input_tokens"], usage["output_tokens"])
    finally:
        pool.closeall()

    logger.info("Step B (parallel n_workers=%d): %s", n_workers, stats)
    return stats


def resolve_pending(
    conn,
    limit: int,
    *,
    bedrock_client,
    wikidata_client,
    model_id: str,
    dry_run: bool = False,
    daily_quota: Optional[int] = None,
    quota_fraction: float = 0.8,
    n_workers: int = 1,
    database_url: Optional[str] = None,
) -> dict:
    """Step B: resolve até `limit` formas pending. Commit por forma (resumível).

    Governador de cota: antes de resolver a cada `BUDGET_CHECK_EVERY` formas,
    checa `budget_exhausted(model_id)` contra o ledger account-wide; se True, para
    gracioso (break) e devolve stats parciais com budget_exhausted=True. Após cada
    forma que consumiu tokens, grava o usage no ledger.

    Sem cota definida (daily_quota None/<=0) → modo sem-teto (apenas grava o ledger).
    Com n_workers > 1 e database_url → executa em paralelo (ThreadedConnectionPool).
    """
    if n_workers > 1 and database_url:
        return _resolve_pending_parallel(
            conn, limit,
            bedrock_client=bedrock_client,
            wikidata_client=wikidata_client,
            model_id=model_id,
            dry_run=dry_run,
            daily_quota=daily_quota,
            quota_fraction=quota_fraction,
            n_workers=n_workers,
            database_url=database_url,
        )

    pending = fetch_pending(conn, limit)
    stats = {
        "resolved": 0, "needs_review": 0, "dropped": 0, "errors": 0,
        "total": len(pending), "budget_exhausted": False,
    }

    has_quota = bool(daily_quota and daily_quota > 0)
    if not has_quota:
        logger.warning(
            "Sem cota diária para %s (BEDROCK_DAILY_TOKEN_QUOTA): modo sem-teto.",
            model_id,
        )

    for i, item in enumerate(pending):
        form_norm = item["surface_norm"]
        etype = item["type"]

        # Governador: checa o budget a cada N formas (margem ~fração).
        if has_quota and i % BUDGET_CHECK_EVERY == 0 and budget_exhausted(
            conn, model_id, daily_quota, quota_fraction
        ):
            logger.info(
                "Budget exhausted para %s — parando gracioso após %d/%d formas.",
                model_id, i, len(pending),
            )
            stats["budget_exhausted"] = True
            break

        try:
            decision = resolve_form(
                conn,
                form_norm,
                etype,
                item.get("sample_unique_id"),
                item.get("attempts") or 0,
                bedrock_client=bedrock_client,
                wikidata_client=wikidata_client,
                model_id=model_id,
                dry_run=dry_run,
            )
            if not dry_run:
                conn.commit()
                # Contabiliza tokens desta forma no ledger (gazetteer = 0, no-op leve).
                usage = decision.get("usage") or _zero_usage()
                if usage.get("input_tokens") or usage.get("output_tokens"):
                    record_usage(
                        conn, model_id, usage["input_tokens"], usage["output_tokens"]
                    )
            action = decision.get("action")
            if action == "drop":
                stats["dropped"] += 1
            elif decision.get("status") == "needs_review":
                stats["needs_review"] += 1
            else:
                stats["resolved"] += 1
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            stats["errors"] += 1
            logger.error("Erro ao resolver forma (%r, %s): %s", form_norm, etype, e)
            try:
                _update_seen(
                    conn, form_norm, etype, "pending", None,
                    (item.get("attempts") or 0) + 1, str(e)[:500],
                )
                conn.commit()
            except Exception:
                conn.rollback()

    logger.info("Step B: %s", stats)
    return stats


# =============================================================================
# Step C — backfill canonical_id nas menções
# =============================================================================

_BACKFILL_SELECT_SQL = """
SELECT nf.unique_id, nf.features
FROM news_features nf
JOIN news n ON n.unique_id = nf.unique_id
WHERE n.published_at >= %s AND n.published_at < %s
  AND nf.features ? 'entities'
"""


def _resolve_alias_map(conn) -> Dict[tuple, str]:
    """Carrega o mapa (alias_norm, type) → entity_id de entity_alias (cache)."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT alias_norm, type, entity_id FROM entity_alias")
        return {(r[0], r[1]): r[2] for r in cursor.fetchall()}
    finally:
        cursor.close()


def backfill_canonical_ids(conn, since: datetime, until: datetime, dry_run: bool = False) -> dict:
    """Step C: anexa canonical_id às menções resolvidas (idempotente, merge-safe).

    Para cada artigo da janela, lê features.entities, resolve canonical_id via
    entity_alias[normalize(forma_canonica|text), type] e regrava só o array
    entities com jsonb_set (preserva outras chaves de features).
    """
    alias_map = _resolve_alias_map(conn)
    cursor = conn.cursor()
    stats = {"articles": 0, "updated": 0, "mentions_linked": 0}
    try:
        cursor.execute(_BACKFILL_SELECT_SQL, (since, until))
        rows = cursor.fetchall()
    finally:
        cursor.close()

    for unique_id, features in rows:
        stats["articles"] += 1
        entities = (features or {}).get("entities") or []
        new_entities, linked, changed = _apply_canonical_ids(entities, alias_map)
        if not changed:
            continue
        stats["mentions_linked"] += linked
        if dry_run:
            stats["updated"] += 1
            continue
        ucur = conn.cursor()
        try:
            ucur.execute(
                """
                UPDATE news_features
                SET features = jsonb_set(features, '{entities}', %s::jsonb, true)
                WHERE unique_id = %s
                """,
                (json_dumps(new_entities), unique_id),
            )
            conn.commit()
            stats["updated"] += 1
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            logger.error("Falha no backfill de %s: %s", unique_id, e)
        finally:
            ucur.close()

    logger.info("Step C: %s", stats)
    return stats


def _apply_canonical_ids(entities: List[dict], alias_map: Dict[tuple, str]):
    """Aplica canonical_id às menções via alias_map. Retorna (novas, linked, changed).

    - Menção resolvida → entity['canonical_id'] = entity_id.
    - Não resolvida → mantém SEM canonical_id (não escreve null espúrio se ausente).
    - Idempotente: se canonical_id já está correto, não conta como mudança.
    """
    new_entities: List[dict] = []
    linked = 0
    changed = False
    for ent in entities:
        ent = dict(ent)  # cópia rasa
        surface = ent.get("forma_canonica") or ent.get("text")
        etype = ent.get("type")
        key = (normalize(surface), etype)
        resolved = alias_map.get(key)
        if resolved is not None:
            linked += 1
            if ent.get("canonical_id") != resolved:
                ent["canonical_id"] = resolved
                changed = True
        new_entities.append(ent)
    return new_entities, linked, changed


def json_dumps(obj) -> str:
    """json.dumps com ensure_ascii=False (acentos preservados no JSONB)."""
    return json.dumps(obj, ensure_ascii=False)


# =============================================================================
# Dedup — near-duplicate entity detection + merge
# =============================================================================

# Thresholds dedicados ao cleanup retroativo (--dedup), distintos dos de
# mint-time (_ENTITY_REUSE_THRESHOLDS). O merge retroativo varre TODAS as
# entidades existentes de um tipo, então um threshold agressivo gera falsos
# positivos (ex.: ORG 0.62 fundiria "Banco Central do Brasil" com "Banco do
# Brasil", Jaccard 0.75). ORG sobe para 0.85; variantes legítimas por sigla
# (ex.: "Ministério da Educação" ↔ "Ministério da Educação (MEC)", também 0.75)
# são capturadas pelo detector determinístico _is_acronym_variant, não pelo
# threshold. Demais tipos mantêm o threshold de mint-time.
_DEDUP_THRESHOLDS: Dict[str, float] = {
    **_ENTITY_REUSE_THRESHOLDS,
    "ORG": 0.85,
}


def run_dedup(
    conn,
    *,
    entity_type: Optional[str] = None,
    dry_run: bool = False,
    threshold: Optional[float] = None,
) -> dict:
    """Encontra e merge entidades near-duplicate em entity_registry.

    Para cada tipo em _DEDUP_THRESHOLDS (ou só entity_type se fornecido):
    1. Busca todas as entidades do tipo.
    2. Compara pares por similaridade Jaccard de tokens.
    3. Merge quando: score >= threshold de dedup do tipo OU os nomes são uma
       variante por sigla (_is_acronym_variant). O OR pelo detector de sigla
       permite fundir "Ministério da Educação" ↔ "Ministério da Educação (MEC)"
       (Jaccard 0.75 < 0.85) sem rebaixar o threshold a ponto de fundir bancos/
       polícias distintos (também 0.75, mas NÃO variantes por sigla).
       No dry_run só loga; no apply executa merge_entities.
       Ao merging: source = entidade com MENOS aliases em entity_alias (ou menor
       entity_id como desempate). target = entidade com MAIS aliases.

    O threshold de dedup ORG é 0.85 (dedicado), distinto do de mint-time (0.62).
    O arg `threshold=` explícito, quando fornecido, sobrepõe tudo (inclusive a
    cláusula de sigla NÃO é necessária — qualquer par >= threshold mergeia).

    Returns:
        {"merged": int, "proposed": int, "types_processed": list[str]}
    """
    types_to_process: List[str] = []
    if entity_type is not None:
        types_to_process = [entity_type]
    else:
        types_to_process = list(_DEDUP_THRESHOLDS.keys())

    merged_total = 0
    proposed_total = 0

    for etype in types_to_process:
        thr = threshold if threshold is not None else _DEDUP_THRESHOLDS.get(etype, 0.70)

        # Fetch all entities of this type.
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT entity_id, canonical_name FROM entity_registry WHERE type = %s",
                (etype,),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

        if len(rows) < 2:
            continue

        # Count aliases per entity_id in Python (avoid extra SQL round-trips in tests).
        # Build a map: entity_id -> alias count from entity_alias
        alias_cursor = conn.cursor()
        try:
            alias_cursor.execute("SELECT alias_norm, type, entity_id FROM entity_alias")
            all_aliases = alias_cursor.fetchall()
        finally:
            alias_cursor.close()

        alias_count: Dict[str, int] = {}
        for _anorm, _atype, eid in all_aliases:
            alias_count[eid] = alias_count.get(eid, 0) + 1

        # Compare pairs (O(n^2), acceptable for small registries per type).
        # Track which entity_ids have already been merged (source) to avoid
        # merging deleted entities.
        merged_sources: set = set()

        for i in range(len(rows)):
            eid_a, name_a = rows[i]
            if eid_a in merged_sources:
                continue
            tokens_a = _name_tokens(name_a)

            for j in range(i + 1, len(rows)):
                eid_b, name_b = rows[j]
                if eid_b in merged_sources:
                    continue
                tokens_b = _name_tokens(name_b)

                score = _jaccard(tokens_a, tokens_b)
                acronym_match = _is_acronym_variant(name_a, name_b)
                if score < thr and not acronym_match:
                    continue

                # Razão do merge (auditoria): threshold de similaridade vs.
                # detector determinístico de variante por sigla.
                if score >= thr:
                    reason = f"Jaccard={score:.3f} >= {thr:.3f}"
                else:
                    reason = f"acronym-variant (Jaccard={score:.3f} < {thr:.3f})"

                proposed_total += 1
                logger.info(
                    "Dedup %s: '%s' ↔ '%s' [%s] %s",
                    etype, name_a, name_b, reason,
                    "[dry-run]" if dry_run else "[merge]",
                )

                if dry_run:
                    continue

                # Decide source (fewer aliases) and target (more aliases).
                count_a = alias_count.get(eid_a, 0)
                count_b = alias_count.get(eid_b, 0)

                if count_a > count_b:
                    target_id, source_id = eid_a, eid_b
                elif count_b > count_a:
                    target_id, source_id = eid_b, eid_a
                else:
                    # Tie-break: lexicographically smaller id is target (stable).
                    if eid_a <= eid_b:
                        target_id, source_id = eid_a, eid_b
                    else:
                        target_id, source_id = eid_b, eid_a

                try:
                    merge_entities(conn, source_id, target_id)
                    conn.commit()
                    merged_total += 1
                    merged_sources.add(source_id)
                    # Update alias_count so subsequent pairs are accurate.
                    alias_count[target_id] = alias_count.get(target_id, 0) + alias_count.get(source_id, 0)
                    alias_count.pop(source_id, None)
                except Exception as exc:  # noqa: BLE001
                    conn.rollback()
                    logger.error("Falha ao mergear %s → %s: %s", source_id, target_id, exc)

    logger.info(
        "run_dedup: types=%s proposed=%d merged=%d dry_run=%s",
        types_to_process, proposed_total, merged_total, dry_run,
    )
    return {
        "merged": merged_total,
        "proposed": proposed_total,
        "types_processed": types_to_process,
    }


# =============================================================================
# CLI
# =============================================================================


def _parse_window(since_arg: Optional[str], until_arg: Optional[str]):
    """Resolve a janela [since, until). Default ≈ últimos 30 dias."""
    now = datetime.now(timezone.utc)
    until = datetime.fromisoformat(until_arg) if until_arg else now
    if since_arg:
        since = datetime.fromisoformat(since_arg)
    else:
        since = until - timedelta(days=DEFAULT_WINDOW_DAYS)
    return since, until


def _build_bedrock_client(region: str):
    """Constrói o BedrockLLMClient (lazy import para não exigir boto3 nos testes)."""
    from .llm_client import BedrockLLMClient

    return BedrockLLMClient(region=region)


def _build_wikidata_client():
    from .wikidata_client import WikidataClient

    return WikidataClient()


def run_canonicalization(
    database_url: str,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    dry_run: bool = False,
    region: str = "us-east-1",
    model_id: Optional[str] = None,
    bedrock_client=None,
    wikidata_client=None,
    n_workers: int = 1,
) -> dict:
    """Orquestra Steps A/B/C. bedrock_client/wikidata_client injetáveis (testes)."""
    since_dt, until_dt = _parse_window(since, until)
    model_id = model_id or get_canon_model_id()

    # Governador de cota: quota por modelo (JSON) + fração (default 0.8) via env.
    quota_cfg = parse_daily_quota_env()
    daily_quota = quota_cfg["quota"].get(model_id)
    quota_fraction = quota_cfg["fraction"]

    conn = psycopg2.connect(database_url)
    try:
        if bedrock_client is None:
            bedrock_client = _build_bedrock_client(region)
        if wikidata_client is None:
            wikidata_client = _build_wikidata_client()

        gather_forms(conn, since_dt, until_dt)
        resolve_stats = resolve_pending(
            conn,
            limit,
            bedrock_client=bedrock_client,
            wikidata_client=wikidata_client,
            model_id=model_id,
            dry_run=dry_run,
            daily_quota=daily_quota,
            quota_fraction=quota_fraction,
            n_workers=n_workers,
            database_url=database_url,
        )
        backfill_stats = backfill_canonical_ids(conn, since_dt, until_dt, dry_run=dry_run)
    finally:
        conn.close()

    return {
        "window": {"since": since_dt.isoformat(), "until": until_dt.isoformat()},
        "model_id": model_id,
        "resolve": resolve_stats,
        "backfill": backfill_stats,
        "dry_run": dry_run,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Canonicalização de entidades (Fase 3)."
    )
    parser.add_argument("--since", default=None, help="Início da janela (ISO, published_at).")
    parser.add_argument("--until", default=None, help="Fim da janela (ISO, exclusivo).")
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help="Máximo de formas distintas resolvidas nesta execução (guard de custo).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Não escreve em entity_registry/entity_alias/news_features.",
    )
    parser.add_argument("--region", default="us-east-1", help="Região AWS do Bedrock.")
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Concorrência de chamadas Bedrock (1=sequencial; recomendado: 10).",
    )
    parser.add_argument(
        "--dedup", action="store_true", default=False,
        help="Encontra e merge entidades near-duplicate (mesmo tipo, nome similar).",
    )
    parser.add_argument(
        "--dedup-type", default=None,
        help="Tipo de entidade para dedup (ex: LAW, ORG). Se omitido, todos os tipos com threshold definido.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args(argv)

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.error("DATABASE_URL não definido")
        return 1

    if args.dedup:
        import psycopg2 as _psycopg2
        conn = _psycopg2.connect(database_url)
        try:
            result = run_dedup(
                conn,
                entity_type=args.dedup_type,
                dry_run=args.dry_run,
            )
        finally:
            conn.close()
        logger.info("Resultado dedup: %s", result)
        return 0

    result = run_canonicalization(
        database_url,
        since=args.since,
        until=args.until,
        limit=args.limit,
        dry_run=args.dry_run,
        region=args.region,
        n_workers=args.workers,
    )
    logger.info("Resultado: %s", result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
