"""
Testes do governador de cota (quota_governor): ledger llm_daily_usage,
contabilidade de tokens, decisão de budget e parsing de config por env.

DB simulado via FakeLedgerDB; nenhuma chamada real.
"""

import logging

import pytest

from news_enrichment import quota_governor as Q


# ---------------------------------------------------------------------- #
# Fake DB que entende apenas o SQL do ledger llm_daily_usage             #
# ---------------------------------------------------------------------- #


class FakeLedgerCursor:
    def __init__(self, db, conn):
        self.db = db
        self.conn = conn
        self.connection = conn
        self._result = []
        self.description = None

    def execute(self, sql, params=None):
        params = params or ()
        s = " ".join(sql.split())
        low = s.lower()
        self.db.log.append((s, params))
        self._result = []

        if self.db.fail_on_execute:
            raise Exception("db down")

        # UPSERT no ledger
        if "insert into llm_daily_usage" in low:
            model_id, in_tok, out_tok = params[0], params[1], params[2]
            row = self.db.ledger.setdefault(
                model_id, {"input_tokens": 0, "output_tokens": 0}
            )
            row["input_tokens"] += in_tok
            row["output_tokens"] += out_tok
            return

        # SUM(input+output) WHERE day=CURRENT_DATE AND model_id=%s
        if "from llm_daily_usage" in low and "sum" in low:
            model_id = params[0]
            row = self.db.ledger.get(model_id)
            if row is None:
                self._result = [(None,)]
            else:
                self._result = [(row["input_tokens"] + row["output_tokens"],)]
            return

        return

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class FakeLedgerConn:
    def __init__(self, db):
        self.db = db
        self.committed = 0
        self.rolled_back = 0

    def cursor(self):
        return FakeLedgerCursor(self.db, self)

    def commit(self):
        if self.db.fail_on_commit:
            raise Exception("commit down")
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass


class FakeLedgerDB:
    def __init__(self):
        self.ledger = {}  # model_id -> {input_tokens, output_tokens}
        self.log = []
        self.fail_on_execute = False
        self.fail_on_commit = False

    def conn(self):
        return FakeLedgerConn(self)


# ---------------------------------------------------------------------- #
# record_usage                                                           #
# ---------------------------------------------------------------------- #


class TestRecordUsage:
    def test_upsert_accumulates(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 100, 50)
        Q.record_usage(conn, "sonnet", 30, 20)
        assert db.ledger["sonnet"] == {"input_tokens": 130, "output_tokens": 70}
        assert conn.committed == 2

    def test_distinct_models_independent(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 100, 50)
        Q.record_usage(conn, "haiku", 5, 5)
        assert db.ledger["sonnet"]["input_tokens"] == 100
        assert db.ledger["haiku"]["input_tokens"] == 5

    def test_uses_current_date_and_atomic_upsert(self):
        """O SQL deve usar CURRENT_DATE e ON CONFLICT ... += EXCLUDED (atômico)."""
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 1, 1)
        sql = [s for (s, _p) in db.log if "insert into llm_daily_usage" in s.lower()][0]
        low = sql.lower()
        assert "current_date" in low
        assert "on conflict (day, model_id) do update" in low
        assert "llm_daily_usage.input_tokens + excluded.input_tokens" in low
        assert "llm_daily_usage.output_tokens + excluded.output_tokens" in low

    def test_db_failure_does_not_raise(self, caplog):
        """record_usage é resiliente: erro de DB loga e NÃO levanta."""
        db = FakeLedgerDB()
        db.fail_on_execute = True
        conn = db.conn()
        with caplog.at_level(logging.WARNING):
            Q.record_usage(conn, "sonnet", 100, 50)  # não deve levantar
        assert conn.rolled_back >= 1

    def test_commit_failure_does_not_raise(self):
        db = FakeLedgerDB()
        db.fail_on_commit = True
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 100, 50)  # não deve levantar

    def test_none_tokens_coerced_to_zero(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", None, None)
        assert db.ledger["sonnet"] == {"input_tokens": 0, "output_tokens": 0}


# ---------------------------------------------------------------------- #
# tokens_used_today                                                      #
# ---------------------------------------------------------------------- #


class TestTokensUsedToday:
    def test_sum_input_plus_output(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 100, 50)
        assert Q.tokens_used_today(conn, "sonnet") == 150

    def test_zero_when_no_rows(self):
        db = FakeLedgerDB()
        conn = db.conn()
        assert Q.tokens_used_today(conn, "sonnet") == 0

    def test_db_failure_returns_zero(self):
        """Falha de leitura → 0 (conservador: não bloqueia o pipeline por erro)."""
        db = FakeLedgerDB()
        db.fail_on_execute = True
        conn = db.conn()
        assert Q.tokens_used_today(conn, "sonnet") == 0


# ---------------------------------------------------------------------- #
# budget_exhausted                                                       #
# ---------------------------------------------------------------------- #


class TestBudgetExhausted:
    def test_under_fraction_not_exhausted(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 700, 0)  # 700 < 0.8*1000
        assert Q.budget_exhausted(conn, "sonnet", 1000, fraction=0.8) is False

    def test_at_fraction_is_exhausted(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 800, 0)  # 800 >= 0.8*1000
        assert Q.budget_exhausted(conn, "sonnet", 1000, fraction=0.8) is True

    def test_over_fraction_is_exhausted(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 900, 100)
        assert Q.budget_exhausted(conn, "sonnet", 1000, fraction=0.8) is True

    def test_default_fraction_is_080(self):
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 800, 0)
        assert Q.budget_exhausted(conn, "sonnet", 1000) is True

    def test_no_quota_never_exhausted(self):
        """Sem cota definida (None ou <=0) → nunca bloqueia (modo sem-teto)."""
        db = FakeLedgerDB()
        conn = db.conn()
        Q.record_usage(conn, "sonnet", 10_000_000, 0)
        assert Q.budget_exhausted(conn, "sonnet", None) is False
        assert Q.budget_exhausted(conn, "sonnet", 0) is False


# ---------------------------------------------------------------------- #
# parse_daily_quota_env                                                  #
# ---------------------------------------------------------------------- #


class TestParseDailyQuotaEnv:
    def test_parses_json_and_fraction(self, monkeypatch):
        monkeypatch.setenv(
            "BEDROCK_DAILY_TOKEN_QUOTA",
            '{"us.anthropic.claude-sonnet-4-6": 5000000}',
        )
        monkeypatch.setenv("BACKFILL_QUOTA_FRACTION", "0.8")
        cfg = Q.parse_daily_quota_env()
        assert cfg["quota"]["us.anthropic.claude-sonnet-4-6"] == 5000000
        assert cfg["fraction"] == 0.8

    def test_missing_env_defaults(self, monkeypatch):
        monkeypatch.delenv("BEDROCK_DAILY_TOKEN_QUOTA", raising=False)
        monkeypatch.delenv("BACKFILL_QUOTA_FRACTION", raising=False)
        cfg = Q.parse_daily_quota_env()
        assert cfg["quota"] == {}
        assert cfg["fraction"] == 0.8  # default

    def test_malformed_json_yields_empty_quota(self, monkeypatch):
        monkeypatch.setenv("BEDROCK_DAILY_TOKEN_QUOTA", "not json {")
        cfg = Q.parse_daily_quota_env()
        assert cfg["quota"] == {}

    def test_malformed_fraction_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("BACKFILL_QUOTA_FRACTION", "abc")
        cfg = Q.parse_daily_quota_env()
        assert cfg["fraction"] == 0.8

    def test_quota_for_helper(self, monkeypatch):
        monkeypatch.setenv(
            "BEDROCK_DAILY_TOKEN_QUOTA", '{"sonnet": 100, "haiku": 200}'
        )
        cfg = Q.parse_daily_quota_env()
        assert cfg["quota"].get("sonnet") == 100
        assert cfg["quota"].get("missing") is None


def test_record_usage_with_none_conn_is_noop():
    """Defensivo: conn None não deve levantar."""
    Q.record_usage(None, "sonnet", 1, 1)
