"""
Testes do re-enriquecimento da chamada combinada (scripts/reenrich_combined_window.py).

Fase 2.5 (DS-1), backfills B2 (null-theme) e B5 (mock). Cobre: SQL das duas
seleções (janela BRT, date-to exclusivo e obrigatório no null-theme, nunca além de
hoje BRT), nunca chama NER, upsert de features só
com `sentiment`, nunca publica evento, governador de cota (record_usage +
budget_exhausted por modelo), --dry-run sem escrita e abort sem
ENRICHMENT_MODEL_ID. Bedrock mockado; Postgres via tests/fakedb.py.

DS-2 (`--select null-summary`): backfill só do resumo (tema gravado, summary
NULL) com o prompt enxuto. Cobre: SQL da seleção, UPDATE só de summary com a
guarda `summary IS NULL`, nunca chama a combinada nem o NER, nunca grava
features (sem sentimento gerado; só a contagem reportada), nunca publica,
resumo vazio/inválido não grava e segue selecionável, governador de cota,
--dry-run e ENRICHMENT_MODEL_ID obrigatória.
"""

import datetime
import importlib.util
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg2
import pytest

from news_enrichment.worker import handler
from tests.fakedb import FakeDB

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "reenrich_combined_window.py")

HAIKU45 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
CODE_TO_ID = {"01": 1, "01.02": 5, "01.02.03": 15}
USAGE = {"input_tokens": 18900, "output_tokens": 301}
TOKENS_PER_ARTICLE = USAGE["input_tokens"] + USAGE["output_tokens"]
TODAY_BRT = datetime.date(2026, 10, 8)
# Janela do B2: do EOL do Haiku 3 até o corte do INF-1 (06/10 00:19Z = 05/10 21:19
# BRT); --date-to é exclusivo.
B2_WINDOW = ["--date-from", "2026-09-25", "--date-to", "2026-10-06"]
SUMMARY_USAGE = {"input_tokens": 900, "output_tokens": 60}
SUMMARY_TOKENS = SUMMARY_USAGE["input_tokens"] + SUMMARY_USAGE["output_tokens"]
# Backfill DS-2: resumos apagados pelo re-scrape desde 02/06 (d406fee, 01/06).
SUMMARY_WINDOW = ["--date-from", "2026-06-01", "--date-to", "2026-10-07"]
UPDATE_SUMMARY_SQL = (
    "update news set summary = %s, updated_at = now() where unique_id = %s and summary is null"
)
EOL_ERROR = (
    "ResourceNotFoundException: This model version has reached the end of its life. "
    "Please refer to the AWS documentation for more details."
)


@pytest.fixture(scope="module")
def rec():
    """Carrega o script por caminho (não é módulo do pacote)."""
    spec = importlib.util.spec_from_file_location("reenrich_combined_window", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ok_result(uid):
    return {
        "unique_id": uid,
        "theme_1_level_1": "Economia e Finanças",
        "theme_1_level_1_code": "01",
        "theme_1_level_1_label": "Economia e Finanças",
        "theme_1_level_2_code": "01.02",
        "theme_1_level_2_label": "Fiscalização e Tributação",
        "theme_1_level_3_code": "01.02.03",
        "theme_1_level_3_label": "Reforma Tributária",
        "most_specific_theme_code": "01.02.03",
        "most_specific_theme_label": "Reforma Tributária",
        "summary": f"Resumo de {uid}.",
        "sentiment": {"label": "neutral", "score": 0.1},
        "_usage": dict(USAGE),
        "_model_id": HAIKU45,
        "_error": None,
    }


def _summary_ok(uid):
    return {
        "summary": f"Resumo enxuto de {uid}.",
        "_usage": dict(SUMMARY_USAGE),
        "_model_id": HAIKU45,
        "_error": None,
    }


def _summary_failed(error, usage=None):
    return {
        "summary": None,
        "_usage": dict(usage or {"input_tokens": 0, "output_tokens": 0}),
        "_model_id": HAIKU45,
        "_error": error,
    }


def _failed_result(uid, error):
    result = {k: None for k in _ok_result(uid)}
    result.update(unique_id=uid, _model_id=HAIKU45, _error=error)
    return result


@pytest.fixture
def env(monkeypatch, rec):
    db = FakeDB()
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("ENRICHMENT_MODEL_ID", HAIKU45)
    monkeypatch.delenv("BEDROCK_DAILY_TOKEN_QUOTA", raising=False)
    monkeypatch.delenv("BACKFILL_QUOTA_FRACTION", raising=False)
    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: db.conn())
    # Relógio fixo: "hoje" (BRT) = 08/10/2026, para os testes não dependerem da data.
    monkeypatch.setattr(rec, "_today_brt", lambda: TODAY_BRT, raising=False)

    clf = MagicMock()
    clf.llm_client.model_id = HAIKU45
    clf.classify_single.side_effect = lambda article, return_format="dict": _ok_result(
        article["unique_id"]
    )
    clf.llm_client.summarize_single.side_effect = lambda article: _summary_ok(article["unique_id"])
    monkeypatch.setattr(handler, "_get_classifier", lambda: clf)
    monkeypatch.setattr(handler, "_get_code_to_id", lambda: dict(CODE_TO_ID))
    monkeypatch.setattr(
        handler, "fetch_article", lambda uid: {"unique_id": uid, "title": "T", "content": "C"}
    )
    publish = MagicMock()
    monkeypatch.setattr(handler, "publish_enriched_event", publish)

    updates = []

    def fake_update(database_url, rows, code_to_id):
        for row in rows:
            updates.append(dict(row))
            news = db.news.setdefault(row["unique_id"], {"published_date": "2026-09-30"})
            news["most_specific_theme_id"] = code_to_id[row["most_specific_theme_code"]]
            news["summary"] = row["summary"]
        return {"updated": len(rows), "skipped": 0, "failed": 0}

    monkeypatch.setattr(rec, "update_news_enrichment", fake_update)
    return SimpleNamespace(db=db, clf=clf, publish=publish, updates=updates)


def _run(rec, uids, **kw):
    params = dict(model_id=HAIKU45, daily_quota=None, quota_fraction=0.8, workers=1)
    params.update(kw)
    return rec.run_reenrich(uids, **params)


def _run_summary(rec, uids, **kw):
    return _run(rec, uids, process=rec.process_one_summary, **kw)


def _news_updates(db):
    """UPDATEs emitidos contra a tabela news (normalizados em minúsculas)."""
    return [
        (sql.lower(), params) for sql, params in db.log if sql.lower().startswith("update news ")
    ]


# ---------------------------------------------------------------------- #
# Seleção                                                                #
# ---------------------------------------------------------------------- #


class TestSelectSql:
    def test_null_theme(self, rec):
        sql = " ".join(rec.build_select_sql("null-theme", with_date_to=True).split()).lower()
        assert "from news n" in sql
        assert "n.most_specific_theme_id is null" in sql
        assert "summary like" not in sql
        # Janela por dia BRT, date-to exclusivo.
        assert "n.published_at >= (%(date_from)s::date::timestamp at time zone" in sql
        assert "n.published_at < (%(date_to)s::date::timestamp at time zone" in sql
        assert "'america/sao_paulo'" in sql
        assert "limit %(limit)s" in sql

    def test_mock(self, rec):
        sql = " ".join(rec.build_select_sql("mock", with_date_to=True).split()).lower()
        assert "n.summary like %(mock_pattern)s" in sql
        assert "most_specific_theme_id is null" not in sql
        params = rec.build_select_params("mock", "2025-09-24", "2026-03-01", 100)
        assert params["mock_pattern"] == "[MOCK]%"
        assert params == {
            "date_from": "2025-09-24",
            "date_to": "2026-03-01",
            "limit": 100,
            "mock_pattern": "[MOCK]%",
        }

    def test_mock_sem_date_to_nao_tem_limite_superior(self, rec):
        sql = rec.build_select_sql("mock", with_date_to=False).lower()
        assert "date_to" not in sql
        assert "date_to" not in rec.build_select_params("mock", "2025-09-24", None, 10)

    def test_null_theme_sem_date_to_e_invalido(self, rec):
        # Sem teto, o ORDER BY published_at DESC pegaria primeiro os artigos novos
        # que o worker ao vivo ainda vai processar (e publicar).
        with pytest.raises(ValueError, match="date"):
            rec.build_select_sql("null-theme", with_date_to=False)

    def test_selecao_invalida(self, rec):
        with pytest.raises(ValueError):
            rec.build_select_sql("tudo", with_date_to=False)

    def test_null_theme_seleciona_a_janela(self, rec, env):
        env.db.seed_news("antes", "2026-09-24")
        env.db.seed_news("inicio", "2026-09-25")
        env.db.seed_news("com-tema", "2026-09-30", most_specific_theme_id=5)
        env.db.seed_news("meio", "2026-10-06")
        env.db.seed_news("fim-exclusivo", "2026-10-07")

        uids = rec.get_window_uids("null-theme", "2026-09-25", "2026-10-07", 100)

        assert uids == ["meio", "inicio"]  # ORDER BY published_at DESC

    def test_mock_seleciona_so_resumos_mock(self, rec, env):
        env.db.seed_news("m1", "2025-10-01", most_specific_theme_id=1, summary="[MOCK] Resumo")
        env.db.seed_news("real", "2025-10-01", most_specific_theme_id=1, summary="Resumo real")
        env.db.seed_news("sem-resumo", "2025-10-02")

        uids = rec.get_window_uids("mock", "2025-09-24", None, 100)

        assert uids == ["m1"]

    def test_limit(self, rec, env):
        for day in range(1, 6):
            env.db.seed_news(f"u{day}", f"2026-10-0{day}")
        assert len(rec.get_window_uids("null-theme", "2026-09-25", "2026-10-07", 3)) == 3


# ---------------------------------------------------------------------- #
# Fluxo por artigo: classify → update → upsert só sentiment → ledger     #
# ---------------------------------------------------------------------- #


class TestFluxo:
    def test_nao_chama_ner(self, rec, env):
        stats = _run(rec, ["u1", "u2"])

        assert stats["ok"] == 2
        env.clf.llm_client.extract_entities.assert_not_called()
        assert env.db.llm_raw == []  # nenhuma resposta crua de NER gravada

    def test_atualiza_tema_e_resumo(self, rec, env):
        _run(rec, ["u1"])

        assert [u["unique_id"] for u in env.updates] == ["u1"]
        assert env.updates[0]["most_specific_theme_code"] == "01.02.03"
        assert env.db.news["u1"]["most_specific_theme_id"] == 15

    def test_upsert_so_sentiment_e_preserva_entidades(self, rec, env):
        canon = [{"text": "MEC", "type": "ORG", "canonical_id": "Q1"}]
        env.db.seed_news_features("u1", canon)

        _run(rec, ["u1"])

        assert env.db.features_upserts == [
            ("u1", {"sentiment": {"label": "neutral", "score": 0.1}})
        ]
        assert env.db.news_features["u1"]["entities"] == canon
        assert env.db.news_features["u1"]["sentiment"] == {"label": "neutral", "score": 0.1}

    def test_sem_sentimento_nao_grava_features(self, rec, env):
        def _no_sentiment(article, return_format="dict"):
            result = _ok_result(article["unique_id"])
            result["sentiment"] = None
            return result

        env.clf.classify_single.side_effect = _no_sentiment

        stats = _run(rec, ["u1"])

        assert stats["ok"] == 1
        assert env.db.features_upserts == []

    def test_nao_publica(self, rec, env):
        _run(rec, ["u1", "u2"])

        env.publish.assert_not_called()

    def test_registra_usage_no_ledger_do_modelo(self, rec, env):
        _run(rec, ["u1", "u2"])

        assert env.db.ledger == {
            HAIKU45: {"input_tokens": 2 * 18900, "output_tokens": 2 * 301},
        }

    def test_falha_transitoria_continua(self, rec, env):
        env.clf.classify_single.side_effect = lambda article, return_format="dict": (
            _failed_result(article["unique_id"], "ThrottlingException: Rate exceeded")
        )

        stats = _run(rec, ["u1", "u2", "u3"])

        assert stats["classification_failed"] == 3
        assert stats["model_unavailable"] is False
        assert env.updates == []
        assert env.db.features_upserts == []

    def test_modelo_indisponivel_aborta(self, rec, env):
        env.clf.classify_single.side_effect = lambda article, return_format="dict": (
            _failed_result(article["unique_id"], EOL_ERROR)
        )

        stats = _run(rec, ["u1", "u2", "u3"])

        assert stats["model_unavailable"] is True
        assert env.clf.classify_single.call_count == 1
        assert env.updates == []

    def test_artigo_ausente(self, rec, env, monkeypatch):
        monkeypatch.setattr(handler, "fetch_article", lambda uid: None)

        stats = _run(rec, ["u1"])

        assert stats["missing"] == 1
        env.clf.classify_single.assert_not_called()


# ---------------------------------------------------------------------- #
# Governador de cota                                                     #
# ---------------------------------------------------------------------- #


class TestGovernador:
    def test_para_antes_de_processar_quando_budget_esgotado(self, rec, env):
        env.db.ledger[HAIKU45] = {"input_tokens": 800, "output_tokens": 0}

        stats = _run(rec, ["u1", "u2"], daily_quota=1000, quota_fraction=0.8)

        assert stats["budget_exhausted"] is True
        env.clf.classify_single.assert_not_called()

    def test_para_no_meio_quando_estoura(self, rec, env):
        # Teto = 5 artigos; checagem a cada BUDGET_CHECK_EVERY (5) artigos.
        quota = int(5 * TOKENS_PER_ARTICLE / 0.8)

        stats = _run(rec, [f"u{i}" for i in range(8)], daily_quota=quota, quota_fraction=0.8)

        assert stats["budget_exhausted"] is True
        assert env.clf.classify_single.call_count == 5

    def test_concorrente_para_entre_lotes(self, rec, env):
        quota = int(5 * TOKENS_PER_ARTICLE / 0.8)

        stats = _run(
            rec, [f"u{i}" for i in range(12)], daily_quota=quota, quota_fraction=0.8, workers=2
        )

        assert stats["budget_exhausted"] is True
        assert env.clf.classify_single.call_count == 5

    def test_budget_e_por_modelo(self, rec, env):
        # Consumo do Sonnet (NER) não bloqueia o backfill do Haiku 4.5.
        env.db.ledger["us.anthropic.claude-sonnet-4-6"] = {
            "input_tokens": 10**9,
            "output_tokens": 0,
        }

        stats = _run(rec, ["u1"], daily_quota=10**6, quota_fraction=0.8)

        assert stats["budget_exhausted"] is False
        assert stats["ok"] == 1


# ---------------------------------------------------------------------- #
# CLI                                                                    #
# ---------------------------------------------------------------------- #


class TestMain:
    def _seed(self, db):
        db.seed_news("u1", "2026-09-26")
        db.seed_news("u2", "2026-10-01")

    def test_dry_run_nao_escreve_nem_chama_bedrock(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "null-theme", *B2_WINDOW, "--dry-run"])

        assert code == 0
        env.clf.classify_single.assert_not_called()
        assert env.updates == []
        assert env.db.features_upserts == []
        assert env.db.ledger == {}
        env.publish.assert_not_called()

    def test_execucao_completa(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "null-theme", *B2_WINDOW])

        assert code == 0
        assert sorted(u["unique_id"] for u in env.updates) == ["u1", "u2"]
        env.clf.llm_client.extract_entities.assert_not_called()
        env.publish.assert_not_called()

    def test_aborta_sem_enrichment_model_id(self, rec, env, monkeypatch):
        self._seed(env.db)
        monkeypatch.delenv("ENRICHMENT_MODEL_ID")
        monkeypatch.setenv("BEDROCK_MODEL_ID", HAIKU45)  # o legado NÃO serve

        code = rec.main(["--select", "null-theme", *B2_WINDOW])

        assert code != 0
        assert env.db.log == []  # nem consultou o banco
        env.clf.classify_single.assert_not_called()

    def test_aborta_sem_database_url(self, rec, env, monkeypatch):
        monkeypatch.delenv("DATABASE_URL")

        code = rec.main(["--select", "null-theme", *B2_WINDOW])

        assert code != 0
        assert env.db.log == []

    def test_aborta_se_classificador_usa_outro_modelo(self, rec, env):
        self._seed(env.db)
        env.clf.llm_client.model_id = "anthropic.claude-3-haiku-20240307-v1:0"

        code = rec.main(["--select", "null-theme", *B2_WINDOW])

        assert code != 0
        env.clf.classify_single.assert_not_called()

    def test_modelo_indisponivel_sai_com_erro(self, rec, env):
        self._seed(env.db)
        env.clf.classify_single.side_effect = lambda article, return_format="dict": (
            _failed_result(article["unique_id"], EOL_ERROR)
        )

        code = rec.main(["--select", "null-theme", *B2_WINDOW])

        assert code != 0

    def test_date_to_deve_ser_posterior(self, rec, env):
        code = rec.main(
            ["--select", "null-theme", "--date-from", "2026-10-01", "--date-to", "2026-10-01"]
        )

        assert code != 0
        assert env.db.log == []

    def test_null_theme_exige_date_to(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "null-theme", "--date-from", "2026-09-25"])

        assert code != 0
        assert env.db.log == []  # nem consultou o banco
        env.clf.classify_single.assert_not_called()

    def test_null_theme_date_to_nao_passa_de_hoje_brt(self, rec, env):
        # date-to exclusivo > hoje incluiria artigos de hoje, que são do worker ao vivo.
        self._seed(env.db)

        code = rec.main(
            ["--select", "null-theme", "--date-from", "2026-09-25", "--date-to", "2026-10-09"]
        )

        assert code != 0
        assert env.db.log == []
        env.clf.classify_single.assert_not_called()

    def test_null_theme_date_to_igual_a_hoje_brt_e_aceito(self, rec, env):
        # date-to = hoje (exclusivo) cobre até ontem 23:59 BRT.
        self._seed(env.db)

        code = rec.main(
            ["--select", "null-theme", "--date-from", "2026-09-25", "--date-to", "2026-10-08"]
        )

        assert code == 0
        assert sorted(u["unique_id"] for u in env.updates) == ["u1", "u2"]

    def test_mock_sem_date_to_continua_valido(self, rec, env):
        env.db.seed_news("m1", "2025-10-01", most_specific_theme_id=1, summary="[MOCK] Resumo")

        code = rec.main(["--select", "mock", "--date-from", "2025-09-24", "--dry-run"])

        assert code == 0
        env.clf.classify_single.assert_not_called()

    def test_select_e_date_from_obrigatorios(self, rec):
        with pytest.raises(SystemExit):
            rec.build_arg_parser().parse_args(["--date-from", "2026-09-25"])
        with pytest.raises(SystemExit):
            rec.build_arg_parser().parse_args(["--select", "null-theme"])

    def test_data_invalida(self, rec):
        with pytest.raises(SystemExit):
            rec.build_arg_parser().parse_args(
                ["--select", "null-theme", "--date-from", "25/09/2026"]
            )

    def test_cota_lida_da_env_por_modelo(self, rec, env, monkeypatch):
        self._seed(env.db)
        monkeypatch.setenv("BEDROCK_DAILY_TOKEN_QUOTA", f'{{"{HAIKU45}": 1000}}')
        env.db.ledger[HAIKU45] = {"input_tokens": 900, "output_tokens": 0}

        code = rec.main(["--select", "null-theme", *B2_WINDOW])

        assert code == 0  # budget esgotado é parada graciosa (resumível)
        env.clf.classify_single.assert_not_called()


# ---------------------------------------------------------------------- #
# DS-2: --select null-summary (só o resumo, prompt enxuto)               #
# ---------------------------------------------------------------------- #


class TestSelectNullSummary:
    def test_sql(self, rec):
        sql = " ".join(rec.build_select_sql("null-summary", with_date_to=True).split()).lower()
        assert "from news n" in sql
        assert "n.most_specific_theme_id is not null" in sql
        assert "n.summary is null" in sql
        assert "summary like" not in sql
        assert "n.published_at >= (%(date_from)s::date::timestamp at time zone" in sql
        assert "n.published_at < (%(date_to)s::date::timestamp at time zone" in sql
        assert "'america/sao_paulo'" in sql
        assert "order by n.published_at desc" in sql
        assert "limit %(limit)s" in sql
        assert rec.build_select_params("null-summary", "2026-06-01", "2026-10-07", 50) == {
            "date_from": "2026-06-01",
            "date_to": "2026-10-07",
            "limit": 50,
        }

    def test_sem_date_to_e_invalido(self, rec):
        with pytest.raises(ValueError, match="date"):
            rec.build_select_sql("null-summary", with_date_to=False)

    def test_seleciona_tema_sem_resumo_na_janela(self, rec, env):
        env.db.seed_news("antes", "2026-05-31", most_specific_theme_id=15)
        env.db.seed_news("inicio", "2026-06-01", most_specific_theme_id=15)
        env.db.seed_news("sem-tema", "2026-07-01")
        env.db.seed_news("com-resumo", "2026-08-01", most_specific_theme_id=15, summary="Ok.")
        env.db.seed_news("meio", "2026-09-15", most_specific_theme_id=5)
        env.db.seed_news("fim-exclusivo", "2026-10-07", most_specific_theme_id=15)

        uids = rec.get_window_uids("null-summary", "2026-06-01", "2026-10-07", 100)

        assert uids == ["meio", "inicio"]  # ORDER BY published_at DESC


class TestContagemComEmbedding:
    def test_sql_so_conta_sem_escrever(self, rec):
        sql = " ".join(rec.WITH_EMBEDDING_SQL.split()).lower()
        assert sql.startswith("select count(*) from news n where")
        assert "n.unique_id = any(%s)" in sql
        assert "n.content_embedding is not null" in sql

    def test_conta_so_os_uids_pedidos_com_embedding(self, rec, env):
        env.db.seed_news("a", "2026-09-01", most_specific_theme_id=15, content_embedding=[0.1])
        env.db.seed_news("b", "2026-09-01", most_specific_theme_id=15)
        env.db.seed_news("fora", "2026-09-01", most_specific_theme_id=15, content_embedding=[0.2])

        assert rec.count_with_embedding(["a", "b", "inexistente"]) == 1


class TestFluxoResumo:
    def _seed(self, db, *uids, summary=None):
        for uid in uids:
            db.seed_news(uid, "2026-09-30", most_specific_theme_id=15, summary=summary)

    def test_grava_so_o_resumo_com_guarda_is_null(self, rec, env):
        self._seed(env.db, "u1")

        stats = _run_summary(rec, ["u1"])

        assert stats["ok"] == 1
        assert env.db.news["u1"]["summary"] == "Resumo enxuto de u1."
        assert env.db.news["u1"]["most_specific_theme_id"] == 15  # tema intacto
        assert _news_updates(env.db) == [(UPDATE_SUMMARY_SQL, ("Resumo enxuto de u1.", "u1"))]

    def test_update_nao_toca_tema_nem_embedding(self, rec):
        sql = " ".join(rec.UPDATE_SUMMARY_SQL.split()).lower()
        assert sql == UPDATE_SUMMARY_SQL
        assert "theme" not in sql
        assert "content_embedding" not in sql

    def test_nao_sobrescreve_resumo_gravado_no_meio_do_run(self, rec, env):
        # Selecionado com summary NULL; o worker ao vivo gravou antes do UPDATE.
        self._seed(env.db, "u1", summary="Resumo do worker.")

        stats = _run_summary(rec, ["u1"])

        assert stats["summary_present"] == 1
        assert "ok" not in stats
        assert env.db.news["u1"]["summary"] == "Resumo do worker."
        assert env.db.ledger[HAIKU45] == SUMMARY_USAGE  # tokens gastos contam

    def test_nao_chama_combinada_nem_ner_nem_grava_features(self, rec, env):
        self._seed(env.db, "u1", "u2")

        stats = _run_summary(rec, ["u1", "u2"])

        assert stats["ok"] == 2
        assert env.clf.llm_client.summarize_single.call_count == 2
        env.clf.classify_single.assert_not_called()
        env.clf.llm_client.extract_entities.assert_not_called()
        assert env.updates == []  # update_news_enrichment (tema) nunca chamado
        assert env.db.features_upserts == []  # nem sentimento nem entidades
        assert env.db.llm_raw == []

    def test_nao_publica(self, rec, env):
        self._seed(env.db, "u1", "u2")

        _run_summary(rec, ["u1", "u2"])

        env.publish.assert_not_called()

    def test_registra_usage_no_ledger_do_modelo(self, rec, env):
        self._seed(env.db, "u1", "u2")

        _run_summary(rec, ["u1", "u2"])

        assert env.db.ledger == {HAIKU45: {"input_tokens": 1800, "output_tokens": 120}}

    @pytest.mark.parametrize(
        "resultado",
        [
            _summary_failed("ValueError: summary ausente ou vazio na resposta", SUMMARY_USAGE),
            dict(_summary_failed(None, SUMMARY_USAGE), summary="   "),
            dict(_summary_failed(None, SUMMARY_USAGE), summary=None),
            dict(_summary_failed(None, SUMMARY_USAGE), summary=42),
        ],
    )
    def test_resumo_vazio_ou_invalido_nao_grava_e_segue_selecionavel(self, rec, env, resultado):
        self._seed(env.db, "u1")
        env.clf.llm_client.summarize_single.side_effect = lambda article: dict(resultado)

        stats = _run_summary(rec, ["u1"])

        assert stats["summary_failed"] == 1
        assert "ok" not in stats
        assert stats["model_unavailable"] is False
        assert _news_updates(env.db) == []
        assert env.db.news["u1"]["summary"] is None
        assert env.db.ledger[HAIKU45] == SUMMARY_USAGE
        assert rec.get_window_uids("null-summary", "2026-06-01", "2026-10-07", 10) == ["u1"]

    def test_falha_transitoria_continua(self, rec, env):
        self._seed(env.db, "u1", "u2", "u3")
        env.clf.llm_client.summarize_single.side_effect = lambda article: _summary_failed(
            "ThrottlingException: Rate exceeded"
        )

        stats = _run_summary(rec, ["u1", "u2", "u3"])

        assert stats["summary_failed"] == 3
        assert stats["model_unavailable"] is False
        assert _news_updates(env.db) == []

    def test_modelo_indisponivel_aborta(self, rec, env):
        self._seed(env.db, "u1", "u2", "u3")
        env.clf.llm_client.summarize_single.side_effect = lambda article: _summary_failed(EOL_ERROR)

        stats = _run_summary(rec, ["u1", "u2", "u3"])

        assert stats["model_unavailable"] is True
        assert env.clf.llm_client.summarize_single.call_count == 1
        assert _news_updates(env.db) == []

    def test_excecao_no_resumo_nao_derruba_o_run(self, rec, env):
        self._seed(env.db, "u1", "u2")
        env.clf.llm_client.summarize_single.side_effect = [
            RuntimeError("boom"),
            _summary_ok("u2"),
        ]

        stats = _run_summary(rec, ["u1", "u2"])

        assert stats["error"] == 1
        assert stats["ok"] == 1
        assert env.db.news["u1"]["summary"] is None

    def test_artigo_ausente(self, rec, env, monkeypatch):
        monkeypatch.setattr(handler, "fetch_article", lambda uid: None)

        stats = _run_summary(rec, ["u1"])

        assert stats["missing"] == 1
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_para_antes_de_processar_quando_budget_esgotado(self, rec, env):
        self._seed(env.db, "u1", "u2")
        env.db.ledger[HAIKU45] = {"input_tokens": 800, "output_tokens": 0}

        stats = _run_summary(rec, ["u1", "u2"], daily_quota=1000, quota_fraction=0.8)

        assert stats["budget_exhausted"] is True
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_para_no_meio_quando_estoura(self, rec, env):
        uids = [f"u{i}" for i in range(8)]
        self._seed(env.db, *uids)
        quota = int(5 * SUMMARY_TOKENS / 0.8)

        stats = _run_summary(rec, uids, daily_quota=quota, quota_fraction=0.8)

        assert stats["budget_exhausted"] is True
        assert env.clf.llm_client.summarize_single.call_count == 5

    def test_concorrente_para_entre_lotes(self, rec, env):
        uids = [f"u{i}" for i in range(12)]
        self._seed(env.db, *uids)
        quota = int(5 * SUMMARY_TOKENS / 0.8)

        stats = _run_summary(rec, uids, daily_quota=quota, quota_fraction=0.8, workers=2)

        assert stats["budget_exhausted"] is True
        assert env.clf.llm_client.summarize_single.call_count == 5


class TestMainNullSummary:
    def _seed(self, db):
        db.seed_news("u1", "2026-06-15", most_specific_theme_id=15)
        db.seed_news("u2", "2026-10-01", most_specific_theme_id=15)
        db.seed_news("sem-tema", "2026-09-01")
        db.seed_news("com-resumo", "2026-09-02", most_specific_theme_id=15, summary="Ok.")

    def test_dry_run_nao_chama_bedrock_nem_escreve(self, rec, env, capsys):
        self._seed(env.db)

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW, "--dry-run"])

        assert code == 0
        out = capsys.readouterr().out
        assert "u1" in out and "u2" in out and "com-resumo" not in out
        env.clf.llm_client.summarize_single.assert_not_called()
        env.clf.classify_single.assert_not_called()
        assert _news_updates(env.db) == []
        assert env.db.features_upserts == []
        assert env.db.ledger == {}
        env.publish.assert_not_called()

    def test_execucao_completa(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code == 0
        assert env.db.news["u1"]["summary"] == "Resumo enxuto de u1."
        assert env.db.news["u2"]["summary"] == "Resumo enxuto de u2."
        assert env.db.news["com-resumo"]["summary"] == "Ok."
        assert env.db.news["sem-tema"]["summary"] is None
        env.clf.classify_single.assert_not_called()
        env.clf.llm_client.extract_entities.assert_not_called()
        assert env.updates == []
        assert env.db.features_upserts == []
        env.publish.assert_not_called()

    def test_reporta_sem_sentimento_sem_gerar(self, rec, env, capsys):
        self._seed(env.db)
        env.db.news_features["u1"] = {"sentiment": {"label": "neutral", "score": 0.0}}
        env.db.news_features["u2"] = {"entities": []}  # sem sentimento

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code == 0
        final = capsys.readouterr().out.split("FIM:")[-1]
        assert "sem_sentimento=1" in final
        assert env.db.features_upserts == []  # o sentimento NÃO é gerado aqui
        assert env.db.news_features["u2"] == {"entities": []}

    def test_reporta_com_embedding_sem_tocar_no_embedding(self, rec, env, capsys):
        # u1 já tem embedding, feito sem o resumo (a partir do content). O B3 só pega
        # content_embedding IS NULL e não o refaria: o operador precisa ver quantos são.
        self._seed(env.db)
        env.db.seed_news("u1", "2026-06-15", most_specific_theme_id=15, content_embedding=[0.1])

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code == 0
        selecao, final = capsys.readouterr().out.split("FIM:")
        assert "com_embedding=1 dos 2 selecionados" in selecao
        assert "com_embedding=1 dos 2 selecionados" in final
        assert env.db.news["u1"]["summary"] == "Resumo enxuto de u1."
        assert env.db.news["u1"]["content_embedding"] == [0.1]  # embedding intacto
        assert env.db.news["u2"]["content_embedding"] is None
        assert all("content_embedding" not in sql for sql, _ in _news_updates(env.db))

    def test_dry_run_reporta_com_embedding(self, rec, env, capsys):
        self._seed(env.db)
        env.db.seed_news("u2", "2026-10-01", most_specific_theme_id=15, content_embedding=[0.2])

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW, "--dry-run"])

        assert code == 0
        assert "com_embedding=1 dos 2 selecionados" in capsys.readouterr().out
        assert _news_updates(env.db) == []
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_null_theme_nao_reporta_com_embedding(self, rec, env, capsys):
        env.db.seed_news("t1", "2026-09-30", content_embedding=[0.3])

        code = rec.main(["--select", "null-theme", *B2_WINDOW, "--dry-run"])

        assert code == 0
        assert "com_embedding" not in capsys.readouterr().out

    def test_aborta_sem_enrichment_model_id(self, rec, env, monkeypatch):
        self._seed(env.db)
        monkeypatch.delenv("ENRICHMENT_MODEL_ID")
        monkeypatch.setenv("BEDROCK_MODEL_ID", HAIKU45)  # o legado NÃO serve

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code != 0
        assert env.db.log == []  # nem consultou o banco
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_aborta_se_classificador_usa_outro_modelo(self, rec, env):
        self._seed(env.db)
        env.clf.llm_client.model_id = "anthropic.claude-3-haiku-20240307-v1:0"

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code != 0
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_exige_date_to(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "null-summary", "--date-from", "2026-06-01"])

        assert code != 0
        assert env.db.log == []
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_date_to_nao_passa_de_hoje_brt(self, rec, env):
        self._seed(env.db)

        code = rec.main(
            ["--select", "null-summary", "--date-from", "2026-06-01", "--date-to", "2026-10-09"]
        )

        assert code != 0
        assert env.db.log == []
        env.clf.llm_client.summarize_single.assert_not_called()

    def test_modelo_indisponivel_sai_com_erro(self, rec, env):
        self._seed(env.db)
        env.clf.llm_client.summarize_single.side_effect = lambda article: _summary_failed(EOL_ERROR)

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code != 0
        assert env.db.news["u2"]["summary"] is None

    def test_cota_lida_da_env(self, rec, env, monkeypatch):
        self._seed(env.db)
        monkeypatch.setenv("BEDROCK_DAILY_TOKEN_QUOTA", f'{{"{HAIKU45}": 1000}}')
        env.db.ledger[HAIKU45] = {"input_tokens": 900, "output_tokens": 0}

        code = rec.main(["--select", "null-summary", *SUMMARY_WINDOW])

        assert code == 0  # budget esgotado é parada graciosa (resumível)
        env.clf.llm_client.summarize_single.assert_not_called()
