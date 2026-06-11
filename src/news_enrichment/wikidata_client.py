"""
WikidataClient — linked-data lookups para canonicalização (Fase 3).

Usa as APIs públicas do Wikidata (sem auth) via httpx:
  - `wbsearchentities` para buscar candidatos (QID + label + description);
  - `wbgetentities` para ler claims (P17 country, P31 instance_of) e habilitar
    desambiguação por país (ex.: Ministério da Saúde BR vs do Líbano).

Princípios:
  - Resiliente: QUALQUER falha (HTTP, timeout, parse) → resultado vazio, NUNCA levanta.
  - Cache em memória (por processo) para não repetir a mesma busca/claim no batch.
  - Timeouts curtos + retries limitados com backoff simples.
  - Todo o HTTP é mockado nos testes; nenhuma chamada real na suíte.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
DEFAULT_TIMEOUT = 8.0
DEFAULT_MAX_RETRIES = 2

# A Wikimedia bloqueia (HTTP 403) requisições sem um User-Agent descritivo.
# Politica: https://meta.wikimedia.org/wiki/User-Agent_policy
WIKIDATA_USER_AGENT = (
    "DestaquesGovBr-EntityCanonicalization/1.0 "
    "(https://destaquesgovbr.com.br; contato@destaquesgovbr.com.br)"
)

# Property IDs usados na desambiguação.
P_COUNTRY = "P17"        # país (claim usado para BR vs estrangeiro)
P_INSTANCE_OF = "P31"    # instância de (tipo da entidade)

# QID do "Brasil" no Wikidata — usado para classificar QIDs como BR-country.
QID_BRAZIL = "Q155"


@dataclass(frozen=True)
class Candidate:
    """Candidato retornado pela busca Wikidata."""

    qid: str
    label: str
    description: str


class WikidataClient:
    """Cliente leve para a Wikidata Action API com cache em memória."""

    def __init__(
        self,
        api_url: str = WIKIDATA_API_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        client: Optional[httpx.Client] = None,
    ):
        """
        Args:
            api_url: endpoint da Action API.
            timeout: timeout (s) por requisição.
            max_retries: número máximo de tentativas por requisição.
            client: httpx.Client injetável (para testes); se None, cria um próprio.
        """
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": WIKIDATA_USER_AGENT}
        )
        # Caches em memória (por processo).
        self._search_cache: Dict[tuple, List[Candidate]] = {}
        self._claims_cache: Dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    # HTTP helper                                                         #
    # ------------------------------------------------------------------ #

    def _get_json(self, params: dict) -> Optional[dict]:
        """GET com retries; devolve o JSON decodificado ou None em falha."""
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.get(self.api_url, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:  # noqa: BLE001 — resiliência deliberada
                last_error = e
                logger.warning(
                    "Wikidata tentativa %d/%d falhou (%s): %s",
                    attempt + 1,
                    self.max_retries,
                    params.get("action"),
                    e,
                )
        logger.error("Wikidata desistiu após %d tentativas: %s", self.max_retries, last_error)
        return None

    # ------------------------------------------------------------------ #
    # search                                                              #
    # ------------------------------------------------------------------ #

    def search(
        self,
        name: str,
        type: Optional[str] = None,  # noqa: A002 — espelha a assinatura do contrato
        lang: str = "pt",
        limit: int = 7,
    ) -> List[Candidate]:
        """
        Busca candidatos via `wbsearchentities`.

        `type` é aceito por simetria com o contrato (pode informar heurísticas
        futuras), mas a Action API de busca não filtra por tipo — a desambiguação
        por tipo/país acontece via get_claims + gates.

        Returns:
            Lista de Candidate (possivelmente vazia). Nunca levanta.
        """
        if not name or not name.strip():
            return []

        cache_key = (name.strip().lower(), lang, limit)
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        params = {
            "action": "wbsearchentities",
            "search": name,
            "language": lang,
            "uselang": lang,
            "format": "json",
            "limit": limit,
            "type": "item",
        }
        data = self._get_json(params)
        candidates: List[Candidate] = []
        if data:
            for hit in data.get("search", []) or []:
                qid = hit.get("id")
                if not qid:
                    continue
                label = hit.get("label") or hit.get("match", {}).get("text") or ""
                description = hit.get("description") or ""
                candidates.append(
                    Candidate(qid=qid, label=label, description=description)
                )

        self._search_cache[cache_key] = candidates
        return candidates

    # ------------------------------------------------------------------ #
    # claims                                                              #
    # ------------------------------------------------------------------ #

    def get_claims(self, qid: str) -> dict:
        """
        Lê claims relevantes de um QID via `wbgetentities`.

        Returns:
            dict com chaves possíveis:
              - "country": QID do país (P17), ou None;
              - "country_is_br": bool (country == Q155);
              - "instance_of": lista de QIDs (P31);
              - "label": label em pt/en quando disponível;
              - "description": descrição quando disponível.
            Em falha retorna {} (nunca levanta).
        """
        if not qid:
            return {}
        if qid in self._claims_cache:
            return self._claims_cache[qid]

        params = {
            "action": "wbgetentities",
            "ids": qid,
            "props": "claims|labels|descriptions",
            "languages": "pt|en",
            "format": "json",
        }
        data = self._get_json(params)
        result: dict = {}
        if data:
            entity = (data.get("entities") or {}).get(qid) or {}
            claims = entity.get("claims") or {}

            country = _first_claim_qid(claims, P_COUNTRY)
            instance_of = _all_claim_qids(claims, P_INSTANCE_OF)
            result = {
                "country": country,
                "country_is_br": country == QID_BRAZIL,
                "instance_of": instance_of,
                "label": _pick_label(entity.get("labels")),
                "description": _pick_label(entity.get("descriptions")),
            }

        self._claims_cache[qid] = result
        return result

    def close(self) -> None:
        """Fecha o httpx.Client interno (no-op se injetado externamente)."""
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------- #
# Pure helpers                                                            #
# ---------------------------------------------------------------------- #


def _first_claim_qid(claims: dict, prop: str) -> Optional[str]:
    """Extrai o QID do primeiro statement de `prop` (entity-id datavalue)."""
    for stmt in claims.get(prop, []) or []:
        qid = _statement_qid(stmt)
        if qid:
            return qid
    return None


def _all_claim_qids(claims: dict, prop: str) -> List[str]:
    """Extrai todos os QIDs dos statements de `prop`."""
    qids: List[str] = []
    for stmt in claims.get(prop, []) or []:
        qid = _statement_qid(stmt)
        if qid:
            qids.append(qid)
    return qids


def _statement_qid(stmt: dict) -> Optional[str]:
    """Extrai o QID alvo (wikibase-entityid) de um statement, ou None."""
    try:
        datavalue = stmt["mainsnak"]["datavalue"]
        if datavalue.get("type") != "wikibase-entityid":
            return None
        return datavalue["value"].get("id")
    except (KeyError, TypeError):
        return None


def _pick_label(labels: Optional[dict]) -> Optional[str]:
    """Escolhe um label/descrição em pt, senão en, senão o primeiro disponível."""
    if not labels:
        return None
    for lang in ("pt", "en"):
        if lang in labels:
            return labels[lang].get("value")
    # primeiro disponível
    for value in labels.values():
        if isinstance(value, dict) and value.get("value"):
            return value["value"]
    return None
