"""
Testes do núcleo de canonicalização (Fase 3).

Bedrock e Wikidata SEMPRE mockados; DB simulado via FakeDB. Nenhuma chamada real,
nenhum reprocessamento contra dados reais.
"""

import json
from unittest.mock import MagicMock

import pytest

from news_enrichment import canonicalization as C
from news_enrichment.wikidata_client import Candidate
from tests.fakedb import FakeDB

# Migration 017 normalize() reference (importado dinamicamente via parametrize abaixo).


# ---------------------------------------------------------------------- #
# Fakes                                                                   #
# ---------------------------------------------------------------------- #


def make_bedrock(response_text):
    """BedrockLLMClient falso: .client.invoke_model devolve `response_text`.

    response_text pode ser str (uma resposta) ou lista (uma por chamada).
    """
    client = MagicMock()
    bedrock = MagicMock()
    bedrock.client = client

    if isinstance(response_text, str):
        responses = [response_text]
    else:
        responses = list(response_text)
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
    """Wikidata falso: search() devolve candidatos pré-definidos; get_claims() idem."""

    def __init__(self, candidates_by_query=None, claims_by_qid=None):
        self._candidates = candidates_by_query or {}
        self._claims = claims_by_qid or {}
        self.search_calls = []
        self.claims_calls = []

    def search(self, name, type=None, lang="pt", limit=7):
        self.search_calls.append(name)
        cands = self._candidates.get(name, self._candidates.get("*", []))
        return [Candidate(**c) if isinstance(c, dict) else c for c in cands]

    def get_claims(self, qid):
        self.claims_calls.append(qid)
        return self._claims.get(qid, {})


def canon_json(**kw):
    base = {
        "canonical_name": kw.get("canonical_name", "X"),
        "type": kw.get("type", "ORG"),
        "aliases": kw.get("aliases", []),
        "wikidata_query": kw.get("wikidata_query", kw.get("canonical_name", "X")),
        "is_br_gov_org": kw.get("is_br_gov_org", False),
        "confidence": kw.get("confidence", 0.9),
        "not_an_entity": kw.get("not_an_entity", False),
    }
    return json.dumps(base)


# ---------------------------------------------------------------------- #
# normalize() parity with migration 017                                  #
# ---------------------------------------------------------------------- #


class TestNormalizeParity:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Ministério da Educação", "ministerio da educacao"),
            ("  FINEP  ", "finep"),
            ("São   Paulo", "sao paulo"),
            ("Pé-de-Meia", "pe-de-meia"),
            ("CAIXA econômica", "caixa economica"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_matches_expected(self, raw, expected):
        assert C.normalize(raw) == expected

    def test_byte_identical_to_migration_017(self):
        """Importa o normalize() da 017 e compara saída em vários casos.

        A 017 importa `loguru` (não está neste venv); como só precisamos da
        função pura normalize(), stubamos loguru em sys.modules antes do exec.
        Isso garante que comparamos com a IMPLEMENTAÇÃO REAL da 017, não com uma
        cópia.
        """
        import importlib.util
        import os
        import sys
        from unittest.mock import MagicMock

        path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "data-platform", "scripts", "migrations",
            "017_seed_entity_registry_from_agencies.py",
        )
        path = os.path.abspath(path)
        if not os.path.exists(path):
            pytest.skip("migration 017 not present in this checkout")

        injected = "loguru" not in sys.modules
        if injected:
            stub = MagicMock()
            stub.logger = MagicMock()
            sys.modules["loguru"] = stub
        try:
            spec = importlib.util.spec_from_file_location("mig017", path)
            mig = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mig)
        finally:
            if injected:
                sys.modules.pop("loguru", None)

        cases = [
            "Ministério da Saúde",
            "  Ministério   da  Educação (MEC) ",
            "Financiadora de Estudos e Projetos (Finep)",
            "São Paulo",
            "ÁGUA",
            "",
            None,
        ]
        for c in cases:
            assert C.normalize(c) == mig.normalize(c), f"divergiu para {c!r}"


# ---------------------------------------------------------------------- #
# gazetteer short-circuit (zero Bedrock/Wikidata)                        #
# ---------------------------------------------------------------------- #


class TestGazetteerShortCircuit:
    def test_seeded_org_resolves_without_llm_or_wikidata(self):
        db = FakeDB()
        db.seed_alias("ministerio da educacao", "ORG", "dgb_mec")
        conn = db.conn()

        bedrock = make_bedrock("SHOULD NOT BE CALLED")
        wikidata = FakeWikidata()

        from news_enrichment import canonicalization_job as J

        decision = J.resolve_form(
            conn,
            "ministerio da educacao",
            "ORG",
            sample_unique_id="uid-1",
            attempts=0,
            bedrock_client=bedrock,
            wikidata_client=wikidata,
            model_id="m",
        )
        assert decision["action"] == "gazetteer"
        assert decision["entity_id"] == "dgb_mec"
        # zero chamadas a Bedrock / Wikidata.
        bedrock.client.invoke_model.assert_not_called()
        assert wikidata.search_calls == []
        # seen marcado resolved.
        assert db.seen[("ministerio da educacao", "ORG")]["status"] == "resolved"
        assert db.seen[("ministerio da educacao", "ORG")]["entity_id"] == "dgb_mec"


# ---------------------------------------------------------------------- #
# Gate matrix                                                            #
# ---------------------------------------------------------------------- #


class TestGateMatrix:
    def _candidates_br(self, qid="Q42"):
        return [
            {
                "qid": qid,
                "label": "Finep",
                "description": "agência brasileira",
                "country": "Q155",
                "country_is_br": True,
                "instance_of": [],
            }
        ]

    def test_high_conf_single_br_qid_links(self):
        canon = C.parse_canon_response(
            canon_json(canonical_name="Finep", type="ORG", confidence=0.95), "Finep"
        )
        decision = C.apply_gates(
            form="finep",
            canon=canon,
            candidates=self._candidates_br("Q42"),
            sample_context="",
            model_id="m",
            bedrock_client=make_bedrock("unused"),
        )
        assert decision["action"] == "link"
        assert decision["entity_id"] == "Q42"
        assert decision["provenance"] == "wikidata"
        assert decision["write_alias"] is True

    def test_high_conf_zero_candidates_is_internal(self):
        canon = C.parse_canon_response(
            canon_json(canonical_name="Programa Local X", type="POLICY", confidence=0.9),
            "Programa Local X",
        )
        decision = C.apply_gates(
            form="programa local x",
            canon=canon,
            candidates=[],
            sample_context="",
            model_id="m",
            bedrock_client=make_bedrock("unused"),
        )
        assert decision["action"] == "internal"
        assert decision["provenance"] == "llm"
        assert decision["entity_id"] is None  # mintado no persist
        assert decision["write_alias"] is True

    def test_multiple_qids_invokes_escalation(self):
        canon = C.parse_canon_response(
            canon_json(canonical_name="João Silva", type="ORG", confidence=0.9), "João Silva"
        )
        candidates = [
            {"qid": "Q1", "label": "A", "description": "", "country": "Q155",
             "country_is_br": True, "instance_of": []},
            {"qid": "Q2", "label": "B", "description": "", "country": "Q155",
             "country_is_br": True, "instance_of": []},
        ]
        # escalada escolhe Q2 com alta confiança.
        bedrock = make_bedrock(json.dumps({"qid": "Q2", "confidence": 0.9}))
        decision = C.apply_gates(
            form="joao silva",
            canon=canon,
            candidates=candidates,
            sample_context="contexto",
            model_id="m",
            bedrock_client=bedrock,
        )
        # escalada FOI invocada (Bedrock chamado uma vez).
        bedrock.client.invoke_model.assert_called_once()
        assert decision["action"] == "link"
        assert decision["entity_id"] == "Q2"

    def test_type_per_always_escalates(self):
        """type=PER com conf alta e QID único BR ainda escala (não auto-link)."""
        canon = C.parse_canon_response(
            canon_json(canonical_name="Lula", type="PER", confidence=0.99), "Lula"
        )
        candidates = self._candidates_br("Q333")
        bedrock = make_bedrock(json.dumps({"qid": "Q333", "confidence": 0.95}))
        decision = C.apply_gates(
            form="lula",
            canon=canon,
            candidates=candidates,
            sample_context="O presidente Lula...",
            model_id="m",
            bedrock_client=bedrock,
        )
        # escalada invocada mesmo com QID único (porque type==PER).
        bedrock.client.invoke_model.assert_called_once()
        assert decision["action"] == "link"
        assert decision["entity_id"] == "Q333"

    def test_post_escalation_low_conf_is_needs_review_no_alias(self):
        canon = C.parse_canon_response(
            canon_json(canonical_name="Ambíguo", type="PER", confidence=0.6), "Ambíguo"
        )
        candidates = [
            {"qid": "Q1", "label": "A", "description": "", "country": "Q155",
             "country_is_br": True, "instance_of": []},
            {"qid": "Q2", "label": "B", "description": "", "country": "Q155",
             "country_is_br": True, "instance_of": []},
        ]
        # escalada não chega a confiança ≥0.7.
        bedrock = make_bedrock(json.dumps({"qid": "Q1", "confidence": 0.4}))
        decision = C.apply_gates(
            form="ambiguo",
            canon=canon,
            candidates=candidates,
            sample_context="",
            model_id="m",
            bedrock_client=bedrock,
        )
        assert decision["action"] == "needs_review"
        assert decision["status"] == "needs_review"
        assert decision["write_alias"] is False

    def test_escalation_returns_no_qid_is_needs_review(self):
        canon = C.parse_canon_response(
            canon_json(canonical_name="X", type="PER", confidence=0.9), "X"
        )
        candidates = self._candidates_br("Q9")
        bedrock = make_bedrock(json.dumps({"qid": None, "confidence": 0.0}))
        decision = C.apply_gates(
            form="x",
            canon=canon,
            candidates=candidates,
            sample_context="",
            model_id="m",
            bedrock_client=bedrock,
        )
        assert decision["action"] == "needs_review"
        assert decision["write_alias"] is False

    def test_not_an_entity_is_dropped(self):
        canon = C.parse_canon_response(
            canon_json(canonical_name="inteligência artificial", not_an_entity=True),
            "inteligência artificial",
        )
        decision = C.apply_gates(
            form="inteligencia artificial",
            canon=canon,
            candidates=[],
            sample_context="",
            model_id="m",
            bedrock_client=make_bedrock("unused"),
        )
        assert decision["action"] == "drop"
        assert decision["status"] == "resolved"
        assert decision["entity_id"] is None
        assert decision["write_alias"] is False


# ---------------------------------------------------------------------- #
# Homonym guard (BR vs foreign) — full resolve_form path                 #
# ---------------------------------------------------------------------- #


class TestHomonymGuard:
    def test_saude_br_vs_libano_distinct_entities(self):
        from news_enrichment import canonicalization_job as J

        db = FakeDB()
        conn = db.conn()
        db.content["uid-br"] = "O Ministério da Saúde do Brasil anunciou..."
        db.content["uid-lb"] = "O Ministério da Saúde do Líbano informou..."

        # Wikidata: cada query devolve um QID com país distinto.
        wikidata = FakeWikidata(
            candidates_by_query={
                "Ministério da Saúde": [
                    {"qid": "Q_BR", "label": "Ministério da Saúde", "description": "Brasil"}
                ],
                "Ministério da Saúde do Líbano": [
                    {"qid": "Q_LB", "label": "Ministério da Saúde do Líbano", "description": "Líbano"}
                ],
            },
            claims_by_qid={
                "Q_BR": {"country": "Q155", "country_is_br": True, "instance_of": [],
                         "description": "órgão BR"},
                "Q_LB": {"country": "Q822", "country_is_br": False, "instance_of": [],
                         "description": "órgão LB"},
            },
        )

        # LLM canonicaliza cada forma com alta confiança, sem PER.
        bedrock_br = make_bedrock(
            canon_json(canonical_name="Ministério da Saúde", type="ORG",
                       is_br_gov_org=True, confidence=0.95,
                       wikidata_query="Ministério da Saúde")
        )
        J.resolve_form(
            conn, "ministerio da saude", "ORG", "uid-br", 0,
            bedrock_client=bedrock_br, wikidata_client=wikidata, model_id="m",
        )

        bedrock_lb = make_bedrock(
            canon_json(canonical_name="Ministério da Saúde do Líbano", type="ORG",
                       is_br_gov_org=False, confidence=0.95,
                       wikidata_query="Ministério da Saúde do Líbano")
        )
        J.resolve_form(
            conn, "ministerio da saude do libano", "ORG", "uid-lb", 0,
            bedrock_client=bedrock_lb, wikidata_client=wikidata, model_id="m",
        )

        br_id = db.alias.get(("ministerio da saude", "ORG"))
        lb_id = db.alias.get(("ministerio da saude do libano", "ORG"))
        assert br_id == "Q_BR"
        assert lb_id == "Q_LB"
        assert br_id != lb_id  # NUNCA fundidas.
        assert "Q_BR" in db.registry
        assert "Q_LB" in db.registry


# ---------------------------------------------------------------------- #
# Finep merge vs distinct EVENT                                          #
# ---------------------------------------------------------------------- #


class TestFinepMerge:
    def test_finep_variants_merge_via_qid(self):
        from news_enrichment import canonicalization_job as J

        db = FakeDB()
        conn = db.conn()
        db.content["uid"] = "A Finep, Financiadora de Estudos e Projetos, anunciou..."

        wikidata = FakeWikidata(
            candidates_by_query={
                "*": [{"qid": "Q_FINEP", "label": "Finep", "description": "agência BR"}]
            },
            claims_by_qid={
                "Q_FINEP": {"country": "Q155", "country_is_br": True, "instance_of": []}
            },
        )

        # Forma 1: "Finep"
        bedrock1 = make_bedrock(
            canon_json(canonical_name="Financiadora de Estudos e Projetos (Finep)",
                       type="ORG", is_br_gov_org=True, confidence=0.96,
                       aliases=["Finep", "FINEP"], wikidata_query="Finep")
        )
        J.resolve_form(conn, "finep", "ORG", "uid", 0,
                       bedrock_client=bedrock1, wikidata_client=wikidata, model_id="m")

        # Forma 2: "Financiadora de Estudos e Projetos (Finep)"
        bedrock2 = make_bedrock(
            canon_json(canonical_name="Financiadora de Estudos e Projetos (Finep)",
                       type="ORG", is_br_gov_org=True, confidence=0.96,
                       aliases=["Finep"], wikidata_query="Financiadora de Estudos e Projetos")
        )
        J.resolve_form(conn, "financiadora de estudos e projetos (finep)", "ORG", "uid", 0,
                       bedrock_client=bedrock2, wikidata_client=wikidata, model_id="m")

        id1 = db.alias.get(("finep", "ORG"))
        id2 = db.alias.get(("financiadora de estudos e projetos (finep)", "ORG"))
        assert id1 == "Q_FINEP"
        assert id2 == "Q_FINEP"  # mesma entidade canônica (reuso por QID).
        # apenas uma linha de registry para o QID.
        assert list(db.registry.keys()).count("Q_FINEP") == 1

    def test_premio_finep_event_is_distinct(self):
        from news_enrichment import canonicalization_job as J

        db = FakeDB()
        # Finep ORG já resolvida.
        db.seed_alias("finep", "ORG", "Q_FINEP")
        db.seed_registry("Q_FINEP", "Financiadora de Estudos e Projetos (Finep)", "ORG",
                         wikidata_id="Q_FINEP")
        conn = db.conn()
        db.content["uid"] = "O Prêmio Finep de Inovação 2025 premiou..."

        # EVENT sem QID → entidade interna distinta.
        wikidata = FakeWikidata(candidates_by_query={"*": []})
        bedrock = make_bedrock(
            canon_json(canonical_name="Prêmio Finep de Inovação 2025", type="EVENT",
                       is_br_gov_org=False, confidence=0.9)
        )
        J.resolve_form(conn, "premio finep de inovacao 2025", "EVENT", "uid", 0,
                       bedrock_client=bedrock, wikidata_client=wikidata, model_id="m")

        event_id = db.alias.get(("premio finep de inovacao 2025", "EVENT"))
        assert event_id is not None
        assert event_id != "Q_FINEP"  # distinto da ORG Finep.
        assert event_id.startswith("dgb_")


# ---------------------------------------------------------------------- #
# Agencies reuse (no duplicate ORG node)                                 #
# ---------------------------------------------------------------------- #


class TestAgenciesReuse:
    def test_org_canonical_matches_seeded_dgb_key_reuses_it(self):
        from news_enrichment import canonicalization_job as J

        db = FakeDB()
        # Linha semeada de agencies.
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O Ministério da Educação anunciou..."

        # Nova forma de superfície "Ministério da Educação" (sem o parêntese),
        # sem QID — deve REUSAR dgb_mec por match de nome, não criar novo nó.
        wikidata = FakeWikidata(candidates_by_query={"*": []})
        bedrock = make_bedrock(
            canon_json(canonical_name="Ministério da Educação (MEC)", type="ORG",
                       is_br_gov_org=True, confidence=0.95)
        )
        J.resolve_form(conn, "ministerio da educacao", "ORG", "uid", 0,
                       bedrock_client=bedrock, wikidata_client=wikidata, model_id="m")

        reused_id = db.alias.get(("ministerio da educacao", "ORG"))
        assert reused_id == "dgb_mec"  # reuso, sem nó duplicado.
        # Nenhum novo nó dgb_ministerio-da-educacao foi criado.
        assert "dgb_ministerio-da-educacao" not in db.registry


# ---------------------------------------------------------------------- #
# add_alias ambiguity guard                                             #
# ---------------------------------------------------------------------- #


class TestAddAliasAmbiguity:
    def test_cross_entity_alias_not_overwritten(self):
        db = FakeDB()
        db.seed_alias("casa civil", "ORG", "dgb_planalto")
        conn = db.conn()
        result = C.add_alias(conn, "casa civil", "ORG", "dgb_casacivil", "canon", 0.9)
        assert result["written"] is False
        assert result["ambiguous"] is True
        assert result["existing_entity_id"] == "dgb_planalto"
        # alias NÃO foi sobrescrito.
        assert db.alias[("casa civil", "ORG")] == "dgb_planalto"

    def test_same_entity_alias_is_noop(self):
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        conn = db.conn()
        result = C.add_alias(conn, "finep", "ORG", "Q_FINEP", "canon", 0.9)
        assert result["written"] is False
        assert result["ambiguous"] is False

    def test_new_alias_is_written(self):
        db = FakeDB()
        conn = db.conn()
        result = C.add_alias(conn, "nova forma", "ORG", "Q1", "canon", 0.9)
        assert result["written"] is True
        assert db.alias[("nova forma", "ORG")] == "Q1"


# ---------------------------------------------------------------------- #
# parse_canon_response tolerance                                         #
# ---------------------------------------------------------------------- #


class TestParseCanonResponse:
    def test_malformed_json_returns_safe_default(self):
        out = C.parse_canon_response("isto não é json {{{", "Finep")
        assert out["canonical_name"] == "Finep"
        assert out["confidence"] == 0.0
        assert out["not_an_entity"] is False

    def test_invalid_type_becomes_none(self):
        out = C.parse_canon_response(canon_json(type="BANANA"), "X")
        assert out["type"] is None

    def test_type_tail_normalized(self):
        out = C.parse_canon_response(canon_json(type="PROGRAMA"), "X")
        assert out["type"] == "POLICY"

    def test_confidence_clamped(self):
        out = C.parse_canon_response(canon_json(confidence=2.0), "X")
        assert out["confidence"] == 1.0
        out = C.parse_canon_response(canon_json(confidence=-5), "X")
        assert out["confidence"] == 0.0

    def test_form_always_in_aliases(self):
        out = C.parse_canon_response(canon_json(aliases=["A", "B"]), "Finep")
        assert "Finep" in out["aliases"]

    def test_empty_response_safe_default(self):
        out = C.parse_canon_response("", "Finep")
        assert out["canonical_name"] == "Finep"


# ---------------------------------------------------------------------- #
# llm_canonicalize resilience                                            #
# ---------------------------------------------------------------------- #


class TestLlmCanonicalize:
    def test_bedrock_failure_returns_safe_default(self):
        bedrock = MagicMock()
        bedrock.client.invoke_model.side_effect = Exception("boom")
        out = C.llm_canonicalize("Finep", "ctx", "m", bedrock)
        assert out["canonical_name"] == "Finep"
        assert out["confidence"] == 0.0

    def test_uses_configured_model_id(self):
        bedrock = make_bedrock(canon_json(canonical_name="Finep"))
        C.llm_canonicalize("Finep", "ctx", "opus-test-xyz", bedrock)
        _, kwargs = bedrock.client.invoke_model.call_args
        assert kwargs["modelId"] == "opus-test-xyz"


# ---------------------------------------------------------------------- #
# config                                                                 #
# ---------------------------------------------------------------------- #


class TestConfig:
    def test_canon_model_id_from_env(self, monkeypatch):
        monkeypatch.setenv("CANON_MODEL_ID", "us.anthropic.claude-opus-4-8-xyz")
        assert C.get_canon_model_id() == "us.anthropic.claude-opus-4-8-xyz"

    def test_canon_model_id_falls_back_to_placeholder(self, monkeypatch):
        monkeypatch.delenv("CANON_MODEL_ID", raising=False)
        assert C.get_canon_model_id() == C.CANON_MODEL_ID_PLACEHOLDER

    def test_canon_prompt_version(self):
        assert C.CANON_PROMPT_VERSION == "canon-v1"


# ---------------------------------------------------------------------- #
# Captura de usage (tokens) nas chamadas Bedrock da canonicalização       #
# ---------------------------------------------------------------------- #


def make_bedrock_with_usage(responses, usages):
    """Bedrock falso que devolve (texto, usage) por chamada.

    responses: lista de strings; usages: lista de dicts usage (mesmo tamanho).
    """
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


class TestCanonUsageCapture:
    def test_llm_canonicalize_returns_usage(self):
        bedrock = make_bedrock_with_usage(
            [json.dumps({"canonical_name": "Finep", "type": "ORG", "confidence": 0.95})],
            [{"input_tokens": 200, "output_tokens": 40}],
        )
        text, usage = C._invoke_bedrock_text(bedrock, "m", "prompt")
        assert usage == {"input_tokens": 200, "output_tokens": 40}

    def test_invoke_usage_absent_yields_zero(self):
        bedrock = make_bedrock_with_usage([json.dumps({"x": 1})], [None])
        _text, usage = C._invoke_bedrock_text(bedrock, "m", "prompt")
        assert usage == {"input_tokens": 0, "output_tokens": 0}

    def test_invoke_failure_yields_none_text_zero_usage(self):
        bad = MagicMock()
        bad.client.invoke_model.side_effect = Exception("boom")
        text, usage = C._invoke_bedrock_text(bad, "m", "prompt")
        assert text is None
        assert usage == {"input_tokens": 0, "output_tokens": 0}

    def test_apply_gates_aggregates_escalation_usage(self):
        """apply_gates que escala (resolve_per_homonym) acumula usage da escalada."""
        candidates = [
            {"qid": "Q1", "label": "A", "description": "", "country_is_br": True},
            {"qid": "Q2", "label": "B", "description": "", "country_is_br": False},
        ]
        canon = {
            "canonical_name": "Ambíguo", "type": "PER", "confidence": 0.6,
            "not_an_entity": False, "aliases": ["Ambíguo"],
        }
        bedrock = make_bedrock_with_usage(
            [json.dumps({"qid": "Q1", "confidence": 0.9})],
            [{"input_tokens": 50, "output_tokens": 10}],
        )
        decision = C.apply_gates(
            form="ambiguo", canon=canon, candidates=candidates,
            sample_context="ctx", model_id="m", bedrock_client=bedrock,
        )
        # decision carrega o usage da escalada para o caller gravar.
        assert decision["usage"]["input_tokens"] == 50
        assert decision["usage"]["output_tokens"] == 10

    def test_apply_gates_no_escalation_zero_usage(self):
        """Caminho sem escalada (auto-link) → usage zero (nenhuma chamada extra)."""
        candidates = [
            {"qid": "Q9", "label": "Único", "description": "", "country_is_br": True},
        ]
        canon = {
            "canonical_name": "Finep", "type": "ORG", "confidence": 0.95,
            "not_an_entity": False, "aliases": ["Finep"],
        }
        decision = C.apply_gates(
            form="finep", canon=canon, candidates=candidates,
            sample_context="ctx", model_id="m", bedrock_client=make_bedrock("unused"),
        )
        assert decision["action"] == "link"
        assert decision["usage"] == {"input_tokens": 0, "output_tokens": 0}


# ---------------------------------------------------------------------- #
# mint_internal_id — bound de 64 chars (entity_registry.entity_id VARCHAR(64))  #
# ---------------------------------------------------------------------- #


class TestMintInternalIdBound:
    def test_short_name_is_plain_slug(self):
        """Nome curto: id determinístico dgb_<slug>, sem sufixo de hash."""
        assert C.mint_internal_id("Finep") == "dgb_finep"

    def test_long_name_fits_64_chars(self):
        long_name = (
            "Superintendência Nacional de Coordenação de Políticas Públicas "
            "de Desenvolvimento Regional Integrado e Sustentável do Brasil"
        )
        mid = C.mint_internal_id(long_name)
        assert len(mid) <= 64
        assert mid.startswith("dgb_")

    def test_long_name_is_deterministic(self):
        long_name = "A" * 300
        assert C.mint_internal_id(long_name) == C.mint_internal_id(long_name)

    def test_distinct_long_names_distinct_ids(self):
        a = C.mint_internal_id("Ministério " + "X" * 100)
        b = C.mint_internal_id("Ministério " + "Y" * 100)
        assert a != b
        assert len(a) <= 64 and len(b) <= 64

    def test_exactly_64_or_less_for_various_lengths(self):
        for n in (0, 1, 50, 52, 53, 60, 100, 500):
            mid = C.mint_internal_id("c" * n)
            assert len(mid) <= 64, (n, mid, len(mid))
