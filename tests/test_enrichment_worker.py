"""
Unit tests for Enrichment Worker.

Tests the FastAPI app (Pub/Sub push handling) and the handler
(fetch → classify → update PG → publish enriched event).
"""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from news_enrichment.worker.app import app
from news_enrichment.worker.handler import (
    enrich_article,
    fetch_article,
    is_already_enriched,
    publish_enriched_event,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def pubsub_envelope():
    data = {"unique_id": "mec-2026-01-01-noticia-1", "agency_key": "mec"}
    return {
        "message": {
            "data": base64.b64encode(json.dumps(data).encode()).decode(),
            "attributes": {"trace_id": "abc-123", "event_version": "1.0"},
            "messageId": "msg-001",
        },
        "subscription": "projects/test/subscriptions/dgb.news.scraped--enrichment",
    }


@pytest.fixture
def sample_article():
    return {
        "unique_id": "mec-2026-01-01-noticia-1",
        "title": "Governo anuncia reforma tributária",
        "subtitle": "Nova proposta visa simplificar o sistema",
        "editorial_lead": None,
        "content": "O governo federal anunciou hoje uma nova proposta de reforma tributária.",
    }


@pytest.fixture
def classification_result():
    return {
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


# =============================================================================
# FastAPI endpoint tests
# =============================================================================


class TestProcessEndpoint:

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @patch("news_enrichment.worker.app.enrich_article")
    def test_valid_message_returns_200(self, mock_enrich, client, pubsub_envelope):
        mock_enrich.return_value = {"status": "enriched"}
        resp = client.post("/process", json=pubsub_envelope)
        assert resp.status_code == 200
        mock_enrich.assert_called_once_with("mec-2026-01-01-noticia-1")

    def test_missing_data_returns_400(self, client):
        resp = client.post("/process", json={"message": {}})
        assert resp.status_code == 400

    def test_missing_unique_id_returns_400(self, client):
        data = base64.b64encode(json.dumps({"agency": "mec"}).encode()).decode()
        resp = client.post("/process", json={"message": {"data": data}})
        assert resp.status_code == 400

    @patch("news_enrichment.worker.app.enrich_article", side_effect=Exception("Bedrock timeout"))
    def test_unhandled_error_still_acks(self, mock_enrich, client, pubsub_envelope):
        """Unhandled errors return 200 to avoid infinite retries."""
        resp = client.post("/process", json=pubsub_envelope)
        assert resp.status_code == 200


# =============================================================================
# Handler: fetch_article
# =============================================================================


class TestFetchArticle:

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_returns_dict_when_found(self, mock_url, mock_connect, sample_article):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = tuple(sample_article.values())
        mock_cursor.description = [(k,) for k in sample_article.keys()]
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_connect.return_value)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value.cursor.return_value = mock_cursor

        result = fetch_article("mec-2026-01-01-noticia-1")
        assert result is not None
        assert result["unique_id"] == "mec-2026-01-01-noticia-1"

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_returns_none_when_not_found(self, mock_url, mock_connect):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_connect.return_value)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value.cursor.return_value = mock_cursor

        result = fetch_article("nonexistent")
        assert result is None


# =============================================================================
# Handler: is_already_enriched
# =============================================================================


class TestIsAlreadyEnriched:

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_true_when_theme_set(self, mock_url, mock_connect):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_connect.return_value)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value.cursor.return_value = mock_cursor

        assert is_already_enriched("test-1") is True

    @patch("news_enrichment.worker.handler.psycopg2.connect")
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_false_when_theme_null(self, mock_url, mock_connect):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (None,)
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_connect.return_value)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value.cursor.return_value = mock_cursor

        assert is_already_enriched("test-1") is False


# =============================================================================
# Handler: enrich_article (integration)
# =============================================================================


class TestEnrichArticle:

    @patch("news_enrichment.worker.handler.publish_enriched_event")
    @patch("news_enrichment.worker.handler.update_news_enrichment")
    @patch("news_enrichment.worker.handler._get_code_to_id")
    @patch("news_enrichment.worker.handler._get_classifier")
    @patch("news_enrichment.worker.handler.fetch_article")
    @patch("news_enrichment.worker.handler.is_already_enriched", return_value=False)
    @patch("news_enrichment.worker.handler._get_database_url", return_value="postgresql://test")
    def test_full_pipeline(
        self, mock_url, mock_enriched, mock_fetch, mock_classifier, mock_code_to_id,
        mock_update, mock_publish, sample_article, classification_result,
    ):
        mock_fetch.return_value = sample_article
        mock_classifier.return_value.classify_single.return_value = classification_result
        mock_code_to_id.return_value = {"01": 1, "01.02": 5, "01.02.03": 15}
        mock_update.return_value = {"updated": 1, "skipped": 0, "failed": 0}

        result = enrich_article("mec-2026-01-01-noticia-1")

        assert result["status"] == "enriched"
        mock_classifier.return_value.classify_single.assert_called_once()
        mock_update.assert_called_once()
        mock_publish.assert_called_once_with(
            "mec-2026-01-01-noticia-1", "01.02.03", True
        )

    @patch("news_enrichment.worker.handler.is_already_enriched", return_value=True)
    def test_skips_already_enriched(self, mock_enriched):
        result = enrich_article("test-1")
        assert result["status"] == "skipped"
        assert result["reason"] == "already_enriched"

    @patch("news_enrichment.worker.handler.fetch_article", return_value=None)
    @patch("news_enrichment.worker.handler.is_already_enriched", return_value=False)
    def test_not_found(self, mock_enriched, mock_fetch):
        result = enrich_article("nonexistent")
        assert result["status"] == "not_found"

    @patch("news_enrichment.worker.handler._get_classifier")
    @patch("news_enrichment.worker.handler.fetch_article")
    @patch("news_enrichment.worker.handler.is_already_enriched", return_value=False)
    def test_classification_failed(self, mock_enriched, mock_fetch, mock_classifier, sample_article):
        mock_fetch.return_value = sample_article
        mock_classifier.return_value.classify_single.return_value = None

        result = enrich_article("test-1")
        assert result["status"] == "classification_failed"


# =============================================================================
# Handler: publish_enriched_event
# =============================================================================


class TestPublishEnrichedEvent:

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": ""})
    def test_no_publish_without_topic(self):
        """No error and no publish when topic not set."""
        publish_enriched_event("test-1", "01.02", True)  # Should not raise

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": "projects/p/topics/t"})
    @patch("news_enrichment.worker.handler.pubsub_v1", create=True)
    def test_publishes_with_correct_data(self, mock_pubsub_module):
        mock_client = MagicMock()
        with patch("news_enrichment.worker.handler.pubsub_v1", create=True) as mock_mod:
            # Simulate the import inside the function
            with patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": "projects/p/topics/t"}):
                with patch("google.cloud.pubsub_v1.PublisherClient", return_value=mock_client):
                    publish_enriched_event("test-1", "01.02.03", True)
                    mock_client.publish.assert_called_once()
                    call_args = mock_client.publish.call_args
                    data = json.loads(call_args[0][1].decode())
                    assert data["unique_id"] == "test-1"
                    assert data["most_specific_theme_code"] == "01.02.03"
                    assert data["has_summary"] is True
