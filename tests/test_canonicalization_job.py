"""
Testes do orquestrador canonicalization_job (Fase 3): Steps A (gather),
B (resolve/persist) e C (backfill canonical_id).

DB simulado via FakeDB; Bedrock e Wikidata mockados. Nenhuma chamada real,
nenhum reprocessamento contra dados reais.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from news_enrichment import canonicalization_job as J
from news_enrichment.wikidata_client import Candidate
from tests.fakedb import FakeDB


def make_bedrock(response_text):
    client = MagicMock()
    bedrock = MagicMock()
    bedrock.client = client
    responses = [response_text] if isinstance(response_text, str) else list(response_text)
    state = {"i": 0}

    def _invoke(modelId=None, body=None):
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        body_mock = MagicMock()
        body_mock.read.return_value = json.dumps(
            {"content": [{"text": responses[idx]}]}
        ).encode()
        return {"body": body_mock}

    client.invoke_model.side_effect = _invoke
    return bedrock


class FakeWikidata:
    def __init__(self, candidates_by_query=None, claims_by_qid=None):
        self._candidates = candidates_by_query or {}
        self._claims = claims_by_qid or {}

    def search(self, name, type=None, lang="pt", limit=7):
        cands = self._candidates.get(name, self._candidates.get("*", []))
        return [Candidate(**c) for c in cands]

    def get_claims(self, qid):
        return self._claims.get(qid, {})


def canon_json(**kw):
    return json.dumps(
        {
            "canonical_name": kw.get("canonical_name", "X"),
            "type": kw.get("type", "ORG"),
            "aliases": kw.get("aliases", []),
            "wikidata_query": kw.get("wikidata_query", kw.get("canonical_name", "X")),
            "is_br_gov_org": kw.get("is_br_gov_org", False),
            "confidence": kw.get("confidence", 0.9),
            "not_an_entity": kw.get("not_an_entity", False),
        }
    )


# ---------------------------------------------------------------------- #
# Step A — gather                                                        #
# ---------------------------------------------------------------------- #


class TestGather:
    def test_stages_new_forms_excludes_resolved_and_aliased(self):
        db = FakeDB()
        # Forma já em entity_alias → excluída.
        db.seed_alias("ministerio da educacao", "ORG", "dgb_mec")
        # Forma já resolvida em seen → excluída.
        db.seen[("bolsa familia", "POLICY")] = {
            "surface_norm": "bolsa familia", "type": "POLICY", "status": "resolved",
            "sample_unique_id": "u0", "attempts": 1,
        }
        # gather rows (surface, type, sample_uid)
        db.gather_rows = [
            ("Ministério da Educação", "ORG", "u1"),   # excluída (alias)
            ("Bolsa Família", "POLICY", "u2"),         # excluída (seen resolved)
            ("Finep", "ORG", "u3"),                    # nova → staged
            ("Copa do Mundo", "EVENT", "u4"),          # nova → staged
        ]
        conn = db.conn()
        since = datetime(2026, 5, 1, tzinfo=timezone.utc)
        until = datetime(2026, 6, 1, tzinfo=timezone.utc)
        staged = J.gather_forms(conn, since, until)

        staged_keys = {(s["surface_norm"], s["type"]) for s in staged}
        assert ("finep", "ORG") in staged_keys
        assert ("copa do mundo", "EVENT") in staged_keys
        assert ("ministerio da educacao", "ORG") not in staged_keys
        assert ("bolsa familia", "POLICY") not in staged_keys
        # staged forms estão em seen como pending.
        assert db.seen[("finep", "ORG")]["status"] == "pending"
        assert db.seen[("finep", "ORG")]["sample_unique_id"] == "u3"

    def test_dedup_same_form_different_samples(self):
        db = FakeDB()
        db.gather_rows = [
            ("Finep", "ORG", "u1"),
            ("Finep", "ORG", "u2"),  # mesma forma normalizada
        ]
        conn = db.conn()
        staged = J.gather_forms(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        finep = [s for s in staged if s["surface_norm"] == "finep"]
        assert len(finep) == 1


# ---------------------------------------------------------------------- #
# Step B — not_an_entity drop persistence                               #
# ---------------------------------------------------------------------- #


class TestResolveDropsNonEntity:
    def test_not_an_entity_marks_resolved_no_registry_no_alias(self):
        db = FakeDB()
        conn = db.conn()
        db.content["uid"] = "Texto sobre inteligência artificial em geral."
        wikidata = FakeWikidata()
        bedrock = make_bedrock(
            canon_json(canonical_name="inteligência artificial", not_an_entity=True)
        )
        decision = J.resolve_form(
            conn, "inteligencia artificial", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        assert decision["action"] == "drop"
        # seen.resolved, entity_id NULL.
        seen = db.seen[("inteligencia artificial", "ORG")]
        assert seen["status"] == "resolved"
        assert seen["entity_id"] is None
        # sem alias, sem registry.
        assert ("inteligencia artificial", "ORG") not in db.alias
        assert db.registry == {}

    def test_needs_review_does_not_write_alias(self):
        db = FakeDB()
        conn = db.conn()
        db.content["uid"] = "ctx"
        wikidata = FakeWikidata(
            candidates_by_query={
                "*": [
                    {"qid": "Q1", "label": "A", "description": ""},
                    {"qid": "Q2", "label": "B", "description": ""},
                ]
            },
            claims_by_qid={
                "Q1": {"country": "Q155", "country_is_br": True, "instance_of": []},
                "Q2": {"country": "Q155", "country_is_br": True, "instance_of": []},
            },
        )
        # canon conf baixa + 2 QIDs → escala; escalada devolve conf baixa.
        bedrock = make_bedrock(
            [
                canon_json(canonical_name="Ambíguo", type="PER", confidence=0.5),
                json.dumps({"qid": "Q1", "confidence": 0.3}),
            ]
        )
        decision = J.resolve_form(
            conn, "ambiguo", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        assert decision["action"] == "needs_review"
        assert db.seen[("ambiguo", "PER")]["status"] == "needs_review"
        assert ("ambiguo", "PER") not in db.alias


# ---------------------------------------------------------------------- #
# Step C — backfill canonical_id                                         #
# ---------------------------------------------------------------------- #


class TestBackfill:
    def test_resolved_mention_gets_canonical_id_unresolved_stays(self):
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        # "tema solto" não está em alias → fica sem canonical_id.
        features = {
            "word_count": 100,  # outra chave deve ser preservada (no UPDATE só entities muda)
            "entities": [
                {"text": "Finep", "type": "ORG", "forma_canonica": "Finep", "count": 2},
                {"text": "Tema Solto", "type": "POLICY", "forma_canonica": "Tema Solto", "count": 1},
            ],
        }
        db.features_rows = [("uid-1", features)]
        conn = db.conn()
        stats = J.backfill_canonical_ids(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert stats["updated"] == 1
        assert stats["mentions_linked"] == 1
        written = json.loads(db.backfilled["uid-1"])
        by_text = {e["text"]: e for e in written}
        assert by_text["Finep"]["canonical_id"] == "Q_FINEP"
        assert "canonical_id" not in by_text["Tema Solto"]

    def test_idempotent_rerun_no_change(self):
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        features = {
            "entities": [
                {"text": "Finep", "type": "ORG", "forma_canonica": "Finep",
                 "count": 1, "canonical_id": "Q_FINEP"},
            ],
        }
        db.features_rows = [("uid-1", features)]
        conn = db.conn()
        stats = J.backfill_canonical_ids(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # já tinha o canonical_id correto → nenhum UPDATE.
        assert stats["updated"] == 0
        assert "uid-1" not in db.backfilled

    def test_jsonb_set_targets_entities_only(self):
        """A escrita usa jsonb_set no caminho {entities} — preserva outras chaves."""
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        db.features_rows = [
            ("uid-1", {"sentiment": {"label": "positive"},
                       "entities": [{"text": "Finep", "type": "ORG",
                                     "forma_canonica": "Finep", "count": 1}]})
        ]
        conn = db.conn()
        J.backfill_canonical_ids(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # o SQL emitido contém jsonb_set(features, '{entities}', ...)
        update_logs = [s for (s, _p) in db.log if "jsonb_set" in s.lower()]
        assert update_logs
        assert "{entities}" in update_logs[0]


# ---------------------------------------------------------------------- #
# apply_canonical_ids (pure)                                             #
# ---------------------------------------------------------------------- #


class TestApplyCanonicalIds:
    def test_uses_forma_canonica_then_text(self):
        alias_map = {("finep", "ORG"): "Q_FINEP"}
        entities = [{"text": "FINEP", "forma_canonica": "Finep", "type": "ORG"}]
        new, linked, changed = J._apply_canonical_ids(entities, alias_map)
        assert linked == 1
        assert changed is True
        assert new[0]["canonical_id"] == "Q_FINEP"

    def test_falls_back_to_text_when_no_forma_canonica(self):
        alias_map = {("finep", "ORG"): "Q_FINEP"}
        entities = [{"text": "Finep", "type": "ORG"}]
        new, linked, changed = J._apply_canonical_ids(entities, alias_map)
        assert new[0]["canonical_id"] == "Q_FINEP"

    def test_unresolved_unchanged(self):
        new, linked, changed = J._apply_canonical_ids(
            [{"text": "X", "type": "ORG"}], {}
        )
        assert linked == 0
        assert changed is False
        assert "canonical_id" not in new[0]


# ---------------------------------------------------------------------- #
# Governador de cota wired em resolve_pending                            #
# ---------------------------------------------------------------------- #


def make_bedrock_usage(responses, usages):
    """Bedrock falso que devolve (texto, usage) por chamada."""
    client = MagicMock()
    bedrock = MagicMock()
    bedrock.client = client
    state = {"i": 0}

    def _invoke(modelId=None, body=None):
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        body_mock = MagicMock()
        payload = {"content": [{"text": responses[idx]}]}
        u = usages[idx] if idx < len(usages) else None
        if u is not None:
            payload["usage"] = u
        body_mock.read.return_value = json.dumps(payload).encode()
        return {"body": body_mock}

    client.invoke_model.side_effect = _invoke
    return bedrock


class TestResolvePendingGovernor:
    def _seed_pending(self, db, n):
        for i in range(n):
            db.seen[(f"forma{i}", "ORG")] = {
                "surface_norm": f"forma{i}", "type": "ORG", "status": "pending",
                "sample_unique_id": f"u{i}", "attempts": 0,
            }

    def test_records_usage_in_ledger(self):
        db = FakeDB()
        self._seed_pending(db, 1)
        # internal (alta conf, sem candidatos) — uma chamada canon, sem escalada.
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="Forma0", type="ORG", confidence=0.95)],
            [{"input_tokens": 300, "output_tokens": 60}],
        )
        wikidata = FakeWikidata()  # zero candidatos
        conn = db.conn()
        stats = J.resolve_pending(
            conn, 10, bedrock_client=bedrock, wikidata_client=wikidata,
            model_id="sonnet", daily_quota=None,
        )
        assert stats["resolved"] == 1
        assert db.ledger["sonnet"] == {"input_tokens": 300, "output_tokens": 60}

    def test_stops_when_budget_exhausted(self):
        db = FakeDB()
        self._seed_pending(db, 10)
        # Pré-carrega o ledger acima do teto (0.8 * 1000 = 800).
        db.ledger["sonnet"] = {"input_tokens": 900, "output_tokens": 0}
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="X", type="ORG", confidence=0.95)],
            [{"input_tokens": 1, "output_tokens": 1}],
        )
        wikidata = FakeWikidata()
        conn = db.conn()
        stats = J.resolve_pending(
            conn, 10, bedrock_client=bedrock, wikidata_client=wikidata,
            model_id="sonnet", daily_quota=1000, quota_fraction=0.8,
        )
        # Parou logo na primeira checagem (i=0) — nada resolvido.
        assert stats["budget_exhausted"] is True
        assert stats["resolved"] == 0
        # Não chamou o Bedrock.
        bedrock.client.invoke_model.assert_not_called()

    def test_no_quota_runs_uncapped(self):
        db = FakeDB()
        self._seed_pending(db, 2)
        db.ledger["sonnet"] = {"input_tokens": 10_000_000, "output_tokens": 0}
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="A", type="ORG", confidence=0.95),
             canon_json(canonical_name="B", type="ORG", confidence=0.95)],
            [{"input_tokens": 1, "output_tokens": 1},
             {"input_tokens": 1, "output_tokens": 1}],
        )
        wikidata = FakeWikidata()
        conn = db.conn()
        stats = J.resolve_pending(
            conn, 10, bedrock_client=bedrock, wikidata_client=wikidata,
            model_id="sonnet", daily_quota=None,
        )
        # Sem cota → não bloqueia, resolve tudo.
        assert stats["resolved"] == 2
        assert stats["budget_exhausted"] is False
