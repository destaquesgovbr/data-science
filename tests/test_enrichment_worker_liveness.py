"""
Enrichment Worker — liveness e perda do evento dgb.news.enriched (incidentes 26/10, 29/10, 02/11/2026).

Causa raiz: o `/process` era `async def` e chamava `enrich_article` (Bedrock via boto3 +
psycopg2, síncronos) direto no event loop. Cada instância processava UMA mensagem por vez
(concorrência efetiva 1) e o `/health` ficava sem resposta durante a rajada; o liveness
(timeout 5 s, 3 falhas) matava a instância. Como o `publish()` não esperava o futuro, o
`dgb.news.enriched` de quem acabara de gravar tema/resumo se perdia, e a reentrega caía em
`already_enriched` sem republicar: artigo com tema, sem embedding e fora do Typesense.

Estes testes fixam o contrato da correção:
  - o `/health` responde enquanto há trabalho em andamento e não depende de thread;
  - o `/process` processa mensagens em paralelo (o event loop não bloqueia);
  - o `publish` espera a confirmação; falha vira 503 (o Pub/Sub reentrega);
  - o `PublisherClient` é reutilizado;
  - `already_enriched` sem `content_embedding` (com resumo) republica o `enriched`.
"""

import asyncio
import base64
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import anyio
import httpx
import pytest

from news_enrichment.worker import app as app_module
from news_enrichment.worker import handler
from news_enrichment.worker.app import app

_UID = "mec-2026-11-02-noticia-1"
_TOPIC = "projects/p/topics/dgb.news.enriched"


def _envelope(uid: str = _UID) -> dict:
    data = base64.b64encode(json.dumps({"unique_id": uid}).encode()).decode()
    return {
        "message": {
            "data": data,
            "attributes": {"trace_id": "t-1", "event_version": "1.0"},
            "messageId": "m-1",
        }
    }


def _run(coro):
    return asyncio.run(coro)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://worker")


@pytest.fixture(autouse=True)
def _reset_publisher():
    """O PublisherClient é um singleton do módulo: isola cada teste."""
    handler._publisher = None
    yield
    handler._publisher = None


# =============================================================================
# /health não depende do trabalho
# =============================================================================


class TestHealthNaoBloqueia:

    def test_health_responde_enquanto_process_esta_em_andamento(self):
        """Com uma mensagem em processamento, o /health responde antes dela terminar."""
        started = threading.Event()
        release = threading.Event()
        done_at: dict[str, float] = {}

        def slow_enrich(uid):
            started.set()
            release.wait(timeout=3)
            done_at["process"] = time.monotonic()
            return {"status": "enriched"}

        async def scenario():
            async with _client() as c:
                proc = asyncio.create_task(c.post("/process", json=_envelope()))
                for _ in range(300):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.01)
                resp = await c.get("/health")
                done_at["health"] = time.monotonic()
                release.set()
                proc_resp = await proc
            return resp, proc_resp

        with patch.object(app_module, "enrich_article", side_effect=slow_enrich):
            resp, proc_resp = _run(scenario())

        assert resp.status_code == 200
        assert proc_resp.status_code == 200
        assert done_at["health"] < done_at["process"], (
            "o /health só respondeu depois do /process: o event loop está bloqueado"
        )

    def test_health_nao_usa_o_threadpool(self):
        """Com o threadpool padrão do anyio esgotado, o /health continua respondendo."""
        release = threading.Event()
        done_at: dict[str, float] = {}

        def hold_thread():
            release.wait(timeout=3)
            done_at["blocker"] = time.monotonic()

        async def scenario():
            limiter = anyio.to_thread.current_default_thread_limiter()
            limiter.total_tokens = 1
            blocker = asyncio.create_task(anyio.to_thread.run_sync(hold_thread))
            await asyncio.sleep(0.05)
            async with _client() as c:
                resp = await c.get("/health")
            done_at["health"] = time.monotonic()
            release.set()
            await blocker
            return resp

        resp = _run(scenario())

        assert resp.status_code == 200
        assert done_at["health"] < done_at["blocker"], (
            "o /health esperou uma thread livre: depende do pool de trabalho"
        )


# =============================================================================
# /process em paralelo
# =============================================================================


class TestProcessParalelo:

    def test_duas_mensagens_sao_processadas_ao_mesmo_tempo(self):
        """Duas mensagens só passam da barreira se estiverem em execução simultânea."""
        barrier = threading.Barrier(2, timeout=2)

        def enrich_with_barrier(uid):
            barrier.wait()
            return {"status": "enriched"}

        async def scenario():
            async with _client() as c:
                return await asyncio.gather(
                    c.post("/process", json=_envelope("a_1")),
                    c.post("/process", json=_envelope("b_2")),
                )

        with patch.object(app_module, "enrich_article", side_effect=enrich_with_barrier):
            responses = _run(scenario())

        for resp in responses:
            assert resp.status_code == 200
            assert json.loads(resp.content)["status"] == "enriched", resp.content

    def test_trabalho_roda_no_executor_dedicado(self):
        """O enrich_article roda numa thread do executor do worker (fora do event loop)."""
        seen: dict[str, str] = {}

        def record_thread(uid):
            seen["thread"] = threading.current_thread().name
            return {"status": "enriched"}

        async def scenario():
            async with _client() as c:
                return await c.post("/process", json=_envelope())

        with patch.object(app_module, "enrich_article", side_effect=record_thread):
            resp = _run(scenario())

        assert resp.status_code == 200
        assert isinstance(app_module._executor, ThreadPoolExecutor)
        assert seen["thread"].startswith("enrich-worker")


# =============================================================================
# Falha de publicação → não-2xx (o Pub/Sub reentrega)
# =============================================================================


class TestFalhaDePublicacaoNaoFazAck:

    def test_falha_de_publicacao_responde_503(self):
        err = handler.EnrichedEventPublishError(f"{_UID}: TimeoutError")

        async def scenario():
            async with _client() as c:
                return await c.post("/process", json=_envelope())

        with patch.object(app_module, "enrich_article", side_effect=err):
            resp = _run(scenario())

        assert resp.status_code == 503

    def test_outros_erros_continuam_fazendo_ack(self):
        """Comportamento antigo preservado: exceção não tratada qualquer → 200 (ACK)."""

        async def scenario():
            async with _client() as c:
                return await c.post("/process", json=_envelope())

        with patch.object(app_module, "enrich_article", side_effect=RuntimeError("x")):
            resp = _run(scenario())

        assert resp.status_code == 200


# =============================================================================
# publish_enriched_event: espera o futuro e reutiliza o client
# =============================================================================


def _publisher_mock(result=None, side_effect=None):
    client = MagicMock()
    future = MagicMock()
    if side_effect is not None:
        future.result.side_effect = side_effect
    else:
        future.result.return_value = result or "msg-123"
    client.publish.return_value = future
    return client, future


class TestPublishEnrichedEventConfirmado:

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": _TOPIC})
    def test_espera_a_confirmacao_com_timeout(self):
        client, future = _publisher_mock()
        with patch("google.cloud.pubsub_v1.PublisherClient", return_value=client):
            handler.publish_enriched_event(_UID, "01.02.03", True)

        client.publish.assert_called_once()
        args, kwargs = client.publish.call_args
        assert args[0] == _TOPIC
        data = json.loads(args[1].decode())
        assert data["unique_id"] == _UID
        assert data["most_specific_theme_code"] == "01.02.03"
        assert data["has_summary"] is True
        assert "enriched_at" in data
        assert kwargs["event_version"] == "1.0"
        assert kwargs["trace_id"]
        future.result.assert_called_once()
        timeout = future.result.call_args.kwargs.get("timeout")
        assert timeout is not None and 0 < timeout <= 60

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": _TOPIC})
    def test_timeout_do_futuro_levanta_erro_de_publicacao(self):
        client, _ = _publisher_mock(side_effect=TimeoutError("sem ack do Pub/Sub"))
        with patch("google.cloud.pubsub_v1.PublisherClient", return_value=client):
            with pytest.raises(handler.EnrichedEventPublishError):
                handler.publish_enriched_event(_UID, "01.02.03", True)

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": _TOPIC})
    def test_erro_no_publish_levanta_erro_de_publicacao(self):
        client = MagicMock()
        client.publish.side_effect = RuntimeError("tópico inexistente")
        with patch("google.cloud.pubsub_v1.PublisherClient", return_value=client):
            with pytest.raises(handler.EnrichedEventPublishError):
                handler.publish_enriched_event(_UID, "01.02.03", True)

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": _TOPIC})
    def test_publisher_client_e_reutilizado(self):
        client, _ = _publisher_mock()
        with patch("google.cloud.pubsub_v1.PublisherClient", return_value=client) as ctor:
            handler.publish_enriched_event(_UID, "01", True)
            handler.publish_enriched_event("outro_2", "02", False)

        assert ctor.call_count == 1
        assert client.publish.call_count == 2

    @patch.dict("os.environ", {"PUBSUB_TOPIC_NEWS_ENRICHED": ""})
    def test_sem_topico_nao_publica_nem_cria_client(self):
        with patch("google.cloud.pubsub_v1.PublisherClient") as ctor:
            handler.publish_enriched_event(_UID, "01", True)
        ctor.assert_not_called()


# =============================================================================
# enrich_article: falha de publicação propaga; already_enriched republica
# =============================================================================


@pytest.fixture
def sample_article():
    return {
        "unique_id": _UID,
        "title": "Governo anuncia reforma tributária",
        "subtitle": None,
        "editorial_lead": None,
        "content": "O governo federal anunciou hoje uma nova proposta.",
    }


@pytest.fixture
def classification_result():
    return {
        "theme_1_level_1_code": "01",
        "theme_1_level_2_code": "01.02",
        "theme_1_level_3_code": "01.02.03",
        "most_specific_theme_code": "01.02.03",
        "summary": "Resumo.",
    }


class TestEnrichArticlePublicacao:

    @pytest.fixture(autouse=True)
    def _pipeline(self, monkeypatch, sample_article, classification_result):
        classifier = MagicMock()
        classifier.classify_single.return_value = dict(classification_result)
        classifier.llm_client.extract_entities.return_value = ([], None)
        monkeypatch.setattr(handler, "is_already_enriched", lambda uid: False)
        monkeypatch.setattr(handler, "fetch_article", lambda uid: dict(sample_article))
        monkeypatch.setattr(handler, "_get_classifier", lambda: classifier)
        monkeypatch.setattr(handler, "ner_already_done", lambda uid: True)
        monkeypatch.setattr(handler, "_record_ledger_usage", lambda *a, **k: None)
        monkeypatch.setattr(handler, "_get_code_to_id", lambda: {"01.02.03": 15})
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")
        monkeypatch.setattr(handler, "_upsert_ai_features", lambda *a, **k: None)
        monkeypatch.setattr(
            handler,
            "update_news_enrichment",
            lambda *a, **k: {"updated": 1, "skipped": 0, "failed": 0},
        )

    def test_falha_de_publicacao_apos_gravar_propaga(self, monkeypatch):
        """Não engole a falha: o /process precisa responder não-2xx para reentregar."""
        monkeypatch.setattr(
            handler,
            "publish_enriched_event",
            MagicMock(side_effect=handler.EnrichedEventPublishError("x")),
        )
        with pytest.raises(handler.EnrichedEventPublishError):
            handler.enrich_article(_UID)


class TestAlreadyEnrichedRepublica:

    @pytest.fixture(autouse=True)
    def _already(self, monkeypatch):
        monkeypatch.setattr(handler, "is_already_enriched", lambda uid: True)
        self.publish = MagicMock()
        monkeypatch.setattr(handler, "publish_enriched_event", self.publish)

    def test_sem_embedding_republica_enriched(self, monkeypatch):
        monkeypatch.setattr(
            handler,
            "enriched_event_pending",
            lambda uid: {"most_specific_theme_code": "05.01.02", "has_summary": True},
        )
        result = handler.enrich_article(_UID)

        self.publish.assert_called_once_with(_UID, "05.01.02", True)
        assert result["status"] == "skipped"
        assert result["reason"] == "already_enriched"
        assert result["republished"] is True

    def test_com_embedding_nao_republica(self, monkeypatch):
        monkeypatch.setattr(handler, "enriched_event_pending", lambda uid: None)
        result = handler.enrich_article(_UID)

        self.publish.assert_not_called()
        assert result == {"status": "skipped", "reason": "already_enriched"}

    def test_falha_ao_republicar_propaga(self, monkeypatch):
        monkeypatch.setattr(
            handler,
            "enriched_event_pending",
            lambda uid: {"most_specific_theme_code": "05.01.02", "has_summary": True},
        )
        self.publish.side_effect = handler.EnrichedEventPublishError("x")
        with pytest.raises(handler.EnrichedEventPublishError):
            handler.enrich_article(_UID)

    def test_republicacao_loga_linha_estavel(self, monkeypatch, caplog):
        monkeypatch.setattr(
            handler,
            "enriched_event_pending",
            lambda uid: {"most_specific_theme_code": "05.01.02", "has_summary": True},
        )
        with caplog.at_level("WARNING", logger="news_enrichment.worker.handler"):
            handler.enrich_article(_UID)
        assert any(
            r.getMessage() == f"enrichment_republished uid={_UID} reason=embedding_missing"
            for r in caplog.records
        )


class TestEnrichedEventPending:
    """Consulta de "evento enriched pendente": tema + resumo e sem content_embedding."""

    def _cursor(self, monkeypatch, row):
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        conn = MagicMock()
        conn.cursor.return_value = cursor
        monkeypatch.setattr(handler.psycopg2, "connect", lambda *a, **k: conn)
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")
        return cursor, conn

    def test_pendente_devolve_codigo_e_has_summary(self, monkeypatch):
        cursor, conn = self._cursor(monkeypatch, ("05.01.02",))
        assert handler.enriched_event_pending(_UID) == {
            "most_specific_theme_code": "05.01.02",
            "has_summary": True,
        }
        conn.close.assert_called_once()

    def test_nada_pendente_devolve_none(self, monkeypatch):
        self._cursor(monkeypatch, None)
        assert handler.enriched_event_pending(_UID) is None

    def test_codigo_nulo_vira_string_vazia(self, monkeypatch):
        self._cursor(monkeypatch, (None,))
        assert handler.enriched_event_pending(_UID) == {
            "most_specific_theme_code": "",
            "has_summary": True,
        }

    def test_sql_exige_tema_resumo_e_embedding_nulo(self, monkeypatch):
        cursor, _ = self._cursor(monkeypatch, None)
        handler.enriched_event_pending(_UID)
        sql = " ".join(cursor.execute.call_args[0][0].split()).lower()
        assert "n.most_specific_theme_id is not null" in sql
        assert "n.summary is not null" in sql
        assert "n.content_embedding is null" in sql
        assert cursor.execute.call_args[0][1] == (_UID,)


# =============================================================================
# Inicialização preguiçosa thread-safe (agora há várias threads de trabalho)
# =============================================================================


class TestInicializacaoThreadSafe:

    def test_classifier_inicializa_uma_vez_com_chamadas_concorrentes(self, monkeypatch):
        calls = {"n": 0}

        def slow_taxonomy(url):
            calls["n"] += 1
            time.sleep(0.2)
            return {}

        monkeypatch.setattr(handler, "_classifier", None)
        monkeypatch.setattr(handler, "_get_database_url", lambda: "postgresql://fake")
        monkeypatch.setattr(handler, "load_taxonomy_from_postgres", slow_taxonomy)
        monkeypatch.setattr(handler, "NewsClassifier", MagicMock())
        monkeypatch.setattr(handler, "_parse_aws_credentials", lambda: (None, None, "us-east-1"))

        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(lambda _: handler._get_classifier(), range(4)))

        assert calls["n"] == 1
        assert all(r is results[0] for r in results)
