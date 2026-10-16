"""
Testes do script de avaliação offline de modelos NER (scripts/eval_ner_models.py).

Só as partes puras e o laço de execução com Bedrock mockado: chaves de
entidade, P/R/F1, recall por salience, matriz de tipos, cobertura de alias,
custo por modelo, conferência de prompt_hash, sorteio estratificado,
SpendLedger (teto rígido), retomada e portões G1–G6. Nenhuma chamada real,
nenhum banco.
"""

import hashlib
import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "eval_ner_models.py")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
_spec = importlib.util.spec_from_file_location("eval_ner_models", _SCRIPT)
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def E(text, typ, forma=None, sal=None, count=1):
    return {
        "text": text,
        "type": typ,
        "forma_canonica": forma or text,
        "salience": sal,
        "count": count,
    }


ARTICLE = {
    "unique_id": "mec-1",
    "title": "Título",
    "subtitle": None,
    "editorial_lead": "Lead",
    "content": "Conteúdo " * 10,
}


# --------------------------------------------------------------------------- #
# Chaves e métricas                                                           #
# --------------------------------------------------------------------------- #


class TestEntityKeys:
    def test_strict_uses_normalized_forma_canonica_and_type(self):
        ents = [E("MEC", "ORG", forma="Ministério da Educação")]
        assert ev.entity_keys(ents, "strict") == {("ministerio da educacao", "ORG")}

    def test_loose_is_name_only(self):
        ents = [E("MEC", "ORG", forma="Ministério da Educação"), E("Brasil", "LOC")]
        assert ev.entity_keys(ents, "loose") == {"ministerio da educacao", "brasil"}

    def test_falls_back_to_text_and_dedupes(self):
        ents = [
            {"text": "Pix", "type": "PRODUCT", "forma_canonica": None},
            {"text": "PIX", "type": "PRODUCT"},
        ]
        assert ev.entity_keys(ents, "strict") == {("pix", "PRODUCT")}

    def test_empty_names_skipped(self):
        assert ev.entity_keys([{"text": "", "type": "ORG"}], "strict") == set()

    def test_bad_mode(self):
        with pytest.raises(ValueError):
            ev.entity_keys([], "fuzzy")


class TestPrf:
    def test_counts(self):
        assert ev.prf_counts({1, 2, 3}, {2, 3, 4, 5}) == (2, 2, 1)

    def test_f1_values(self):
        p, r, f1 = ev.f1_from_counts(2, 2, 1)
        assert p == pytest.approx(0.5)
        assert r == pytest.approx(2 / 3)
        assert f1 == pytest.approx(2 * 0.5 * (2 / 3) / (0.5 + 2 / 3))

    def test_both_empty_is_perfect(self):
        assert ev.f1_from_counts(0, 0, 0) == (1.0, 1.0, 1.0)

    def test_no_prediction_is_zero(self):
        p, r, f1 = ev.f1_from_counts(0, 0, 3)
        assert (r, f1) == (0.0, 0.0)


class TestSalienceRecall:
    def test_only_salient_ref_entities_count(self):
        ref = [E("Bolsa Família", "POLICY", sal=0.9), E("Brasil", "LOC", sal=0.3), E("MEC", "ORG")]
        cand = [E("Bolsa Familia", "ORG", sal=0.1)]  # tipo diferente: só o nome conta
        assert ev.salience_recall(ref, cand, 0.7) == (1, 1)

    def test_miss(self):
        ref = [E("Bolsa Família", "POLICY", sal=0.7), E("Finep", "ORG", sal=0.8)]
        assert ev.salience_recall(ref, [E("Finep", "ORG")], 0.7) == (1, 2)


class TestTypeConfusion:
    def test_pairs_by_name(self):
        ref = [E("Plano Safra", "WORK"), E("Brasil", "LOC"), E("Finep", "ORG")]
        cand = [E("Plano Safra", "POLICY"), E("Brasil", "LOC")]
        conf = ev.type_confusion(ref, cand)
        assert conf[("WORK", "POLICY")] == 1
        assert conf[("LOC", "LOC")] == 1
        assert sum(conf.values()) == 2


class TestAliasCoverage:
    def test_hits_over_strict_keys(self):
        alias = {("brasil", "LOC"), ("finep", "ORG")}
        ents = [E("Brasil", "LOC"), E("Finep", "PER"), E("Novo", "ORG"), E("BRASIL", "LOC")]
        assert ev.alias_coverage(ents, alias) == (1, 3)


# --------------------------------------------------------------------------- #
# Custo                                                                       #
# --------------------------------------------------------------------------- #


class TestCost:
    @pytest.mark.parametrize(
        "model_id,expected",
        [
            ("us.anthropic.claude-sonnet-4-6", 3.0 + 15.0),
            ("us.anthropic.claude-sonnet-5-5", 2.0 + 10.0),
            ("us.anthropic.claude-haiku-5-5", 0.10 + 0.50),
            ("us.anthropic.claude-haiku-4-5-20251001-v1:0", 1.0 + 5.0),
        ],
    )
    def test_price_per_million(self, model_id, expected):
        # 100K de entrada (limite da tarifa curta do Haiku 5.5) e 100K de saída
        usage = {"input_tokens": 100_000, "output_tokens": 100_000}
        assert ev.cost_usd(model_id, usage) == pytest.approx(expected / 10)

    def test_haiku55_long_prompt_rate(self):
        usage = {"input_tokens": 200_000, "output_tokens": 0}
        assert ev.cost_usd("us.anthropic.claude-haiku-5-5", usage) == pytest.approx(0.10)

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError):
            ev.cost_usd("us.anthropic.claude-opus-5-5", {"input_tokens": 1, "output_tokens": 1})

    def test_estimate_is_upper_bound_on_output(self):
        est = ev.estimate_cost("us.anthropic.claude-sonnet-5-5", "x" * 3000, 4000)
        # entrada estimada ≥ 1 token por 2 caracteres; saída = max_tokens inteiro
        assert est >= (1500 * 2.0 + 4000 * 10.0) / 1e6


# --------------------------------------------------------------------------- #
# prompt_hash, export e amostra                                               #
# --------------------------------------------------------------------------- #


class TestPromptHash:
    def test_matches_production_prompt(self):
        prompt = ev.build_prompt(ARTICLE)
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        assert ev.prompt_hash_ok(ARTICLE, h)
        assert not ev.prompt_hash_ok(dict(ARTICLE, content="outro"), h)


class TestParseRawExport:
    def test_parses_json_lines(self, tmp_path):
        p = tmp_path / "x.out"
        p.write_text('{"a": 1}\n\n{"a": 2}\n')
        rows, bad = ev.parse_raw_export(str(p))
        assert rows == [{"a": 1}, {"a": 2}]
        assert bad == []

    def test_psql_error_aborts(self, tmp_path):
        p = tmp_path / "x.out"
        p.write_text('{"a": 1}\npsql:<stdin>:3: ERROR:  boom\n')
        with pytest.raises(RuntimeError):
            ev.parse_raw_export(str(p))

    def test_non_json_reported(self, tmp_path):
        p = tmp_path / "x.out"
        p.write_text('{"a": 1}\nlixo\n')
        rows, bad = ev.parse_raw_export(str(p))
        assert rows == [{"a": 1}]
        assert bad == ["lixo"]


class TestRefEntities:
    def test_parsed_object(self):
        raw = {"entities": [{"text": "Finep", "type": "org", "count": 2}]}
        ents = ev.ref_entities(raw)
        assert [(e["text"], e["type"]) for e in ents] == [("Finep", "ORG")]

    def test_raw_text_fallback(self):
        raw = {"raw_text": 'Aqui: ```json {"entities": [{"text": "Pix", "type": "PRODUCT"}]} ```'}
        assert [e["text"] for e in ev.ref_entities(raw)] == ["Pix"]

    def test_none(self):
        assert ev.ref_entities(None) == []


class TestStratifiedTake:
    def _rows(self):
        rows = []
        for y in ("2023", "2024"):
            for tam in ("P", "M", "G"):
                for i in range(5):
                    rows.append(
                        {"unique_id": f"{y}{tam}{i}", "y": y, "tam": tam, "h": f"{i:02d}{tam}"}
                    )
        return rows

    def test_even_split_per_size(self):
        out = ev.stratified_take(self._rows(), {"2023": 6, "2024": 3})
        got = sorted((r["y"], r["tam"]) for r in out)
        assert got.count(("2023", "P")) == 2 and got.count(("2023", "G")) == 2
        assert sum(1 for r in out if r["y"] == "2024") == 3
        assert {r["tam"] for r in out if r["y"] == "2024"} == {"P", "M", "G"}

    def test_takes_lowest_hash_first(self):
        out = ev.stratified_take(self._rows(), {"2023": 3})
        assert sorted(r["unique_id"] for r in out) == ["2023G0", "2023M0", "2023P0"]

    def test_shortfall_filled_from_other_sizes(self):
        rows = [r for r in self._rows() if not (r["y"] == "2023" and r["tam"] == "G")]
        out = ev.stratified_take(rows, {"2023": 9})
        assert len(out) == 9
        assert all(r["y"] == "2023" for r in out)

    def test_deterministic(self):
        a = ev.stratified_take(self._rows(), {"2023": 7, "2024": 4})
        b = ev.stratified_take(list(reversed(self._rows())), {"2023": 7, "2024": 4})
        assert [r["unique_id"] for r in a] == [r["unique_id"] for r in b]

    def test_parse_quota(self):
        assert ev.parse_quota("2023=80,2024=40") == {"2023": 80, "2024": 40}


# --------------------------------------------------------------------------- #
# SpendLedger                                                                 #
# --------------------------------------------------------------------------- #


class TestSpendLedger:
    def test_reserve_commit_and_persist(self, tmp_path):
        path = str(tmp_path / "spend.json")
        led = ev.SpendLedger(path, 1.0)
        r = led.reserve(0.3)
        led.commit(r, 0.1, "h55", {"input_tokens": 10, "output_tokens": 5})
        assert led.spent == pytest.approx(0.1)
        again = ev.SpendLedger(path, 1.0)
        assert again.spent == pytest.approx(0.1)
        data = json.loads(open(path).read())
        assert data["by_arm"]["h55"]["calls"] == 1
        assert data["by_arm"]["h55"]["output_tokens"] == 5

    def test_reservation_blocks_overshoot(self, tmp_path):
        led = ev.SpendLedger(str(tmp_path / "s.json"), 1.0)
        led.reserve(0.6)
        with pytest.raises(ev.BudgetExceeded):
            led.reserve(0.5)  # 0,6 pendente + 0,5 > 1,0

    def test_spent_counts_after_reload(self, tmp_path):
        path = str(tmp_path / "s.json")
        led = ev.SpendLedger(path, 1.0)
        led.commit(led.reserve(0.9), 0.9, "x", {})
        led2 = ev.SpendLedger(path, 1.0)
        with pytest.raises(ev.BudgetExceeded):
            led2.reserve(0.2)

    def test_failed_call_releases_reservation(self, tmp_path):
        led = ev.SpendLedger(str(tmp_path / "s.json"), 1.0)
        led.commit(led.reserve(0.9), 0.0, "x", {})
        led.reserve(0.9)  # liberado: não estoura

    def test_budget_cannot_grow_on_reload(self, tmp_path):
        path = str(tmp_path / "s.json")
        ev.SpendLedger(path, 1.0)
        with pytest.raises(ValueError):
            ev.SpendLedger(path, 5.0)


# --------------------------------------------------------------------------- #
# Execução de um braço (Bedrock mockado) e retomada                           #
# --------------------------------------------------------------------------- #


def _mock_client(model_id, payloads):
    client = ev.make_parser_client(model_id)
    client.client = MagicMock()
    seq = []
    for p in payloads:
        if isinstance(p, Exception):
            seq.append(p)
        else:
            body = MagicMock()
            body.read.return_value = json.dumps(p).encode()
            seq.append({"body": body})
    client.client.invoke_model.side_effect = seq
    return client


def _throttle():
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Too many requests"}}, "InvokeModel"
    )


class TestCallOne:
    ARM = ev.ARMS["h55_ad_low"]

    def test_ok_record(self, tmp_path):
        text = json.dumps({"entities": [{"text": "Finep", "type": "ORG"}]})
        payload = {
            "content": [
                {"type": "thinking", "thinking": "", "signature": "s"},
                {"type": "text", "text": text},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 2000, "output_tokens": 300},
        }
        client = _mock_client("us.anthropic.claude-haiku-5-5", [payload])
        led = ev.SpendLedger(str(tmp_path / "s.json"), 1.0)
        rec = ev.call_one(client, "h55_ad_low", self.ARM, ARTICLE, led, sleep=lambda *_: None)
        assert rec["status"] == "ok"
        assert rec["block_types"] == ["thinking", "text"]
        assert [e["text"] for e in rec["entities"]] == ["Finep"]
        assert rec["json_puro"] is True and rec["json_extraivel"] is True
        assert rec["cost_usd"] == pytest.approx((2000 * 0.10 + 300 * 0.50) / 1e6)
        assert led.spent == pytest.approx(rec["cost_usd"])
        sent = json.loads(client.client.invoke_model.call_args.kwargs["body"])
        assert "temperature" not in sent and sent["output_config"] == {"effort": "low"}

    def test_markdown_is_extractable_not_pure(self, tmp_path):
        text = '```json\n{"entities": []}\n```'
        payload = {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {},
        }
        client = _mock_client("us.anthropic.claude-haiku-5-5", [payload])
        rec = ev.call_one(
            client, "h55_ad_low", self.ARM, ARTICLE, ev.SpendLedger(str(tmp_path / "s"), 1.0)
        )
        assert rec["json_puro"] is False and rec["json_extraivel"] is True

    def test_refusal_record(self, tmp_path):
        payload = {
            "content": [],
            "stop_reason": "refusal",
            "stop_details": {"category": "bio"},
            "usage": {"input_tokens": 100, "output_tokens": 1},
        }
        client = _mock_client("us.anthropic.claude-haiku-5-5", [payload])
        rec = ev.call_one(
            client, "h55_ad_low", self.ARM, ARTICLE, ev.SpendLedger(str(tmp_path / "s"), 1.0)
        )
        assert rec["status"] == "refusal"
        assert rec["refusal_category"] == "bio"
        assert rec["entities"] == []
        assert client.client.invoke_model.call_count == 1

    def test_no_text_record(self, tmp_path):
        payload = {
            "content": [{"type": "thinking", "thinking": "", "signature": "s"}],
            "stop_reason": "max_tokens",
            "usage": {"input_tokens": 100, "output_tokens": 8000},
        }
        client = _mock_client("us.anthropic.claude-haiku-5-5", [payload])
        rec = ev.call_one(
            client, "h55_ad_low", self.ARM, ARTICLE, ev.SpendLedger(str(tmp_path / "s"), 1.0)
        )
        assert rec["status"] == "no_text"
        assert rec["stop_reason"] == "max_tokens"
        assert rec["cost_usd"] > 0

    def test_throttling_retried_once(self, tmp_path):
        ok = {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}}
        client = _mock_client("us.anthropic.claude-haiku-5-5", [_throttle(), ok])
        rec = ev.call_one(
            client,
            "h55_ad_low",
            self.ARM,
            ARTICLE,
            ev.SpendLedger(str(tmp_path / "s"), 1.0),
            sleep=lambda *_: None,
        )
        assert rec["status"] == "ok" and rec["attempts"] == 2

    def test_throttling_twice_is_error(self, tmp_path):
        client = _mock_client("us.anthropic.claude-haiku-5-5", [_throttle(), _throttle()])
        led = ev.SpendLedger(str(tmp_path / "s"), 1.0)
        rec = ev.call_one(client, "h55_ad_low", self.ARM, ARTICLE, led, sleep=lambda *_: None)
        assert rec["status"] == "api_error"
        assert rec["error"].startswith("ThrottlingException")
        assert led.spent == 0.0

    def test_validation_not_retried(self, tmp_path):
        err = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "bad"}}, "InvokeModel"
        )
        client = _mock_client("us.anthropic.claude-haiku-5-5", [err])
        rec = ev.call_one(
            client, "h55_ad_low", self.ARM, ARTICLE, ev.SpendLedger(str(tmp_path / "s"), 1.0)
        )
        assert rec["status"] == "api_error"
        assert client.client.invoke_model.call_count == 1

    def test_s46_sends_legacy_body(self, tmp_path):
        ok = {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {}}
        client = _mock_client("us.anthropic.claude-sonnet-4-6", [ok])
        ev.call_one(
            client, "s46", ev.ARMS["s46"], ARTICLE, ev.SpendLedger(str(tmp_path / "s"), 1.0)
        )
        sent = client.client.invoke_model.call_args.kwargs["body"]
        assert sent == json.dumps(
            ev.build_request_for(
                "us.anthropic.claude-sonnet-4-6", ev.ARMS["s46"], ev.build_prompt(ARTICLE)
            )
        )
        assert json.loads(sent)["temperature"] == 0.0


class TestArmModelCheck:
    def test_family_mismatch(self):
        with pytest.raises(ValueError):
            ev.check_arm_model("h55_ad_low", "us.anthropic.claude-sonnet-5-5")
        with pytest.raises(ValueError):
            ev.check_arm_model("s46", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

    def test_ok(self):
        ev.check_arm_model("s55_bt_low", "us.anthropic.claude-sonnet-5-5")
        ev.check_arm_model("s46", "us.anthropic.claude-sonnet-4-6")


class TestProductionDefaultMatchesEvaluatedArm:
    """O default de produção é exatamente o corpo que foi avaliado."""

    @pytest.mark.parametrize(
        "model_id",
        ["us.anthropic.claude-haiku-5-5", "global.anthropic.claude-haiku-5-5"],
    )
    def test_haiku_55_default_is_h55_off_low(self, model_id):
        prompt = ev.build_prompt(ARTICLE)
        assert json.dumps(ev.build_ner_request_body(model_id, prompt)) == json.dumps(
            ev.build_request_for(model_id, ev.ARMS["h55_off_low"], prompt)
        )

    def test_sonnet_55_default_is_s55_bt_low(self):
        prompt = ev.build_prompt(ARTICLE)
        mid = "us.anthropic.claude-sonnet-5-5"
        assert json.dumps(ev.build_ner_request_body(mid, prompt)) == json.dumps(
            ev.build_request_for(mid, ev.ARMS["s55_bt_low"], prompt)
        )


class TestResume:
    def test_done_uids_only_final_statuses(self, tmp_path):
        p = tmp_path / "r.jsonl"
        lines = [
            {"uid": "a", "status": "ok"},
            {"uid": "b", "status": "api_error"},
            {"uid": "c", "status": "refusal"},
            {"uid": "d", "status": "no_text"},
        ]
        p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        assert ev.done_uids(str(p)) == {"a", "c", "d"}

    def test_done_uids_missing_file(self, tmp_path):
        assert ev.done_uids(str(tmp_path / "nada.jsonl")) == set()

    def test_last_record_wins(self, tmp_path):
        p = tmp_path / "r.jsonl"
        p.write_text(
            json.dumps({"uid": "b", "status": "api_error"})
            + "\n"
            + json.dumps({"uid": "b", "status": "ok"})
            + "\n"
        )
        assert ev.load_records(str(p))["b"]["status"] == "ok"

    def test_plan_targets_prefix_and_skips_done(self):
        sample = [{"unique_id": u} for u in "abcdef"]
        todo = ev.plan_targets(sample, limit=4, done={"a", "c"})
        assert [a["unique_id"] for a in todo] == ["b", "d"]

    def test_run_arm_resumes_and_respects_budget(self, tmp_path):
        sample = [dict(ARTICLE, unique_id=f"u{i}") for i in range(5)]
        ok = {
            "content": [{"type": "text", "text": "{}"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1000, "output_tokens": 100},
        }
        client = _mock_client("us.anthropic.claude-haiku-5-5", [ok] * 10)
        out = str(tmp_path / "h.jsonl")
        led = ev.SpendLedger(str(tmp_path / "s.json"), 1.0)
        s1 = ev.run_arm(client, "h55_ad_low", sample, out, led, limit=2, workers=1)
        assert s1["ok"] == 2
        s2 = ev.run_arm(client, "h55_ad_low", sample, out, led, limit=4, workers=2)
        assert s2["ok"] == 2  # só os 2 novos
        assert client.client.invoke_model.call_count == 4
        assert len(ev.load_records(out)) == 4

    def test_run_arm_stops_at_budget(self, tmp_path):
        sample = [dict(ARTICLE, unique_id=f"u{i}") for i in range(5)]
        ok = {
            "content": [{"type": "text", "text": "{}"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 2000, "output_tokens": 1000},
        }
        client = _mock_client("us.anthropic.claude-sonnet-5-5", [ok] * 10)
        # reserva por chamada (s55_bt_low, max_tokens 4000) ≈ US$0,045 e gasto real
        # US$0,014: com teto 0,05 a 2ª reserva (0,014 + 0,045) estoura → 1 chamada
        led = ev.SpendLedger(str(tmp_path / "s.json"), 0.05)
        s = ev.run_arm(
            client, "s55_bt_low", sample, str(tmp_path / "o.jsonl"), led, limit=5, workers=1
        )
        assert s["ok"] == 1
        assert s["budget_stop"] is True


# --------------------------------------------------------------------------- #
# Métricas por braço e portões                                                #
# --------------------------------------------------------------------------- #


def _sample_row(uid, y, tam, ref_ents):
    return {"unique_id": uid, "y": y, "tam": tam, "ref": {"raw_response": {"entities": ref_ents}}}


class TestArmMetrics:
    def test_metrics_basic(self):
        ref_a = [E("Finep", "ORG", sal=0.9), E("Brasil", "LOC", sal=0.2)]
        ref_b = [E("Pix", "PRODUCT", sal=0.8)]
        sample = {
            "a": _sample_row("a", "2023", "P", ref_a),
            "b": _sample_row("b", "2024", "G", ref_b),
        }
        records = {
            "a": {
                "uid": "a",
                "status": "ok",
                "entities": [E("Finep", "ORG"), E("Brasil", "ORG")],
                "json_extraivel": True,
                "json_puro": True,
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 100, "output_tokens": 10},
                "cost_usd": 0.01,
                "latency_s": 1.0,
            },
            "b": {
                "uid": "b",
                "status": "refusal",
                "entities": [],
                "json_extraivel": False,
                "json_puro": False,
                "stop_reason": "refusal",
                "usage": {},
                "cost_usd": 0.0,
                "latency_s": 0.5,
            },
        }
        m = ev.arm_metrics(sample, records, alias_set={("finep", "ORG")})
        assert m["n"] == 2
        assert m["refusals"] == 1
        assert m["json_extraivel_rate"] == pytest.approx(0.5)
        # estrito: a → tp 1 (Finep), fp 1 (Brasil/ORG), fn 1 (Brasil/LOC); b → fn 1
        assert (m["strict"]["tp"], m["strict"]["fp"], m["strict"]["fn"]) == (1, 1, 2)
        assert (m["loose"]["tp"], m["loose"]["fp"], m["loose"]["fn"]) == (2, 0, 1)
        assert m["salience_recall"] == pytest.approx(1 / 2)
        assert m["ents_per_article"] == pytest.approx(1.0)
        assert m["ref_ents_per_article"] == pytest.approx(1.5)
        assert m["alias_coverage"] == pytest.approx(1 / 2)
        assert m["by_stratum"]["y=2023"]["n"] == 1

    def test_restrict_to_uids(self):
        sample = {
            "a": _sample_row("a", "2023", "P", [E("X", "ORG")]),
            "b": _sample_row("b", "2023", "P", []),
        }
        records = {
            u: {
                "uid": u,
                "status": "ok",
                "entities": [],
                "json_extraivel": True,
                "json_puro": True,
                "stop_reason": "end_turn",
                "usage": {},
                "cost_usd": 0.0,
                "latency_s": 0.1,
            }
            for u in "ab"
        }
        m = ev.arm_metrics(sample, records, alias_set=set(), uids={"b"})
        assert m["n"] == 1


class TestGates:
    FLOOR = {"strict": {"f1": 0.80}, "salience_recall": 0.95}

    def _m(self, **kw):
        base = {
            "n": 200,
            "json_extraivel_rate": 1.0,
            "refusals": 0,
            "max_tokens": 0,
            "api_errors": 0,
            "strict": {"f1": 0.78},
            "salience_recall": 0.94,
            "by_stratum": {
                "y=2023": {"n": 80, "f1_strict": 0.75},
                "tam=P": {"n": 30, "f1_strict": 0.1},
            },
            "ents_per_article": 10.0,
            "ref_ents_per_article": 10.0,
            "alias_coverage": 0.60,
            "ref_alias_coverage": 0.62,
        }
        base.update(kw)
        return base

    def test_all_pass(self):
        g = ev.evaluate_gates(self._m(), self.FLOOR)
        assert all(g[k]["pass"] for k in ("G1", "G2", "G3", "G4", "G5", "G6"))
        assert g["pass_all"] is True

    def test_g1_refusals(self):
        assert ev.evaluate_gates(self._m(refusals=2), self.FLOOR)["G1"]["pass"] is False
        assert ev.evaluate_gates(self._m(refusals=1), self.FLOOR)["G1"]["pass"] is True

    def test_g1_json(self):
        assert (
            ev.evaluate_gates(self._m(json_extraivel_rate=0.985), self.FLOOR)["G1"]["pass"] is False
        )

    def test_g2(self):
        assert ev.evaluate_gates(self._m(strict={"f1": 0.749}), self.FLOOR)["G2"]["pass"] is False

    def test_g3(self):
        assert ev.evaluate_gates(self._m(salience_recall=0.919), self.FLOOR)["G3"]["pass"] is False

    def test_g4_only_strata_with_n_ge_40(self):
        bad = {"y=2023": {"n": 80, "f1_strict": 0.69}}
        assert ev.evaluate_gates(self._m(by_stratum=bad), self.FLOOR)["G4"]["pass"] is False

    def test_g5_ratio(self):
        assert ev.evaluate_gates(self._m(ents_per_article=7.9), self.FLOOR)["G5"]["pass"] is False
        assert ev.evaluate_gates(self._m(ents_per_article=12.6), self.FLOOR)["G5"]["pass"] is False

    def test_g6_alias(self):
        assert ev.evaluate_gates(self._m(alias_coverage=0.56), self.FLOOR)["G6"]["pass"] is False

    def test_no_floor_is_undetermined(self):
        g = ev.evaluate_gates(self._m(), None)
        assert g["G2"]["pass"] is None and g["pass_all"] is None


class TestProjection:
    def test_projection(self):
        p = ev.project(
            cost_per_article=0.001,
            tokens_per_article=3000,
            n_articles=191_500,
            quota_tokens_day=6_000_000,
            articles_day_cap=20_000,
        )
        assert p["cost_usd"] == pytest.approx(191.5)
        assert p["days_by_quota"] == pytest.approx(191_500 * 3000 / 6_000_000)
        assert p["days_by_dag_cap"] == pytest.approx(191_500 / 20_000)
        assert p["days"] == pytest.approx(max(p["days_by_quota"], p["days_by_dag_cap"]))

    def test_projection_without_quota(self):
        p = ev.project(0.001, 3000, 191_500, None, 20_000)
        assert p["days_by_quota"] is None
        assert p["days"] == pytest.approx(191_500 / 20_000)


class TestBlindReview:
    def test_key_and_markdown(self):
        items = [
            {
                "uid": f"u{i}",
                "title": f"T{i}",
                "ref": [E("A", "ORG")],
                "cand": [E("B", "ORG")],
                "f1": 0.0,
            }
            for i in range(4)
        ]
        md, key = ev.blind_review(items, "h55_ad_low", seed=1)
        assert set(key) == {"u0", "u1", "u2", "u3"}
        for k in key.values():
            assert sorted([k["A"], k["B"]]) == ["h55_ad_low", "referencia_s46"]
        assert "h55_ad_low" not in md and "referencia" not in md
        assert md.count("Lista A") == 4


# --------------------------------------------------------------------------- #
# Piso alternativo: pares históricos Sonnet 4.6 × Sonnet 4.6 (sem chamada)    #
# --------------------------------------------------------------------------- #


class TestHistoricalFloor:
    def _pair(self, alt_raw):
        return {
            "unique_id": "p1",
            "y": "2026",
            "tam": "M",
            "ref": {"prompt_hash": "h", "raw_response": {"entities": [E("Finep", "ORG", sal=0.9)]}},
            "alt": {"prompt_hash": "h", "raw_response": alt_raw},
        }

    def test_alt_record_structured(self):
        rec = ev.alt_record(self._pair({"entities": [{"text": "Finep", "type": "ORG"}]}))
        assert rec["uid"] == "p1"
        assert rec["arm"] == "s46hist"
        assert rec["status"] == "ok"
        assert rec["model_id"] == "us.anthropic.claude-sonnet-4-6"
        assert [e["text"] for e in rec["entities"]] == ["Finep"]
        assert rec["json_puro"] is True and rec["json_extraivel"] is True
        assert rec["cost_usd"] == 0.0

    def test_alt_record_raw_text(self):
        raw = {"raw_text": '```json\n{"entities": [{"text": "Pix", "type": "PRODUCT"}]}\n```'}
        rec = ev.alt_record(self._pair(raw))
        assert rec["json_puro"] is False and rec["json_extraivel"] is True
        assert [e["text"] for e in rec["entities"]] == ["Pix"]

    def test_alt_record_requires_same_hash(self):
        pair = self._pair({"entities": []})
        pair["alt"]["prompt_hash"] = "outro"
        with pytest.raises(ValueError):
            ev.alt_record(pair)

    def test_floor_pairs_metrics_against_ref(self):
        pair = self._pair({"entities": [{"text": "Finep", "type": "ORG"}]})
        rec = ev.alt_record(pair)
        m = ev.arm_metrics({"p1": pair}, {"p1": rec}, alias_set=set())
        assert m["strict"]["f1"] == pytest.approx(1.0)
        assert m["salience_recall"] == pytest.approx(1.0)

    def test_choose_floor_prefers_live(self):
        live, hist = {"n": 20}, {"n": 150}
        assert ev.choose_floor(live, hist) == (live, "s46")
        assert ev.choose_floor(None, hist) == (hist, "s46hist")
        assert ev.choose_floor({"n": 0}, hist) == (hist, "s46hist")
        assert ev.choose_floor(None, None) == (None, None)


# --------------------------------------------------------------------------- #
# Métrica diagnóstica "sem sigla" (não é portão)                              #
# --------------------------------------------------------------------------- #


class TestRelaxedKeys:
    def test_strips_trailing_parenthetical(self):
        ents = [
            E("DOU", "ORG", forma="Diário Oficial da União (DOU)"),
            E("MIDR", "ORG", forma="Ministério da Integração e do Desenvolvimento Regional"),
        ]
        assert ev.entity_keys(ents, "relaxed") == {
            ("diario oficial da uniao", "ORG"),
            ("ministerio da integracao e do desenvolvimento regional", "ORG"),
        }

    def test_inner_parenthetical_kept(self):
        ents = [E("Lei (A) B", "LAW")]
        assert ev.entity_keys(ents, "relaxed") == {("lei (a) b", "LAW")}

    def test_only_parenthetical_kept(self):
        assert ev.entity_keys([E("(CGU)", "ORG")], "relaxed") == {("(cgu)", "ORG")}

    def test_type_still_counts(self):
        a = ev.entity_keys([E("X", "ORG", forma="Xis (X)")], "relaxed")
        b = ev.entity_keys([E("X", "LOC", forma="Xis")], "relaxed")
        assert a != b

    def test_arm_metrics_reports_relaxed(self):
        sample = {
            "a": {
                "unique_id": "a",
                "y": "2025",
                "tam": "G",
                "ref": {
                    "raw_response": {"entities": [E("DOU", "ORG", forma="Diário Oficial da União")]}
                },
            }
        }
        recs = {
            "a": {
                "uid": "a",
                "status": "ok",
                "entities": [E("DOU", "ORG", forma="Diário Oficial da União (DOU)")],
                "json_extraivel": True,
                "json_puro": True,
                "stop_reason": "end_turn",
                "usage": {},
                "cost_usd": 0.0,
                "latency_s": 0.1,
            }
        }
        m = ev.arm_metrics(sample, recs, alias_set=set())
        assert m["strict"]["f1"] == pytest.approx(0.0)
        assert m["relaxed"]["f1"] == pytest.approx(1.0)


class TestBlindReviewText:
    def test_includes_article_text_in_details(self):
        items = [
            {
                "uid": "u1",
                "title": "T1",
                "text": "Lead do artigo\nConteúdo com Finep",
                "ref": [E("Finep", "ORG")],
                "cand": [],
                "f1": 0.0,
            }
        ]
        md, _ = ev.blind_review(items, "h55_off_low", seed=1)
        assert "<details>" in md
        assert "> Conteúdo com Finep" in md

    def test_article_text_helper(self):
        art = {"title": "T", "subtitle": None, "editorial_lead": "L", "content": "x" * 5000}
        txt = ev.article_text(art)
        assert txt.startswith("T\n")
        assert "L" in txt
        assert txt.count("x") == 3000  # o mesmo recorte do prompt
