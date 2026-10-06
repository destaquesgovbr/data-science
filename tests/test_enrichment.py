"""
Testes unitários para o pipeline de enriquecimento LLM.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import news_enrichment.llm_client as llm_client_mod
from news_enrichment.classifier import NewsClassifier
from news_enrichment.enrichment_job import (
    update_news_enrichment,
)
from news_enrichment.llm_client import BedrockLLMClient
from news_enrichment.taxonomy import load_taxonomy_from_postgres, build_theme_code_to_id_map


# --- Fixtures ---


SAMPLE_NEWS = [
    {
        "unique_id": "abc123",
        "title": "Governo anuncia reforma tributária",
        "subtitle": "Medida visa simplificar o sistema",
        "editorial_lead": "Presidente apresentou proposta",
        "content": "O governo federal anunciou hoje uma ampla reforma tributária...",
    },
    {
        "unique_id": "def456",
        "title": "Ministério da Saúde lança campanha de vacinação",
        "subtitle": None,
        "editorial_lead": None,
        "content": "Nova campanha de vacinação começa na próxima semana...",
    },
]

SAMPLE_LLM_RESPONSE = json.dumps(
    {
        "theme_1_level_1": "Economia e Finanças",
        "theme_1_level_1_code": "01",
        "theme_1_level_1_label": "Economia e Finanças",
        "theme_1_level_2_code": "01.02",
        "theme_1_level_2_label": "Fiscalização e Tributação",
        "theme_1_level_3_code": "01.02.03",
        "theme_1_level_3_label": "Reforma Tributária",
        "most_specific_theme_code": "01.02.03",
        "most_specific_theme_label": "Reforma Tributária",
        "summary": "Governo federal anuncia proposta de reforma tributária.",
    }
)

SAMPLE_CODE_TO_ID = {
    "01": 1,
    "01.02": 5,
    "01.02.03": 15,
    "03": 3,
    "03.01": 10,
    "03.01.02": 25,
}


# --- Tests: LLM Client ---


class TestBedrockLLMClient:
    """Testes para o cliente Bedrock."""

    def test_parse_response_valid_json(self):
        """Deve parsear JSON válido da resposta."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None

        result = client._parse_response(SAMPLE_LLM_RESPONSE)

        assert result["theme_1_level_1_code"] == "01"
        assert result["theme_1_level_2_code"] == "01.02"
        assert result["theme_1_level_3_code"] == "01.02.03"
        assert result["summary"] is not None

    def test_parse_response_json_with_markdown(self):
        """Deve extrair JSON mesmo com markdown ao redor."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None

        response_with_markdown = f"```json\n{SAMPLE_LLM_RESPONSE}\n```"
        result = client._parse_response(response_with_markdown)

        assert result["theme_1_level_1_code"] == "01"

    def test_parse_response_no_json(self):
        """Deve levantar ValueError se não encontrar JSON."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None

        with pytest.raises(ValueError, match="JSON não encontrado"):
            client._parse_response("Resposta sem JSON nenhum")

    def test_parse_response_missing_fields(self):
        """Deve preencher campos ausentes com None."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None

        partial_json = json.dumps({"theme_1_level_1": "Economia"})
        result = client._parse_response(partial_json)

        assert result["theme_1_level_1"] == "Economia"
        assert result["theme_1_level_2_code"] is None
        assert result["summary"] is None

    def test_create_fallback_result(self):
        """Deve criar resultado com campos null mantendo dados originais."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)

        row = {"unique_id": "abc123", "title": "Test"}
        result = client._create_fallback_result(row)

        assert result["unique_id"] == "abc123"
        assert result["title"] == "Test"
        assert result["theme_1_level_1"] is None
        assert result["summary"] is None

    def test_build_prompt_with_taxonomy(self):
        """Deve incluir taxonomia no prompt quando fornecida."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = {"01": {"label": "Economia", "subcategories": {}}}

        prompt = client._build_prompt({"title": "Test", "content": "Content"})

        assert "TAXONOMIA DISPONÍVEL" in prompt
        assert "Economia" in prompt

    def test_build_prompt_without_taxonomy(self):
        """Deve usar modo orgânico quando sem taxonomia."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None

        prompt = client._build_prompt({"title": "Test", "content": "Content"})

        assert "árvore temática hierárquica" in prompt

    def test_build_prompt_content_limit(self):
        """Deve limitar conteúdo a 2000 caracteres."""
        client = BedrockLLMClient.__new__(BedrockLLMClient)
        client.taxonomy = None

        long_content = "x" * 5000
        prompt = client._build_prompt({"title": "Test", "content": long_content})

        # O prompt não deve ter o conteúdo completo
        assert "x" * 5000 not in prompt


# --- Tests: Taxonomy ---


class TestTaxonomy:
    """Testes para carregamento de taxonomia."""

    @patch("news_enrichment.taxonomy.psycopg2")
    def test_load_taxonomy(self, mock_psycopg2):
        """Deve construir hierarquia correta a partir de rows do banco."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("01", "Economia e Finanças", 1, None),
            ("01.01", "Política Econômica", 2, "01"),
            ("01.01.01", "Inflação", 3, "01.01"),
            ("03", "Saúde", 1, None),
        ]

        taxonomy = load_taxonomy_from_postgres("postgresql://test")

        assert "01" in taxonomy
        assert taxonomy["01"]["label"] == "Economia e Finanças"
        assert "01.01" in taxonomy["01"]["subcategories"]
        assert "01.01.01" in taxonomy["01"]["subcategories"]["01.01"]["subcategories"]
        assert "03" in taxonomy
        assert taxonomy["03"]["label"] == "Saúde"

    @patch("news_enrichment.taxonomy.psycopg2")
    def test_build_code_to_id_map(self, mock_psycopg2):
        """Deve construir mapeamento code → id."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("01", 1),
            ("01.01", 5),
            ("01.01.01", 15),
        ]

        code_to_id = build_theme_code_to_id_map("postgresql://test")

        assert code_to_id["01"] == 1
        assert code_to_id["01.01"] == 5
        assert code_to_id["01.01.01"] == 15


# --- Tests: Enrichment Job ---


class TestUpdateNewsEnrichment:
    """Testes para atualização no PostgreSQL."""

    @patch("news_enrichment.enrichment_job.execute_batch")
    @patch("news_enrichment.enrichment_job.psycopg2")
    def test_update_with_valid_data(self, mock_psycopg2, mock_execute_batch):
        """Deve atualizar notícias com classificação válida."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        enriched_rows = [
            {
                "unique_id": "abc123",
                "theme_1_level_1_code": "01",
                "theme_1_level_2_code": "01.02",
                "theme_1_level_3_code": "01.02.03",
                "summary": "Resumo da notícia",
            }
        ]

        stats = update_news_enrichment("postgresql://test", enriched_rows, SAMPLE_CODE_TO_ID)

        assert stats["updated"] == 1
        assert stats["skipped"] == 0
        mock_conn.commit.assert_called_once()
        mock_execute_batch.assert_called_once()

    @patch("news_enrichment.enrichment_job.psycopg2")
    def test_skip_rows_without_theme(self, mock_psycopg2):
        """Deve pular notícias sem tema identificado."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        enriched_rows = [
            {
                "unique_id": "abc123",
                "theme_1_level_1_code": None,
                "theme_1_level_2_code": None,
                "theme_1_level_3_code": None,
                "summary": None,
            }
        ]

        stats = update_news_enrichment("postgresql://test", enriched_rows, SAMPLE_CODE_TO_ID)

        assert stats["skipped"] == 1
        assert stats["updated"] == 0

    @patch("news_enrichment.enrichment_job.psycopg2")
    def test_skip_rows_with_unknown_codes(self, mock_psycopg2):
        """Deve pular notícias cujos codes não existem na tabela themes."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        enriched_rows = [
            {
                "unique_id": "abc123",
                "theme_1_level_1_code": "99",  # Não existe
                "theme_1_level_2_code": "99.01",
                "theme_1_level_3_code": None,
                "summary": "Resumo",
            }
        ]

        stats = update_news_enrichment("postgresql://test", enriched_rows, SAMPLE_CODE_TO_ID)

        assert stats["skipped"] == 1

    @patch("news_enrichment.enrichment_job.execute_batch")
    @patch("news_enrichment.enrichment_job.psycopg2")
    def test_partial_theme_levels(self, mock_psycopg2, mock_execute_batch):
        """Deve funcionar com classificação parcial (só L1)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        enriched_rows = [
            {
                "unique_id": "abc123",
                "theme_1_level_1_code": "01",
                "theme_1_level_2_code": None,
                "theme_1_level_3_code": None,
                "summary": "Resumo",
            }
        ]

        stats = update_news_enrichment("postgresql://test", enriched_rows, SAMPLE_CODE_TO_ID)

        assert stats["updated"] == 1

    @patch("news_enrichment.enrichment_job.psycopg2")
    def test_empty_input(self, mock_psycopg2):
        """Deve retornar sem erro para lista vazia."""
        stats = update_news_enrichment("postgresql://test", [], SAMPLE_CODE_TO_ID)

        assert stats["updated"] == 0
        assert stats["skipped"] == 0


# --- Tests: observabilidade da falha da chamada combinada (Fase 2.5, DS-1) ---

_EOL_MSG = (
    "This model version has reached the end of its life. "
    "Please refer to the AWS documentation for more details."
)


def _client_error(code: str, message: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "InvokeModel")


def _bare_client(model_id: str = "anthropic.claude-3-haiku-20240307-v1:0") -> BedrockLLMClient:
    client = BedrockLLMClient.__new__(BedrockLLMClient)
    client.taxonomy = None
    client.model_id = model_id
    client.max_retries = 3
    return client


class TestFallbackComErro:
    """O fallback da chamada combinada carrega `_error` = "<ErrorCode>: <msg>"."""

    @patch("news_enrichment.llm_client.time.sleep")
    def test_fallback_inclui_codigo_do_erro(self, mock_sleep):
        client = _bare_client()
        client._call_bedrock = MagicMock(
            side_effect=_client_error("ResourceNotFoundException", _EOL_MSG)
        )

        result = client._enrich_single_news({"unique_id": "abc123", "title": "T"})

        assert result["_error"] == f"ResourceNotFoundException: {_EOL_MSG}"
        assert result["theme_1_level_1_code"] is None
        assert result["_model_id"] == "anthropic.claude-3-haiku-20240307-v1:0"
        assert client._call_bedrock.call_count == 3

    @patch("news_enrichment.llm_client.time.sleep")
    def test_fallback_erro_generico_usa_nome_da_excecao(self, mock_sleep):
        client = _bare_client()
        client._call_bedrock = MagicMock(
            return_value=("resposta sem json", {"input_tokens": 1, "output_tokens": 1})
        )

        result = client._enrich_single_news({"unique_id": "abc123"})

        assert result["_error"].startswith("ValueError: ")
        assert "JSON não encontrado" in result["_error"]

    def test_fallback_do_batch_inclui_erro(self):
        client = _bare_client()
        client.batch_size = 1
        client.sleep_between_batches = 0
        client._enrich_single_news = MagicMock(side_effect=RuntimeError("boom"))

        results = client.enrich_news_batch([{"unique_id": "abc123"}])

        assert results[0]["_error"] == "RuntimeError: boom"

    def test_sucesso_nao_tem_error(self):
        client = _bare_client()
        client._call_bedrock = MagicMock(
            return_value=(SAMPLE_LLM_RESPONSE, {"input_tokens": 10, "output_tokens": 2})
        )

        result = client._enrich_single_news({"unique_id": "abc123"})

        assert not result.get("_error")
        assert result["theme_1_level_1_code"] == "01"


class TestIsModelUnavailableError:
    """Erro de fim de vida / modelo inexistente → alerta CRITICAL estável."""

    @pytest.mark.parametrize(
        "error",
        [
            f"ResourceNotFoundException: {_EOL_MSG}",
            "ResourceNotFoundException: Could not resolve the foundation model "
            "from the provided model identifier.",
            "ValidationException: The provided model identifier is invalid.",
            "ValidationException: Invocation of model ID anthropic.claude-haiku-4-5 with "
            "on-demand throughput isn't supported. Retry your request with the ID or ARN "
            "of an inference profile that contains this model.",
            "AccessDeniedException: You don't have access to the model with the "
            "specified model ID.",
            # IAM sem permissão de InvokeModel no ARN do modelo (troca de modelo sem
            # IAM para o perfil `us.` ou para os ARNs regionais): a mensagem cita o
            # ARN com hífen ("foundation-model/", "inference-profile/").
            "AccessDeniedException: User: arn:aws:iam::123456789012:user/dgb is not "
            "authorized to perform: bedrock:InvokeModel on resource: "
            "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
            "AccessDeniedException: User: arn:aws:sts::123456789012:assumed-role/r/s is not "
            "authorized to perform: bedrock:InvokeModel on resource: "
            "arn:aws:bedrock:us-east-1:123456789012:inference-profile/"
            "us.anthropic.claude-haiku-4-5-20251001-v1:0 because no identity-based policy "
            "allows the bedrock:InvokeModel action",
            "AccessDeniedException: User: arn:aws:iam::123456789012:user/dgb is not "
            "authorized to perform: bedrock:InvokeModel on resource: "
            "arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0 "
            "with an explicit deny in a service control policy",
        ],
    )
    def test_detecta_modelo_indisponivel(self, error):
        assert llm_client_mod.is_model_unavailable_error(error) is True

    @pytest.mark.parametrize(
        "error",
        [
            None,
            "",
            "ThrottlingException: Rate exceeded",
            "ValidationException: Input is too long for requested model.",
            "ValueError: JSON não encontrado na resposta",
            "ServiceUnavailableException: Bedrock is unable to process your request.",
            # AccessDenied que não é do modelo (outra ação/recurso) não alerta.
            "AccessDeniedException: User: arn:aws:iam::123456789012:user/dgb is not "
            "authorized to perform: sts:AssumeRole on resource: "
            "arn:aws:iam::123456789012:role/outro",
            # Os marcadores de ARN valem só para AccessDenied: uma ValidationException
            # de entrada que cite o ARN do modelo não é modelo indisponível.
            "ValidationException: Malformed input request for "
            "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-haiku-4-5, "
            "please reformat your input and try again.",
        ],
    )
    def test_ignora_erros_transitorios_ou_de_entrada(self, error):
        assert llm_client_mod.is_model_unavailable_error(error) is False


class TestClassifierPropagaErro:
    def test_classify_single_propaga_error(self):
        classifier = NewsClassifier.__new__(NewsClassifier)
        classifier.verbose = False
        classifier.llm_client = MagicMock()
        classifier.llm_client.enrich_news_batch.return_value = [
            {
                "unique_id": "abc123",
                "title": "T",
                "content": "C",
                "theme_1_level_1_code": None,
                "_model_id": "m",
                "_error": "ThrottlingException: Rate exceeded",
            }
        ]

        result = classifier.classify_single(
            {"unique_id": "abc123", "title": "T", "content": "C"}, return_format="dict"
        )

        assert result["_error"] == "ThrottlingException: Rate exceeded"
        assert result["_model_id"] == "m"
        assert "title" not in result
