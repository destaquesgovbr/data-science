"""
Testes do handler para a Fase 2: chamada NER separada, armazenamento da
resposta crua em news_llm_raw, e shape evoluído das menções em news_features.

DB e Bedrock são mockados; nenhuma chamada real.
"""

from unittest.mock import MagicMock, patch

import pytest

from news_enrichment.worker import handler


@pytest.fixture
def sample_article():
    return {
        "unique_id": "mec-2026-01-01-1",
        "title": "Governo amplia o Bolsa Família",
        "subtitle": None,
        "editorial_lead": None,
        "content": "O Ministério da Saúde anunciou a ampliação do Bolsa Família.",
    }


@pytest.fixture
def classification_result():
    return {
        "theme_1_level_1_code": "01",
        "theme_1_level_1_label": "Economia",
        "theme_1_level_2_code": "01.02",
        "theme_1_level_2_label": "X",
        "theme_1_level_3_code": "01.02.03",
        "theme_1_level_3_label": "Y",
        "most_specific_theme_code": "01.02.03",
        "most_specific_theme_label": "Y",
        "summary": "Resumo.",
        "sentiment": {"label": "positive", "score": 0.6},
    }


# --- _upsert_ai_features: evolved mention shape ---


class TestUpsertAiFeaturesMentionShape:
    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_writes_evolved_entity_shape(self, mock_url, mock_connect):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        entities = [
            {
                "text": "Bolsa Família",
                "type": "POLICY",
                "count": 2,
                "forma_canonica": "Bolsa Família",
                "salience": 0.9,
            }
        ]
        result = {"sentiment": {"label": "positive", "score": 0.6}, "entities": entities}
        handler._upsert_ai_features("uid-1", result)

        # Inspeciona o JSON que foi gravado.
        args, _ = mock_cursor.execute.call_args
        json_arg = args[1][1]  # psycopg2.extras.Json wrapper
        written = json_arg.adapted if hasattr(json_arg, "adapted") else json_arg
        ent = written["entities"][0]
        assert set(ent.keys()) == {"text", "type", "count", "forma_canonica", "salience"}
        # canonical_id e offsets ficam de fora (fases posteriores).
        assert "canonical_id" not in ent
        assert "offsets" not in ent

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_uses_jsonb_merge(self, mock_url, mock_connect):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = {"entities": [{"text": "Finep", "type": "ORG", "count": 1}]}
        handler._upsert_ai_features("uid-1", result)
        sql = mock_cursor.execute.call_args[0][0]
        assert "features || EXCLUDED.features" in sql

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_normalizes_partial_entities(self, mock_url, mock_connect):
        """Entidades vindas já parseadas mas sem todas as chaves são completadas."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = {"entities": [{"text": "Finep", "type": "ORG"}]}
        handler._upsert_ai_features("uid-1", result)
        json_arg = mock_cursor.execute.call_args[0][1][1]
        written = json_arg.adapted if hasattr(json_arg, "adapted") else json_arg
        ent = written["entities"][0]
        assert ent["count"] == 1
        assert ent["forma_canonica"] == "Finep"
        assert ent["salience"] is None

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_no_write_when_no_features(self, mock_url, mock_connect):
        handler._upsert_ai_features("uid-1", {})
        mock_connect.assert_not_called()


# --- store_raw_llm_response: news_llm_raw ---


class TestStoreRawLlmResponse:
    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_inserts_into_news_llm_raw(self, mock_url, mock_connect):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        raw = {
            "model_id": "sonnet-ner",
            "prompt_version": "ner-v1",
            "prompt_hash": "abc123",
            "raw_response": '{"entities": []}',
        }
        handler.store_raw_llm_response("uid-1", "ner", raw)

        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "news_llm_raw" in sql
        assert "uid-1" in params
        assert "ner" in params
        assert "sonnet-ner" in params
        assert "ner-v1" in params
        assert "abc123" in params
        mock_conn.commit.assert_called_once()

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_db_failure_does_not_raise(self, mock_url, mock_connect):
        """Falha ao gravar a resposta crua nunca derruba o enriquecimento."""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("db down")
        mock_connect.return_value = mock_conn

        raw = {
            "model_id": "m",
            "prompt_version": "v",
            "prompt_hash": "h",
            "raw_response": "{}",
        }
        # Não deve levantar.
        handler.store_raw_llm_response("uid-1", "ner", raw)

    def test_none_raw_is_noop(self):
        # raw None (chamada Bedrock falhou) — não tenta gravar nada.
        with patch("news_enrichment.worker.handler.psycopg2.connect") as mock_connect:
            handler.store_raw_llm_response("uid-1", "ner", None)
            mock_connect.assert_not_called()

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_raw_response_stored_as_object_not_quoted_string(self, mock_url, mock_connect):
        """
        raw_response deve ir para o JSONB como OBJETO estruturado (dict/list),
        nunca como string crua (que viraria escalar JSON com double-encoding).
        """
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # extract_entities já entrega raw_response parseado (objeto).
        raw = {
            "model_id": "sonnet-ner",
            "prompt_version": "ner-v1",
            "prompt_hash": "abc123",
            "raw_response": {"entities": [{"text": "Finep", "type": "ORG", "count": 1}]},
        }
        handler.store_raw_llm_response("uid-1", "ner", raw)

        json_arg = mock_cursor.execute.call_args[0][1][-1]  # último param = Json(...)
        wrapped = json_arg.adapted if hasattr(json_arg, "adapted") else json_arg
        assert isinstance(wrapped, (dict, list))
        assert not isinstance(wrapped, str)
        assert wrapped == {"entities": [{"text": "Finep", "type": "ORG", "count": 1}]}

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_raw_response_prose_fallback_stored_as_object(self, mock_url, mock_connect):
        """Resposta não-JSON (prosa) chega como {'raw_text': ...} — objeto, não string."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        raw = {
            "model_id": "sonnet-ner",
            "prompt_version": "ner-v1",
            "prompt_hash": "abc123",
            "raw_response": {"raw_text": "Não há entidades nesta notícia."},
        }
        handler.store_raw_llm_response("uid-1", "ner", raw)

        json_arg = mock_cursor.execute.call_args[0][1][-1]
        wrapped = json_arg.adapted if hasattr(json_arg, "adapted") else json_arg
        assert isinstance(wrapped, dict)
        assert not isinstance(wrapped, str)
        assert wrapped == {"raw_text": "Não há entidades nesta notícia."}


# --- enrich_article: wires NER as a separate call ---


class TestEnrichArticleNerIntegration:
    @patch("news_enrichment.worker.handler.store_raw_llm_response")
    @patch("news_enrichment.worker.handler._upsert_ai_features")
    @patch("news_enrichment.worker.handler.publish_enriched_event")
    @patch("news_enrichment.worker.handler.update_news_enrichment")
    @patch("news_enrichment.worker.handler._get_code_to_id")
    @patch("news_enrichment.worker.handler._get_classifier")
    @patch("news_enrichment.worker.handler.fetch_article")
    @patch("news_enrichment.worker.handler.is_already_enriched", return_value=False)
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_ner_called_separately_and_raw_stored(
        self,
        mock_url,
        mock_enriched,
        mock_fetch,
        mock_classifier,
        mock_code_to_id,
        mock_update,
        mock_publish,
        mock_upsert,
        mock_store_raw,
        sample_article,
        classification_result,
    ):
        mock_fetch.return_value = sample_article
        clf = mock_classifier.return_value
        clf.classify_single.return_value = dict(classification_result)
        # NER é uma chamada separada via o llm_client do classifier.
        ner_entities = [
            {
                "text": "Bolsa Família",
                "type": "POLICY",
                "count": 1,
                "forma_canonica": "Bolsa Família",
                "salience": 0.8,
            }
        ]
        ner_raw = {
            "model_id": "sonnet-ner",
            "prompt_version": "ner-v1",
            "prompt_hash": "h",
            "raw_response": '{"entities": [...]}',
        }
        clf.llm_client.extract_entities.return_value = (ner_entities, ner_raw)
        mock_code_to_id.return_value = {"01": 1, "01.02": 5, "01.02.03": 15}
        mock_update.return_value = {"updated": 1, "skipped": 0, "failed": 0}

        result = handler.enrich_article("mec-2026-01-01-1")

        assert result["status"] == "enriched"
        # NER chamado com return_raw=True
        clf.llm_client.extract_entities.assert_called_once()
        _, kwargs = clf.llm_client.extract_entities.call_args
        assert kwargs.get("return_raw") is True
        # Raw armazenado com task='ner'
        mock_store_raw.assert_called_once()
        store_args = mock_store_raw.call_args[0]
        assert store_args[0] == "mec-2026-01-01-1"
        assert store_args[1] == "ner"
        assert store_args[2] == ner_raw
        # Entidades do NER fluem para _upsert_ai_features
        upsert_result = mock_upsert.call_args[0][1]
        assert upsert_result["entities"] == ner_entities

    @patch("news_enrichment.worker.handler.store_raw_llm_response")
    @patch("news_enrichment.worker.handler._upsert_ai_features")
    @patch("news_enrichment.worker.handler.publish_enriched_event")
    @patch("news_enrichment.worker.handler.update_news_enrichment")
    @patch("news_enrichment.worker.handler._get_code_to_id")
    @patch("news_enrichment.worker.handler._get_classifier")
    @patch("news_enrichment.worker.handler.fetch_article")
    @patch("news_enrichment.worker.handler.is_already_enriched", return_value=False)
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_ner_failure_does_not_break_enrichment(
        self,
        mock_url,
        mock_enriched,
        mock_fetch,
        mock_classifier,
        mock_code_to_id,
        mock_update,
        mock_publish,
        mock_upsert,
        mock_store_raw,
        sample_article,
        classification_result,
    ):
        mock_fetch.return_value = sample_article
        clf = mock_classifier.return_value
        clf.classify_single.return_value = dict(classification_result)
        clf.llm_client.extract_entities.side_effect = Exception("ner boom")
        mock_code_to_id.return_value = {"01": 1, "01.02": 5, "01.02.03": 15}
        mock_update.return_value = {"updated": 1, "skipped": 0, "failed": 0}

        result = handler.enrich_article("mec-2026-01-01-1")
        # Enriquecimento (tema/sentimento) ainda completa.
        assert result["status"] == "enriched"
        mock_upsert.assert_called_once()
