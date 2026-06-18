"""
Fake psycopg2 connection/cursor para os testes de canonicalização.

Simula apenas o subconjunto de SQL que os módulos de canonicalização emitem
contra entity_alias, entity_registry e entity_registry_seen. NÃO é um motor SQL
geral — reconhece os comandos por substring estável e opera sobre dicts em
memória. Suficiente para validar a lógica de gates/reuso/persistência sem DB real.
"""

class FakeCursor:
    def __init__(self, db, conn):
        self.db = db
        self.conn = conn
        self.connection = conn
        self._result = []
        self.description = None
        self.rowcount = 0

    # -- protocolo mínimo --

    def execute(self, sql, params=None):
        params = params or ()
        s = " ".join(sql.split())  # normaliza whitespace para matching
        self.db.log.append((s, params))
        self._result = []
        self.description = None

        low = s.lower()

        # entity_alias SELECT
        if low.startswith("select entity_id from entity_alias where alias_norm"):
            alias_norm, atype = params[0], params[1]
            ent = self.db.alias.get((alias_norm, atype))
            if ent is not None:
                self._result = [(ent,)]
            return

        # entity_alias INSERT
        if "insert into entity_alias" in low:
            alias_norm, atype, entity_id = params[0], params[1], params[2]
            if "on conflict" in low and "do update" in low:
                self.db.alias[(alias_norm, atype)] = entity_id  # sobrescreve (ON CONFLICT DO UPDATE)
            else:
                self.db.alias.setdefault((alias_norm, atype), entity_id)  # first-write-wins
            return

        # entity_registry reuse by wikidata
        if "from entity_registry where wikidata_id" in low:
            qid = params[0]
            for r in self.db.registry.values():
                if r.get("wikidata_id") == qid or r["entity_id"] == qid:
                    self._result = [(r["entity_id"],)]
                    return
            return

        # entity_registry name reuse (trigram path) — força fallback
        if "similarity(canonical_name" in low:
            raise Exception("similarity() not available in fake db")

        # entity_registry fallback select por type (qualquer tipo, não só ORG)
        if "select entity_id, canonical_name from entity_registry where type" in low:
            # extrai o tipo do params
            atype = params[0] if params else None
            if atype:
                self._result = [
                    (r["entity_id"], r["canonical_name"])
                    for r in self.db.registry.values()
                    if r.get("type") == atype.upper()
                ]
            return

        # entity_registry_seen SELECT status
        if "select status from entity_registry_seen" in low:
            surface_norm, atype = params[0], params[1]
            row = self.db.seen.get((surface_norm, atype))
            if row is not None:
                self._result = [(row["status"],)]
            return

        # entity_registry_seen INSERT (pending upsert) — antes do registry genérico
        if "insert into entity_registry_seen" in low:
            surface_norm, atype, sample = params[0], params[1], params[2]
            existing = self.db.seen.get((surface_norm, atype))
            if existing is None:
                self.db.seen[(surface_norm, atype)] = {
                    "surface_norm": surface_norm,
                    "type": atype,
                    "status": "pending",
                    "entity_id": None,
                    "attempts": 0,
                    "sample_unique_id": sample,
                    "last_error": None,
                }
            else:
                if existing.get("sample_unique_id") is None:
                    existing["sample_unique_id"] = sample
            return

        # entity_registry_seen UPDATE
        if low.startswith("update entity_registry_seen set status"):
            status, entity_id, attempts, last_error = (
                params[0], params[1], params[2], params[3],
            )
            surface_norm, atype = params[4], params[5]
            row = self.db.seen.setdefault(
                (surface_norm, atype),
                {"surface_norm": surface_norm, "type": atype, "sample_unique_id": None},
            )
            row.update(
                status=status, entity_id=entity_id, attempts=attempts, last_error=last_error
            )
            return

        # entity_registry UPSERT (após os handlers de _seen para não colidir)
        if "insert into entity_registry " in low or low.startswith("insert into entity_registry\n"):
            self._upsert_registry(params)
            return

        # fetch pending
        if "where status = 'pending'" in low:
            self.description = [("surface_norm",), ("type",), ("sample_unique_id",), ("attempts",)]
            self._result = [
                (r["surface_norm"], r["type"], r.get("sample_unique_id"), r.get("attempts", 0))
                for r in self.db.seen.values()
                if r["status"] == "pending"
            ]
            return

        # news.content
        if "select content from news where unique_id" in low:
            uid = params[0]
            self._result = [(self.db.content.get(uid, ""),)]
            return

        # news_llm_raw insert
        if "insert into news_llm_raw" in low:
            self.db.llm_raw.append(params)
            return

        # llm_daily_usage UPSERT (ledger de cota)
        if "insert into llm_daily_usage" in low:
            model_id, in_tok, out_tok = params[0], params[1], params[2]
            row = self.db.ledger.setdefault(
                model_id, {"input_tokens": 0, "output_tokens": 0}
            )
            row["input_tokens"] += int(in_tok or 0)
            row["output_tokens"] += int(out_tok or 0)
            return

        # llm_daily_usage SUM (tokens usados hoje)
        if "from llm_daily_usage" in low and "sum" in low:
            model_id = params[0]
            row = self.db.ledger.get(model_id)
            if row is None:
                self._result = [(0,)]
            else:
                self._result = [(row["input_tokens"] + row["output_tokens"],)]
            return

        # entity_alias full dump
        if low.startswith("select alias_norm, type, entity_id from entity_alias"):
            self._result = [(k[0], k[1], v) for k, v in self.db.alias.items()]
            return

        # gather mentions
        if "from news_features nf" in low and "jsonb_array_elements" in low:
            self.description = [("surface",), ("type",), ("sample_unique_id",)]
            self._result = list(self.db.gather_rows)
            return

        # backfill select
        if low.startswith("select nf.unique_id, nf.features"):
            self._result = list(self.db.features_rows)
            return

        # news_features jsonb_set update
        if "update news_features set features = jsonb_set" in low:
            new_json, uid = params[0], params[1]
            self.db.backfilled[uid] = new_json
            return

        # merge_entities SQL 1 — UPDATE entity_registry AS t SET (herda metadata + merge aliases JSONB)
        if low.startswith("update entity_registry as t set"):
            import json as _json
            target_id, source_id = params[0], params[1]
            tgt = self.db.registry.get(target_id)
            src = self.db.registry.get(source_id)
            if tgt is not None and src is not None:
                # COALESCE: só herda se target não tem
                if not tgt.get("wikidata_id") and src.get("wikidata_id"):
                    tgt["wikidata_id"] = src["wikidata_id"]
                if not tgt.get("wikidata_url") and src.get("wikidata_url"):
                    tgt["wikidata_url"] = src["wikidata_url"]
                # merge aliases JSONB: union sem duplicatas
                def _parse_aliases(val):
                    if val is None:
                        return []
                    if isinstance(val, list):
                        return val
                    try:
                        return _json.loads(val)
                    except Exception:
                        return []
                tgt_aliases = _parse_aliases(tgt.get("aliases"))
                src_aliases = _parse_aliases(src.get("aliases"))
                merged = list({a for a in tgt_aliases + src_aliases})
                tgt["aliases"] = _json.dumps(merged, ensure_ascii=False)
            return

        # merge_entities SQL 2 — UPDATE entity_alias SET entity_id (redirect aliases, NOT EXISTS)
        if "update entity_alias set entity_id" in low and "not exists" in low:
            target_id, source_id = params[0], params[1]
            # target_id in params[2] is redundant check (same as params[0])
            migrated = 0
            to_update = []
            for k, v in list(self.db.alias.items()):
                if v == source_id:
                    # check: does (k[0], k[1], target_id) already exist?
                    if self.db.alias.get(k) != target_id:
                        to_update.append(k)
            for k in to_update:
                self.db.alias[k] = target_id
                migrated += 1
            self.rowcount = migrated
            return

        # merge_entities SQL 3 — DELETE remaining source aliases from entity_alias
        if "delete from entity_alias where entity_id" in low:
            source_id = params[0]
            keys_to_delete = [k for k, v in list(self.db.alias.items()) if v == source_id]
            for k in keys_to_delete:
                del self.db.alias[k]
            return

        # merge_entities SQL 4 — DELETE source from entity_registry
        if "delete from entity_registry where entity_id" in low:
            source_id = params[0]
            self.db.registry.pop(source_id, None)
            return

        # default: no-op
        return

    def _upsert_registry(self, params):
        (
            entity_id, canonical_name, etype, aliases, wikidata_id, wikidata_url,
            description, agency_key, confidence, provenance, extra,
        ) = params
        existing = self.db.registry.get(entity_id)
        if existing is None:
            self.db.registry[entity_id] = {
                "entity_id": entity_id,
                "canonical_name": canonical_name,
                "type": etype,
                "aliases": aliases,
                "wikidata_id": wikidata_id,
                "wikidata_url": wikidata_url,
                "description": description,
                "agency_key": agency_key,
                "confidence": confidence,
                "provenance": provenance,
                "extra": extra,
            }
        else:
            # ON CONFLICT DO UPDATE (aditivo)
            if wikidata_id and not existing.get("wikidata_id"):
                existing["wikidata_id"] = wikidata_id
            if description and not existing.get("description"):
                existing["description"] = description

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class FakeConn:
    def __init__(self, db):
        self.db = db
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return FakeCursor(self.db, self)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass


class FakeDB:
    """Estado em memória partilhado entre cursores."""

    def __init__(self):
        self.alias = {}        # (alias_norm, type) -> entity_id
        self.registry = {}     # entity_id -> row dict
        self.seen = {}         # (surface_norm, type) -> row dict
        self.content = {}      # unique_id -> content
        self.llm_raw = []      # list of params tuples
        self.gather_rows = []  # (surface, type, sample_uid)
        self.features_rows = []  # (unique_id, features dict)
        self.backfilled = {}   # unique_id -> new entities json str
        self.ledger = {}       # model_id -> {input_tokens, output_tokens}
        self.log = []          # (sql, params)

    def conn(self):
        return FakeConn(self)

    def seed_alias(self, alias_norm, type, entity_id):
        self.alias[(alias_norm, type)] = entity_id

    def seed_registry(self, entity_id, canonical_name, type, **kw):
        self.registry[entity_id] = {
            "entity_id": entity_id,
            "canonical_name": canonical_name,
            "type": type,
            "aliases": kw.get("aliases", "[]"),
            "wikidata_id": kw.get("wikidata_id"),
            "wikidata_url": kw.get("wikidata_url"),
            "description": kw.get("description"),
            "agency_key": kw.get("agency_key"),
            "confidence": kw.get("confidence"),
            "provenance": kw.get("provenance"),
            "extra": kw.get("extra"),
        }
