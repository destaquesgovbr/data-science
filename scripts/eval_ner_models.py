#!/usr/bin/env python
"""
Avaliação offline de modelos NER contra a referência Sonnet 4.6 (prompt ner-v1).

Subcomandos:
  discover  STS (conta), perfis de inferência, modelos de base e cotas do Bedrock
            (só leitura; cada chamada em try/except).
  probe     uma chamada trivial por braço (max_tokens pequeno) para provar que o
            modelo responde pelo InvokeModel com o corpo do perfil.
  prepare   valida a exportação somente leitura (uma linha JSON por artigo),
            confere o prompt_hash da referência e faz o sorteio estratificado.
  run       roda um braço sobre a amostra (JSONL por braço, retomável) com teto
            de gasto rígido (SpendLedger).
  report    métricas por braço contra a referência, portões G1–G6, projeção de
            custo/dias, CSV por artigo e revisão cega (G7).

NÃO toca no banco: a amostra vem de arquivo, e o script não importa o handler.
O corpo da requisição e o parser são os mesmos da produção
(news_enrichment.llm_client): o que for avaliado é o que vai para o ar.

Credenciais: AWS_BEDROCK_CONNECTION_URI (aws://KEY:SECRET@/?region_name=...).
Rodar com env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN
-u AWS_PROFILE -u AWS_REGION e PYTHONPATH=<worktree>/src.
"""

import argparse
import csv
import json
import math
import os
import random
import re
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import hashlib

from botocore.exceptions import ClientError

from news_enrichment.canonicalization import normalize
from news_enrichment.llm_client import (
    BedrockLLMClient,
    NerRefusal,
    _extract_usage,
    build_ner_request_body,
    format_bedrock_error,
    ner_model_family,
    ner_response_text,
)

# --------------------------------------------------------------------------- #
# Configuração                                                                #
# --------------------------------------------------------------------------- #

# Braços do experimento. max_tokens/effort/thinking None = default do corpo
# (no legado, o corpo congelado de produção).
ARMS: Dict[str, Dict] = {
    "s46": {
        "family": "legacy",
        "needs": "sonnet-4-6",
        "effort": None,
        "thinking": None,
        "max_tokens": None,
    },
    "h45": {
        "family": "legacy",
        "needs": "haiku-4-5",
        "effort": None,
        "thinking": None,
        "max_tokens": None,
    },
    "s55_bt_low": {
        "family": "sonnet-5-5",
        "effort": "low",
        "thinking": "between_tools",
        "max_tokens": 4000,
    },
    "s55_ad_low": {
        "family": "sonnet-5-5",
        "effort": "low",
        "thinking": "adaptive",
        "max_tokens": 8000,
    },
    "h55_ad_low": {
        "family": "haiku-5-5",
        "effort": "low",
        "thinking": "adaptive",
        "max_tokens": 8000,
    },
    "h55_off_low": {
        "family": "haiku-5-5",
        "effort": "low",
        "thinking": "disabled",
        "max_tokens": 4000,
    },
}
LEGACY_MAX_TOKENS = 2000

# Preço de lista (USD por milhão de tokens: entrada, saída). Bedrock pode diferir.
PRICES = {
    "sonnet-4-6": (3.0, 15.0),
    "sonnet-5-5": (2.0, 10.0),
    "haiku-5-5": (0.10, 0.50),
    "haiku-4-5": (1.0, 5.0),
}
HAIKU55_LONG_PROMPT = (0.50, 2.50)  # prompt > 100K tokens
_PRICE_KEY_RE = re.compile(r"claude-(sonnet|haiku|opus)-(\d+)-(\d+)(?![0-9])")

FINAL_STATUSES = frozenset({"ok", "refusal", "no_text"})
REF_LABEL = "referencia_s46"
SIZES = ("P", "M", "G")
DAILY_QUOTA_MARKER = "too many tokens per day"


# --------------------------------------------------------------------------- #
# Prompt, parser e corpo (mesmas funções da produção)                         #
# --------------------------------------------------------------------------- #


def make_parser_client(model_id: Optional[str] = None) -> BedrockLLMClient:
    """BedrockLLMClient sem boto3 (só prompt/parse); `.client` é atribuído depois."""
    client = BedrockLLMClient.__new__(BedrockLLMClient)
    client.taxonomy = None
    client.ner_model_id = model_id
    client.model_id = None
    client.max_retries = 1
    return client


_PARSER = make_parser_client()


def build_prompt(article: Dict) -> str:
    return _PARSER._build_ner_prompt(article)


def prompt_hash_ok(article: Dict, ref_hash: Optional[str]) -> bool:
    prompt = build_prompt(article)
    return bool(ref_hash) and hashlib.sha256(prompt.encode("utf-8")).hexdigest() == ref_hash


def build_request_for(model_id: str, arm_cfg: Dict, prompt: str) -> Dict:
    return build_ner_request_body(
        model_id,
        prompt,
        effort=arm_cfg.get("effort"),
        thinking=arm_cfg.get("thinking"),
        max_tokens=arm_cfg.get("max_tokens"),
    )


def check_arm_model(arm_name: str, model_id: str) -> None:
    """O ID precisa ser da família do braço (evita rodar o corpo errado)."""
    cfg = ARMS[arm_name]
    family = ner_model_family(model_id)
    if family != cfg["family"]:
        raise ValueError(
            f"braço {arm_name} espera família {cfg['family']}, ID {model_id!r} é {family}"
        )
    needs = cfg.get("needs")
    if needs and needs not in (model_id or ""):
        raise ValueError(f"braço {arm_name} espera um ID de {needs}, recebido {model_id!r}")


def ref_entities(raw_response) -> List[Dict]:
    """Entidades da referência gravada (raw_response de news_llm_raw), pelo parser de produção."""
    if raw_response is None:
        return []
    if isinstance(raw_response, str):
        text = raw_response
    elif isinstance(raw_response, dict) and set(raw_response) == {"raw_text"}:
        text = raw_response["raw_text"] or ""
    else:
        text = json.dumps(raw_response, ensure_ascii=False)
    return _PARSER._parse_entities(text)


# --------------------------------------------------------------------------- #
# Métricas puras                                                              #
# --------------------------------------------------------------------------- #


def _name(ent: Dict) -> str:
    return normalize(ent.get("forma_canonica") or ent.get("text"))


_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)$")


def _strip_trailing_paren(name: str) -> str:
    """Tira uma sigla/aposto final entre parênteses ("ministerio x (mx)" → "ministerio x")."""
    stripped = _TRAILING_PAREN_RE.sub("", name).strip()
    return stripped or name


def entity_keys(ents: Iterable[Dict], mode: str) -> Set:
    """Chaves de comparação.

    strict  = (nome normalizado, tipo); loose = só o nome;
    relaxed = (nome sem parêntese final, tipo) — DIAGNÓSTICO, não é portão: separa
    divergência de estilo da forma_canonica (com/sem sigla) de divergência real.
    """
    if mode not in ("strict", "loose", "relaxed"):
        raise ValueError(f"modo inválido: {mode!r}")
    out: Set = set()
    for e in ents or []:
        name = _name(e)
        if not name:
            continue
        if mode == "strict":
            out.add((name, e.get("type")))
        elif mode == "relaxed":
            out.add((_strip_trailing_paren(name), e.get("type")))
        else:
            out.add(name)
    return out


def prf_counts(ref_keys: Set, cand_keys: Set) -> Tuple[int, int, int]:
    tp = len(ref_keys & cand_keys)
    return tp, len(cand_keys - ref_keys), len(ref_keys - cand_keys)


def f1_from_counts(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    if tp + fp + fn == 0:
        return 1.0, 1.0, 1.0
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def salience_recall(ref: List[Dict], cand: List[Dict], threshold: float = 0.7) -> Tuple[int, int]:
    salient = {
        _name(e)
        for e in ref or []
        if e.get("salience") is not None and e["salience"] >= threshold and _name(e)
    }
    cand_names = entity_keys(cand, "loose")
    return len(salient & cand_names), len(salient)


def type_confusion(ref: List[Dict], cand: List[Dict]) -> Counter:
    ref_t: Dict[str, str] = {}
    for e in ref or []:
        ref_t.setdefault(_name(e), e.get("type"))
    cand_t: Dict[str, str] = {}
    for e in cand or []:
        cand_t.setdefault(_name(e), e.get("type"))
    conf: Counter = Counter()
    for name, rt in ref_t.items():
        if name and name in cand_t:
            conf[(rt, cand_t[name])] += 1
    return conf


def alias_coverage(ents: List[Dict], alias_set: Set) -> Tuple[int, int]:
    keys = entity_keys(ents, "strict")
    return sum(1 for k in keys if k in alias_set), len(keys)


# --------------------------------------------------------------------------- #
# Custo e SpendLedger                                                         #
# --------------------------------------------------------------------------- #


def _price_key(model_id: str) -> Optional[str]:
    m = _PRICE_KEY_RE.search(model_id or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def cost_usd(model_id: str, usage: Dict) -> float:
    key = _price_key(model_id)
    if key not in PRICES:
        raise ValueError(f"sem preço para o modelo {model_id!r}")
    in_tok = int((usage or {}).get("input_tokens") or 0)
    out_tok = int((usage or {}).get("output_tokens") or 0)
    p_in, p_out = PRICES[key]
    if key == "haiku-5-5" and in_tok > 100_000:
        p_in, p_out = HAIKU55_LONG_PROMPT
    return (in_tok * p_in + out_tok * p_out) / 1e6


def estimate_cost(model_id: str, prompt: str, max_tokens: int) -> float:
    """Teto da chamada: ≥1 token de entrada por 2 caracteres e a saída inteira."""
    in_est = math.ceil(len(prompt) / 2) + 50
    return cost_usd(model_id, {"input_tokens": in_est, "output_tokens": max_tokens})


class BudgetExceeded(RuntimeError):
    pass


class SpendLedger:
    """Gasto acumulado em arquivo JSON, com reserva antes de cada chamada.

    reserve(estimativa) falha se gasto + reservas pendentes + estimativa passar do
    teto; commit(reserva, real) troca a reserva pelo custo medido. Como a
    estimativa é um teto (saída = max_tokens), o gasto real nunca passa do teto.
    """

    def __init__(self, path: str, budget_usd: float):
        self.path = path
        self.budget = float(budget_usd)
        self._lock = threading.Lock()
        self._pending = 0.0
        data = {"spent_usd": 0.0, "calls": 0, "by_arm": {}}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            prev = data.get("budget_usd")
            if prev is not None and self.budget > float(prev) + 1e-12:
                raise ValueError(f"teto não pode subir na retomada ({prev} → {self.budget})")
        self.spent = float(data.get("spent_usd", 0.0))
        self.calls = int(data.get("calls", 0))
        self.by_arm = data.get("by_arm", {})
        self._save()

    def reserve(self, estimate: float) -> float:
        with self._lock:
            if self.spent + self._pending + estimate > self.budget + 1e-12:
                raise BudgetExceeded(
                    f"teto US${self.budget:.4f}: gasto {self.spent:.4f} + pendente "
                    f"{self._pending:.4f} + estimativa {estimate:.4f}"
                )
            self._pending += estimate
            return estimate

    def commit(self, reserved: float, actual: float, arm: str, usage: Dict) -> None:
        with self._lock:
            self._pending = max(0.0, self._pending - reserved)
            self.spent += actual
            self.calls += 1
            a = self.by_arm.setdefault(
                arm, {"usd": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0}
            )
            a["usd"] += actual
            a["calls"] += 1
            a["input_tokens"] += int((usage or {}).get("input_tokens") or 0)
            a["output_tokens"] += int((usage or {}).get("output_tokens") or 0)
            self._save()

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(
                {
                    "budget_usd": self.budget,
                    "spent_usd": self.spent,
                    "calls": self.calls,
                    "by_arm": self.by_arm,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
            )
        os.replace(tmp, self.path)


# --------------------------------------------------------------------------- #
# Export, amostra e retomada                                                  #
# --------------------------------------------------------------------------- #


def parse_raw_export(path: str) -> Tuple[List[Dict], List[str]]:
    """Lê a saída do ro_sql.sh (uma linha JSON por registro).

    Linha de erro do psql (o ro_sql.sh junta o stderr) aborta; outras linhas não
    JSON são devolvidas para o chamador decidir.
    """
    rows: List[Dict] = []
    bad: List[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("ERROR") or s.startswith("psql:") or "ERROR:" in s[:80]:
                raise RuntimeError(f"erro do psql na exportação: {s[:200]}")
            try:
                rows.append(json.loads(s))
            except ValueError:
                bad.append(s)
    return rows, bad


def parse_quota(text: str) -> Dict[str, int]:
    out = {}
    for part in text.split(","):
        k, v = part.split("=")
        out[k.strip()] = int(v)
    return out


def stratified_take(rows: List[Dict], quota_by_year: Dict[str, int]) -> List[Dict]:
    """Por ano, divide a cota igualmente entre os tamanhos (P/M/G), pela ordem do
    hash; falta num tamanho é coberta pelos outros tamanhos do mesmo ano."""
    groups: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    for r in rows:
        groups[(str(r["y"]), r["tam"])].append(r)
    for g in groups.values():
        g.sort(key=lambda r: (r["h"], r["unique_id"]))
    out: List[Dict] = []
    for year, quota in sorted(quota_by_year.items()):
        base, extra = divmod(quota, len(SIZES))
        targets = {s: base + (1 if i < extra else 0) for i, s in enumerate(SIZES)}
        taken: List[Dict] = []
        leftovers: List[Dict] = []
        for s in SIZES:
            g = groups.get((year, s), [])
            taken.extend(g[: targets[s]])
            leftovers.extend(g[targets[s] :])
        if len(taken) < quota:
            leftovers.sort(key=lambda r: (r["h"], r["unique_id"]))
            taken.extend(leftovers[: quota - len(taken)])
        out.extend(taken)
    return out


def done_uids(path: str) -> Set[str]:
    return {u for u, r in load_records(path).items() if r.get("status") in FINAL_STATUSES}


def load_records(path: str, key: str = "uid") -> Dict[str, Dict]:
    """Registros de um JSONL de braço, indexados por `key` (default uid; sem o campo → uid)."""
    recs: Dict[str, Dict] = {}
    if not os.path.exists(path):
        return recs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                recs[r.get(key) or r["uid"]] = r
    return recs


def plan_targets(sample: List[Dict], limit: Optional[int], done: Set[str]) -> List[Dict]:
    head = sample if limit is None else sample[:limit]
    return [a for a in head if a["unique_id"] not in done]


# --------------------------------------------------------------------------- #
# Chamada e execução de um braço                                              #
# --------------------------------------------------------------------------- #


def _json_flags(client: BedrockLLMClient, text: Optional[str]) -> Tuple[bool, bool]:
    if not text:
        return False, False
    try:
        obj = json.loads(text.strip())
        puro = isinstance(obj, dict) and isinstance(obj.get("entities"), list)
    except ValueError:
        puro = False
    extr = client._extract_json(text)
    extraivel = isinstance(extr, list) or (
        isinstance(extr, dict) and isinstance(extr.get("entities"), list)
    )
    return puro, extraivel


def call_one(
    client: BedrockLLMClient,
    arm_name: str,
    arm_cfg: Dict,
    article: Dict,
    ledger: SpendLedger,
    sleep=time.sleep,
) -> Dict:
    """Uma chamada NER real. Uma retentativa só para throttling; nenhuma para 400."""
    model_id = client.ner_model_id
    prompt = build_prompt(article)
    body_req = build_request_for(model_id, arm_cfg, prompt)  # valida antes de reservar
    reserved = ledger.reserve(estimate_cost(model_id, prompt, body_req["max_tokens"]))
    overrides = {k: arm_cfg.get(k) for k in ("effort", "thinking", "max_tokens")}
    t0 = time.monotonic()
    attempts = 0
    body: Optional[Dict] = None
    error: Optional[str] = None
    while True:
        attempts += 1
        try:
            body = client._invoke_ner_raw(prompt, **overrides)
            break
        except ClientError as e:
            code = (e.response.get("Error") or {}).get("Code", "")
            error = format_bedrock_error(e)
            if code == "ThrottlingException" and attempts == 1:
                sleep(3.0 + random.uniform(0, 2.0))
                continue
            break
        except Exception as e:  # rede, timeout, JSON inválido
            error = format_bedrock_error(e)
            break
    latency = time.monotonic() - t0

    rec = {
        "uid": article["unique_id"],
        "arm": arm_name,
        "model_id": model_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "attempts": attempts,
        "latency_s": round(latency, 3),
        "status": None,
        "stop_reason": None,
        "refusal_category": None,
        "block_types": [],
        "raw_text": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "cost_usd": 0.0,
        "entities": [],
        "json_puro": False,
        "json_extraivel": False,
        "error": None,
    }
    if body is None:
        ledger.commit(reserved, 0.0, arm_name, {})
        rec.update(status="api_error", error=error)
        return rec

    usage = _extract_usage(body)
    cost = cost_usd(model_id, usage)
    ledger.commit(reserved, cost, arm_name, usage)
    rec.update(
        usage=usage,
        cost_usd=cost,
        stop_reason=body.get("stop_reason"),
        block_types=[
            b.get("type", "text") if isinstance(b, dict) else type(b).__name__
            for b in (body.get("content") or [])
        ],
    )
    try:
        text = ner_response_text(body)
        rec["status"] = "ok"
    except NerRefusal as r:
        text = None
        rec.update(status="refusal", refusal_category=r.category)
    except ValueError as e:
        text = None
        rec.update(status="no_text", error=str(e))
    rec["raw_text"] = text
    if text:
        rec["entities"] = client._parse_entities(text)
        rec["json_puro"], rec["json_extraivel"] = _json_flags(client, text)
    return rec


def run_arm(
    client: BedrockLLMClient,
    arm_name: str,
    sample: List[Dict],
    out_path: str,
    ledger: SpendLedger,
    limit: Optional[int],
    workers: int = 3,
    sleep=time.sleep,
    max_consecutive_errors: int = 5,
) -> Dict:
    """Roda o braço nos primeiros `limit` artigos da amostra, pulando os já feitos."""
    arm_cfg = ARMS[arm_name]
    targets = plan_targets(sample, limit, done_uids(out_path))
    summary: Counter = Counter()
    write_lock = threading.Lock()
    flags = {"budget_stop": False, "daily_quota_stop": False, "error_stop": False}
    consecutive_errors = 0
    spent_before = ledger.spent

    def task(article):
        return call_one(client, arm_name, arm_cfg, article, ledger, sleep=sleep)

    queue = list(targets)
    in_flight = set()
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool, open(
        out_path, "a", encoding="utf-8"
    ) as out:
        while queue or in_flight:
            stop = any(flags.values())
            while queue and not stop and len(in_flight) < max(1, workers):
                in_flight.add(pool.submit(task, queue.pop(0)))
            if not in_flight:
                break
            done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
            for fut in done:
                try:
                    rec = fut.result()
                except BudgetExceeded as e:
                    flags["budget_stop"] = True
                    print(f"[{arm_name}] parada por teto: {e}", flush=True)
                    continue
                with write_lock:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                summary[rec["status"]] += 1
                if rec["status"] == "api_error":
                    consecutive_errors += 1
                    print(f"[{arm_name}] {rec['uid']}: {rec['error'][:300]}", flush=True)
                    if DAILY_QUOTA_MARKER in (rec["error"] or "").lower():
                        flags["daily_quota_stop"] = True
                    if consecutive_errors >= max_consecutive_errors:
                        flags["error_stop"] = True
                else:
                    consecutive_errors = 0
            if any(flags.values()):
                queue.clear()
    result = {
        "arm": arm_name,
        "targets": len(targets),
        "ok": summary.get("ok", 0),
        "refusal": summary.get("refusal", 0),
        "no_text": summary.get("no_text", 0),
        "api_error": summary.get("api_error", 0),
        "spent_usd_run": ledger.spent - spent_before,
        "spent_usd_total": ledger.spent,
    }
    result.update(flags)
    return result


# --------------------------------------------------------------------------- #
# Métricas por braço, portões e projeção                                      #
# --------------------------------------------------------------------------- #


def _ref_of(row: Dict) -> List[Dict]:
    return ref_entities((row.get("ref") or {}).get("raw_response"))


def arm_metrics(
    sample_by_uid: Dict[str, Dict],
    records: Dict[str, Dict],
    alias_set: Set,
    uids: Optional[Set[str]] = None,
) -> Dict:
    """Métricas de um braço contra a referência gravada (sobre os registros dados)."""
    sel = [u for u in records if u in sample_by_uid and (uids is None or u in uids)]
    sel.sort()
    tot = {"strict": [0, 0, 0], "loose": [0, 0, 0], "relaxed": [0, 0, 0]}
    strata: Dict[str, List[int]] = defaultdict(lambda: [0, 0, 0, 0])  # tp fp fn n
    sal_hits = sal_total = 0
    alias_hits = alias_total = ref_alias_hits = ref_alias_total = 0
    n_ents = n_ref_ents = 0
    conf: Counter = Counter()
    per_article_f1 = []
    statuses = Counter()
    stops = Counter()
    json_extr = json_puro = 0
    costs, in_toks, out_toks, lats = [], [], [], []
    for u in sel:
        rec, row = records[u], sample_by_uid[u]
        ref = _ref_of(row)
        cand = rec.get("entities") or []
        statuses[rec.get("status")] += 1
        stops[rec.get("stop_reason")] += 1
        json_extr += bool(rec.get("json_extraivel"))
        json_puro += bool(rec.get("json_puro"))
        for mode in ("strict", "loose", "relaxed"):
            c = prf_counts(entity_keys(ref, mode), entity_keys(cand, mode))
            for i in range(3):
                tot[mode][i] += c[i]
            if mode == "strict":
                per_article_f1.append(f1_from_counts(*c)[2])
                for key in (f"y={row.get('y')}", f"tam={row.get('tam')}"):
                    s = strata[key]
                    s[0] += c[0]
                    s[1] += c[1]
                    s[2] += c[2]
                    s[3] += 1
        h, t = salience_recall(ref, cand)
        sal_hits += h
        sal_total += t
        h, t = alias_coverage(cand, alias_set)
        alias_hits += h
        alias_total += t
        h, t = alias_coverage(ref, alias_set)
        ref_alias_hits += h
        ref_alias_total += t
        n_ents += len(entity_keys(cand, "strict"))
        n_ref_ents += len(entity_keys(ref, "strict"))
        conf.update(type_confusion(ref, cand))
        if rec.get("status") != "api_error":
            costs.append(float(rec.get("cost_usd") or 0.0))
            usage = rec.get("usage") or {}
            in_toks.append(int(usage.get("input_tokens") or 0))
            out_toks.append(int(usage.get("output_tokens") or 0))
            lats.append(float(rec.get("latency_s") or 0.0))
    n = len(sel)

    def prf(mode):
        tp, fp, fn = tot[mode]
        p, r, f1 = f1_from_counts(tp, fp, fn)
        return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}

    def pct(vals, q):
        if not vals:
            return None
        s = sorted(vals)
        return s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)]

    return {
        "n": n,
        "status": dict(statuses),
        "refusals": statuses.get("refusal", 0),
        "api_errors": statuses.get("api_error", 0),
        "no_text": statuses.get("no_text", 0),
        "max_tokens": stops.get("max_tokens", 0),
        "json_extraivel_rate": json_extr / n if n else None,
        "json_puro_rate": json_puro / n if n else None,
        "strict": prf("strict"),
        "loose": prf("loose"),
        "relaxed": prf("relaxed"),
        "f1_strict_macro": statistics.mean(per_article_f1) if per_article_f1 else None,
        "salience_recall": sal_hits / sal_total if sal_total else None,
        "salience_n": sal_total,
        "by_stratum": {
            k: {"n": v[3], "f1_strict": f1_from_counts(v[0], v[1], v[2])[2]}
            for k, v in sorted(strata.items())
        },
        "ents_per_article": n_ents / n if n else None,
        "ref_ents_per_article": n_ref_ents / n if n else None,
        "alias_coverage": alias_hits / alias_total if alias_total else None,
        "ref_alias_coverage": ref_alias_hits / ref_alias_total if ref_alias_total else None,
        "type_confusion": {f"{a}->{b}": c for (a, b), c in sorted(conf.items())},
        "cost_per_article": statistics.mean(costs) if costs else None,
        "input_tokens_per_article": statistics.mean(in_toks) if in_toks else None,
        "output_tokens_per_article": statistics.mean(out_toks) if out_toks else None,
        "latency_p50": pct(lats, 0.5),
        "latency_p95": pct(lats, 0.95),
        "per_article_f1": dict(zip(sel, per_article_f1)),
    }


def evaluate_gates(m: Dict, floor: Optional[Dict], eps: float = 1e-9) -> Dict:
    """G1–G6 (seção 3 do plano). Sem piso, G2–G4 ficam indeterminados (None)."""
    n = m["n"] or 0
    g: Dict[str, Dict] = {}
    g1 = (
        n > 0
        and (m["json_extraivel_rate"] or 0) >= 0.99 - eps
        and m["refusals"] <= n / 200 + eps
        and m["max_tokens"] <= n / 200 + eps
        and m["api_errors"] <= 0.01 * n + eps
    )
    g["G1"] = {
        "pass": bool(g1),
        "detail": f"json={m['json_extraivel_rate']}, recusas={m['refusals']}, "
        f"max_tokens={m['max_tokens']}, erros={m['api_errors']} (n={n})",
    }
    if floor is None:
        for k in ("G2", "G3", "G4"):
            g[k] = {"pass": None, "detail": "sem piso (braço s46 não rodou)"}
    else:
        f_f1 = floor["strict"]["f1"]
        g["G2"] = {
            "pass": m["strict"]["f1"] >= f_f1 - 0.05 - eps,
            "detail": f"F1 estrito {m['strict']['f1']:.4f} vs piso {f_f1:.4f} − 0,05",
        }
        f_sal = floor.get("salience_recall")
        sal = m.get("salience_recall")
        if f_sal is None or sal is None:
            g["G3"] = {"pass": None, "detail": "sem entidades com salience ≥ 0,7"}
        else:
            g["G3"] = {
                "pass": sal >= f_sal - 0.03 - eps,
                "detail": f"recall sal≥0,7 {sal:.4f} vs piso {f_sal:.4f} − 0,03",
            }
        fails = {
            k: v["f1_strict"]
            for k, v in m["by_stratum"].items()
            if v["n"] >= 40 and v["f1_strict"] < f_f1 - 0.10 - eps
        }
        checked = [k for k, v in m["by_stratum"].items() if v["n"] >= 40]
        g["G4"] = {
            "pass": not fails,
            "detail": f"estratos n≥40: {checked}; abaixo de piso−0,10: {fails or 'nenhum'}",
        }
    ratio = (
        m["ents_per_article"] / m["ref_ents_per_article"] if m.get("ref_ents_per_article") else None
    )
    g["G5"] = {
        "pass": ratio is not None and 0.8 - eps <= ratio <= 1.25 + eps,
        "detail": f"razão entidades/artigo = {ratio}",
    }
    ac, rac = m.get("alias_coverage"), m.get("ref_alias_coverage")
    g["G6"] = {
        "pass": ac is not None and rac is not None and ac >= rac - 0.05 - eps,
        "detail": f"cobertura alias {ac} vs referência {rac} − 5 p.p.",
    }
    vals = [g[k]["pass"] for k in ("G1", "G2", "G3", "G4", "G5", "G6")]
    g["pass_all"] = False if any(v is False for v in vals) else (None if None in vals else True)
    return g


def project(
    cost_per_article: float,
    tokens_per_article: float,
    n_articles: int,
    quota_tokens_day: Optional[float],
    articles_day_cap: Optional[float],
) -> Dict:
    total_tokens = tokens_per_article * n_articles
    by_quota = total_tokens / quota_tokens_day if quota_tokens_day else None
    by_cap = n_articles / articles_day_cap if articles_day_cap else None
    days = max(d for d in (by_quota, by_cap) if d is not None) if (by_quota or by_cap) else None
    return {
        "cost_usd": cost_per_article * n_articles,
        "total_tokens": total_tokens,
        "days_by_quota": by_quota,
        "days_by_dag_cap": by_cap,
        "days": days,
    }


# --------------------------------------------------------------------------- #
# Revisão cega (G7)                                                           #
# --------------------------------------------------------------------------- #


def _fmt_ents(ents: List[Dict]) -> List[str]:
    def key(e):
        return (-(e.get("salience") or 0.0), _name(e))

    lines = []
    for e in sorted(ents, key=key):
        sal = e.get("salience")
        forma = e.get("forma_canonica")
        extra = f" → {forma}" if forma and forma != e.get("text") else ""
        lines.append(
            f"- {e.get('text')}{extra} [{e.get('type')}]"
            + (f" (sal {sal:.2f})" if isinstance(sal, (int, float)) else "")
        )
    return lines or ["- (nenhuma entidade)"]


def pair_key(pair: Dict) -> str:
    """Chave de um par histórico: unique_id|prompt_hash.

    Um artigo pode ter mais de um par (prompt_hash diferentes, conteúdo
    re-raspado); indexar só por unique_id descartava pares em silêncio.
    """
    return f"{pair['unique_id']}|{(pair.get('ref') or {}).get('prompt_hash')}"


def alt_record(pair: Dict, arm: str = "s46hist") -> Dict:
    """Registro de "braço" a partir da resposta Sonnet 4.6 mais antiga de um par histórico.

    O par (exportado só leitura) tem duas respostas Sonnet 4.6 gravadas para o
    mesmo prompt_hash: `ref` (a mais recente, como na amostra) e `alt` (a mais
    antiga). Comparar alt com ref dá o piso Sonnet 4.6 × Sonnet 4.6 sem chamada.
    """
    ref, alt = pair.get("ref") or {}, pair.get("alt") or {}
    if not ref.get("prompt_hash") or ref.get("prompt_hash") != alt.get("prompt_hash"):
        raise ValueError(f"par {pair.get('unique_id')}: prompt_hash diferente entre ref e alt")
    raw = alt.get("raw_response")
    structured = isinstance(raw, dict) and "raw_text" not in raw
    text = raw.get("raw_text") if isinstance(raw, dict) and "raw_text" in raw else None
    return {
        "uid": pair["unique_id"],
        "pair_key": pair_key(pair),
        "arm": arm,
        "model_id": "us.anthropic.claude-sonnet-4-6",
        "status": "ok",
        "stop_reason": None,
        "refusal_category": None,
        "block_types": [],
        "raw_text": text,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "cost_usd": 0.0,
        "latency_s": None,
        "entities": ref_entities(raw),
        "json_puro": structured,
        "json_extraivel": structured or _json_flags(_PARSER, text)[1],
        "error": None,
        "alt_created_at": alt.get("created_at"),
    }


def load_floor(sample_path: str, records_path: str) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    """Amostra e registros do piso histórico, indexados por par (pair_key).

    Registros gerados antes do pair_key (sem o campo) caem para unique_id, como
    antes, com aviso para re-rodar `floor-pairs` (sem chamada ao Bedrock).
    """
    rows = load_sample(sample_path)
    recs = load_records(records_path, key="pair_key")
    if recs and not all("pair_key" in r for r in recs.values()):
        uids = {r["unique_id"] for r in rows}
        print(
            f"AVISO: registros do piso sem pair_key; indexando por unique_id "
            f"({len(rows)} pares → {len(uids)} artigos). Re-rode floor-pairs para usar todos."
        )
        return {r["unique_id"]: r for r in rows}, load_records(records_path)
    sample = {pair_key(r): r for r in rows}
    if len(sample) < len(rows):
        print(f"AVISO: {len(rows) - len(sample)} pares repetidos na amostra do piso")
    return sample, recs


def choose_floor(
    live: Optional[Dict], hist: Optional[Dict]
) -> Tuple[Optional[Dict], Optional[str]]:
    """Piso: o s46 re-rodado ao vivo quando existe; senão, os pares históricos."""
    if live and live.get("n"):
        return live, "s46"
    if hist and hist.get("n"):
        return hist, "s46hist"
    return None, None


def article_text(article: Dict) -> str:
    """Texto que o modelo viu: título, subtítulo, lead e o recorte de 3000 caracteres."""
    parts = [article.get("title"), article.get("subtitle"), article.get("editorial_lead")]
    parts.append((article.get("content") or "")[:3000])
    return "\n".join(p for p in parts if p)


def blind_review(items: List[Dict], arm_name: str, seed: int = 20261016) -> Tuple[str, Dict]:
    rng = random.Random(seed)
    key: Dict[str, Dict[str, str]] = {}
    out = [
        "# Revisão cega — NER (G7)",
        "",
        "Para cada notícia, compare as listas A e B de entidades extraídas do mesmo texto.",
        "Marque qual está melhor (entidades certas, tipos certos, sem tópicos genéricos).",
        "A ordem A/B é sorteada; a chave fica em outro arquivo.",
        "",
    ]
    for i, it in enumerate(items, 1):
        swap = rng.random() < 0.5
        a, b = (it["cand"], it["ref"]) if swap else (it["ref"], it["cand"])
        key[it["uid"]] = (
            {"A": arm_name, "B": REF_LABEL} if swap else {"A": REF_LABEL, "B": arm_name}
        )
        out += [
            f"## {i}. {it.get('title') or '(sem título)'}",
            "",
            f"`{it['uid']}`",
            "",
            *(
                [
                    "<details><summary>Texto enviado ao modelo</summary>",
                    "",
                    *[f"> {line}" if line.strip() else ">" for line in it["text"].splitlines()],
                    "",
                    "</details>",
                    "",
                ]
                if it.get("text")
                else []
            ),
            "**Lista A**",
            "",
            *_fmt_ents(a),
            "",
            "**Lista B**",
            "",
            *_fmt_ents(b),
            "",
            "Veredito: [ ] A melhor  [ ] B melhor  [ ] equivalentes",
            "",
        ]
    return "\n".join(out), key


# --------------------------------------------------------------------------- #
# AWS                                                                         #
# --------------------------------------------------------------------------- #


def aws_credentials() -> Tuple[str, str, str]:
    """Credenciais da URI Airflow em AWS_BEDROCK_CONNECTION_URI (nunca impressas)."""
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        if os.environ.get(var):
            raise SystemExit(f"{var} está definida no ambiente: rode pelo wrapper com env -u")
    uri = os.environ.get("AWS_BEDROCK_CONNECTION_URI", "")
    if not uri:
        raise SystemExit("AWS_BEDROCK_CONNECTION_URI ausente")
    parsed = urlparse(uri)
    key = unquote(parsed.username) if parsed.username else None
    secret = unquote(parsed.password) if parsed.password else None
    region = parse_qs(parsed.query).get("region_name", ["us-east-1"])[0]
    if not key or not secret:
        raise SystemExit("AWS_BEDROCK_CONNECTION_URI sem usuário/senha")
    return key, secret, region


def _boto(service: str, region: Optional[str] = None, **cfg):
    import boto3
    from botocore.config import Config

    key, secret, default_region = aws_credentials()
    return boto3.client(
        service,
        region_name=region or default_region,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(**cfg) if cfg else None,
    )


def build_client(model_id: str) -> BedrockLLMClient:
    client = make_parser_client(model_id)
    client.client = _boto(
        "bedrock-runtime",
        read_timeout=300,
        connect_timeout=10,
        retries={"mode": "standard", "total_max_attempts": 1},
    )
    return client


def _err(e: Exception) -> str:
    return format_bedrock_error(e)[:400]


def cmd_discover(args) -> int:
    pat = re.compile(args.filter)
    report: Dict = {}
    try:
        ident = _boto("sts").get_caller_identity()
        report["account"] = ident.get("Account")
        print(f"STS Account={ident.get('Account')} Arn={ident.get('Arn')}")
        if args.expect_account and ident.get("Account") != args.expect_account:
            print(f"ATENÇÃO: conta diferente da esperada {args.expect_account}")
    except Exception as e:
        print(f"STS get_caller_identity: {_err(e)}")
    bedrock = None
    try:
        bedrock = _boto("bedrock")
    except Exception as e:
        print(f"bedrock client: {_err(e)}")
    if bedrock is not None:
        try:
            profiles, token = [], None
            while True:
                kw = {"maxResults": 1000}
                if token:
                    kw["nextToken"] = token
                resp = bedrock.list_inference_profiles(**kw)
                profiles += resp.get("inferenceProfileSummaries", [])
                token = resp.get("nextToken")
                if not token:
                    break
            hits = [p for p in profiles if pat.search(p.get("inferenceProfileId", ""))]
            report["inference_profiles"] = [p.get("inferenceProfileId") for p in hits]
            print(
                f"\nlist_inference_profiles: {len(profiles)} perfis, {len(hits)} casam /{args.filter}/"
            )
            for p in sorted(hits, key=lambda p: p.get("inferenceProfileId")):
                regions = sorted({m.get("modelArn", "").split(":")[3] for m in p.get("models", [])})
                print(
                    f"  {p.get('inferenceProfileId'):55s} status={p.get('status')} "
                    f"type={p.get('type')} regiões={regions}"
                )
        except Exception as e:
            print(f"list_inference_profiles: {_err(e)}")
        try:
            models = bedrock.list_foundation_models(byProvider="Anthropic").get(
                "modelSummaries", []
            )
            hits = [m for m in models if pat.search(m.get("modelId", ""))]
            report["foundation_models"] = [m.get("modelId") for m in hits]
            print(f"\nlist_foundation_models(Anthropic): {len(models)} modelos, {len(hits)} casam")
            for m in sorted(hits, key=lambda m: m.get("modelId")):
                print(
                    f"  {m.get('modelId'):55s} inference={m.get('inferenceTypesSupported')} "
                    f"lifecycle={(m.get('modelLifecycle') or {}).get('status')}"
                )
            for m in hits:
                mid = m.get("modelId", "")
                if "5-5" not in mid:
                    continue
                if not hasattr(bedrock, "get_foundation_model_availability"):
                    print("  get_foundation_model_availability: indisponível nesta versão do boto3")
                    break
                try:
                    av = bedrock.get_foundation_model_availability(modelId=mid)
                    av.pop("ResponseMetadata", None)
                    print(f"  disponibilidade {mid}: {json.dumps(av, default=str)}")
                except Exception as e:
                    print(f"  disponibilidade {mid}: {_err(e)}")
        except Exception as e:
            print(f"list_foundation_models: {_err(e)}")
    try:
        sq = _boto("service-quotas")
        quotas, token = [], None
        while True:
            kw = {"ServiceCode": "bedrock", "MaxResults": 100}
            if token:
                kw["NextToken"] = token
            resp = sq.list_service_quotas(**kw)
            quotas += resp.get("Quotas", [])
            token = resp.get("NextToken")
            if not token:
                break
        qpat = re.compile(args.quota_filter, re.I)
        hits = [q for q in quotas if qpat.search(q.get("QuotaName", ""))]
        report["quotas"] = {q.get("QuotaName"): q.get("Value") for q in hits}
        print(
            f"\nservice-quotas(bedrock): {len(quotas)} cotas, {len(hits)} casam /{args.quota_filter}/"
        )
        for q in sorted(hits, key=lambda q: q.get("QuotaName")):
            print(f"  {q.get('QuotaName')}: {q.get('Value')} ({q.get('QuotaCode')})")
    except Exception as e:
        print(f"service-quotas list_service_quotas: {_err(e)}")
    if args.out_json:
        with open(args.out_json, "w") as f:
            json.dump(report, f, indent=2, default=str)
    return 0


def cmd_probe(args) -> int:
    family = ner_model_family(args.model_id)
    cfg = {"effort": args.effort, "thinking": args.thinking, "max_tokens": args.max_tokens}
    if family == "legacy":
        cfg = {"effort": None, "thinking": None, "max_tokens": None}
    prompt = 'Responda apenas com este JSON, sem nada antes ou depois: {"entities": []}'
    body = build_request_for(args.model_id, cfg, prompt)
    shown = {k: v for k, v in body.items() if k != "messages"}
    ledger = SpendLedger(args.spend, args.budget_usd)
    reserved = ledger.reserve(estimate_cost(args.model_id, prompt, body["max_tokens"]))
    client = build_client(args.model_id)
    t0 = time.monotonic()
    out: Dict = {"label": args.label, "model_id": args.model_id, "request": shown}
    try:
        resp = client._invoke_ner_raw(prompt, **cfg)
        usage = _extract_usage(resp)
        cost = cost_usd(args.model_id, usage)
        ledger.commit(reserved, cost, f"probe:{args.label}", usage)
        texts = [
            b.get("text") for b in resp.get("content") or [] if b.get("type", "text") == "text"
        ]
        out.update(
            ok=True,
            stop_reason=resp.get("stop_reason"),
            stop_details=resp.get("stop_details"),
            block_types=[b.get("type") for b in resp.get("content") or []],
            usage=usage,
            cost_usd=round(cost, 6),
            text="".join(t for t in texts if t)[:200],
            model=resp.get("model"),
        )
    except Exception as e:
        ledger.commit(reserved, 0.0, f"probe:{args.label}", {})
        out.update(ok=False, error=_err(e))
    out["latency_s"] = round(time.monotonic() - t0, 2)
    out["ledger_spent_usd"] = round(ledger.spent, 6)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("ok") else 2


def cmd_prepare(args) -> int:
    rows, bad = parse_raw_export(args.raw)
    print(f"linhas JSON: {len(rows)}; linhas não-JSON: {len(bad)}")
    if bad:
        for b in bad[:5]:
            print(f"  não-JSON: {b[:160]}")
        return 2
    kept, drops = [], Counter()
    for r in rows:
        article = {
            k: r.get(k) for k in ("unique_id", "title", "subtitle", "editorial_lead", "content")
        }
        art = dict(r, **article)
        if not args.no_ref:
            ref = r.get("ref")
            if not ref:
                drops["sem_referencia"] += 1
                continue
            if not prompt_hash_ok(article, ref.get("prompt_hash")):
                drops["hash_divergente"] += 1
                continue
        kept.append(art)
    print(f"válidos: {len(kept)}; descartados: {dict(drops)}")
    if args.quota and args.quota != "all":
        quota = parse_quota(args.quota)
        chosen = stratified_take(kept, quota)
        missing = sum(quota.values()) - len(chosen)
        if missing:
            print(f"ATENÇÃO: faltaram {missing} artigos para a cota {quota}")
    else:
        chosen = kept
    chosen.sort(key=lambda r: (r.get("h") or "", r["unique_id"]))  # prefixo ≈ aleatório
    with open(args.out, "w", encoding="utf-8") as f:
        for r in chosen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    strata = Counter((str(r.get("y")), r.get("tam")) for r in chosen)
    print(f"gravados: {len(chosen)} em {args.out}")
    for k in sorted(strata):
        print(f"  {k[0]} {k[1]}: {strata[k]}")
    return 0


def load_sample(path: str) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def cmd_run(args) -> int:
    check_arm_model(args.arm, args.model_id)
    sample = load_sample(args.sample)
    label = os.path.splitext(os.path.basename(args.sample))[0]
    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"{args.arm}__{label}.jsonl")
    targets = plan_targets(sample, args.limit, done_uids(out_path))
    first = (
        build_request_for(args.model_id, ARMS[args.arm], build_prompt(targets[0]))
        if targets
        else None
    )
    est = sum(
        estimate_cost(
            args.model_id, build_prompt(a), ARMS[args.arm].get("max_tokens") or LEGACY_MAX_TOKENS
        )
        for a in targets
    )
    print(
        f"[{args.arm}] modelo={args.model_id} amostra={label} alvo={len(targets)} "
        f"teto estimado (pior caso)=US${est:.4f}"
    )
    if first:
        print(
            f"[{args.arm}] corpo: {json.dumps({k: v for k, v in first.items() if k != 'messages'})}"
        )
    if args.dry_run:
        return 0
    ledger = SpendLedger(args.spend, args.budget_usd)
    print(f"[{args.arm}] ledger antes: US${ledger.spent:.4f} de US${ledger.budget:.2f}")
    client = build_client(args.model_id)
    res = run_arm(client, args.arm, sample, out_path, ledger, args.limit, args.workers)
    print(json.dumps(res, ensure_ascii=False))
    return 0


def cmd_report(args) -> int:
    os.makedirs(args.out_dir, exist_ok=True)
    sample = load_sample(args.sample)
    label = os.path.splitext(os.path.basename(args.sample))[0]
    by_uid = {r["unique_id"]: r for r in sample}
    alias_set: Set = set()
    if args.alias:
        rows, bad = parse_raw_export(args.alias)
        alias_set = {(r[0], r[1]) for r in rows if isinstance(r, list) and len(r) == 2}
        print(f"entity_alias: {len(alias_set)} pares (alias_norm, type); linhas ruins {len(bad)}")
    arm_files = sorted(f for f in os.listdir(args.runs_dir) if f.endswith(f"__{label}.jsonl"))
    records = {f.split("__")[0]: load_records(os.path.join(args.runs_dir, f)) for f in arm_files}
    metrics = {arm: arm_metrics(by_uid, recs, alias_set) for arm, recs in records.items()}
    floor_hist = None
    if args.floor_sample:
        flabel = os.path.splitext(os.path.basename(args.floor_sample))[0]
        fsample, frecs = load_floor(
            args.floor_sample, os.path.join(args.runs_dir, f"{args.floor_arm}__{flabel}.jsonl")
        )
        floor_hist = arm_metrics(fsample, frecs, alias_set)
    floor, floor_label = choose_floor(metrics.get("s46"), floor_hist)
    floor_uids = set(records.get("s46", {}))
    gates = {arm: evaluate_gates(m, floor) for arm, m in metrics.items() if arm != "s46"}
    same20 = {
        arm: arm_metrics(by_uid, recs, alias_set, uids=floor_uids)
        for arm, recs in records.items()
        if arm != "s46" and floor_uids
    }
    ref_nonjson = sum(
        1
        for r in sample
        if isinstance((r.get("ref") or {}).get("raw_response"), dict)
        and "raw_text" in r["ref"]["raw_response"]
    )
    quotas = json.loads(args.quota_tokens_day) if args.quota_tokens_day else {}
    model_of = {
        arm: next((r.get("model_id") for r in recs.values() if r.get("model_id")), None)
        for arm, recs in records.items()
    }
    projections = {}
    for arm, m in metrics.items():
        if m["cost_per_article"] is None:
            continue
        toks = (m["input_tokens_per_article"] or 0) + (m["output_tokens_per_article"] or 0)
        projections[arm] = project(
            m["cost_per_article"],
            toks,
            args.n_articles,
            quotas.get(arm) or quotas.get(model_of.get(arm) or ""),
            args.articles_day_cap,
        )

    # Por artigo
    with open(os.path.join(args.out_dir, "por_artigo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "uid",
                "y",
                "tam",
                "arm",
                "status",
                "stop_reason",
                "n_ref",
                "n_cand",
                "tp_strict",
                "fp_strict",
                "fn_strict",
                "f1_strict",
                "f1_loose",
                "sal_hits",
                "sal_total",
                "input_tokens",
                "output_tokens",
                "cost_usd",
                "latency_s",
                "json_puro",
                "json_extraivel",
                "refusal_category",
                "error",
            ]
        )
        for arm, recs in sorted(records.items()):
            for u, rec in sorted(recs.items()):
                row = by_uid.get(u)
                if not row:
                    continue
                ref, cand = _ref_of(row), rec.get("entities") or []
                cs = prf_counts(entity_keys(ref, "strict"), entity_keys(cand, "strict"))
                cl = prf_counts(entity_keys(ref, "loose"), entity_keys(cand, "loose"))
                sh, st = salience_recall(ref, cand)
                usage = rec.get("usage") or {}
                w.writerow(
                    [
                        u,
                        row.get("y"),
                        row.get("tam"),
                        arm,
                        rec.get("status"),
                        rec.get("stop_reason"),
                        len(entity_keys(ref, "strict")),
                        len(entity_keys(cand, "strict")),
                        *cs,
                        round(f1_from_counts(*cs)[2], 4),
                        round(f1_from_counts(*cl)[2], 4),
                        sh,
                        st,
                        usage.get("input_tokens"),
                        usage.get("output_tokens"),
                        round(float(rec.get("cost_usd") or 0), 6),
                        rec.get("latency_s"),
                        rec.get("json_puro"),
                        rec.get("json_extraivel"),
                        rec.get("refusal_category"),
                        (rec.get("error") or "")[:200],
                    ]
                )

    # Extras (adversarial / pendentes antigos): validade e recusas
    extras = {}
    for extra in args.extra or []:
        elabel, epath = extra.split("=", 1)
        esample = {r["unique_id"]: r for r in load_sample(epath)}
        for f in sorted(os.listdir(args.runs_dir)):
            if f.endswith(f"__{os.path.splitext(os.path.basename(epath))[0]}.jsonl"):
                arm = f.split("__")[0]
                recs = load_records(os.path.join(args.runs_dir, f))
                extras[(elabel, arm)] = arm_metrics(esample, recs, alias_set)

    # Revisão cega
    cand_arm = args.blind_arm
    passing = sorted(
        (a for a, g in gates.items() if g["pass_all"]),
        key=lambda a: metrics[a]["cost_per_article"] or 1e9,
    )
    if not cand_arm:
        if passing:
            cand_arm = passing[0]
        elif gates:
            cand_arm = max(gates, key=lambda a: metrics[a]["strict"]["f1"])
    blind_note = ""
    if cand_arm and cand_arm in records:
        f1s = metrics[cand_arm]["per_article_f1"]
        ok = [u for u in f1s if records[cand_arm][u].get("status") == "ok"]
        ok.sort(key=lambda u: (f1s[u], by_uid[u].get("h") or "", u))
        items = [
            {
                "uid": u,
                "title": by_uid[u].get("title"),
                "text": article_text(by_uid[u]),
                "ref": _ref_of(by_uid[u]),
                "cand": records[cand_arm][u].get("entities") or [],
                "f1": f1s[u],
            }
            for u in ok[: args.blind_n]
        ]
        md, key = blind_review(items, cand_arm, seed=args.seed)
        with open(os.path.join(args.out_dir, "revisao_cega.md"), "w", encoding="utf-8") as f:
            f.write(md + "\n")
        with open(
            os.path.join(args.out_dir, "revisao_cega_chave.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"braco_candidato": cand_arm, "itens": key}, f, indent=2, ensure_ascii=False)
        blind_note = (
            f"Revisão cega: braço `{cand_arm}` contra a referência, {len(items)} artigos "
            f"com menor F1 estrito (`revisao_cega.md`; chave em `revisao_cega_chave.json`)."
        )

    # Resumo
    def fmt(v, nd=3):
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:.{nd}f}"
        return str(v)

    L = [
        "# Avaliação NER — modelos candidatos contra a referência Sonnet 4.6 (ner-v1)",
        "",
        f"Gerado em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. "
        f"Amostra `{label}`: {len(sample)} artigos; referência não-JSON puro: {ref_nonjson}.",
        "Preços de lista (Bedrock pode diferir). Referência = linha mais recente de "
        "`news_llm_raw` (Sonnet 4.6, ner-v1); piso = concordância Sonnet 4.6 × Sonnet 4.6 "
        '(origem na seção dos portões). "F1 sem sigla" é diagnóstico (não é portão).',
        "",
        "## Métricas por braço",
        "",
        "| braço | modelo | n | ok | recusa | sem texto | erro API | max_tokens | JSON extraível | "
        "JSON puro | P estrito | R estrito | F1 estrito | F1 frouxo | F1 sem sigla (diag.) | "
        "recall sal≥0,7 | ent/art (ref) | alias (ref) | US$/art | tok in/out | lat p50/p95 s |",
        "|" + "---|" * 21,
    ]
    for arm, m in sorted(metrics.items()):
        st = m["status"]
        L.append(
            f"| {arm} | `{model_of.get(arm)}` | {m['n']} | {st.get('ok', 0)} | {m['refusals']} | "
            f"{m['no_text']} | {m['api_errors']} | {m['max_tokens']} | {fmt(m['json_extraivel_rate'])} | "
            f"{fmt(m['json_puro_rate'])} | {fmt(m['strict']['precision'])} | {fmt(m['strict']['recall'])} | "
            f"{fmt(m['strict']['f1'])} | {fmt(m['loose']['f1'])} | {fmt(m['relaxed']['f1'])} | "
            f"{fmt(m['salience_recall'])} | "
            f"{fmt(m['ents_per_article'], 2)} ({fmt(m['ref_ents_per_article'], 2)}) | "
            f"{fmt(m['alias_coverage'])} ({fmt(m['ref_alias_coverage'])}) | "
            f"{fmt(m['cost_per_article'], 5)} | {fmt(m['input_tokens_per_article'], 0)}/"
            f"{fmt(m['output_tokens_per_article'], 0)} | {fmt(m['latency_p50'], 1)}/{fmt(m['latency_p95'], 1)} |"
        )
    if same20:
        L += [
            "",
            f"### Mesmos {len(floor_uids)} artigos do piso (comparação pareada)",
            "",
            "| braço | n | F1 estrito | F1 frouxo | recall sal≥0,7 | ent/art (ref) |",
            "|---|---|---|---|---|---|",
            f"| s46 (piso) | {floor['n']} | {fmt(floor['strict']['f1'])} | {fmt(floor['loose']['f1'])} | "
            f"{fmt(floor['salience_recall'])} | {fmt(floor['ents_per_article'], 2)} "
            f"({fmt(floor['ref_ents_per_article'], 2)}) |",
        ]
        for arm, m in sorted(same20.items()):
            L.append(
                f"| {arm} | {m['n']} | {fmt(m['strict']['f1'])} | {fmt(m['loose']['f1'])} | "
                f"{fmt(m['salience_recall'])} | {fmt(m['ents_per_article'], 2)} "
                f"({fmt(m['ref_ents_per_article'], 2)}) |"
            )
    L += [
        "",
        "## F1 estrito por estrato",
        "",
        "| braço | "
        + " | ".join(sorted({k for m in metrics.values() for k in m["by_stratum"]}))
        + " |",
    ]
    skeys = sorted({k for m in metrics.values() for k in m["by_stratum"]})
    L.append("|" + "---|" * (len(skeys) + 1))
    for arm, m in sorted(metrics.items()):
        L.append(
            f"| {arm} | "
            + " | ".join(
                f"{fmt(m['by_stratum'][k]['f1_strict'])} (n={m['by_stratum'][k]['n']})"
                if k in m["by_stratum"]
                else "—"
                for k in skeys
            )
            + " |"
        )
    L += ["", "## Portões G1–G6 (G7 = revisão cega do usuário)", ""]
    if floor is None:
        L.append("**Sem piso:** o braço s46 não rodou; G2–G4 ficam indeterminados.")
    else:
        origem = (
            "Sonnet 4.6 re-rodado ao vivo contra a referência"
            if floor_label == "s46"
            else "pares históricos Sonnet 4.6 × Sonnet 4.6 com o mesmo prompt_hash "
            "(resposta mais antiga contra a mais recente; sem chamada)"
        )
        L.append(
            f"Piso ({floor_label}: {origem}; n={floor['n']}): F1 estrito "
            f"{fmt(floor['strict']['f1'])}, F1 frouxo {fmt(floor['loose']['f1'])}, "
            f"F1 sem sigla (diag.) {fmt(floor['relaxed']['f1'])}, "
            f"recall sal≥0,7 {fmt(floor['salience_recall'])}, "
            f"ent/art {fmt(floor['ents_per_article'], 2)} (ref {fmt(floor['ref_ents_per_article'], 2)})."
        )
        L.append("")
        L.append(
            "Piso por estrato: "
            + "; ".join(
                f"{k} {fmt(v['f1_strict'])} (n={v['n']})" for k, v in floor["by_stratum"].items()
            )
        )
    L += [
        "",
        "| braço | G1 | G2 | G3 | G4 | G5 | G6 | G1–G6 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    sym = {True: "passa", False: "FALHA", None: "indet."}
    for arm, g in sorted(gates.items()):
        L.append(
            f"| {arm} | "
            + " | ".join(sym[g[k]["pass"]] for k in ("G1", "G2", "G3", "G4", "G5", "G6"))
            + f" | **{sym[g['pass_all']]}** |"
        )
    L.append("")
    for arm, g in sorted(gates.items()):
        L.append(
            f"- **{arm}**: "
            + "; ".join(f"{k}: {g[k]['detail']}" for k in ("G1", "G2", "G3", "G4", "G5", "G6"))
        )
    L += [
        "",
        f"## Projeção para {args.n_articles:,} artigos pendentes".replace(",", "."),
        "",
        "Dias = máx(tokens ÷ cota diária; artigos ÷ teto do DAG de "
        + f"{args.articles_day_cap:,.0f}".replace(",", ".")
        + " artigos/dia). Cota em tokens/dia informada por braço quando conhecida.",
        "",
        "| braço | US$/artigo | custo total US$ | tokens/artigo | cota tokens/dia | dias (cota) | "
        "dias (teto DAG) | dias |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for arm, p in sorted(projections.items()):
        m = metrics[arm]
        q = quotas.get(arm) or quotas.get(model_of.get(arm) or "")
        toks = (m["input_tokens_per_article"] or 0) + (m["output_tokens_per_article"] or 0)
        L.append(
            f"| {arm} | {fmt(m['cost_per_article'], 5)} | {fmt(p['cost_usd'], 0)} | {fmt(toks, 0)} | "
            f"{q if q else 'desconhecida'} | {fmt(p['days_by_quota'], 1)} | "
            f"{fmt(p['days_by_dag_cap'], 1)} | {fmt(p['days'], 1)} |"
        )
    if extras:
        L += [
            "",
            "## Conjuntos extras (validade e recusas)",
            "",
            "| conjunto | braço | n | ok | recusas | sem texto | erros | JSON extraível | F1 estrito vs ref |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for (elabel, arm), m in sorted(extras.items()):
            has_ref = any(
                (r.get("ref") or {}).get("raw_response")
                for r in load_sample(
                    next(e.split("=", 1)[1] for e in args.extra if e.startswith(elabel + "="))
                )
            )
            L.append(
                f"| {elabel} | {arm} | {m['n']} | {m['status'].get('ok', 0)} | {m['refusals']} | "
                f"{m['no_text']} | {m['api_errors']} | {fmt(m['json_extraivel_rate'])} | "
                f"{fmt(m['strict']['f1']) if has_ref else '— (sem referência)'} |"
            )
    L += ["", "## Matriz de tipos (referência → candidato, por nome)", ""]
    for arm, m in sorted(metrics.items()):
        diffs = {
            k: v for k, v in m["type_confusion"].items() if k.split("->")[0] != k.split("->")[1]
        }
        same = sum(
            v for k, v in m["type_confusion"].items() if k.split("->")[0] == k.split("->")[1]
        )
        L.append(f"- **{arm}**: tipo igual {same}; divergentes {diffs or 'nenhum'}")
    if args.spend and os.path.exists(args.spend):
        with open(args.spend) as f:
            sp = json.load(f)
        L += [
            "",
            "## Gasto (SpendLedger)",
            "",
            f"Total US${sp['spent_usd']:.4f} de US${sp['budget_usd']:.2f} em {sp['calls']} chamadas.",
            "",
            "| item | US$ | chamadas | tokens in | tokens out |",
            "|---|---|---|---|---|",
        ]
        for k, v in sorted(sp["by_arm"].items()):
            L.append(
                f"| {k} | {v['usd']:.4f} | {v['calls']} | {v['input_tokens']} | {v['output_tokens']} |"
            )
    if blind_note:
        L += ["", "## Revisão cega (G7)", "", blind_note]
    with open(os.path.join(args.out_dir, "resumo.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(args.out_dir, "metricas.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "metrics": {
                    a: {k: v for k, v in m.items() if k != "per_article_f1"}
                    for a, m in metrics.items()
                },
                "gates": gates,
                "floor_label": floor_label,
                "floor": {k: v for k, v in (floor or {}).items() if k != "per_article_f1"},
                "projections": projections,
                "same_as_floor": {
                    a: {k: v for k, v in m.items() if k != "per_article_f1"}
                    for a, m in same20.items()
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    print(f"relatório em {args.out_dir}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover")
    d.add_argument("--filter", default=r"5-5|sonnet-4-6|haiku-4-5")
    d.add_argument("--quota-filter", default=r"5\.5|Sonnet 4\.6|Haiku 4\.5")
    d.add_argument("--expect-account", default=None)
    d.add_argument("--out-json", default=None)

    p = sub.add_parser("probe")
    p.add_argument("--model-id", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--effort", default=None)
    p.add_argument("--thinking", default=None)
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--spend", required=True)
    p.add_argument("--budget-usd", type=float, required=True)

    pr = sub.add_parser("prepare")
    pr.add_argument("--raw", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--quota", default="all")
    pr.add_argument("--no-ref", action="store_true")

    r = sub.add_parser("run")
    r.add_argument("--arm", required=True, choices=sorted(ARMS))
    r.add_argument("--model-id", required=True)
    r.add_argument("--sample", required=True)
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--out-dir", required=True)
    r.add_argument("--spend", required=True)
    r.add_argument("--budget-usd", type=float, required=True)
    r.add_argument("--dry-run", action="store_true")

    rp = sub.add_parser("report")
    rp.add_argument("--sample", required=True)
    rp.add_argument("--runs-dir", required=True)
    rp.add_argument("--alias", default=None)
    rp.add_argument("--out-dir", required=True)
    rp.add_argument("--extra", action="append", help="rótulo=caminho de outra amostra")
    rp.add_argument("--spend", default=None)
    rp.add_argument("--blind-arm", default=None)
    rp.add_argument("--blind-n", type=int, default=20)
    rp.add_argument("--seed", type=int, default=20261016)
    rp.add_argument("--n-articles", type=int, default=191_500)
    rp.add_argument("--articles-day-cap", type=float, default=20_000)
    rp.add_argument(
        "--quota-tokens-day", default=None, help='JSON {"braço ou model_id": tokens/dia}'
    )
    rp.add_argument("--floor-sample", default=None, help="amostra de pares históricos (piso)")
    rp.add_argument("--floor-arm", default="s46hist")

    fp = sub.add_parser("floor-pairs")
    fp.add_argument("--sample", required=True)
    fp.add_argument("--out-dir", required=True)
    fp.add_argument("--arm", default="s46hist")

    args = ap.parse_args(argv)
    return {
        "discover": cmd_discover,
        "probe": cmd_probe,
        "prepare": cmd_prepare,
        "run": cmd_run,
        "report": cmd_report,
        "floor-pairs": cmd_floor_pairs,
    }[args.cmd](args)


def cmd_floor_pairs(args) -> int:
    """Grava o JSONL do piso histórico (sem chamada ao Bedrock)."""
    sample = load_sample(args.sample)
    label = os.path.splitext(os.path.basename(args.sample))[0]
    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"{args.arm}__{label}.jsonl")
    ok = skipped = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for pair in sample:
            try:
                rec = alt_record(pair, arm=args.arm)
            except ValueError as e:
                skipped += 1
                print(f"pulado: {e}")
                continue
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            ok += 1
    print(f"piso histórico: {ok} pares gravados em {out_path}; pulados {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
