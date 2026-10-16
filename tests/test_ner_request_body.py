"""
Corpo da requisição NER por modelo e leitura da resposta por tipo de bloco.

- Modelos legados (Sonnet 4.6, Haiku 4.5, Haiku 3, qualquer ID fora dos perfis
  5.5) recebem o corpo de sempre, byte a byte (temperature 0.0, max_tokens 2000).
- Sonnet 5.5 e Haiku 5.5 omitem temperature (400 nesses modelos), levam
  output_config.effort e thinking por perfil, e validam as combinações antes
  da chamada.
- A resposta é lida juntando só os blocos type=text (bloco sem `type` conta
  como texto, como nos mocks antigos); stop_reason=refusal vira NerRefusal.

Bedrock é sempre mockado; nenhuma chamada real.
"""

import json

import pytest

from news_enrichment.llm_client import (
    NER_PROFILES,
    NerRefusal,
    build_ner_request_body,
    ner_model_family,
    ner_response_text,
)

PROMPT = 'Você é um especialista em NER.\nNOTÍCIA: "Bolsa Família" é POLICY.'

LEGACY_IDS = [
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "ner-model-test",
]

SONNET_55_IDS = [
    "us.anthropic.claude-sonnet-5-5",
    "anthropic.claude-sonnet-5-5",
    "global.anthropic.claude-sonnet-5-5-v1:0",
]
HAIKU_55_IDS = [
    "us.anthropic.claude-haiku-5-5",
    "anthropic.claude-haiku-5-5",
]


def _legacy_string(prompt: str) -> str:
    """O string exato que _call_bedrock_ner envia hoje (json.dumps padrão)."""
    return (
        '{"anthropic_version": "bedrock-2023-05-31", "max_tokens": 2000, '
        '"temperature": 0.0, "messages": [{"role": "user", "content": ' + json.dumps(prompt) + "}]}"
    )


# --------------------------------------------------------------------------- #
# Família do modelo                                                           #
# --------------------------------------------------------------------------- #


class TestNerModelFamily:
    @pytest.mark.parametrize("model_id", LEGACY_IDS)
    def test_legacy_ids(self, model_id):
        assert ner_model_family(model_id) == "legacy"

    @pytest.mark.parametrize("model_id", SONNET_55_IDS)
    def test_sonnet_55_ids(self, model_id):
        assert ner_model_family(model_id) == "sonnet-5-5"

    @pytest.mark.parametrize("model_id", HAIKU_55_IDS)
    def test_haiku_55_ids(self, model_id):
        assert ner_model_family(model_id) == "haiku-5-5"

    def test_none_is_legacy(self):
        assert ner_model_family(None) == "legacy"

    def test_lookalike_versions_are_legacy(self):
        # Só 5-5 exato; sem casar 5-50, sonnet-5 ou opus-5-5.
        assert ner_model_family("us.anthropic.claude-sonnet-5-50") == "legacy"
        assert ner_model_family("us.anthropic.claude-sonnet-5") == "legacy"
        assert ner_model_family("us.anthropic.claude-opus-5-5") == "legacy"


# --------------------------------------------------------------------------- #
# (a) Corpo legado byte a byte                                                #
# --------------------------------------------------------------------------- #


class TestLegacyBody:
    @pytest.mark.parametrize("model_id", LEGACY_IDS)
    def test_legacy_body_is_byte_identical(self, model_id):
        body = build_ner_request_body(model_id, PROMPT)
        assert json.dumps(body) == _legacy_string(PROMPT)

    @pytest.mark.parametrize("model_id", LEGACY_IDS)
    def test_legacy_key_order(self, model_id):
        body = build_ner_request_body(model_id, PROMPT)
        assert list(body) == ["anthropic_version", "max_tokens", "temperature", "messages"]

    @pytest.mark.parametrize(
        "override", [{"effort": "low"}, {"thinking": "disabled"}, {"max_tokens": 4000}]
    )
    def test_legacy_rejects_overrides(self, override):
        # O corpo legado é congelado: nenhum override silencioso.
        with pytest.raises(ValueError):
            build_ner_request_body("us.anthropic.claude-sonnet-4-6", PROMPT, **override)


# --------------------------------------------------------------------------- #
# (b) Perfis 5.5                                                              #
# --------------------------------------------------------------------------- #


class TestProfile55Body:
    @pytest.mark.parametrize("model_id", SONNET_55_IDS + HAIKU_55_IDS)
    def test_no_sampling_params(self, model_id):
        body = build_ner_request_body(model_id, PROMPT)
        assert "temperature" not in body
        assert "top_p" not in body
        assert "top_k" not in body

    @pytest.mark.parametrize("model_id", SONNET_55_IDS + HAIKU_55_IDS)
    def test_effort_in_output_config(self, model_id):
        body = build_ner_request_body(model_id, PROMPT)
        family = ner_model_family(model_id)
        assert body["output_config"] == {"effort": NER_PROFILES[family]["effort"]}
        assert "effort" not in body  # nunca top-level

    @pytest.mark.parametrize("model_id", SONNET_55_IDS + HAIKU_55_IDS)
    def test_profile_max_tokens_and_message(self, model_id):
        body = build_ner_request_body(model_id, PROMPT)
        family = ner_model_family(model_id)
        assert body["max_tokens"] == NER_PROFILES[family]["max_tokens"]
        assert body["anthropic_version"] == "bedrock-2023-05-31"
        assert body["messages"] == [{"role": "user", "content": PROMPT}]

    def test_sonnet_default_is_between_tools_low(self):
        body = build_ner_request_body("us.anthropic.claude-sonnet-5-5", PROMPT)
        assert body["thinking"] == {"type": "between_tools"}  # sem outros campos
        assert body["output_config"] == {"effort": "low"}

    def test_haiku_default_is_adaptive_low(self):
        body = build_ner_request_body("us.anthropic.claude-haiku-5-5", PROMPT)
        assert "thinking" not in body  # adaptativo = default do modelo, campo omitido
        assert body["output_config"] == {"effort": "low"}

    def test_overrides_applied(self):
        body = build_ner_request_body(
            "us.anthropic.claude-haiku-5-5",
            PROMPT,
            effort="medium",
            thinking="disabled",
            max_tokens=3000,
        )
        assert body["thinking"] == {"type": "disabled"}
        assert body["output_config"] == {"effort": "medium"}
        assert body["max_tokens"] == 3000

    def test_sonnet_adaptive_override_omits_thinking(self):
        body = build_ner_request_body(
            "us.anthropic.claude-sonnet-5-5", PROMPT, thinking="adaptive", max_tokens=8000
        )
        assert "thinking" not in body
        assert body["max_tokens"] == 8000

    def test_body_is_json_serializable(self):
        for mid in SONNET_55_IDS + HAIKU_55_IDS:
            json.loads(json.dumps(build_ner_request_body(mid, PROMPT)))


# --------------------------------------------------------------------------- #
# (c) Combinações inválidas → ValueError antes da chamada                     #
# --------------------------------------------------------------------------- #


class TestInvalidCombinations:
    def test_between_tools_only_on_sonnet(self):
        with pytest.raises(ValueError):
            build_ner_request_body(
                "us.anthropic.claude-haiku-5-5", PROMPT, thinking="between_tools"
            )

    def test_disabled_not_on_sonnet(self):
        with pytest.raises(ValueError):
            build_ner_request_body("us.anthropic.claude-sonnet-5-5", PROMPT, thinking="disabled")

    @pytest.mark.parametrize("effort", ["xhigh", "max"])
    def test_disabled_haiku_needs_effort_le_high(self, effort):
        with pytest.raises(ValueError):
            build_ner_request_body(
                "us.anthropic.claude-haiku-5-5", PROMPT, thinking="disabled", effort=effort
            )

    @pytest.mark.parametrize("effort", ["xhigh", "max"])
    def test_between_tools_needs_effort_le_high(self, effort):
        with pytest.raises(ValueError):
            build_ner_request_body(
                "us.anthropic.claude-sonnet-5-5", PROMPT, thinking="between_tools", effort=effort
            )

    @pytest.mark.parametrize("effort", ["low", "medium", "high"])
    def test_thinking_off_accepts_effort_le_high(self, effort):
        build_ner_request_body(
            "us.anthropic.claude-haiku-5-5", PROMPT, thinking="disabled", effort=effort
        )
        build_ner_request_body(
            "us.anthropic.claude-sonnet-5-5", PROMPT, thinking="between_tools", effort=effort
        )

    def test_adaptive_accepts_xhigh(self):
        body = build_ner_request_body(
            "us.anthropic.claude-sonnet-5-5", PROMPT, thinking="adaptive", effort="xhigh"
        )
        assert body["output_config"] == {"effort": "xhigh"}

    def test_unknown_effort(self):
        with pytest.raises(ValueError):
            build_ner_request_body("us.anthropic.claude-haiku-5-5", PROMPT, effort="minimal")

    def test_unknown_thinking(self):
        with pytest.raises(ValueError):
            build_ner_request_body("us.anthropic.claude-haiku-5-5", PROMPT, thinking="enabled")

    @pytest.mark.parametrize("bad", [0, -1, "4000", 2.5])
    def test_bad_max_tokens(self, bad):
        with pytest.raises(ValueError):
            build_ner_request_body("us.anthropic.claude-haiku-5-5", PROMPT, max_tokens=bad)


# --------------------------------------------------------------------------- #
# (d) Leitura por tipo de bloco                                               #
# --------------------------------------------------------------------------- #


class TestNerResponseText:
    def test_skips_thinking_block(self):
        body = {
            "content": [
                {"type": "thinking", "thinking": "", "signature": "x"},
                {"type": "text", "text": '{"entities": []}'},
            ],
            "stop_reason": "end_turn",
        }
        assert ner_response_text(body) == '{"entities": []}'

    def test_block_without_type_counts_as_text(self):
        assert ner_response_text({"content": [{"text": "abc"}]}) == "abc"

    def test_joins_multiple_text_blocks(self):
        body = {
            "content": [
                {"type": "text", "text": '{"entities": '},
                {"type": "thinking", "thinking": "", "signature": "s"},
                {"type": "text", "text": "[]}"},
            ]
        }
        assert ner_response_text(body) == '{"entities": []}'

    def test_redacted_thinking_ignored(self):
        body = {
            "content": [
                {"type": "redacted_thinking", "data": "zzz"},
                {"type": "text", "text": "ok"},
            ]
        }
        assert ner_response_text(body) == "ok"

    def test_only_thinking_raises(self):
        # max_tokens consumido no pensamento: sem texto → erro (repetível),
        # nunca string vazia que marcaria o artigo como processado.
        body = {
            "content": [{"type": "thinking", "thinking": "", "signature": "x"}],
            "stop_reason": "max_tokens",
        }
        with pytest.raises(ValueError, match="max_tokens"):
            ner_response_text(body)

    def test_empty_content_raises(self):
        with pytest.raises(ValueError):
            ner_response_text({"content": [], "stop_reason": "end_turn"})

    def test_refusal_raises_ner_refusal(self):
        body = {
            "content": [],
            "stop_reason": "refusal",
            "stop_details": {"type": "refusal", "category": "cyber", "explanation": "x"},
            "usage": {"input_tokens": 900, "output_tokens": 3},
        }
        with pytest.raises(NerRefusal) as exc:
            ner_response_text(body)
        assert exc.value.category == "cyber"
        assert exc.value.explanation == "x"
        assert exc.value.usage == {"input_tokens": 900, "output_tokens": 3}

    def test_refusal_without_details(self):
        body = {"content": [{"type": "text", "text": "parcial"}], "stop_reason": "refusal"}
        with pytest.raises(NerRefusal) as exc:
            ner_response_text(body)
        assert exc.value.category is None
        assert exc.value.usage == {"input_tokens": 0, "output_tokens": 0}
