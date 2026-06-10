"""
Testes para o extrator de entidades nomeadas (NER) — Fase 2.

A nova taxonomia: ORG, PER, LOC, EVENT, POLICY, LAW (+ WORK/PRODUCT opcionais).
MISC deixa de ser sancionado como saída. Bedrock é SEMPRE mockado aqui;
nenhuma chamada real é feita na suíte.
"""

import json
from unittest.mock import MagicMock

from news_enrichment.llm_client import (
    NER_PROMPT_VERSION,
    SANCTIONED_ENTITY_TYPES,
    BedrockLLMClient,
)


# --- Fixtures ---


def _make_client(model_id: str = "ner-model-test") -> BedrockLLMClient:
    """Instancia o cliente sem tocar no boto3 (não chama __init__)."""
    client = BedrockLLMClient.__new__(BedrockLLMClient)
    client.taxonomy = None
    client.ner_model_id = model_id
    client.model_id = "enrichment-model-test"
    return client


SAMPLE_ARTICLE = {
    "unique_id": "mec-2026-01-01-1",
    "title": "Governo amplia o Bolsa Família e anuncia Copa do Mundo Feminina",
    "subtitle": None,
    "editorial_lead": None,
    "content": (
        "O Ministério da Saúde anunciou hoje a ampliação do Bolsa Família. "
        "O Brasil sediará a Copa do Mundo Feminina da FIFA 2027."
    ),
}


# --- Tests: parser (_parse_entities) ---


class TestParseEntities:
    """Parser tolerante da resposta NER."""

    def test_bolsa_familia_is_policy(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {
                        "text": "Bolsa Família",
                        "type": "POLICY",
                        "forma_canonica": "Bolsa Família",
                        "salience": 0.9,
                        "count": 2,
                    }
                ]
            }
        )
        result = client._parse_entities(raw)
        assert len(result) == 1
        ent = result[0]
        assert ent["text"] == "Bolsa Família"
        assert ent["type"] == "POLICY"
        assert ent["forma_canonica"] == "Bolsa Família"
        assert ent["salience"] == 0.9
        assert ent["count"] == 2

    def test_copa_do_mundo_is_event(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {
                        "text": "Copa do Mundo Feminina da FIFA 2027",
                        "type": "EVENT",
                        "forma_canonica": "Copa do Mundo Feminina da FIFA 2027",
                        "salience": 0.7,
                        "count": 1,
                    }
                ]
            }
        )
        result = client._parse_entities(raw)
        assert len(result) == 1
        assert result[0]["type"] == "EVENT"
        assert result[0]["text"] == "Copa do Mundo Feminina da FIFA 2027"

    def test_topic_not_entity_is_dropped(self):
        """'inteligência artificial' é tópico genérico — se vier como MISC, some."""
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {"text": "inteligência artificial", "type": "MISC", "count": 3},
                    {"text": "Ministério da Saúde", "type": "ORG", "count": 1},
                ]
            }
        )
        result = client._parse_entities(raw)
        texts = [e["text"] for e in result]
        assert "inteligência artificial" not in texts
        assert "Ministério da Saúde" in texts

    def test_demographic_group_misc_is_dropped(self):
        """'mulheres' (grupo demográfico) como MISC é descartado."""
        client = _make_client()
        raw = json.dumps(
            {"entities": [{"text": "mulheres", "type": "MISC", "count": 5}]}
        )
        result = client._parse_entities(raw)
        assert result == []

    def test_foreign_ministry_kept_distinct(self):
        """Ministério da Saúde do Líbano: ORG estrangeiro, NÃO funde com o brasileiro."""
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {
                        "text": "Ministério da Saúde do Líbano",
                        "type": "ORG",
                        "forma_canonica": "Ministério da Saúde do Líbano",
                        "count": 1,
                    },
                    {
                        "text": "Ministério da Saúde",
                        "type": "ORG",
                        "forma_canonica": "Ministério da Saúde",
                        "count": 1,
                    },
                ]
            }
        )
        result = client._parse_entities(raw)
        texts = sorted(e["text"] for e in result)
        # Ambos preservados como menções distintas (canonicalização é fase posterior).
        assert texts == ["Ministério da Saúde", "Ministério da Saúde do Líbano"]

    def test_type_tail_programa_normalized_to_policy(self):
        client = _make_client()
        raw = json.dumps(
            {"entities": [{"text": "Pé-de-Meia", "type": "PROGRAMA", "count": 1}]}
        )
        result = client._parse_entities(raw)
        assert len(result) == 1
        assert result[0]["type"] == "POLICY"

    def test_type_tail_program_law_decreto_normalized_to_policy(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {"text": "Novo PAC", "type": "PROGRAM", "count": 1},
                    {"text": "Lei Maria da Penha", "type": "LAW", "count": 1},
                    {"text": "Decreto 11.000", "type": "DECRETO", "count": 1},
                ]
            }
        )
        result = client._parse_entities(raw)
        # LAW é tipo sancionado; PROGRAM/DECRETO → POLICY.
        by_text = {e["text"]: e["type"] for e in result}
        assert by_text["Novo PAC"] == "POLICY"
        assert by_text["Lei Maria da Penha"] == "LAW"
        assert by_text["Decreto 11.000"] == "POLICY"

    def test_type_tail_award_normalized_to_event(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {"text": "Prêmio Finep de Inovação 2025", "type": "AWARD", "count": 1}
                ]
            }
        )
        result = client._parse_entities(raw)
        assert len(result) == 1
        assert result[0]["type"] == "EVENT"

    def test_unknown_type_outside_sanctioned_is_dropped(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {"text": "alguma coisa", "type": "BANANA", "count": 1},
                    {"text": "Finep", "type": "ORG", "count": 1},
                ]
            }
        )
        result = client._parse_entities(raw)
        assert [e["text"] for e in result] == ["Finep"]

    def test_missing_count_defaults_to_one(self):
        client = _make_client()
        raw = json.dumps({"entities": [{"text": "Finep", "type": "ORG"}]})
        result = client._parse_entities(raw)
        assert result[0]["count"] == 1

    def test_missing_salience_defaults_to_none(self):
        client = _make_client()
        raw = json.dumps({"entities": [{"text": "Finep", "type": "ORG", "count": 1}]})
        result = client._parse_entities(raw)
        assert result[0]["salience"] is None

    def test_missing_forma_canonica_falls_back_to_text(self):
        client = _make_client()
        raw = json.dumps({"entities": [{"text": "Finep", "type": "ORG", "count": 1}]})
        result = client._parse_entities(raw)
        assert result[0]["forma_canonica"] == "Finep"

    def test_malformed_json_returns_empty_never_raises(self):
        client = _make_client()
        assert client._parse_entities("isto não é json {{{") == []

    def test_no_json_returns_empty(self):
        client = _make_client()
        assert client._parse_entities("Resposta sem JSON nenhum") == []

    def test_entities_not_a_list_returns_empty(self):
        client = _make_client()
        raw = json.dumps({"entities": {"text": "x", "type": "ORG"}})
        assert client._parse_entities(raw) == []

    def test_entity_without_text_is_skipped(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {"type": "ORG", "count": 1},
                    {"text": "Finep", "type": "ORG", "count": 1},
                ]
            }
        )
        result = client._parse_entities(raw)
        assert [e["text"] for e in result] == ["Finep"]

    def test_entity_without_type_is_skipped(self):
        client = _make_client()
        raw = json.dumps(
            {
                "entities": [
                    {"text": "sem tipo", "count": 1},
                    {"text": "Finep", "type": "ORG", "count": 1},
                ]
            }
        )
        result = client._parse_entities(raw)
        assert [e["text"] for e in result] == ["Finep"]

    def test_markdown_wrapped_json_is_parsed(self):
        client = _make_client()
        inner = json.dumps({"entities": [{"text": "Finep", "type": "ORG", "count": 1}]})
        raw = f"```json\n{inner}\n```"
        result = client._parse_entities(raw)
        assert [e["text"] for e in result] == ["Finep"]

    def test_bare_list_response_is_parsed(self):
        """Modelo pode devolver lista crua em vez de {'entities': [...]}."""
        client = _make_client()
        raw = json.dumps([{"text": "Finep", "type": "ORG", "count": 1}])
        result = client._parse_entities(raw)
        assert [e["text"] for e in result] == ["Finep"]

    def test_count_coerced_to_int(self):
        client = _make_client()
        raw = json.dumps({"entities": [{"text": "Finep", "type": "ORG", "count": "3"}]})
        result = client._parse_entities(raw)
        assert result[0]["count"] == 3

    def test_lowercase_type_is_normalized(self):
        client = _make_client()
        raw = json.dumps({"entities": [{"text": "Lula", "type": "per", "count": 1}]})
        result = client._parse_entities(raw)
        assert result[0]["type"] == "PER"

    def test_sanctioned_set_has_no_misc(self):
        assert "MISC" not in SANCTIONED_ENTITY_TYPES
        for t in ("ORG", "PER", "LOC", "EVENT", "POLICY", "LAW"):
            assert t in SANCTIONED_ENTITY_TYPES


# --- Tests: prompt ---


class TestNerPrompt:
    """O prompt PT do NER com taxonomia explícita + bloco 'NÃO é entidade'."""

    def test_prompt_lists_sanctioned_types(self):
        client = _make_client()
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        for t in ("ORG", "PER", "LOC", "EVENT", "POLICY", "LAW"):
            assert t in prompt

    def test_prompt_does_not_sanction_misc(self):
        client = _make_client()
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        # MISC não deve aparecer como tipo de saída sancionado.
        assert "MISC" not in prompt

    def test_prompt_has_nao_e_entidade_block(self):
        client = _make_client()
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        assert "NÃO é entidade" in prompt
        # exemplos do bloco negativo
        assert "inteligência artificial" in prompt
        assert "mulheres" in prompt

    def test_prompt_requests_forma_canonica_and_salience(self):
        client = _make_client()
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        assert "forma_canonica" in prompt
        assert "salience" in prompt

    def test_prompt_does_not_request_wikidata_qid(self):
        client = _make_client()
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        lower = prompt.lower()
        assert "wikidata" not in lower
        assert "qid" not in lower

    def test_prompt_includes_article_content(self):
        client = _make_client()
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        assert "Bolsa Família" in prompt
        assert SAMPLE_ARTICLE["title"] in prompt

    def test_prompt_content_is_truncated(self):
        client = _make_client()
        long = dict(SAMPLE_ARTICLE, content="x" * 9000)
        prompt = client._build_ner_prompt(long)
        assert "x" * 9000 not in prompt

    def test_prompt_version_constant_present(self):
        assert isinstance(NER_PROMPT_VERSION, str)
        assert NER_PROMPT_VERSION


# --- Tests: extract_entities (Bedrock mockado) ---


class TestExtractEntities:
    """extract_entities() faz a chamada Bedrock dedicada (mockada)."""

    def _client_with_mocked_bedrock(self, response_text: str, model_id="ner-model-test"):
        client = _make_client(model_id=model_id)
        body = MagicMock()
        body.read.return_value = json.dumps(
            {"content": [{"text": response_text}]}
        ).encode()
        client.client = MagicMock()
        client.client.invoke_model.return_value = {"body": body}
        return client

    def test_uses_ner_model_id(self):
        canned = json.dumps(
            {"entities": [{"text": "Bolsa Família", "type": "POLICY", "count": 1}]}
        )
        client = self._client_with_mocked_bedrock(canned, model_id="sonnet-ner-xyz")
        client.extract_entities(SAMPLE_ARTICLE)
        _, kwargs = client.client.invoke_model.call_args
        assert kwargs["modelId"] == "sonnet-ner-xyz"

    def test_returns_parsed_entities(self):
        canned = json.dumps(
            {
                "entities": [
                    {"text": "Bolsa Família", "type": "POLICY", "count": 1},
                    {"text": "inteligência artificial", "type": "MISC", "count": 2},
                ]
            }
        )
        client = self._client_with_mocked_bedrock(canned)
        ents = client.extract_entities(SAMPLE_ARTICLE)
        texts = [e["text"] for e in ents]
        assert "Bolsa Família" in texts
        assert "inteligência artificial" not in texts  # dropped

    def test_returns_raw_response_when_requested(self):
        canned = json.dumps(
            {"entities": [{"text": "Finep", "type": "ORG", "count": 1}]}
        )
        client = self._client_with_mocked_bedrock(canned)
        ents, raw = client.extract_entities(SAMPLE_ARTICLE, return_raw=True)
        assert [e["text"] for e in ents] == ["Finep"]
        assert raw["model_id"] == "ner-model-test"
        assert raw["prompt_version"] == NER_PROMPT_VERSION
        assert isinstance(raw["prompt_hash"], str) and len(raw["prompt_hash"]) == 64
        assert raw["raw_response"] == canned

    def test_prompt_hash_is_deterministic(self):
        canned = json.dumps({"entities": []})
        client = self._client_with_mocked_bedrock(canned)
        _, raw1 = client.extract_entities(SAMPLE_ARTICLE, return_raw=True)
        _, raw2 = client.extract_entities(SAMPLE_ARTICLE, return_raw=True)
        assert raw1["prompt_hash"] == raw2["prompt_hash"]

    def test_prompt_hash_matches_sha256_of_prompt(self):
        import hashlib

        canned = json.dumps({"entities": []})
        client = self._client_with_mocked_bedrock(canned)
        prompt = client._build_ner_prompt(SAMPLE_ARTICLE)
        _, raw = client.extract_entities(SAMPLE_ARTICLE, return_raw=True)
        assert raw["prompt_hash"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def test_bedrock_error_returns_empty_list(self):
        client = _make_client()
        client.client = MagicMock()
        client.client.invoke_model.side_effect = Exception("boom")
        ents = client.extract_entities(SAMPLE_ARTICLE)
        assert ents == []

    def test_bedrock_error_return_raw_yields_none_raw(self):
        client = _make_client()
        client.client = MagicMock()
        client.client.invoke_model.side_effect = Exception("boom")
        ents, raw = client.extract_entities(SAMPLE_ARTICLE, return_raw=True)
        assert ents == []
        assert raw is None


# --- Tests: combined prompt no longer emits entities ---


class TestCombinedPromptDropsEntities:
    """A chamada combinada (tema+resumo+sentimento) NÃO pede mais entidades."""

    def test_combined_prompt_has_no_entities(self):
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None
        prompt = client._build_prompt({"title": "Test", "content": "Conteúdo"})
        assert "entities" not in prompt
        assert "Extraia as entidades" not in prompt

    def test_combined_prompt_still_has_sentiment_and_summary(self):
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None
        prompt = client._build_prompt({"title": "Test", "content": "Conteúdo"})
        assert "sentiment" in prompt
        assert "summary" in prompt

    def test_combined_parse_does_not_require_entities(self):
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None
        raw = json.dumps(
            {
                "theme_1_level_1": "Economia",
                "theme_1_level_1_code": "01",
                "theme_1_level_1_label": "Economia",
                "theme_1_level_2_code": "01.02",
                "theme_1_level_2_label": "X",
                "theme_1_level_3_code": "01.02.03",
                "theme_1_level_3_label": "Y",
                "most_specific_theme_code": "01.02.03",
                "most_specific_theme_label": "Y",
                "summary": "Resumo.",
                "sentiment": {"label": "neutral", "score": 0.0},
            }
        )
        result = client._parse_response(raw)
        assert result["summary"] == "Resumo."
        assert "entities" not in result or result.get("entities") in (None, [])
