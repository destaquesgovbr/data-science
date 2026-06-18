"""
Testes do driver de backfill NER do acervo (scripts/backfill_ner_corpus.py).

Cobre: SELECT resumível (NOT EXISTS sobre news_llm_raw), ordem configurável,
e integração do governador de cota (record_usage + budget_exhausted). Bedrock
e DB mockados; nenhuma chamada real.
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Carrega o script (não é um módulo do pacote) por caminho.
_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "backfill_ner_corpus.py"
)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
_spec = importlib.util.spec_from_file_location("backfill_ner_corpus", _SCRIPT)
bnc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bnc)


# ---------------------------------------------------------------------- #
# SELECT resumível: NOT EXISTS sobre news_llm_raw                        #
# ---------------------------------------------------------------------- #


class TestSelectSql:
    def test_select_uses_not_exists_on_ner_raw(self):
        sql = bnc.build_select_sql(order="asc")
        low = " ".join(sql.split()).lower()
        assert "from news n" in low
        assert "not exists" in low
        assert "news_llm_raw" in low
        assert "task = 'ner'" in low or "task='ner'" in low
        assert "prompt_version" in low
        assert "order by n.published_at asc" in low

    def test_order_desc(self):
        sql = bnc.build_select_sql(order="desc")
        assert "DESC" in sql

    def test_default_order_is_asc_oldest_first(self):
        # O default do CLI é asc (oldest-first) — cobre o acervo histórico.
        args = bnc.build_arg_parser().parse_args([])
        assert args.order == "asc"

    def test_does_not_require_existing_features(self):
        """Cobre os ~314k SEM NER: NÃO exige nf.features ? 'entities'."""
        sql = bnc.build_select_sql(order="asc").lower()
        assert "features ? 'entities'" not in sql


# ---------------------------------------------------------------------- #
# Governador wired no driver                                             #
# ---------------------------------------------------------------------- #


class TestGovernorIntegration:
    @patch.object(bnc, "_get_conn")
    @patch.object(bnc, "budget_exhausted")
    def test_stops_when_budget_exhausted_before_processing(
        self, mock_budget, mock_conn
    ):
        mock_budget.return_value = True
        mock_conn.return_value = MagicMock()
        stats = bnc.run_backfill(
            uids=["u1", "u2", "u3"],
            model_id="sonnet",
            daily_quota=1000,
            quota_fraction=0.8,
            workers=1,
            dry_run=False,
        )
        assert stats["budget_exhausted"] is True
        assert stats.get("ok", 0) == 0

    @patch.object(bnc, "_record_usage_for")
    @patch.object(bnc, "process_one")
    @patch.object(bnc, "_get_conn")
    @patch.object(bnc, "budget_exhausted", return_value=False)
    def test_records_usage_after_each_call(
        self, mock_budget, mock_conn, mock_process, mock_record
    ):
        mock_conn.return_value = MagicMock()
        # process_one devolve (uid, status, usage)
        mock_process.side_effect = [
            ("u1", "ok:2ent", {"input_tokens": 100, "output_tokens": 10}),
            ("u2", "ok:1ent", {"input_tokens": 50, "output_tokens": 5}),
        ]
        stats = bnc.run_backfill(
            uids=["u1", "u2"],
            model_id="sonnet",
            daily_quota=None,  # sem-teto
            quota_fraction=0.8,
            workers=1,
            dry_run=False,
        )
        assert stats["ok"] == 2
        # Gravou usage para cada chamada.
        assert mock_record.call_count == 2

    @patch.object(bnc, "_record_usage_for")
    @patch.object(bnc, "process_one")
    @patch.object(bnc, "_get_conn")
    @patch.object(bnc, "budget_exhausted", return_value=False)
    def test_no_quota_runs_all(
        self, mock_budget, mock_conn, mock_process, mock_record
    ):
        mock_conn.return_value = MagicMock()
        mock_process.side_effect = [
            ("u1", "ok:1ent", {"input_tokens": 1, "output_tokens": 1}),
            ("u2", "ner_failed", {"input_tokens": 0, "output_tokens": 0}),
        ]
        stats = bnc.run_backfill(
            uids=["u1", "u2"], model_id="sonnet", daily_quota=None,
            quota_fraction=0.8, workers=1, dry_run=False,
        )
        assert stats["ok"] == 1
        assert stats["ner_failed"] == 1
        assert stats["budget_exhausted"] is False


def test_process_one_returns_usage_tuple():
    """process_one extrai entities, raw e usage; dry-run não escreve."""
    article = {"unique_id": "u1", "title": "t", "content": "c"}
    ner_raw = {
        "model_id": "sonnet", "prompt_version": "ner-v1", "prompt_hash": "h",
        "raw_response": {"entities": []},
        "usage": {"input_tokens": 77, "output_tokens": 7},
    }
    with patch.object(bnc.handler, "fetch_article", return_value=article), \
         patch.object(bnc.handler, "_get_classifier") as mock_clf:
        mock_clf.return_value.llm_client.extract_entities.return_value = (
            [{"text": "Finep", "type": "ORG"}], ner_raw,
        )
        uid, status, usage = bnc.process_one("u1", dry_run=True)
        assert uid == "u1"
        assert usage == {"input_tokens": 77, "output_tokens": 7}
        assert status.startswith("dry")
