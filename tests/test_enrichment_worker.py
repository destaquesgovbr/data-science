"""
Unit tests for Enrichment Worker.

Tests the FastAPI app (Pub/Sub push handling) and the handler
(fetch → classify → update PG → publish enriched event).
"""

import base64
import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from news_enrichment.llm_client import DEFAULT_ENRICHMENT_MODEL_ID
from news_enrichment.worker import handler
from news_enrichment.worker.app import app
from news_enrichment.worker.handler import (
    enrich_article,
    fetch_article,
    is_already_enriched,
    publish_enriched_event,
)
from tests.fakedb import FakeDB


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

    # Guarda "NER no máximo 1x por uid" consulta o DB: aqui o NER ainda não rodou.
    @pytest.fixture(autouse=True)
    def _ner_not_done(self):
        with patch("news_enrichment.worker.handler.ner_already_done", return_value=False):
            yield

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


# =============================================================================
# Fase 2.5 (DS-1): falha da chamada combinada visível + NER no máximo 1x por uid
# =============================================================================

_HANDLER_LOGGER = "news_enrichment.worker.handler"
_UID = "mec-2026-09-30-noticia-1"
_HAIKU3 = "anthropic.claude-3-haiku-20240307-v1:0"
_EOL_ERROR = (
    "ResourceNotFoundException: This model version has reached the end of its life. "
    "Please refer to the AWS documentation for more details."
)
_NER_ENTITIES = [
    {
        "text": "Bolsa Família",
        "type": "POLICY",
        "count": 1,
        "forma_canonica": "Bolsa Família",
        "salience": 0.8,
    }
]
_NER_RAW = {
    "model_id": "us.anthropic.claude-sonnet-4-6",
    "prompt_version": "ner-v1",
    "prompt_hash": "h",
    "raw_response": {"entities": []},
    "usage": {"input_tokens": 1200, "output_tokens": 40},
}


def _combined_fallback(error=_EOL_ERROR, model_id=_HAIKU3):
    """Resultado de classify_single quando a chamada combinada falha (fallback)."""
    result = {
        "unique_id": _UID,
        "theme_1_level_1": None,
        "theme_1_level_1_code": None,
        "theme_1_level_1_label": None,
        "theme_1_level_2_code": None,
        "theme_1_level_2_label": None,
        "theme_1_level_3_code": None,
        "theme_1_level_3_label": None,
        "most_specific_theme_code": None,
        "most_specific_theme_label": None,
        "summary": None,
        "sentiment": None,
        "_usage": None,
        "_model_id": model_id,
        "_error": error,
    }
    return result


def _messages(caplog, level):
    return [r.getMessage() for r in caplog.records if r.levelno == level]


@pytest.fixture
def failing_classifier():
    clf = MagicMock()
    clf.llm_client.model_id = _HAIKU3
    clf.llm_client.ner_model_id = "us.anthropic.claude-sonnet-4-6"
    clf.classify_single.return_value = _combined_fallback()
    clf.llm_client.extract_entities.return_value = (list(_NER_ENTITIES), dict(_NER_RAW))
    return clf


class TestCombinedFailure:
    """Falha combinada: ERROR estável, status classification_failed, sem publicar."""

    @pytest.fixture(autouse=True)
    def _patches(self, failing_classifier, sample_article):
        with patch.object(handler, "is_already_enriched", return_value=False), patch.object(
            handler, "fetch_article", return_value=dict(sample_article)
        ), patch.object(handler, "_get_classifier", return_value=failing_classifier), patch.object(
            handler, "publish_enriched_event"
        ) as mock_publish, patch.object(
            handler, "update_news_enrichment"
        ) as mock_update, patch.object(
            handler, "_upsert_ai_features"
        ) as mock_upsert, patch.object(
            handler, "store_raw_llm_response"
        ) as mock_store_raw, patch.object(
            handler, "_record_ledger_usage"
        ) as mock_ledger:
            self.mock_publish = mock_publish
            self.mock_update = mock_update
            self.mock_upsert = mock_upsert
            self.mock_store_raw = mock_store_raw
            self.mock_ledger = mock_ledger
            yield

    @patch.object(handler, "ner_already_done", return_value=True)
    def test_falha_combinada_loga_erro_e_retorna_classification_failed(
        self, mock_done, failing_classifier, caplog
    ):
        failing_classifier.classify_single.return_value = _combined_fallback(
            error="ThrottlingException: Rate exceeded"
        )
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        result = handler.enrich_article(_UID)

        assert result["status"] == "classification_failed"
        assert result["error"] == "ThrottlingException: Rate exceeded"
        errors = _messages(caplog, logging.ERROR)
        assert (
            f"enrichment_combined_failed uid={_UID} model={_HAIKU3} "
            "error=ThrottlingException: Rate exceeded"
        ) in errors
        # Erro transitório não dispara o alerta de modelo indisponível.
        assert not _messages(caplog, logging.CRITICAL)

    @patch.object(handler, "ner_already_done", return_value=True)
    def test_temas_todos_nulos_sem_error_tambem_e_falha(
        self, mock_done, failing_classifier, caplog
    ):
        failing_classifier.classify_single.return_value = _combined_fallback(error=None)
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        result = handler.enrich_article(_UID)

        assert result["status"] == "classification_failed"
        assert any(
            m.startswith(f"enrichment_combined_failed uid={_UID} model={_HAIKU3} error=")
            for m in _messages(caplog, logging.ERROR)
        )

    @patch.object(handler, "ner_already_done", return_value=True)
    def test_falha_combinada_nao_publica_nem_atualiza_tema(self, mock_done):
        result = handler.enrich_article(_UID)

        assert result["status"] == "classification_failed"
        self.mock_publish.assert_not_called()
        self.mock_update.assert_not_called()

    @patch.object(handler, "ner_already_done", return_value=True)
    def test_modelo_em_fim_de_vida_loga_critical_estavel(self, mock_done, caplog):
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        handler.enrich_article(_UID)

        critical = _messages(caplog, logging.CRITICAL)
        assert len(critical) == 1
        assert critical[0].startswith(f"enrichment_model_unavailable model={_HAIKU3}")

    @patch.object(handler, "ner_already_done", return_value=False)
    def test_falha_combinada_mantem_ner_e_upsert_de_entidades_sem_entidades_previas(
        self, mock_done, failing_classifier
    ):
        result = handler.enrich_article(_UID)

        assert result["status"] == "classification_failed"
        assert result["ner"] == "ran"
        failing_classifier.llm_client.extract_entities.assert_called_once()
        self.mock_store_raw.assert_called_once()
        upserted = self.mock_upsert.call_args[0][1]
        assert upserted == {"entities": _NER_ENTITIES}
        self.mock_publish.assert_not_called()

    @patch.object(handler, "ner_already_done", return_value=True)
    def test_falha_combinada_com_entidades_pula_ner(self, mock_done, failing_classifier):
        result = handler.enrich_article(_UID)

        assert result["status"] == "classification_failed"
        assert result["ner"] == "skipped_already_done"
        failing_classifier.llm_client.extract_entities.assert_not_called()
        self.mock_upsert.assert_not_called()


class TestNerNoMaximoUmaVezPorUid:
    """Anti-amplificação: o scraper republica `scraped` ~13x/dia por artigo."""

    @pytest.fixture
    def fake_db(self, monkeypatch, failing_classifier, sample_article):
        db = FakeDB()
        monkeypatch.setattr(handler.psycopg2, "connect", lambda *a, **k: db.conn())
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")
        monkeypatch.setattr(handler, "is_already_enriched", lambda uid: False)
        monkeypatch.setattr(handler, "fetch_article", lambda uid: dict(sample_article))
        monkeypatch.setattr(handler, "_get_classifier", lambda: failing_classifier)
        self.mock_publish = MagicMock()
        monkeypatch.setattr(handler, "publish_enriched_event", self.mock_publish)
        return db

    def test_dois_eventos_com_classificacao_falhando_chamam_ner_uma_vez(
        self, fake_db, failing_classifier
    ):
        first = handler.enrich_article(_UID)
        second = handler.enrich_article(_UID)

        assert failing_classifier.llm_client.extract_entities.call_count == 1
        assert first["status"] == second["status"] == "classification_failed"
        assert first["ner"] == "ran"
        assert second["ner"] == "skipped_already_done"
        assert fake_db.news_features[_UID]["entities"][0]["text"] == "Bolsa Família"
        self.mock_publish.assert_not_called()

    def test_ner_sem_entidades_tambem_conta_como_feito(self, fake_db, failing_classifier):
        # NER respondeu (raw gravado) mas sem entidades: não re-roda na republicação.
        failing_classifier.llm_client.extract_entities.return_value = ([], dict(_NER_RAW))

        handler.enrich_article(_UID)
        handler.enrich_article(_UID)

        assert failing_classifier.llm_client.extract_entities.call_count == 1

    def test_entidades_preexistentes_nao_sao_sobrescritas(self, fake_db, failing_classifier):
        canon = [{"text": "MEC", "type": "ORG", "canonical_id": "Q1"}]
        fake_db.seed_news_features(_UID, canon)

        handler.enrich_article(_UID)

        failing_classifier.llm_client.extract_entities.assert_not_called()
        assert fake_db.news_features[_UID]["entities"] == canon

    def test_ledger_registra_tokens_do_ner_na_falha(self, fake_db):
        handler.enrich_article(_UID)

        assert fake_db.ledger["us.anthropic.claude-sonnet-4-6"] == {
            "input_tokens": 1200,
            "output_tokens": 40,
        }


class TestNerAlreadyDone:
    @pytest.fixture
    def fake_db(self, monkeypatch):
        db = FakeDB()
        monkeypatch.setattr(handler.psycopg2, "connect", lambda *a, **k: db.conn())
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")
        return db

    def test_false_sem_features_nem_raw(self, fake_db):
        assert handler.ner_already_done(_UID) is False

    def test_true_com_entidades(self, fake_db):
        fake_db.seed_news_features(_UID, [{"text": "MEC", "type": "ORG"}])
        assert handler.ner_already_done(_UID) is True

    def test_true_com_raw_de_ner(self, fake_db):
        fake_db.llm_raw.append((_UID, "ner", "m", "ner-v1", "h", None))
        assert handler.ner_already_done(_UID) is True

    def test_sql_checa_entities_e_news_llm_raw(self, fake_db):
        handler.ner_already_done(_UID)
        sql = fake_db.log[-1][0].lower()
        assert "features ? 'entities'" in sql
        assert "news_llm_raw" in sql and "task = 'ner'" in sql

    def test_falha_ao_conectar_levanta(self, monkeypatch):
        # Não devolve True disfarçado de "já feito": quem chama distingue o caso.
        def _boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr(handler.psycopg2, "connect", _boom)
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")

        with pytest.raises(RuntimeError, match="db down"):
            handler.ner_already_done(_UID)

    def test_falha_na_consulta_levanta_e_fecha_conexao(self, monkeypatch):
        conn = MagicMock()
        conn.cursor.return_value.execute.side_effect = RuntimeError("statement timeout")
        monkeypatch.setattr(handler.psycopg2, "connect", lambda *a, **k: conn)
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")

        with pytest.raises(RuntimeError, match="statement timeout"):
            handler.ner_already_done(_UID)
        conn.close.assert_called_once()


class TestNerGuardCheckFailed:
    """Guarda do NER indisponível (erro de DB): pula o NER (fail-closed) com status próprio.

    A métrica de NER por uid não pode contar "pulado por erro de DB" como "já feito":
    no caminho de sucesso o tema é gravado e a idempotência impede nova tentativa,
    então esse artigo fica sem NER até o backfill_ner_corpus.py.
    """

    @pytest.fixture(autouse=True)
    def _patches(self, sample_article):
        with patch.object(handler, "is_already_enriched", return_value=False), patch.object(
            handler, "fetch_article", return_value=dict(sample_article)
        ), patch.object(
            handler, "ner_already_done", side_effect=RuntimeError("db down")
        ), patch.object(
            handler, "publish_enriched_event"
        ) as mock_publish, patch.object(
            handler,
            "update_news_enrichment",
            return_value={"updated": 1, "skipped": 0, "failed": 0},
        ), patch.object(
            handler, "_get_code_to_id", return_value={"01.02.03": 15}
        ), patch.object(
            handler, "_get_database_url", return_value="postgresql://fake"
        ), patch.object(
            handler, "_upsert_ai_features"
        ) as mock_upsert, patch.object(
            handler, "store_raw_llm_response"
        ) as mock_store_raw, patch.object(
            handler, "_record_ledger_usage"
        ):
            self.mock_publish = mock_publish
            self.mock_upsert = mock_upsert
            self.mock_store_raw = mock_store_raw
            yield

    def _stable_ner_lines(self, caplog):
        return [
            (r.levelno, r.getMessage())
            for r in caplog.records
            if r.getMessage().startswith("enrichment_ner ")
        ]

    def test_falha_combinada_com_guarda_indisponivel(self, failing_classifier, caplog):
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        with patch.object(handler, "_get_classifier", return_value=failing_classifier):
            result = handler.enrich_article(_UID)

        assert result["status"] == "classification_failed"
        assert result["ner"] == "skipped_check_failed"
        failing_classifier.llm_client.extract_entities.assert_not_called()
        self.mock_store_raw.assert_not_called()
        self.mock_upsert.assert_not_called()
        assert self._stable_ner_lines(caplog) == [
            (
                logging.WARNING,
                f"enrichment_ner uid={_UID} status=skipped_check_failed "
                "model=us.anthropic.claude-sonnet-4-6 error=RuntimeError",
            )
        ]

    def test_sucesso_com_guarda_indisponivel(
        self, failing_classifier, classification_result, caplog
    ):
        failing_classifier.classify_single.return_value = dict(classification_result)
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        with patch.object(handler, "_get_classifier", return_value=failing_classifier):
            result = handler.enrich_article(_UID)

        assert result["status"] == "enriched"
        failing_classifier.llm_client.extract_entities.assert_not_called()
        self.mock_publish.assert_called_once()
        lines = self._stable_ner_lines(caplog)
        assert len(lines) == 1
        assert lines[0][1].startswith(f"enrichment_ner uid={_UID} status=skipped_check_failed ")
        assert all("skipped_already_done" not in m for _, m in lines)


class TestSuccessPathNerGuard:
    """Caminho de sucesso também respeita o NER no máximo uma vez por uid."""

    @patch.object(handler, "ner_already_done", return_value=True)
    @patch.object(handler, "_upsert_ai_features")
    @patch.object(handler, "publish_enriched_event")
    @patch.object(handler, "update_news_enrichment")
    @patch.object(handler, "_get_code_to_id", return_value={"01": 1})
    @patch.object(handler, "_get_classifier")
    @patch.object(handler, "fetch_article")
    @patch.object(handler, "is_already_enriched", return_value=False)
    @patch.object(handler, "_get_database_url", return_value="postgresql://test")
    def test_sucesso_com_entidades_existentes_pula_ner(
        self, mock_url, mock_enriched, mock_fetch, mock_classifier, mock_code_to_id,
        mock_update, mock_publish, mock_upsert, mock_done, sample_article,
        classification_result,
    ):
        mock_fetch.return_value = sample_article
        mock_classifier.return_value.classify_single.return_value = dict(classification_result)
        mock_update.return_value = {"updated": 1, "skipped": 0, "failed": 0}

        result = handler.enrich_article(_UID)

        assert result["status"] == "enriched"
        mock_classifier.return_value.llm_client.extract_entities.assert_not_called()
        mock_publish.assert_called_once()
        assert "entities" not in mock_upsert.call_args[0][1] or not mock_upsert.call_args[0][1][
            "entities"
        ]

    @patch.object(handler, "ner_already_done", return_value=True)
    @patch.object(handler, "_upsert_ai_features")
    @patch.object(handler, "publish_enriched_event")
    @patch.object(handler, "update_news_enrichment")
    @patch.object(handler, "_get_code_to_id", return_value={})
    @patch.object(handler, "_get_classifier")
    @patch.object(handler, "fetch_article")
    @patch.object(handler, "is_already_enriched", return_value=False)
    @patch.object(handler, "_get_database_url", return_value="postgresql://test")
    def test_update_failed_loga_error_estavel(
        self, mock_url, mock_enriched, mock_fetch, mock_classifier, mock_code_to_id,
        mock_update, mock_publish, mock_upsert, mock_done, sample_article,
        classification_result, caplog,
    ):
        mock_fetch.return_value = sample_article
        mock_classifier.return_value.classify_single.return_value = dict(classification_result)
        mock_update.return_value = {"updated": 0, "skipped": 1, "failed": 0}
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        result = handler.enrich_article(_UID)

        assert result["status"] == "update_failed"
        assert any(
            m.startswith(f"enrichment_update_failed uid={_UID}")
            for m in _messages(caplog, logging.ERROR)
        )
        mock_publish.assert_not_called()


class TestAppAcksClassificationFailed:
    @patch("news_enrichment.worker.app.enrich_article")
    def test_classification_failed_responde_200(self, mock_enrich, client, pubsub_envelope):
        mock_enrich.return_value = {
            "status": "classification_failed",
            "error": _EOL_ERROR,
            "ner": "skipped_already_done",
        }
        resp = client.post("/process", json=pubsub_envelope)
        assert resp.status_code == 200
        assert resp.json()["status"] == "classification_failed"


class TestEnrichmentModelEnv:
    """Sem ENRICHMENT_MODEL_ID/BEDROCK_MODEL_ID: ERROR (não warning) e default legado."""

    def test_sem_env_loga_error_e_usa_default_legado(self, monkeypatch, caplog):
        monkeypatch.delenv("ENRICHMENT_MODEL_ID", raising=False)
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        model_id = handler._resolve_enrichment_model_id()

        assert model_id == DEFAULT_ENRICHMENT_MODEL_ID
        assert any(
            m.startswith(f"enrichment_model_env_missing default={DEFAULT_ENRICHMENT_MODEL_ID}")
            for m in _messages(caplog, logging.ERROR)
        )

    def test_enrichment_model_id_tem_precedencia(self, monkeypatch, caplog):
        monkeypatch.setenv("ENRICHMENT_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "outro")
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        assert (
            handler._resolve_enrichment_model_id()
            == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        )
        assert not _messages(caplog, logging.ERROR)

    def test_bedrock_model_id_legado_sem_error(self, monkeypatch, caplog):
        monkeypatch.delenv("ENRICHMENT_MODEL_ID", raising=False)
        monkeypatch.setenv("BEDROCK_MODEL_ID", "legado")
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        assert handler._resolve_enrichment_model_id() == "legado"
        assert not _messages(caplog, logging.ERROR)

    @patch.object(handler, "NewsClassifier")
    @patch.object(handler, "load_taxonomy_from_postgres", return_value={})
    @patch.object(handler, "_get_database_url", return_value="postgresql://test")
    def test_get_classifier_sem_env_loga_error(
        self, mock_url, mock_tax, mock_clf, monkeypatch, caplog
    ):
        monkeypatch.delenv("ENRICHMENT_MODEL_ID", raising=False)
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
        monkeypatch.delenv("NER_MODEL_ID", raising=False)
        monkeypatch.setattr(handler, "_classifier", None)
        caplog.set_level(logging.INFO, logger=_HANDLER_LOGGER)

        handler._get_classifier()

        assert mock_clf.call_args.kwargs["model_id"] == DEFAULT_ENRICHMENT_MODEL_ID
        assert any(
            m.startswith("enrichment_model_env_missing") for m in _messages(caplog, logging.ERROR)
        )
