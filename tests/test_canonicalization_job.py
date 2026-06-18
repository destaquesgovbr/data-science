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


# ---------------------------------------------------------------------- #
# _persist_decision — reuso por nome para LAW e ORG                     #
# ---------------------------------------------------------------------- #


class TestPersistDecisionLawReuse:
    def test_law_near_duplicate_does_not_mint_new_entity(self):
        """LAW com nome similar a uma já registrada deve reusar o id existente."""
        db = FakeDB()
        # Registry já tem "Estatuto da Surdocegueira" como LAW
        db.seed_registry("dgb_estatuto-da-surdocegueira", "Estatuto da Surdocegueira", "LAW")
        conn = db.conn()
        db.content["uid"] = "O Estatuto Surdocegueira foi aprovado..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})

        # LLM canonicaliza para um nome quase idêntico (Jaccard = 1.0, nome exato)
        bedrock = make_bedrock(
            canon_json(
                canonical_name="Estatuto da Surdocegueira",
                type="LAW",
                is_br_gov_org=False,
                confidence=0.9,
            )
        )
        J.resolve_form(
            conn, "estatuto surdocegueira", "LAW", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )

        # Deve reusar dgb_estatuto-da-surdocegueira, não criar novo nó
        reused_id = db.alias.get(("estatuto surdocegueira", "LAW"))
        assert reused_id == "dgb_estatuto-da-surdocegueira"
        # Apenas 1 entidade LAW no registry (sem duplicata)
        law_entries = [
            r for r in db.registry.values() if r.get("type") == "LAW"
        ]
        assert len(law_entries) == 1

    def test_law_different_number_mints_new_entity(self):
        """LAW com número diferente (baixa similaridade) cria nova entidade."""
        db = FakeDB()
        db.seed_registry("dgb_lei-14-100", "Lei nº 14.100/2022", "LAW")
        conn = db.conn()
        db.content["uid"] = "A nova lei foi sancionada..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})

        bedrock = make_bedrock(
            canon_json(
                canonical_name="Lei nº 14.967/2024",
                type="LAW",
                is_br_gov_org=False,
                confidence=0.9,
            )
        )
        J.resolve_form(
            conn, "lei no 14 967 2024", "LAW", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )

        # Nova entidade criada (id diferente)
        new_id = db.alias.get(("lei no 14 967 2024", "LAW"))
        assert new_id is not None
        assert new_id != "dgb_lei-14-100"
        law_entries = [
            r for r in db.registry.values() if r.get("type") == "LAW"
        ]
        assert len(law_entries) == 2

    def test_org_reuse_still_works(self):
        """Backward compat: ORG com nomes similares ainda reusa (threshold 0.62)."""
        db = FakeDB()
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O ministério anunciou..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})

        bedrock = make_bedrock(
            canon_json(
                canonical_name="Ministério da Educação (MEC)",
                type="ORG",
                is_br_gov_org=True,
                confidence=0.95,
            )
        )
        J.resolve_form(
            conn, "ministerio da educacao", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )

        reused_id = db.alias.get(("ministerio da educacao", "ORG"))
        assert reused_id == "dgb_mec"
        org_entries = [r for r in db.registry.values() if r.get("type") == "ORG"]
        assert len(org_entries) == 1

    def test_org_acronym_variant_reused_at_mint_time(self):
        """Mint-time ORG acronym-aware: LLM devolve o nome curto, mas reusa a sigla.

        Seed "Ministério da Educação (MEC)"; o LLM canonicaliza para o nome SEM a
        sigla ("Ministério da Educação"), Jaccard 0.75 < 0.85 (threshold subiu).
        Deve reusar a entidade existente via _is_acronym_variant (sem mintar nova).
        """
        db = FakeDB()
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O ministério anunciou..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})
        bedrock = make_bedrock(
            canon_json(
                canonical_name="Ministério da Educação",  # sem a sigla
                type="ORG",
                is_br_gov_org=True,
                confidence=0.95,
            )
        )
        J.resolve_form(
            conn, "ministerio da educacao", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        reused_id = db.alias.get(("ministerio da educacao", "ORG"))
        assert reused_id == "dgb_mec"
        org_entries = [r for r in db.registry.values() if r.get("type") == "ORG"]
        assert len(org_entries) == 1

    def test_org_distinct_bank_mints_new_at_mint_time(self):
        """Mint-time ORG: 'Banco do Brasil' NÃO reusa 'Banco Central do Brasil' (0.75<0.85)."""
        db = FakeDB()
        db.seed_registry("dgb_bcb", "Banco Central do Brasil", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O banco anunciou..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})
        bedrock = make_bedrock(
            canon_json(
                canonical_name="Banco do Brasil",
                type="ORG",
                is_br_gov_org=True,
                confidence=0.95,
            )
        )
        J.resolve_form(
            conn, "banco do brasil", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Duas ORGs distintas no registry (mintou nova, não reusou o BCB).
        org_entries = [r for r in db.registry.values() if r.get("type") == "ORG"]
        assert len(org_entries) == 2
        assert db.alias.get(("banco do brasil", "ORG")) != "dgb_bcb"


# ---------------------------------------------------------------------- #
# PER short-circuit — skip Bedrock when Wikidata has no candidates        #
# ---------------------------------------------------------------------- #


class TestPERShortCircuit:
    def test_per_no_wikidata_skips_bedrock(self):
        """PER sem candidatos Wikidata → needs_review direto, Bedrock não chamado."""
        db = FakeDB()
        db.content["uid"] = "José Silva é servidor público federal."
        # FakeWikidata retorna [] para qualquer busca (default)
        wikidata = FakeWikidata()
        bedrock = make_bedrock(canon_json(canonical_name="José Silva", type="PER"))
        conn = db.conn()
        decision = J.resolve_form(
            conn, "jose silva", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Bedrock NÃO deve ter sido chamado
        bedrock.client.invoke_model.assert_not_called()
        # Decisão deve ser needs_review
        assert decision["action"] == "needs_review"
        assert decision["status"] == "needs_review"
        assert decision["entity_id"] is None
        # seen deve estar marcado como needs_review
        seen = db.seen[("jose silva", "PER")]
        assert seen["status"] == "needs_review"

    def test_per_with_wikidata_candidates_calls_bedrock(self):
        """PER com candidatos Wikidata → Bedrock É chamado (caminho normal)."""
        db = FakeDB()
        db.content["uid"] = "Lula anunciou novas medidas econômicas."
        # FakeWikidata retorna candidato para qualquer query (chave especial "*")
        wikidata = FakeWikidata(
            candidates_by_query={
                "*": [{"qid": "Q37181", "label": "Lula", "description": "presidente do Brasil"}]
            }
        )
        bedrock = make_bedrock(
            [
                canon_json(canonical_name="Lula", type="PER", confidence=0.9),
                json.dumps({"qid": "Q37181", "confidence": 0.9}),
            ]
        )
        conn = db.conn()
        J.resolve_form(
            conn, "lula", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Bedrock DEVE ter sido chamado (ao menos 1 vez)
        assert bedrock.client.invoke_model.call_count >= 1

    def test_per_short_circuit_dry_run_does_not_write_seen(self):
        """dry_run=True: short-circuit retorna needs_review mas não escreve no DB."""
        db = FakeDB()
        db.content["uid"] = "ctx"
        wikidata = FakeWikidata()  # retorna [] para qualquer busca
        bedrock = make_bedrock(canon_json(canonical_name="Joao Ninguem", type="PER"))
        conn = db.conn()
        decision = J.resolve_form(
            conn, "joao ninguem", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
            dry_run=True,
        )
        # seen NÃO deve ter sido escrito
        assert ("joao ninguem", "PER") not in db.seen
        # Decisão ainda deve ser needs_review
        assert decision["action"] == "needs_review"
        # Bedrock não chamado
        bedrock.client.invoke_model.assert_not_called()

    def test_org_type_not_short_circuited(self):
        """ORG não sofre short-circuit (apenas PER). Bedrock É chamado."""
        db = FakeDB()
        db.content["uid"] = "ctx"
        # Wikidata retorna [] para qualquer query
        wikidata = FakeWikidata()
        bedrock = make_bedrock(canon_json(canonical_name="Empresa X", type="ORG", confidence=0.9))
        conn = db.conn()
        J.resolve_form(
            conn, "empresa x", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Bedrock DEVE ter sido chamado (ORG não tem short-circuit)
        assert bedrock.client.invoke_model.call_count >= 1

    def test_per_gazetteer_hit_bypasses_short_circuit(self):
        """Gazetteer tem prioridade máxima: se hit, não consulta Wikidata para pre-check."""
        db = FakeDB()
        # Alias "lula" → "Q37181" já no gazetteer
        db.seed_alias("lula", "PER", "Q37181")
        db.content["uid"] = "ctx"
        # FakeWikidata com spy para detectar chamadas de search
        class SpyWikidata(FakeWikidata):
            def __init__(self):
                super().__init__()
                self.search_calls = []

            def search(self, name, type=None, lang="pt", limit=7):
                self.search_calls.append(name)
                return super().search(name, type=type, lang=lang, limit=limit)

        spy_wikidata = SpyWikidata()
        bedrock = make_bedrock(canon_json(canonical_name="Lula", type="PER"))
        conn = db.conn()
        decision = J.resolve_form(
            conn, "lula", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=spy_wikidata, model_id="m",
        )
        # Deve retornar "gazetteer"
        assert decision["action"] == "gazetteer"
        assert decision["entity_id"] == "Q37181"
        # Wikidata NÃO deve ter sido chamado para pre-check
        assert spy_wikidata.search_calls == []
        # Bedrock também não chamado
        bedrock.client.invoke_model.assert_not_called()


# ---------------------------------------------------------------------- #
# --dedup CLI: run_dedup                                                  #
# ---------------------------------------------------------------------- #


class TestDedup:
    def test_dry_run_does_not_merge(self):
        """dry_run=True: near-duplicates são propostos mas não mergeados."""
        db = FakeDB()
        # Dois LAWs near-duplicate: Jaccard("lei estatuto surdocegueira",
        # "lei estatuto surdocegueira 2024") = 3/4 = 0.75 >= threshold 0.75
        db.seed_registry("dgb_lei-estatuto-surdocegueira", "Lei Estatuto Surdocegueira", "LAW")
        db.seed_registry(
            "dgb_lei-estatuto-surdocegueira-2024", "Lei Estatuto Surdocegueira 2024", "LAW"
        )
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=True)
        # Nenhum merge deve ter ocorrido
        assert len(db.registry) == 2
        # Mas deve ter proposto 1 merge
        assert result["proposed"] >= 1
        assert result["merged"] == 0

    def test_apply_merges_near_duplicates(self):
        """dry_run=False: near-duplicates são efetivamente mergeados."""
        db = FakeDB()
        db.seed_registry("dgb_programa-nacional-habitacao", "Programa Nacional Habitacao", "LAW")
        db.seed_registry(
            "dgb_programa-nacional-habitacao-popular",
            "Programa Nacional Habitacao Popular",
            "LAW",
        )
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=False)
        # Após merge: apenas 1 entidade restante
        assert len(db.registry) == 1
        assert result["merged"] >= 1
        assert result["proposed"] >= 1

    def test_dissimilar_entities_not_merged(self):
        """Entidades com nomes muito diferentes não são mergeadas."""
        db = FakeDB()
        # Jaccard("lei 14967 2024", "codigo civil") é muito baixo (< 0.75)
        db.seed_registry("dgb_lei-14967-2024", "Lei 14967 2024", "LAW")
        db.seed_registry("dgb_codigo-civil", "Codigo Civil", "LAW")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=False)
        # Nada deve ter sido mergeado nem proposto
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2

    def test_dedup_all_types_when_no_type_given(self):
        """Sem entity_type: processa todos os tipos em _ENTITY_REUSE_THRESHOLDS."""
        from news_enrichment.canonicalization import _ENTITY_REUSE_THRESHOLDS

        db = FakeDB()
        # Adiciona entidades para dois tipos diferentes
        db.seed_registry("dgb_org-a", "Ministerio Educacao", "ORG")
        db.seed_registry("dgb_org-b", "Ministerio Educacao Federal", "ORG")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type=None, dry_run=True)
        # Deve ter processado pelo menos todos os tipos com threshold definido
        for t in _ENTITY_REUSE_THRESHOLDS:
            assert t in result["types_processed"]

    def test_dedup_target_is_entity_with_more_aliases(self):
        """O target do merge é a entidade com mais aliases (source é a com menos)."""
        db = FakeDB()
        # dgb_lei-a tem 2 aliases; dgb_lei-b tem 0
        db.seed_registry("dgb_lei-a", "Lei Estatuto Surdocegueira", "LAW")
        db.seed_registry("dgb_lei-b", "Lei Estatuto Surdocegueira 2024", "LAW")
        # Adiciona 2 aliases para dgb_lei-a
        db.seed_alias("lei estatuto surdocegueira", "LAW", "dgb_lei-a")
        db.seed_alias("lei estatuto", "LAW", "dgb_lei-a")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=False)
        # dgb_lei-a deve ter sobrevivido (mais aliases = target)
        assert "dgb_lei-a" in db.registry
        assert "dgb_lei-b" not in db.registry
        assert result["merged"] >= 1


class TestDedupWikidataWins:
    """run_dedup: num par QID×dgb_, o QID Wikidata vence (vira target),
    independentemente da contagem de aliases (regra de identidade do projeto)."""

    def test_is_qid_helper(self):
        assert J._is_qid("Q216330")
        assert J._is_qid("Q5")
        assert not J._is_qid("dgb_ans")
        assert not J._is_qid("Qabc")
        assert not J._is_qid("")
        assert not J._is_qid("XQ123")

    def test_qid_is_target_even_with_fewer_aliases(self):
        """QID vence o dgb_ mesmo tendo MENOS aliases que o dgb_."""
        db = FakeDB()
        # mesma org: "X" vs "X (SIGLA)" → variante por sigla (path a)
        db.seed_registry("dgb_ans", "Agencia Nacional de Saude Suplementar", "ORG")
        db.seed_registry("Q9592631", "Agencia Nacional de Saude Suplementar (ANS)", "ORG")
        # dgb_ tem MAIS aliases — pela heurística antiga seria target (errado)
        db.seed_alias("ans", "ORG", "dgb_ans")
        db.seed_alias("agencia nacional de saude suplementar", "ORG", "dgb_ans")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] >= 1
        # O QID sobreviveu como chave canônica; o dgb_ foi o source removido.
        assert "Q9592631" in db.registry
        assert "dgb_ans" not in db.registry

    def test_qid_is_target_regardless_of_order(self):
        """Direção QID-wins independe da ordem de varredura (QID semeado primeiro
        = eid_a no laço, exercita o ramo `a_qid and not b_qid`)."""
        db = FakeDB()
        db.seed_registry("Q4314917", "Agencia Nacional de Aviacao Civil (Anac)", "ORG")
        db.seed_registry("dgb_anac", "Agencia Nacional de Aviacao Civil", "ORG")
        db.seed_alias("anac", "ORG", "dgb_anac")  # dgb_ tem o alias; QID não
        conn = db.conn()
        J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert "Q4314917" in db.registry
        assert "dgb_anac" not in db.registry

    def test_both_dgb_uses_alias_count_heuristic(self):
        """Par dgb_×dgb_ (sem QID) mantém a heurística de mais-aliases=target."""
        db = FakeDB()
        db.seed_registry("dgb_a", "Lei Estatuto Surdocegueira", "LAW")
        db.seed_registry("dgb_b", "Lei Estatuto Surdocegueira 2024", "LAW")
        db.seed_alias("lei estatuto surdocegueira", "LAW", "dgb_a")
        db.seed_alias("lei estatuto", "LAW", "dgb_a")
        conn = db.conn()
        J.run_dedup(conn, entity_type="LAW", dry_run=False)
        assert "dgb_a" in db.registry  # mais aliases = target
        assert "dgb_b" not in db.registry


class TestDedupOrgThreshold:
    """run_dedup ORG: threshold dedicado (0.85) + detector de variante por sigla."""

    def test_org_false_positive_banks_not_merged(self):
        """'Banco Central do Brasil' vs 'Banco do Brasil' (Jaccard 0.75) NÃO mergeia.

        Com o threshold de dedup ORG (0.85) e por não serem variante de sigla,
        instituições distintas são preservadas.
        """
        db = FakeDB()
        db.seed_registry("dgb_banco-central-do-brasil", "Banco Central do Brasil", "ORG")
        db.seed_registry("dgb_banco-do-brasil", "Banco do Brasil", "ORG")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2
        assert "dgb_banco-central-do-brasil" in db.registry
        assert "dgb_banco-do-brasil" in db.registry

    def test_org_police_false_positive_not_merged(self):
        """'Polícia Federal' vs 'Polícia Rodoviária Federal' NÃO mergeia."""
        db = FakeDB()
        db.seed_registry("dgb_policia-federal", "Polícia Federal", "ORG")
        db.seed_registry(
            "dgb_policia-rodoviaria-federal", "Polícia Rodoviária Federal", "ORG"
        )
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2

    def test_org_acronym_variant_merged_below_threshold(self):
        """'Ministério da Educação' vs 'Ministério da Educação (MEC)' mergeia.

        Jaccard = 3/4 = 0.75 < 0.85 (threshold dedup ORG), mas é variante por
        sigla → deve mergear assim mesmo. dgb_mec (mais aliases) é o target.
        """
        db = FakeDB()
        db.seed_registry("dgb_min-educacao", "Ministério da Educação", "ORG")
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG")
        # dgb_mec tem mais aliases → sobrevive como target.
        db.seed_alias("ministerio da educacao (mec)", "ORG", "dgb_mec")
        db.seed_alias("mec", "ORG", "dgb_mec")
        db.seed_alias("ministerio da educacao", "ORG", "dgb_min-educacao")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] == 1
        assert result["proposed"] == 1
        assert len(db.registry) == 1
        assert "dgb_mec" in db.registry
        assert "dgb_min-educacao" not in db.registry
        # alias do source migrado para o target.
        assert db.alias[("ministerio da educacao", "ORG")] == "dgb_mec"

    def test_org_explicit_threshold_overrides(self):
        """O arg threshold= explícito ainda sobrepõe tudo (banks com thr 0.70 → mergeia)."""
        db = FakeDB()
        db.seed_registry("dgb_banco-central-do-brasil", "Banco Central do Brasil", "ORG")
        db.seed_registry("dgb_banco-do-brasil", "Banco do Brasil", "ORG")
        conn = db.conn()
        # Jaccard = 3/4 = 0.75 >= 0.70 explícito → mergeia (override do default 0.85).
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False, threshold=0.70)
        assert result["merged"] == 1
        assert len(db.registry) == 1

    def test_org_acronym_variant_dry_run_merges_nothing(self):
        """dry_run=True: variante por sigla é proposta mas NÃO mergeada."""
        db = FakeDB()
        db.seed_registry("dgb_min-educacao", "Ministério da Educação", "ORG")
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=True)
        assert result["proposed"] >= 1
        assert result["merged"] == 0
        assert len(db.registry) == 2
