"""
Canonicalização de entidades (Fase 3) — núcleo lógico.

Funções (quase) puras e testáveis que transformam uma forma-de-superfície
distinta numa entidade canônica em `entity_registry`, com resolver determinístico
em `entity_alias` e backfill de `canonical_id` nas menções de `news_features`.

Fluxo por forma distinta:
    gazetteer_lookup (zero LLM)
      └─ miss → llm_canonicalize (Opus) → link_wikidata → apply_gates
                  └─ escreve entity_registry (+reuse) / entity_alias.

Princípios:
  - Bedrock e Wikidata SEMPRE mockados nos testes; nenhuma chamada real na suíte.
  - O id do modelo Opus é configurável por env (CANON_MODEL_ID) — nunca hardcode.
  - Parsers tolerantes: resposta malformada → default seguro, NUNCA levanta.
  - normalize() é byte-idêntico ao helper da migração 017 do data-platform, para
    que lookups de alias batam nas linhas semeadas.
"""

import hashlib
import json
import logging
import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# Config
# =============================================================================

# ID do modelo de canonicalização (inference-profile do Bedrock).
# SEMPRE configurável por env CANON_MODEL_ID — NUNCA hardcode adivinhado.
#
# Em produção (Terraform) CANON_MODEL_ID = "us.anthropic.claude-sonnet-4-6"
# (Sonnet 4.6 — confirmado funcionando; Opus 4.8 dá AccessDenied). Opus 4.6 segue
# disponível como upgrade futuro de qualidade, sem mudança de código (só env).
# O placeholder abaixo serve APENAS para dev/testes locais (sem env) e é sempre
# sobreposto pela env no deploy.
CANON_MODEL_ID_PLACEHOLDER = "anthropic.claude-3-haiku-20240307-v1:0"


def get_canon_model_id() -> str:
    """Resolve o id do modelo de canonicalização (env CANON_MODEL_ID)."""
    return os.environ.get("CANON_MODEL_ID") or CANON_MODEL_ID_PLACEHOLDER


# Versão do prompt de canonicalização (rastreabilidade/idempotência em news_llm_raw).
CANON_PROMPT_VERSION = "canon-v1"

# Tipos sancionados (mesma taxonomia da Fase 2).
SANCTIONED_ENTITY_TYPES = frozenset(
    {"ORG", "PER", "LOC", "EVENT", "POLICY", "LAW", "WORK", "PRODUCT"}
)

_TYPE_TAIL_NORMALIZATION = {
    "PROGRAM": "POLICY",
    "PROGRAMA": "POLICY",
    "DECRETO": "POLICY",
    "DECREE": "POLICY",
    "AWARD": "EVENT",
    "PREMIO": "EVENT",
    "PRÊMIO": "EVENT",
}

# Limiares dos gates (espelham a Fase 3 do plano).
AUTOLINK_CONFIDENCE = 0.85
NEEDS_REVIEW_CONFIDENCE = 0.70

# Limiar de similaridade (Jaccard de tokens) para reuso de ORG existente
# (proxy local de trigram quando não há pg_trgm disponível no caminho de teste).
# 0.85: o antigo 0.62 era falso-positivo demais ("Banco do Brasil" reusaria
# "Banco Central do Brasil", Jaccard 0.75). Variantes legítimas por sigla
# ("Ministério da Educação" ↔ "Ministério da Educação (MEC)", também 0.75) são
# preservadas pela cláusula OR _is_acronym_variant nos finders, não pelo limiar.
ORG_REUSE_SIMILARITY = 0.85

# Limiares de similaridade para reuso por tipo (previne duplicatas dgb_).
_ENTITY_REUSE_THRESHOLDS: dict[str, float] = {
    "ORG":     0.85,   # herdado do ORG_REUSE_SIMILARITY (subiu de 0.62; ver acima)
    "LAW":     0.75,   # lei 14.967/2024 vs lei nº 14.967, de 9 de setembro de 2024
    "POLICY":  0.70,
    "PROGRAM": 0.70,
    "EVENT":   0.80,
}


# =============================================================================
# normalize() — byte-idêntico ao helper da migração 017 do data-platform
# =============================================================================


def normalize(s: Optional[str]) -> str:
    """Normaliza uma forma de superfície numa chave de texto.

    NFKD -> drop não-ASCII -> lowercase -> colapsa whitespace interno -> strip.
    Espaços são preservados (é uma chave de texto, não um slug).

    Deve ser BYTE-IDÊNTICO a data-platform/scripts/migrations/
    017_seed_entity_registry_from_agencies.py::normalize, senão os lookups de
    alias não batem nas linhas semeadas.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def slugify(s: Optional[str]) -> str:
    """Slug ASCII para mintar `dgb_<slug>` quando não há QID."""
    norm = normalize(s)
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    return slug


# entity_registry.entity_id é VARCHAR(64). Mantemos os ids dentro desse limite.
_ENTITY_ID_MAX_LEN = 64
_MINT_PREFIX = "dgb_"
# Quando o slug não cabe, truncamos e anexamos um sufixo de hash determinístico
# para preservar unicidade: dgb_ (4) + slug[:52] (52) + _ (1) + hash6 (6) = 63 ≤ 64.
_MINT_SLUG_TRUNC = 52
_MINT_HASH_LEN = 6


def mint_internal_id(canonical_name: str) -> str:
    """Mint de id interno `dgb_<slug>` para entidade sem QID (≤ 64 chars).

    - Nome curto: `dgb_<slug>` (determinístico; ids existentes NÃO mudam).
    - Nome longo (slug que estouraria VARCHAR(64)): trunca o slug a 52 chars e
      anexa `_<hash6>` (sha1 do canonical_name completo) → determinístico e único.
    """
    slug = slugify(canonical_name)
    candidate = f"{_MINT_PREFIX}{slug}"
    if len(candidate) <= _ENTITY_ID_MAX_LEN:
        return candidate
    truncated = slug[:_MINT_SLUG_TRUNC].rstrip("-")
    digest = hashlib.sha1(canonical_name.encode("utf-8")).hexdigest()[:_MINT_HASH_LEN]
    return f"{_MINT_PREFIX}{truncated}_{digest}"


# =============================================================================
# Gazetteer (determinístico, zero LLM)
# =============================================================================


def gazetteer_lookup(conn, surface_norm: str, type: str) -> Optional[str]:  # noqa: A002
    """Hit exato em entity_alias (resolver determinístico, zero LLM).

    Args:
        conn: conexão psycopg2.
        surface_norm: forma já normalizada (normalize()).
        type: tipo da entidade (ORG/PER/...).

    Returns:
        entity_id se houver hit; None caso contrário.
    """
    if not surface_norm or not type:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT entity_id FROM entity_alias WHERE alias_norm = %s AND type = %s",
            (surface_norm, type),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()


# =============================================================================
# LLM canonicalize (Opus) — prompt PT + parser tolerante
# =============================================================================


def build_canon_prompt(form: str, sample_context: str) -> str:
    """Constrói o prompt PT de canonicalização (determinístico para o mesmo input)."""
    context_preview = (sample_context or "")[:1500]
    prompt = f"""Você é um especialista em desambiguação e canonicalização de entidades nomeadas em notícias governamentais brasileiras.

Recebe UMA forma de superfície (como apareceu em notícias) e um trecho de contexto. Sua tarefa é descrever a entidade canônica correspondente. Responda APENAS com um JSON válido (sem markdown, sem comentários, sem explicações).

TIPOS VÁLIDOS: ORG, PER, LOC, EVENT, POLICY, LAW, WORK, PRODUCT.

REGRAS:
- "canonical_name": o nome canônico mais completo e correto da entidade (resolva siglas e variações). Ex.: "Finep" e "Financiadora de Estudos e Projetos (Finep)" têm o mesmo canonical_name "Financiadora de Estudos e Projetos (Finep)".
- "type": um dos tipos válidos acima.
- "aliases": lista de formas de superfície alternativas conhecidas (siglas, nome completo, variações comuns). Inclua a própria forma recebida.
- "wikidata_query": a melhor string de busca para encontrar esta entidade no Wikidata (geralmente o canonical_name; para órgãos brasileiros, prefira o nome em português).
- "is_br_gov_org": true SOMENTE se for um órgão/entidade do GOVERNO BRASILEIRO (ministério, autarquia, empresa pública, agência federal/estadual/municipal). false para empresas privadas, pessoas, lugares, ou órgãos estrangeiros.
- "confidence": número entre 0.0 e 1.0 indicando o quão seguro você está da identificação canônica.
- "not_an_entity": true se a forma recebida NÃO é uma entidade nomeada (tópico genérico como "inteligência artificial"; grupo demográfico como "mulheres"; cargo genérico; número/data solta). Quando true, os demais campos podem ser vazios.

IMPORTANTE — HOMÔNIMOS: NÃO funda entidades distintas que compartilham nome. "Ministério da Saúde" (Brasil) e "Ministério da Saúde do Líbano" são entidades DIFERENTES (países diferentes). Reflita o país no canonical_name quando necessário para distinguir.

FORMA RECEBIDA: {form}

CONTEXTO (trecho de notícia onde a forma apareceu):
{context_preview}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "canonical_name": "Financiadora de Estudos e Projetos (Finep)",
  "type": "ORG",
  "aliases": ["Finep", "FINEP", "Financiadora de Estudos e Projetos"],
  "wikidata_query": "Financiadora de Estudos e Projetos",
  "is_br_gov_org": true,
  "confidence": 0.96,
  "not_an_entity": false
}}"""
    return prompt


def _canon_safe_default(form: str) -> dict:
    """Default seguro quando a resposta do LLM é inutilizável."""
    return {
        "canonical_name": form,
        "type": None,
        "aliases": [form] if form else [],
        "wikidata_query": form,
        "is_br_gov_org": False,
        "confidence": 0.0,
        "not_an_entity": False,
    }


def parse_canon_response(response: str, form: str) -> dict:
    """Parser tolerante da resposta de canonicalização.

    Malformado/ausente → default seguro (NUNCA levanta). Valida `type` contra o
    conjunto sancionado (com normalização de cauda); type inválido → None.
    """
    if not response:
        return _canon_safe_default(form)

    parsed = _extract_json_object(response)
    if not isinstance(parsed, dict):
        return _canon_safe_default(form)

    out = _canon_safe_default(form)

    canonical_name = parsed.get("canonical_name")
    if isinstance(canonical_name, str) and canonical_name.strip():
        out["canonical_name"] = canonical_name.strip()

    raw_type = parsed.get("type")
    out["type"] = _validate_type(raw_type)

    aliases = parsed.get("aliases")
    out["aliases"] = _clean_aliases(aliases, form)

    wq = parsed.get("wikidata_query")
    if isinstance(wq, str) and wq.strip():
        out["wikidata_query"] = wq.strip()
    else:
        out["wikidata_query"] = out["canonical_name"]

    out["is_br_gov_org"] = bool(parsed.get("is_br_gov_org", False))
    out["not_an_entity"] = bool(parsed.get("not_an_entity", False))

    conf = parsed.get("confidence")
    out["confidence"] = _clamp_confidence(conf)

    return out


def _validate_type(raw_type) -> Optional[str]:
    """Valida/normaliza o tipo contra o conjunto sancionado; None se inválido."""
    if not isinstance(raw_type, str) or not raw_type.strip():
        return None
    t = raw_type.strip().upper()
    t = _TYPE_TAIL_NORMALIZATION.get(t, t)
    return t if t in SANCTIONED_ENTITY_TYPES else None


def _clean_aliases(aliases, form: str) -> List[str]:
    """Normaliza a lista de aliases para strings distintas; garante incluir `form`."""
    out: List[str] = []
    seen = set()
    if isinstance(aliases, list):
        for a in aliases:
            if isinstance(a, str) and a.strip():
                v = a.strip()
                if v not in seen:
                    seen.add(v)
                    out.append(v)
    if form and form not in seen:
        out.append(form)
    return out


def _clamp_confidence(conf) -> float:
    """Coage confidence para float em [0,1]; default 0.0."""
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return 0.0
    if c < 0.0:
        return 0.0
    if c > 1.0:
        return 1.0
    return c


def _extract_json_object(response: str):
    """Extrai o primeiro objeto JSON de um texto (tolera markdown). None se falhar."""
    start = response.find("{")
    end = response.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(response[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None


def _zero_usage() -> Dict[str, int]:
    return {"input_tokens": 0, "output_tokens": 0}


def _add_usage(acc: Dict[str, int], delta: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Soma tokens de `delta` em `acc` (in-place-safe). delta None → no-op."""
    if not delta:
        return acc
    acc["input_tokens"] = int(acc.get("input_tokens", 0)) + int(delta.get("input_tokens", 0) or 0)
    acc["output_tokens"] = int(acc.get("output_tokens", 0)) + int(delta.get("output_tokens", 0) or 0)
    return acc


def _extract_usage(response_body: dict) -> Dict[str, int]:
    """Extrai usage{input_tokens,output_tokens} do corpo Anthropic-on-Bedrock (→ 0)."""
    usage = (response_body or {}).get("usage") or {}
    try:
        in_tok = int(usage.get("input_tokens", 0) or 0)
    except (TypeError, ValueError):
        in_tok = 0
    try:
        out_tok = int(usage.get("output_tokens", 0) or 0)
    except (TypeError, ValueError):
        out_tok = 0
    return {"input_tokens": in_tok, "output_tokens": out_tok}


def llm_canonicalize(form: str, sample_context: str, model_id: str, bedrock_client) -> dict:
    """Chamada Sonnet de canonicalização para UMA forma distinta.

    Args:
        form: forma de superfície distinta (não normalizada).
        sample_context: trecho de news.content de um artigo de amostra.
        model_id: id do modelo de canonicalização (CANON_MODEL_ID).
        bedrock_client: BedrockLLMClient (ou compatível) com `.client.invoke_model`.

    Returns:
        dict canonicalizado (parse tolerante). Em falha de Bedrock → default seguro.
        Sempre inclui a chave `usage` (tokens da chamada) para o ledger de cota.
    """
    prompt = build_canon_prompt(form, sample_context)
    raw, usage = _invoke_bedrock_text(bedrock_client, model_id, prompt, max_tokens=800)
    if raw is None:
        out = _canon_safe_default(form)
        out["usage"] = usage
        return out
    out = parse_canon_response(raw, form)
    out["usage"] = usage
    return out


def _invoke_bedrock_text(
    bedrock_client, model_id: str, prompt: str, max_tokens: int = 800
) -> Tuple[Optional[str], Dict[str, int]]:
    """Invoca o Bedrock (Anthropic messages) e devolve (texto, usage).

    Em falha → (None, usage zerado). usage = {input_tokens, output_tokens} extraído
    do corpo da resposta (para o ledger de cota); campos ausentes → 0. O caller
    grava o usage; este módulo permanece SEM dependência de conexão de DB.
    """
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        response = bedrock_client.client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
        )
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"], _extract_usage(response_body)
    except Exception as e:  # noqa: BLE001 — resiliência: falha → None
        logger.warning("Chamada Bedrock (canon) falhou para modelo %s: %s", model_id, e)
        return None, _zero_usage()


# =============================================================================
# Wikidata linking
# =============================================================================


def link_wikidata(client, canonical_name: str, type: str, wikidata_query: str) -> Optional[dict]:  # noqa: A002
    """Tenta linkar a entidade ao Wikidata, retornando o melhor Q0 candidato BR.

    Esta função NÃO decide o link final (isso é dos gates) — ela coleta os
    candidatos com claims de país e devolve o "primeiro BR" quando há exatamente
    um candidato BR-country (caminho de auto-link simples). Para múltiplos
    candidatos, devolve None aqui e deixa apply_gates/escalada decidir via
    list_candidates().

    Returns:
        {qid, description, country} se houver exatamente um candidato BR-country;
        None caso contrário (0 candidatos, ou múltiplos/ambíguos).
    """
    candidates = list_candidates(client, canonical_name, type, wikidata_query)
    br = [c for c in candidates if c.get("country_is_br")]
    if len(br) == 1:
        c = br[0]
        return {"qid": c["qid"], "description": c.get("description"), "country": c.get("country")}
    return None


def list_candidates(client, canonical_name: str, type: str, wikidata_query: str) -> List[dict]:  # noqa: A002
    """Lista candidatos Wikidata enriquecidos com claims (country/instance_of).

    Returns:
        Lista de dicts {qid, label, description, country, country_is_br, instance_of}.
        Vazia em falha (client resiliente).
    """
    query = wikidata_query or canonical_name
    raw_candidates = client.search(query, type=type)
    enriched: List[dict] = []
    for cand in raw_candidates:
        claims = client.get_claims(cand.qid) or {}
        enriched.append(
            {
                "qid": cand.qid,
                "label": cand.label,
                "description": cand.description or claims.get("description"),
                "country": claims.get("country"),
                "country_is_br": bool(claims.get("country_is_br")),
                "instance_of": claims.get("instance_of", []),
            }
        )
    return enriched


# =============================================================================
# Escalada contextual (homônimos / PER)
# =============================================================================


def build_homonym_prompt(form: str, sample_context: str, candidates: List[dict]) -> str:
    """Prompt de desambiguação contextual entre múltiplos QIDs."""
    context_preview = (sample_context or "")[:2000]
    lines = []
    for i, c in enumerate(candidates):
        country = c.get("country") or "?"
        lines.append(
            f"{i + 1}. QID={c.get('qid')} | {c.get('label')} | "
            f"país={country} | {c.get('description') or ''}"
        )
    candidates_block = "\n".join(lines)
    prompt = f"""Você é um especialista em desambiguação de entidades. Dada uma forma de superfície, um trecho de notícia e uma lista de candidatos do Wikidata, escolha QUAL candidato é o correto NO CONTEXTO, ou indique nenhum.

Responda APENAS com JSON válido: {{"qid": "<QID escolhido ou null>", "confidence": <0.0-1.0>}}

FORMA: {form}

CONTEXTO:
{context_preview}

CANDIDATOS:
{candidates_block}

Se nenhum candidato corresponde claramente ao contexto, responda {{"qid": null, "confidence": 0.0}}."""
    return prompt


def resolve_per_homonym(
    form: str,
    sample_context: str,
    candidates: List[dict],
    model_id: str,
    bedrock_client,
) -> Optional[dict]:
    """Escalada contextual (Sonnet) para desambiguar entre múltiplos QIDs.

    Returns:
        {qid, confidence, usage} com o QID escolhido (que DEVE estar entre os
        candidatos), ou None se o modelo não escolher / responder ruído / qid fora
        da lista. Em falha de Bedrock → None. Quando retorna None mas houve chamada,
        o usage não é perdido: use `resolve_per_homonym_with_usage` para tê-lo.
    """
    result, _usage = resolve_per_homonym_with_usage(
        form, sample_context, candidates, model_id, bedrock_client
    )
    return result


def resolve_per_homonym_with_usage(
    form: str,
    sample_context: str,
    candidates: List[dict],
    model_id: str,
    bedrock_client,
) -> Tuple[Optional[dict], Dict[str, int]]:
    """Como resolve_per_homonym, mas também devolve o usage da chamada (p/ ledger).

    Returns:
        (decisão|None, usage). usage é sempre contabilizado mesmo quando a decisão
        é None (o token gasto na escalada conta para a cota).
    """
    if not candidates:
        return None, _zero_usage()
    prompt = build_homonym_prompt(form, sample_context, candidates)
    raw, usage = _invoke_bedrock_text(bedrock_client, model_id, prompt, max_tokens=200)
    if raw is None:
        return None, usage
    parsed = _extract_json_object(raw)
    if not isinstance(parsed, dict):
        return None, usage
    qid = parsed.get("qid")
    if not isinstance(qid, str) or not qid.strip():
        return None, usage
    qid = qid.strip()
    valid_qids = {c.get("qid") for c in candidates}
    if qid not in valid_qids:
        return None, usage
    return {"qid": qid, "confidence": _clamp_confidence(parsed.get("confidence"))}, usage


# =============================================================================
# Gates de decisão
# =============================================================================


def apply_gates(
    *,
    form: str,
    canon: dict,
    candidates: List[dict],
    sample_context: str,
    model_id: str,
    bedrock_client,
) -> dict:
    """Lógica de decisão da canonicalização (Fase 3).

    Regras (implementadas EXATAMENTE):
      - not_an_entity → drop (seen.resolved, entity_id NULL, sem alias).
      - conf≥0.85 + exatamente um QID BR-country → auto-link (provenance='wikidata').
      - conf≥0.85 + 0 candidatos QID → entidade interna sem link (provenance='llm',
        mint dgb_<slug>).
      - múltiplos QIDs OU conf<0.85 OU type=='PER' → escalar resolve_per_homonym;
        se devolver QID confiante → link; senão se ainda <0.7 → needs_review
        (NÃO escreve entity_alias; seen.status='needs_review').

    Returns:
        dict de decisão:
          {action, status, entity_id, qid, provenance, write_alias, canon, link}
        action ∈ {'drop','link','internal','needs_review'}
        status ∈ {'resolved','needs_review'}
    """
    # 1) não-entidade → drop
    if canon.get("not_an_entity"):
        return _decision(
            action="drop",
            status="resolved",
            entity_id=None,
            qid=None,
            provenance=None,
            write_alias=False,
            canon=canon,
            link=None,
        )

    conf = _clamp_confidence(canon.get("confidence"))
    etype = canon.get("type")
    br_candidates = [c for c in candidates if c.get("country_is_br")]
    needs_escalation = (
        len(candidates) > 1
        or conf < AUTOLINK_CONFIDENCE
        or etype == "PER"
    )

    # 2) auto-link: alta confiança + UM ÚNICO candidato QID (não ambíguo), sem
    #    necessidade de escalada. Um único candidato é inequívoco, seja BR ou
    #    estrangeiro — é exatamente este caminho que mantém "Ministério da Saúde"
    #    (Q BR) e "Ministério da Saúde do Líbano" (Q estrangeiro) como entidades
    #    DISTINTAS (cada forma linka ao seu único QID). O destaque "BR-country" da
    #    spec vale para o caso de MÚLTIPLOS candidatos (escolher o BR), tratado na
    #    escalada abaixo.
    if not needs_escalation and conf >= AUTOLINK_CONFIDENCE and len(candidates) == 1:
        # Preferência: se houver exatamente um candidato BR, é ele; senão o único.
        c = br_candidates[0] if len(br_candidates) == 1 else candidates[0]
        return _decision(
            action="link",
            status="resolved",
            entity_id=c["qid"],
            qid=c["qid"],
            provenance="wikidata",
            write_alias=True,
            canon=canon,
            link=c,
        )

    # 3) alta confiança + 0 candidatos → entidade interna sem link
    if not needs_escalation and conf >= AUTOLINK_CONFIDENCE and len(candidates) == 0:
        return _decision(
            action="internal",
            status="resolved",
            entity_id=None,  # mintado no upsert (dgb_<slug>)
            qid=None,
            provenance="llm",
            write_alias=True,
            canon=canon,
            link=None,
        )

    # 4) escalada contextual (múltiplos QIDs / baixa conf / PER)
    if candidates:
        escalation, esc_usage = resolve_per_homonym_with_usage(
            form, sample_context, candidates, model_id, bedrock_client
        )
        if escalation and escalation.get("qid"):
            esc_conf = _clamp_confidence(escalation.get("confidence"))
            if esc_conf >= NEEDS_REVIEW_CONFIDENCE:
                chosen = next(
                    (c for c in candidates if c.get("qid") == escalation["qid"]), None
                )
                return _decision(
                    action="link",
                    status="resolved",
                    entity_id=escalation["qid"],
                    qid=escalation["qid"],
                    provenance="wikidata",
                    write_alias=True,
                    canon=canon,
                    link=chosen,
                    usage=esc_usage,
                )
        # escalada não chegou a uma escolha confiante → needs_review
        return _decision(
            action="needs_review",
            status="needs_review",
            entity_id=None,
            qid=None,
            provenance=None,
            write_alias=False,
            canon=canon,
            link=None,
            usage=esc_usage,
        )

    # 5) sem candidatos mas precisava escalar (PER sem QID, ou conf baixa) →
    #    se a confiança do LLM ainda é razoável e é entidade clara, mantém interno;
    #    senão needs_review. Conservador: PER sem QID e baixa conf → needs_review.
    if conf >= AUTOLINK_CONFIDENCE and etype != "PER":
        return _decision(
            action="internal",
            status="resolved",
            entity_id=None,
            qid=None,
            provenance="llm",
            write_alias=True,
            canon=canon,
            link=None,
        )

    return _decision(
        action="needs_review",
        status="needs_review",
        entity_id=None,
        qid=None,
        provenance=None,
        write_alias=False,
        canon=canon,
        link=None,
    )


def _decision(
    *, action, status, entity_id, qid, provenance, write_alias, canon, link, usage=None
) -> dict:
    return {
        "action": action,
        "status": status,
        "entity_id": entity_id,
        "qid": qid,
        "provenance": provenance,
        "write_alias": write_alias,
        "canon": canon,
        "link": link,
        # usage da(s) chamada(s) extra(s) feitas DENTRO de apply_gates (escalada).
        # NÃO inclui o usage da llm_canonicalize (esse vem em canon["usage"]).
        "usage": usage or _zero_usage(),
    }


# =============================================================================
# Registry de-dup / agencies reuse
# =============================================================================


def _name_tokens(s: str) -> set:
    """Tokens normalizados de um nome (para similaridade Jaccard)."""
    norm = normalize(s)
    return {t for t in norm.split(" ") if t}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# Captura um grupo parentético (p.ex. "(MEC)").
_PAREN_RE = re.compile(r"\(([^()]*)\)")

# Token de ano (1900–2099) delimitado por fronteira de palavra. Usado para nunca
# fundir EDIÇÕES distintas de um evento/programa ("Enem 2025" vs "Enem 2026",
# "ENGP" vs "ENGP 2026"). NÃO casa dígitos internos de um número maior (ex.: o
# "2024" dentro de "20240" falha o \b final).
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _strip_parens(name: str) -> str:
    """Remove todos os grupos `(...)` de um nome (sem normalizar)."""
    return _PAREN_RE.sub(" ", name)


def _year_tokens(name: str) -> frozenset:
    """Conjunto de anos (4 dígitos, 1900–2099) presentes no nome."""
    if not name:
        return frozenset()
    return frozenset(_YEAR_RE.findall(name))


def differs_by_year(name_a: str, name_b: str) -> bool:
    """True se os dois nomes têm conjuntos de anos DIFERENTES → edições distintas.

    "Copa do Mundo FIFA de 2026" vs "Copa do Mundo FIFA 2026" → {2026}=={2026} →
    False (mesma edição, pode fundir). "ENGP" vs "ENGP 2026" → {}≠{2026} → True
    (edições distintas, NUNCA fundir). "Enem 2025" vs "Enem 2026" → True.
    """
    return _year_tokens(name_a) != _year_tokens(name_b)


def _paren_contents(name: str) -> List[str]:
    """Conteúdos parentéticos de `name`, normalizados a APENAS letras (a-z), em ordem.

    Casing/acentos dobrados via normalize(); não-letras (espaços, pontuação,
    dígitos) descartados. Ex.: "(Finep)" → "finep"; "(Primeira Turma)" →
    "primeiraturma"; "(Líbano)" → "libano". Vazios são omitidos.
    """
    out: List[str] = []
    for m in _PAREN_RE.findall(name):
        letters = "".join(c for c in normalize(m) if c.isalpha())
        if letters:
            out.append(letters)
    return out


def _letters_of(s: str) -> str:
    """Apenas letras (a-z) de `s` após normalize() — espaços/acentos/case removidos."""
    return "".join(c for c in normalize(s) if c.isalpha())


def _is_subsequence(needle: str, haystack: str) -> bool:
    """True se os caracteres de `needle` aparecem, em ordem, dentro de `haystack`.

    Discriminador casing-agnóstico de "sigla derivada do nome-base": as letras de
    uma sigla parentética (ex.: "finep") devem formar uma subsequência das letras
    do nome-base (ex.: "financiadoradeestudoseprojetos"). Qualificadores de
    nova-informação (país/estado/turma: "libano", "bahia", "primeiraturma") NÃO
    são subsequência do base e portanto NÃO qualificam. needle vazio → False.
    """
    if not needle:
        return False
    it = iter(haystack)
    return all(ch in it for ch in needle)


def _is_acronym_variant(name_a: str, name_b: str) -> bool:
    """True se `name_a` e `name_b` são a MESMA entidade diferindo só por sigla.

    Casos confiantes (simétrico):
      (a) Parenthetical strip equality: remover um grupo `(...)` de um dos nomes
          o torna igual (normalizado) ao outro. Ex.: "Ministério da Educação (MEC)"
          → "Ministério da Educação" == o outro.
      (b) Acronym expansion match: o conteúdo parentético (ou o nome inteiro, se
          for uma sigla solta) é o acrônimo das palavras significativas do outro
          nome (ou do seu próprio nome despido). Ex.: "(MEC)" = iniciais de
          "Ministério (da) Educação (e) Cultura".

    Conservador: exige sigla com >=2 letras maiúsculas e match exato das iniciais.
    Retorna False quando não há parêntese nem relação de acrônimo (ex.: "Banco
    Central do Brasil" vs "Banco do Brasil", "Polícia Federal" vs "Polícia
    Rodoviária Federal"). Entradas vazias → False (nunca levanta).
    """
    if not name_a or not name_b:
        return False

    norm_a = normalize(name_a)
    norm_b = normalize(name_b)
    if not norm_a or not norm_b:
        return False

    stripped_a = normalize(_strip_parens(name_a))
    stripped_b = normalize(_strip_parens(name_b))

    # (a) Parenthetical strip equality, COM discriminador de homonímia: despir o
    #     parêntese de um nome o iguala ao outro (ou ao outro despido). MAS isso
    #     só conta como variante por sigla se o parêntese distintivo for uma SIGLA
    #     DERIVADA do nome-base — i.e. suas letras formam uma subsequência das
    #     letras do base (case/acento-insensível). Um qualificador de
    #     nova-informação (país/estado/turma) NÃO é subsequência do base e portanto
    #     são entidades DIFERENTES ("Ministério da Saúde (Brasil)" vs "(Líbano)").
    has_paren_a = stripped_a != norm_a
    has_paren_b = stripped_b != norm_b

    def _all_parens_are_sigla_of_base(name: str, base_letters: str) -> bool:
        contents = _paren_contents(name)
        if not contents:
            return False
        return all(_is_subsequence(c, base_letters) for c in contents)

    # Caso 1: exatamente um lado tem parêntese ("X" vs "X (Y)"); os dois reduzem
    #         ao mesmo base. Merge sse Y é sigla-do-base.
    # Caso 2: ambos têm parêntese reduzindo ao MESMO base ("X (Y1)" vs "X (Y2)").
    #         Merge sse AMBOS Y1 e Y2 são sigla-do-base (ambos só soletram a sigla
    #         da mesma org); se qualquer um for qualificador novo → entidades
    #         distintas → não merge.
    if has_paren_a and stripped_a and (stripped_a == norm_b or stripped_a == stripped_b):
        base_letters = _letters_of(stripped_a)
        ok_a = _all_parens_are_sigla_of_base(name_a, base_letters)
        ok_b = True if not has_paren_b else _all_parens_are_sigla_of_base(name_b, base_letters)
        if ok_a and ok_b:
            return True
    if has_paren_b and stripped_b and (stripped_b == norm_a or stripped_b == stripped_a):
        base_letters = _letters_of(stripped_b)
        ok_b = _all_parens_are_sigla_of_base(name_b, base_letters)
        ok_a = True if not has_paren_a else _all_parens_are_sigla_of_base(name_a, base_letters)
        if ok_a and ok_b:
            return True

    # NOTA: NÃO existe um path (b) de "expansão de acrônimo entre bases
    # diferentes" (ex.: casar "MEC" com "Ministério da Educação e Cultura" só
    # pelas iniciais). Tentativas desse tipo geram falsos-positivos graves em
    # dados reais por DOIS motivos: (1) colisão de sigla — orgs distintas que
    # compartilham acrônimo ("Forças Armadas do Brasil" e "Força Aérea
    # Brasileira" ambas → "FAB"; duas "SPA"); (2) sub-unidade vs pai — a
    # sub-unidade carrega a sigla do pai no parêntese ("Diretoria Colegiada da
    # ANM (ANM)" vs "Agência Nacional de Mineração"), o que é uma relação
    # SUBORDINATE_TO, não um merge. O único sinal confiável para AUTO-merge é o
    # path (a): MESMA base + sigla-do-base anexada. Casos de sigla solta ("MEC"
    # como nome inteiro) são raros no registry e, se surgirem, é mais seguro
    # deixá-los para needs_review do que arriscar fundir entidades distintas.
    return False


def find_existing_by_wikidata(conn, qid: str) -> Optional[str]:
    """Reuso por QID exato: entity_registry.wikidata_id == qid OU entity_id == qid."""
    if not qid:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT entity_id FROM entity_registry "
            "WHERE wikidata_id = %s OR entity_id = %s LIMIT 1",
            (qid, qid),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()


def find_existing_org_by_name(conn, canonical_name: str, threshold: float = ORG_REUSE_SIMILARITY) -> Optional[str]:
    """Reuso de ORG por nome (match forte contra ORGs existentes, esp. dgb_<key>).

    Estratégia:
      1. Tenta similaridade trigram via pg_trgm (`similarity`/`%`) se disponível.
      2. Fallback: compara tokens (Jaccard) em Python contra as ORGs candidatas.

    Returns:
        entity_id da ORG existente com match forte, ou None.
    """
    if not canonical_name:
        return None
    cursor = conn.cursor()
    try:
        # Caminho preferido: pg_trgm. Resiliente — se a função/operador não existir,
        # cai no fallback Python.
        try:
            cursor.execute(
                """
                SELECT entity_id, canonical_name, similarity(canonical_name, %s) AS sim
                FROM entity_registry
                WHERE type = 'ORG'
                ORDER BY sim DESC
                LIMIT 10
                """,
                (canonical_name,),
            )
            rows = cursor.fetchall()
        except Exception:
            # Fallback: pega ORGs e compara em Python.
            try:
                cursor.connection.rollback()
            except Exception:
                pass
            cursor.execute(
                "SELECT entity_id, canonical_name FROM entity_registry WHERE type = 'ORG'"
            )
            rows = [(r[0], r[1], None) for r in cursor.fetchall()]

        target_tokens = _name_tokens(canonical_name)
        best_id = None
        best_score = 0.0
        acronym_id = None
        for row in rows:
            entity_id = row[0]
            cand_name = row[1]
            # Guard de edição: nunca reusar entre nomes que diferem por ano
            # ("Enem 2025" vs "Enem 2026" são edições distintas).
            if differs_by_year(canonical_name, cand_name):
                continue
            trgm_sim = row[2] if len(row) > 2 else None
            jac = _jaccard(target_tokens, _name_tokens(cand_name))
            # combina: usa o maior entre trigram (se houver) e Jaccard de tokens.
            score = max(jac, float(trgm_sim) if trgm_sim is not None else 0.0)
            if score > best_score:
                best_score = score
                best_id = entity_id
            # Reuso por variante de sigla (OR): permite subir o threshold sem
            # perder "Ministério da Educação" ↔ "Ministério da Educação (MEC)".
            if acronym_id is None and _is_acronym_variant(canonical_name, cand_name):
                acronym_id = entity_id
        if best_id is not None and best_score >= threshold:
            return best_id
        if acronym_id is not None:
            return acronym_id
        return None
    finally:
        cursor.close()


def find_existing_entity_by_name(
    conn, canonical_name: str, entity_type: str,
    threshold: float = 0.70,
) -> Optional[str]:
    """Reuso por nome para qualquer tipo (mesma estratégia pg_trgm + Jaccard de find_existing_org_by_name).

    Parametrizado por entity_type — permite usar em LAW, POLICY, PROGRAM, EVENT além de ORG.
    """
    if not canonical_name:
        return None
    cursor = conn.cursor()
    try:
        # Caminho preferido: pg_trgm. Resiliente — se a função/operador não existir,
        # cai no fallback Python.
        try:
            cursor.execute(
                """
                SELECT entity_id, canonical_name, similarity(canonical_name, %s) AS sim
                FROM entity_registry
                WHERE type = %s
                ORDER BY sim DESC
                LIMIT 10
                """,
                (canonical_name, entity_type),
            )
            rows = cursor.fetchall()
        except Exception:
            # Fallback: pega entidades do tipo e compara em Python.
            try:
                cursor.connection.rollback()
            except Exception:
                pass
            cursor.execute(
                "SELECT entity_id, canonical_name FROM entity_registry WHERE type = %s",
                (entity_type,),
            )
            rows = [(r[0], r[1], None) for r in cursor.fetchall()]

        target_tokens = _name_tokens(canonical_name)
        best_id = None
        best_score = 0.0
        acronym_id = None
        for row in rows:
            entity_id = row[0]
            cand_name = row[1]
            # Guard de edição: nunca reusar entre nomes que diferem por ano
            # ("Enem 2025" vs "Enem 2026" são edições distintas).
            if differs_by_year(canonical_name, cand_name):
                continue
            trgm_sim = row[2] if len(row) > 2 else None
            jac = _jaccard(target_tokens, _name_tokens(cand_name))
            # combina: usa o maior entre trigram (se houver) e Jaccard de tokens.
            score = max(jac, float(trgm_sim) if trgm_sim is not None else 0.0)
            if score > best_score:
                best_score = score
                best_id = entity_id
            # Reuso por variante de sigla (OR): permite subir o threshold (ORG 0.85)
            # sem perder "Ministério da Educação" ↔ "Ministério da Educação (MEC)".
            if acronym_id is None and _is_acronym_variant(canonical_name, cand_name):
                acronym_id = entity_id
        if best_id is not None and best_score >= threshold:
            return best_id
        if acronym_id is not None:
            return acronym_id
        return None
    finally:
        cursor.close()


# =============================================================================
# Persistência: upsert_entity / add_alias
# =============================================================================


def upsert_entity(
    conn,
    *,
    entity_id: str,
    canonical_name: str,
    type: str,  # noqa: A002
    aliases: List[str],
    wikidata_id: Optional[str] = None,
    wikidata_url: Optional[str] = None,
    description: Optional[str] = None,
    agency_key: Optional[str] = None,
    confidence: Optional[float] = None,
    provenance: Optional[str] = None,
    extra: Optional[dict] = None,
) -> str:
    """Insere/atualiza uma linha em entity_registry (idempotente por entity_id).

    NUNCA re-chaveia uma linha existente — ON CONFLICT atualiza apenas campos
    aditivos/descritivos (aliases mesclados, description, confidence). Devolve o
    entity_id.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO entity_registry
                (entity_id, canonical_name, type, aliases, wikidata_id, wikidata_url,
                 description, agency_key, confidence, provenance, extra,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb,
                    NOW(), NOW())
            ON CONFLICT (entity_id) DO UPDATE SET
                canonical_name = COALESCE(entity_registry.canonical_name, EXCLUDED.canonical_name),
                description = COALESCE(EXCLUDED.description, entity_registry.description),
                wikidata_id = COALESCE(entity_registry.wikidata_id, EXCLUDED.wikidata_id),
                wikidata_url = COALESCE(entity_registry.wikidata_url, EXCLUDED.wikidata_url),
                confidence = GREATEST(
                    COALESCE(entity_registry.confidence, 0),
                    COALESCE(EXCLUDED.confidence, 0)
                ),
                updated_at = NOW()
            """,
            (
                entity_id,
                canonical_name,
                type,
                json.dumps(aliases or [], ensure_ascii=False),
                wikidata_id,
                wikidata_url,
                description,
                agency_key,
                confidence,
                provenance,
                json.dumps(extra or {}, ensure_ascii=False),
            ),
        )
        return entity_id
    finally:
        cursor.close()


def _rewrite_mentions_canonical_id(conn, source_id: str, target_id: str) -> int:
    """Reescreve canonical_id source→target nas menções de news_features.

    Sem isto, após deletar o source de entity_registry as menções
    (`news_features.features.entities[].canonical_id`) que apontavam para o
    source ficariam órfãs, e a tabela de grafo `news_entities` (FK ON DELETE
    CASCADE) perderia essas linhas no próximo rebuild. Espelha o padrão de
    `backfill_canonical_ids` (Step C): seleciona só os artigos afetados via o
    índice GIN (migração 018), reescreve o array entities em Python e regrava
    com jsonb_set (preserva as outras chaves de features). Idempotente.

    Returns: número de artigos (linhas news_features) atualizados.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT unique_id, features FROM news_features "
            "WHERE features->'entities' @> %s::jsonb",
            (json.dumps([{"canonical_id": source_id}]),),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    updated = 0
    for unique_id, features in rows:
        entities = (features or {}).get("entities") or []
        changed = False
        new_entities = []
        for ent in entities:
            ent = dict(ent)
            if ent.get("canonical_id") == source_id:
                ent["canonical_id"] = target_id
                changed = True
            new_entities.append(ent)
        if not changed:
            continue
        ucur = conn.cursor()
        try:
            ucur.execute(
                "UPDATE news_features "
                "SET features = jsonb_set(features, '{entities}', %s::jsonb, true) "
                "WHERE unique_id = %s",
                (json.dumps(new_entities, ensure_ascii=False), unique_id),
            )
            updated += 1
        finally:
            ucur.close()
    return updated


def merge_entities(conn, source_id: str, target_id: str) -> int:
    """Merge source_id → target_id: migra aliases, herda metadata, deleta source.

    1. Herda wikidata_id/wikidata_url do source para o target (COALESCE — só atualiza se target não tem).
    2. Merge do JSONB aliases: union das listas do target e source.
    3. Reescreve canonical_id source→target nas menções de news_features (evita
       órfãos + perda de arestas no grafo).
    4. Redireciona aliases em entity_alias que apontam para source → target
       (apenas os que não criariam conflito de PK, i.e., (alias_norm, type) ainda não existe no target).
    5. Deleta aliases restantes do source em entity_alias.
    6. Deleta source de entity_registry.

    Returns: número de alias rows migradas (passo 4).
    """
    cursor = conn.cursor()
    try:
        # 1+2: herdar metadata (COALESCE) e merge aliases JSONB
        cursor.execute(
            """
            UPDATE entity_registry AS t SET
                wikidata_id  = COALESCE(t.wikidata_id, s.wikidata_id),
                wikidata_url = COALESCE(t.wikidata_url, s.wikidata_url),
                aliases      = (SELECT jsonb_agg(a) FROM (
                                    SELECT jsonb_array_elements_text(COALESCE(t.aliases, '[]'::jsonb))
                                    UNION
                                    SELECT jsonb_array_elements_text(COALESCE(s.aliases, '[]'::jsonb))
                                ) sub(a)),
                updated_at = NOW()
            FROM entity_registry s
            WHERE t.entity_id = %s AND s.entity_id = %s
            """,
            (target_id, source_id),
        )

        # 3: reescrever canonical_id source→target nas menções (news_features)
        _rewrite_mentions_canonical_id(conn, source_id, target_id)

        # 4: redirecionar aliases sem conflito de PK
        cursor.execute(
            """
            UPDATE entity_alias SET entity_id = %s
            WHERE entity_id = %s
            AND NOT EXISTS (
                SELECT 1 FROM entity_alias ea2
                WHERE ea2.alias_norm = entity_alias.alias_norm
                  AND ea2.type = entity_alias.type
                  AND ea2.entity_id = %s
            )
            """,
            (target_id, source_id, target_id),
        )
        migrated = cursor.rowcount

        # 5: limpar aliases restantes do source
        cursor.execute(
            "DELETE FROM entity_alias WHERE entity_id = %s",
            (source_id,),
        )

        # 6: deletar source da registry
        cursor.execute(
            "DELETE FROM entity_registry WHERE entity_id = %s",
            (source_id,),
        )

        return migrated
    finally:
        cursor.close()


def add_alias(
    conn,
    surface_norm: str,
    type: str,  # noqa: A002
    entity_id: str,
    source: str,
    confidence: Optional[float] = None,
) -> dict:
    """Insere um alias→entity em entity_alias, respeitando ambiguidade cross-entity.

    Se (alias_norm, type) já mapeia para um entity_id DIFERENTE, NÃO sobrescreve:
    pula e registra a ambiguidade (espelha o comportamento da migração 017).

    Returns:
        {"written": bool, "ambiguous": bool, "existing_entity_id": str|None}
    """
    if not surface_norm or not type or not entity_id:
        return {"written": False, "ambiguous": False, "existing_entity_id": None}

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT entity_id FROM entity_alias WHERE alias_norm = %s AND type = %s",
            (surface_norm, type),
        )
        row = cursor.fetchone()
        if row is not None:
            existing = row[0]
            if existing == entity_id:
                # já mapeado para a mesma entidade — no-op idempotente.
                return {"written": False, "ambiguous": False, "existing_entity_id": existing}
            # Wikidata-wins: existing é dgb_ e novo entity_id é QID (não começa com dgb_)
            # → promover o alias para o QID via merge_entities.
            if existing.startswith(_MINT_PREFIX) and not entity_id.startswith(_MINT_PREFIX):
                merge_entities(conn, source_id=existing, target_id=entity_id)
                # Reescreve o alias para apontar para o QID (ON CONFLICT DO UPDATE SET entity_id).
                cursor.execute(
                    """
                    INSERT INTO entity_alias (alias_norm, type, entity_id, source, confidence)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (alias_norm, type) DO UPDATE SET entity_id = EXCLUDED.entity_id
                    """,
                    (surface_norm, type, entity_id, source, confidence),
                )
                return {"written": True, "merged": True, "existing_entity_id": existing}
            # mapeado para entidade DIFERENTE — ambiguidade: não sobrescreve.
            logger.warning(
                "Alias ambíguo cross-entity ignorado: (%r, %s) já aponta para %s, "
                "tentativa para %s",
                surface_norm,
                type,
                existing,
                entity_id,
            )
            return {"written": False, "ambiguous": True, "existing_entity_id": existing}

        cursor.execute(
            """
            INSERT INTO entity_alias (alias_norm, type, entity_id, source, confidence)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (alias_norm, type) DO NOTHING
            """,
            (surface_norm, type, entity_id, source, confidence),
        )
        return {"written": True, "ambiguous": False, "existing_entity_id": None}
    finally:
        cursor.close()
