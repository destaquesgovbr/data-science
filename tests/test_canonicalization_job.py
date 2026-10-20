"""
Testes do orquestrador canonicalization_job (Fase 3): Steps A (gather),
B (resolve/persist) e C (backfill canonical_id).

DB simulado via FakeDB; Bedrock e Wikidata mockados. Nenhuma chamada real,
nenhum reprocessamento contra dados reais.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from news_enrichment import canonicalization_job as J
from news_enrichment.wikidata_client import Candidate
from tests.fakedb import FakeDB


def make_bedrock(response_text):
    client = MagicMock()
    bedrock = MagicMock()
    bedrock.client = client
    responses = [response_text] if isinstance(response_text, str) else list(response_text)
    state = {"i": 0}

    def _invoke(modelId=None, body=None):
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        body_mock = MagicMock()
        body_mock.read.return_value = json.dumps(
            {"content": [{"text": responses[idx]}]}
        ).encode()
        return {"body": body_mock}

    client.invoke_model.side_effect = _invoke
    return bedrock


class FakeWikidata:
    def __init__(self, candidates_by_query=None, claims_by_qid=None):
        self._candidates = candidates_by_query or {}
        self._claims = claims_by_qid or {}

    def search(self, name, type=None, lang="pt", limit=7):
        cands = self._candidates.get(name, self._candidates.get("*", []))
        return [Candidate(**c) for c in cands]

    def get_claims(self, qid):
        return self._claims.get(qid, {})


def canon_json(**kw):
    return json.dumps(
        {
            "canonical_name": kw.get("canonical_name", "X"),
            "type": kw.get("type", "ORG"),
            "aliases": kw.get("aliases", []),
            "wikidata_query": kw.get("wikidata_query", kw.get("canonical_name", "X")),
            "is_br_gov_org": kw.get("is_br_gov_org", False),
            "confidence": kw.get("confidence", 0.9),
            "not_an_entity": kw.get("not_an_entity", False),
        }
    )


# ---------------------------------------------------------------------- #
# Step A — gather                                                        #
# ---------------------------------------------------------------------- #


class TestGather:
    def test_stages_new_forms_excludes_resolved_and_aliased(self):
        db = FakeDB()
        # Forma já em entity_alias → excluída.
        db.seed_alias("ministerio da educacao", "ORG", "dgb_mec")
        # Forma já resolvida em seen → excluída.
        db.seen[("bolsa familia", "POLICY")] = {
            "surface_norm": "bolsa familia", "type": "POLICY", "status": "resolved",
            "sample_unique_id": "u0", "attempts": 1,
        }
        # gather rows (surface, type, sample_uid)
        db.gather_rows = [
            ("Ministério da Educação", "ORG", "u1"),   # excluída (alias)
            ("Bolsa Família", "POLICY", "u2"),         # excluída (seen resolved)
            ("Finep", "ORG", "u3"),                    # nova → staged
            ("Copa do Mundo", "EVENT", "u4"),          # nova → staged
        ]
        conn = db.conn()
        since = datetime(2026, 5, 1, tzinfo=timezone.utc)
        until = datetime(2026, 6, 1, tzinfo=timezone.utc)
        staged = J.gather_forms(conn, since, until)

        staged_keys = {(s["surface_norm"], s["type"]) for s in staged}
        assert ("finep", "ORG") in staged_keys
        assert ("copa do mundo", "EVENT") in staged_keys
        assert ("ministerio da educacao", "ORG") not in staged_keys
        assert ("bolsa familia", "POLICY") not in staged_keys
        # staged forms estão em seen como pending.
        assert db.seen[("finep", "ORG")]["status"] == "pending"
        assert db.seen[("finep", "ORG")]["sample_unique_id"] == "u3"

    def test_dedup_same_form_different_samples(self):
        db = FakeDB()
        db.gather_rows = [
            ("Finep", "ORG", "u1"),
            ("Finep", "ORG", "u2"),  # mesma forma normalizada
        ]
        conn = db.conn()
        staged = J.gather_forms(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        finep = [s for s in staged if s["surface_norm"] == "finep"]
        assert len(finep) == 1


# ---------------------------------------------------------------------- #
# Step B — not_an_entity drop persistence                               #
# ---------------------------------------------------------------------- #


class TestResolveDropsNonEntity:
    def test_not_an_entity_marks_resolved_no_registry_no_alias(self):
        db = FakeDB()
        conn = db.conn()
        db.content["uid"] = "Texto sobre inteligência artificial em geral."
        wikidata = FakeWikidata()
        bedrock = make_bedrock(
            canon_json(canonical_name="inteligência artificial", not_an_entity=True)
        )
        decision = J.resolve_form(
            conn, "inteligencia artificial", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        assert decision["action"] == "drop"
        # seen.resolved, entity_id NULL.
        seen = db.seen[("inteligencia artificial", "ORG")]
        assert seen["status"] == "resolved"
        assert seen["entity_id"] is None
        # sem alias, sem registry.
        assert ("inteligencia artificial", "ORG") not in db.alias
        assert db.registry == {}

    def test_needs_review_does_not_write_alias(self):
        db = FakeDB()
        conn = db.conn()
        db.content["uid"] = "ctx"
        wikidata = FakeWikidata(
            candidates_by_query={
                "*": [
                    {"qid": "Q1", "label": "A", "description": ""},
                    {"qid": "Q2", "label": "B", "description": ""},
                ]
            },
            claims_by_qid={
                "Q1": {"country": "Q155", "country_is_br": True, "instance_of": []},
                "Q2": {"country": "Q155", "country_is_br": True, "instance_of": []},
            },
        )
        # canon conf baixa + 2 QIDs → escala; escalada devolve conf baixa.
        bedrock = make_bedrock(
            [
                canon_json(canonical_name="Ambíguo", type="PER", confidence=0.5),
                json.dumps({"qid": "Q1", "confidence": 0.3}),
            ]
        )
        decision = J.resolve_form(
            conn, "ambiguo", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        assert decision["action"] == "needs_review"
        assert db.seen[("ambiguo", "PER")]["status"] == "needs_review"
        assert ("ambiguo", "PER") not in db.alias


# ---------------------------------------------------------------------- #
# Step C — backfill canonical_id                                         #
# ---------------------------------------------------------------------- #


class TestBackfill:
    def test_resolved_mention_gets_canonical_id_unresolved_stays(self):
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        # "tema solto" não está em alias → fica sem canonical_id.
        features = {
            "word_count": 100,  # outra chave deve ser preservada (no UPDATE só entities muda)
            "entities": [
                {"text": "Finep", "type": "ORG", "forma_canonica": "Finep", "count": 2},
                {"text": "Tema Solto", "type": "POLICY", "forma_canonica": "Tema Solto", "count": 1},
            ],
        }
        db.features_rows = [("uid-1", features)]
        conn = db.conn()
        stats = J.backfill_canonical_ids(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert stats["updated"] == 1
        assert stats["mentions_linked"] == 1
        written = json.loads(db.backfilled["uid-1"])
        by_text = {e["text"]: e for e in written}
        assert by_text["Finep"]["canonical_id"] == "Q_FINEP"
        assert "canonical_id" not in by_text["Tema Solto"]

    def test_idempotent_rerun_no_change(self):
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        features = {
            "entities": [
                {"text": "Finep", "type": "ORG", "forma_canonica": "Finep",
                 "count": 1, "canonical_id": "Q_FINEP"},
            ],
        }
        db.features_rows = [("uid-1", features)]
        conn = db.conn()
        stats = J.backfill_canonical_ids(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # já tinha o canonical_id correto → nenhum UPDATE.
        assert stats["updated"] == 0
        assert "uid-1" not in db.backfilled

    def test_jsonb_set_targets_entities_only(self):
        """A escrita usa jsonb_set no caminho {entities} — preserva outras chaves."""
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        db.features_rows = [
            ("uid-1", {"sentiment": {"label": "positive"},
                       "entities": [{"text": "Finep", "type": "ORG",
                                     "forma_canonica": "Finep", "count": 1}]})
        ]
        conn = db.conn()
        J.backfill_canonical_ids(
            conn,
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        # o SQL emitido contém jsonb_set(features, '{entities}', ...)
        update_logs = [s for (s, _p) in db.log if "jsonb_set" in s.lower()]
        assert update_logs
        assert "{entities}" in update_logs[0]


# ---------------------------------------------------------------------- #
# Step C — leitura em lotes (memória constante)                          #
# ---------------------------------------------------------------------- #

JANELA = (
    datetime(2018, 1, 1, tzinfo=timezone.utc),
    datetime(2027, 1, 1, tzinfo=timezone.utc),
)
LOTE_PADRAO = 2000


def _artigos_variados():
    """10 artigos da janela, fora de ordem, cobrindo os casos do Step C."""
    finep = {"text": "Finep", "type": "ORG", "forma_canonica": "Finep", "count": 1}
    return [
        ("uid-07", {"word_count": 7, "entities": [dict(finep)]}),             # liga
        ("uid-02", {"entities": [dict(finep, canonical_id="Q_FINEP")]}),      # já ligado
        ("uid-10", {"entities": [{"text": "Tema Solto", "type": "POLICY"}]}),  # não resolve
        ("uid-01", {"entities": [dict(finep, canonical_id="Q_VELHO"),          # re-aponta
                                 {"text": "MEC", "type": "ORG"}]}),            # liga por text
        ("uid-05", {"entities": None}),                                        # null → []
        ("uid-09", {"entities": []}),
        ("uid-03", {"sentiment": {"label": "positive"},
                    "entities": [{"text": "MEC", "type": "ORG",
                                  "forma_canonica": "Ministério da Educação"},
                                 dict(finep)]}),
        ("uid-08", {"entities": [{"text": "Lula", "type": "PER"}]}),
        ("uid-04", {"entities": [{"text": "Finep", "type": "PER"}]}),         # tipo não bate
        ("uid-06", {"entities": [dict(finep), dict(finep)]}),
    ]


def _backfill_referencia(features_rows, alias_map):
    """Oráculo: a regra do Step C anterior (fetchall do acervo, um artigo por vez).

    Retorna (stats, {unique_id: entities gravadas}).
    """
    stats = {"articles": 0, "updated": 0, "mentions_linked": 0}
    writes = {}
    for unique_id, features in features_rows:
        stats["articles"] += 1
        entities = (features or {}).get("entities") or []
        new_entities, linked, changed = J._apply_canonical_ids(entities, alias_map)
        if not changed:
            continue
        stats["mentions_linked"] += linked
        stats["updated"] += 1
        writes[unique_id] = new_entities
    return stats, writes


class TestBackfillEmLotes:
    """O Step C lê news_features em lotes (keyset em unique_id), com memória constante.

    Antes, um fetchall trazia o acervo inteiro desde 2018 (~197 mil artigos com o
    JSON todo de features) e o job morria por OOM (2Gi) desde 20/10/2026.
    """

    def _db(self):
        db = FakeDB()
        for forma, etype, eid in [
            ("Finep", "ORG", "Q_FINEP"),
            ("MEC", "ORG", "Q_MEC"),
            ("Ministério da Educação", "ORG", "Q_MEC"),
            ("Lula", "PER", "Q_LULA"),
        ]:
            db.seed_alias(J.normalize(forma), etype, eid)
        db.features_rows = _artigos_variados()
        return db

    def test_resultado_identico_ao_da_versao_anterior(self):
        db = self._db()
        esperado_stats, esperado_writes = _backfill_referencia(db.features_rows, dict(db.alias))
        stats = J.backfill_canonical_ids(db.conn(), *JANELA, batch_size=3)
        assert stats == esperado_stats
        assert stats == {"articles": 10, "updated": 5, "mentions_linked": 8}
        gravado = {uid: json.loads(v) for uid, v in db.backfilled.items()}
        assert gravado == esperado_writes

    def test_lote_pequeno_e_lote_unico_gravam_o_mesmo(self):
        a, b = self._db(), self._db()
        stats_a = J.backfill_canonical_ids(a.conn(), *JANELA, batch_size=3)
        stats_b = J.backfill_canonical_ids(b.conn(), *JANELA, batch_size=10_000)
        assert stats_a == stats_b
        assert a.backfilled == b.backfilled

        def updates(db):
            return sorted(p for (s, p) in db.log if s.lower().startswith("update news_features"))

        assert updates(a) == updates(b)

    def test_nenhuma_leitura_traz_mais_que_o_lote(self):
        db = self._db()
        J.backfill_canonical_ids(db.conn(), *JANELA, batch_size=3)
        assert db.backfill_page_sizes == [3, 3, 3, 1]
        assert max(db.backfill_page_sizes) <= 3

    def test_lote_padrao_de_2000(self):
        """Sem batch_size explícito, nenhum SELECT traz mais que 2000 artigos."""
        db = FakeDB()
        db.seed_alias("finep", "ORG", "Q_FINEP")
        n = 2 * LOTE_PADRAO + 1
        db.features_rows = [
            (f"uid-{i:05d}", {"entities": [{"text": "Finep", "type": "ORG"}]})
            for i in range(n)
        ]
        stats = J.backfill_canonical_ids(db.conn(), *JANELA)
        assert db.backfill_page_sizes == [LOTE_PADRAO, LOTE_PADRAO, 1]
        assert stats == {"articles": n, "updated": n, "mentions_linked": n}
        assert J._BACKFILL_BATCH_SIZE == LOTE_PADRAO

    def test_keyset_avanca_pelo_ultimo_unique_id_sem_pular_nem_repetir(self):
        db = self._db()
        stats = J.backfill_canonical_ids(db.conn(), *JANELA, batch_size=3)
        assert [p[2] for p in db.backfill_selects] == ["", "uid-03", "uid-06", "uid-09"]
        # mesma janela [since, until) e mesmo LIMIT em todas as páginas
        assert all(p[:2] == JANELA and p[3] == 3 for p in db.backfill_selects)
        assert stats["articles"] == 10

    def test_total_multiplo_do_lote_termina_com_pagina_vazia(self):
        db = self._db()
        db.features_rows = db.features_rows[:9]
        stats = J.backfill_canonical_ids(db.conn(), *JANELA, batch_size=3)
        assert db.backfill_page_sizes == [3, 3, 3, 0]
        assert stats["articles"] == 9

    def test_select_traz_so_entities_e_mantem_a_janela(self):
        db = self._db()
        J.backfill_canonical_ids(db.conn(), *JANELA, batch_size=3)
        sqls = [s for (s, _p) in db.log if s.lower().startswith("select nf.unique_id")]
        assert sqls
        sql = sqls[0]
        assert sql.startswith(
            "SELECT nf.unique_id, nf.features->'entities' FROM news_features nf "
            "JOIN news n ON n.unique_id = nf.unique_id WHERE "
        )
        where = sql.split(" WHERE ", 1)[1]
        assert "n.published_at >= %s AND n.published_at < %s" in where
        assert "nf.features ? 'entities'" in where
        assert where.endswith("AND nf.unique_id > %s ORDER BY nf.unique_id LIMIT %s")

    def test_dry_run_paginado_conta_mas_nao_escreve(self):
        db = self._db()
        conn = db.conn()
        stats = J.backfill_canonical_ids(conn, *JANELA, dry_run=True, batch_size=3)
        assert stats == {"articles": 10, "updated": 5, "mentions_linked": 8}
        assert db.backfilled == {}
        assert [s for (s, _p) in db.log if not s.lower().startswith("select")] == []
        assert conn.committed == 0
        assert db.backfill_page_sizes == [3, 3, 3, 1]

    def test_falha_num_update_nao_interrompe_os_lotes_seguintes(self):
        db = self._db()
        db.fail_update_uids = {"uid-01"}  # 1º lote
        conn = db.conn()
        stats = J.backfill_canonical_ids(conn, *JANELA, batch_size=3)
        assert stats == {"articles": 10, "updated": 4, "mentions_linked": 8}
        assert set(db.backfilled) == {"uid-03", "uid-06", "uid-07", "uid-08"}
        assert conn.rolled_back == 1

    def test_batch_size_invalido(self):
        with pytest.raises(ValueError):
            J.backfill_canonical_ids(FakeDB().conn(), *JANELA, batch_size=0)


# ---------------------------------------------------------------------- #
# apply_canonical_ids (pure)                                             #
# ---------------------------------------------------------------------- #


class TestApplyCanonicalIds:
    def test_uses_forma_canonica_then_text(self):
        alias_map = {("finep", "ORG"): "Q_FINEP"}
        entities = [{"text": "FINEP", "forma_canonica": "Finep", "type": "ORG"}]
        new, linked, changed = J._apply_canonical_ids(entities, alias_map)
        assert linked == 1
        assert changed is True
        assert new[0]["canonical_id"] == "Q_FINEP"

    def test_falls_back_to_text_when_no_forma_canonica(self):
        alias_map = {("finep", "ORG"): "Q_FINEP"}
        entities = [{"text": "Finep", "type": "ORG"}]
        new, linked, changed = J._apply_canonical_ids(entities, alias_map)
        assert new[0]["canonical_id"] == "Q_FINEP"

    def test_unresolved_unchanged(self):
        new, linked, changed = J._apply_canonical_ids(
            [{"text": "X", "type": "ORG"}], {}
        )
        assert linked == 0
        assert changed is False
        assert "canonical_id" not in new[0]


# ---------------------------------------------------------------------- #
# Governador de cota wired em resolve_pending                            #
# ---------------------------------------------------------------------- #


def make_bedrock_usage(responses, usages):
    """Bedrock falso que devolve (texto, usage) por chamada."""
    client = MagicMock()
    bedrock = MagicMock()
    bedrock.client = client
    state = {"i": 0}

    def _invoke(modelId=None, body=None):
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        body_mock = MagicMock()
        payload = {"content": [{"text": responses[idx]}]}
        u = usages[idx] if idx < len(usages) else None
        if u is not None:
            payload["usage"] = u
        body_mock.read.return_value = json.dumps(payload).encode()
        return {"body": body_mock}

    client.invoke_model.side_effect = _invoke
    return bedrock


class TestResolvePendingGovernor:
    def _seed_pending(self, db, n):
        for i in range(n):
            db.seen[(f"forma{i}", "ORG")] = {
                "surface_norm": f"forma{i}", "type": "ORG", "status": "pending",
                "sample_unique_id": f"u{i}", "attempts": 0,
            }

    def test_records_usage_in_ledger(self):
        db = FakeDB()
        self._seed_pending(db, 1)
        # internal (alta conf, sem candidatos) — uma chamada canon, sem escalada.
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="Forma0", type="ORG", confidence=0.95)],
            [{"input_tokens": 300, "output_tokens": 60}],
        )
        wikidata = FakeWikidata()  # zero candidatos
        conn = db.conn()
        stats = J.resolve_pending(
            conn, 10, bedrock_client=bedrock, wikidata_client=wikidata,
            model_id="sonnet", daily_quota=None,
        )
        assert stats["resolved"] == 1
        assert db.ledger["sonnet"] == {"input_tokens": 300, "output_tokens": 60}

    def test_stops_when_budget_exhausted(self):
        db = FakeDB()
        self._seed_pending(db, 10)
        # Pré-carrega o ledger acima do teto (0.8 * 1000 = 800).
        db.ledger["sonnet"] = {"input_tokens": 900, "output_tokens": 0}
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="X", type="ORG", confidence=0.95)],
            [{"input_tokens": 1, "output_tokens": 1}],
        )
        wikidata = FakeWikidata()
        conn = db.conn()
        stats = J.resolve_pending(
            conn, 10, bedrock_client=bedrock, wikidata_client=wikidata,
            model_id="sonnet", daily_quota=1000, quota_fraction=0.8,
        )
        # Parou logo na primeira checagem (i=0) — nada resolvido.
        assert stats["budget_exhausted"] is True
        assert stats["resolved"] == 0
        # Não chamou o Bedrock.
        bedrock.client.invoke_model.assert_not_called()

    def test_no_quota_runs_uncapped(self):
        db = FakeDB()
        self._seed_pending(db, 2)
        db.ledger["sonnet"] = {"input_tokens": 10_000_000, "output_tokens": 0}
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="A", type="ORG", confidence=0.95),
             canon_json(canonical_name="B", type="ORG", confidence=0.95)],
            [{"input_tokens": 1, "output_tokens": 1},
             {"input_tokens": 1, "output_tokens": 1}],
        )
        wikidata = FakeWikidata()
        conn = db.conn()
        stats = J.resolve_pending(
            conn, 10, bedrock_client=bedrock, wikidata_client=wikidata,
            model_id="sonnet", daily_quota=None,
        )
        # Sem cota → não bloqueia, resolve tudo.
        assert stats["resolved"] == 2
        assert stats["budget_exhausted"] is False


# ---------------------------------------------------------------------- #
# Step B — ordem da fila: formas recentes (NER ao vivo) primeiro          #
# ---------------------------------------------------------------------- #


class TestFetchPendingSqlShape:
    """Trava a forma do SQL da fila: o FakeDB reimplementa a ordenação e não pega
    mutações como DESC→ASC ou o corte de data movido do ON para o WHERE."""

    def _sql(self):
        conn = MagicMock()
        cur = conn.cursor.return_value
        cur.description = [("surface_norm",), ("type",), ("sample_unique_id",), ("attempts",)]
        cur.fetchall.return_value = []
        J.fetch_pending(conn, 10)
        sql = " ".join(cur.execute.call_args[0][0].split())
        return sql

    def test_cutoff_de_data_fica_no_on_e_nao_no_where(self):
        sql = self._sql()
        on_part = sql.split("LEFT JOIN news n", 1)[1].split("WHERE", 1)[0]
        where_part = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
        assert "n.published_at >= %s" in on_part
        assert "published_at" not in where_part

    def test_ordem_recentes_primeiro_fifo_e_desempate_pela_chave(self):
        sql = self._sql()
        order = sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0].strip()
        assert order == "(n.unique_id IS NOT NULL) DESC, s.first_seen_at ASC, s.surface_norm, s.type"


class TestFetchPendingPriority:
    """Formas cujo artigo de amostra é recente passam à frente da fila histórica.

    Com o NER histórico mais rápido que o teto do canon, a fila cresce; em FIFO
    puro as formas do NER ao vivo ficariam atrás dela e sem canonical_id.
    """

    def _seed(self, db, form, now, first_seen_ago, published_ago, status="pending"):
        uid = f"uid-{form}"
        db.seed_seen(form, "ORG", status=status, sample_unique_id=uid,
                     first_seen_at=now - first_seen_ago)
        if published_ago is not None:
            db.seed_news(uid, "-", published_at=now - published_ago)

    def test_recent_forms_first_fifo_within_each_group(self):
        db = FakeDB()
        now = datetime.now(timezone.utc)
        d, h = timedelta(days=1), timedelta(hours=1)
        # Fila histórica (staged há dias, artigos antigos)...
        self._seed(db, "antiga1", now, 5 * d, 1000 * d)
        self._seed(db, "antiga2", now, 4 * d, 900 * d)
        # ...formas do NER ao vivo, staged depois...
        self._seed(db, "recente2", now, 1 * h, 2 * h)
        self._seed(db, "recente1", now, 1 * d, 1 * d + 1 * h)
        # ...e uma antiga staged na mesma passada do ao vivo.
        self._seed(db, "antiga3", now, 2 * h, 800 * d)
        # Terminal não entra na fila, mesmo com amostra recente.
        self._seed(db, "revisao", now, 3 * h, 3 * h, status="needs_review")

        got = [p["surface_norm"] for p in J.fetch_pending(db.conn(), 10)]

        assert got == ["recente1", "recente2", "antiga1", "antiga2", "antiga3"]

    def test_limit_keeps_recent_forms_ahead_of_backlog(self):
        db = FakeDB()
        now = datetime.now(timezone.utc)
        d = timedelta(days=1)
        for i in range(5):
            self._seed(db, f"antiga{i}", now, (10 - i) * d, 900 * d)
        self._seed(db, "recente_a", now, 2 * d, 2 * d)
        self._seed(db, "recente_b", now, 1 * d, 1 * d)

        got = [p["surface_norm"] for p in J.fetch_pending(db.conn(), 2)]

        assert got == ["recente_a", "recente_b"]

    def test_window_boundary_and_missing_sample_stay_in_queue(self):
        db = FakeDB()
        now = datetime.now(timezone.utc)
        d = timedelta(days=1)
        self._seed(db, "fora_15d", now, 10 * d, 15 * d)
        db.seed_seen("sem_amostra", "ORG", sample_unique_id=None, first_seen_at=now - 9 * d)
        db.seed_seen("amostra_sumiu", "ORG", sample_unique_id="uid-inexistente",
                     first_seen_at=now - 8 * d)
        self._seed(db, "dentro_13d", now, 7 * d, 13 * d)

        got = [p["surface_norm"] for p in J.fetch_pending(db.conn(), 10)]

        # Janela de RECENT_PRIORITY_DAYS (14): 13d é recente, 15d não. Sem
        # amostra (ou amostra fora de news) continua na fila, no grupo FIFO.
        assert got == ["dentro_13d", "fora_15d", "sem_amostra", "amostra_sumiu"]
        assert J.RECENT_PRIORITY_DAYS == 14

    def test_resolve_pending_spends_limited_run_on_recent_form(self):
        db = FakeDB()
        now = datetime.now(timezone.utc)
        d = timedelta(days=1)
        self._seed(db, "antiga", now, 3 * d, 900 * d)
        self._seed(db, "recente", now, 1 * d, 1 * d)
        bedrock = make_bedrock_usage(
            [canon_json(canonical_name="Recente", type="ORG", confidence=0.95)],
            [{"input_tokens": 1, "output_tokens": 1}],
        )
        stats = J.resolve_pending(
            db.conn(), 1, bedrock_client=bedrock, wikidata_client=FakeWikidata(),
            model_id="sonnet", daily_quota=None,
        )

        assert stats["resolved"] == 1
        assert db.seen[("recente", "ORG")]["status"] == "resolved"
        assert db.seen[("antiga", "ORG")]["status"] == "pending"


# ---------------------------------------------------------------------- #
# _persist_decision — reuso por nome para LAW e ORG                     #
# ---------------------------------------------------------------------- #


class TestPersistDecisionLawReuse:
    def test_law_near_duplicate_does_not_mint_new_entity(self):
        """LAW com nome similar a uma já registrada deve reusar o id existente."""
        db = FakeDB()
        # Registry já tem "Estatuto da Surdocegueira" como LAW
        db.seed_registry("dgb_estatuto-da-surdocegueira", "Estatuto da Surdocegueira", "LAW")
        conn = db.conn()
        db.content["uid"] = "O Estatuto Surdocegueira foi aprovado..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})

        # LLM canonicaliza para um nome quase idêntico (Jaccard = 1.0, nome exato)
        bedrock = make_bedrock(
            canon_json(
                canonical_name="Estatuto da Surdocegueira",
                type="LAW",
                is_br_gov_org=False,
                confidence=0.9,
            )
        )
        J.resolve_form(
            conn, "estatuto surdocegueira", "LAW", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )

        # Deve reusar dgb_estatuto-da-surdocegueira, não criar novo nó
        reused_id = db.alias.get(("estatuto surdocegueira", "LAW"))
        assert reused_id == "dgb_estatuto-da-surdocegueira"
        # Apenas 1 entidade LAW no registry (sem duplicata)
        law_entries = [
            r for r in db.registry.values() if r.get("type") == "LAW"
        ]
        assert len(law_entries) == 1

    def test_law_different_number_mints_new_entity(self):
        """LAW com número diferente (baixa similaridade) cria nova entidade."""
        db = FakeDB()
        db.seed_registry("dgb_lei-14-100", "Lei nº 14.100/2022", "LAW")
        conn = db.conn()
        db.content["uid"] = "A nova lei foi sancionada..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})

        bedrock = make_bedrock(
            canon_json(
                canonical_name="Lei nº 14.967/2024",
                type="LAW",
                is_br_gov_org=False,
                confidence=0.9,
            )
        )
        J.resolve_form(
            conn, "lei no 14 967 2024", "LAW", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )

        # Nova entidade criada (id diferente)
        new_id = db.alias.get(("lei no 14 967 2024", "LAW"))
        assert new_id is not None
        assert new_id != "dgb_lei-14-100"
        law_entries = [
            r for r in db.registry.values() if r.get("type") == "LAW"
        ]
        assert len(law_entries) == 2

    def test_org_reuse_still_works(self):
        """Backward compat: ORG com nomes similares ainda reusa (threshold 0.62)."""
        db = FakeDB()
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O ministério anunciou..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})

        bedrock = make_bedrock(
            canon_json(
                canonical_name="Ministério da Educação (MEC)",
                type="ORG",
                is_br_gov_org=True,
                confidence=0.95,
            )
        )
        J.resolve_form(
            conn, "ministerio da educacao", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )

        reused_id = db.alias.get(("ministerio da educacao", "ORG"))
        assert reused_id == "dgb_mec"
        org_entries = [r for r in db.registry.values() if r.get("type") == "ORG"]
        assert len(org_entries) == 1

    def test_org_acronym_variant_reused_at_mint_time(self):
        """Mint-time ORG acronym-aware: LLM devolve o nome curto, mas reusa a sigla.

        Seed "Ministério da Educação (MEC)"; o LLM canonicaliza para o nome SEM a
        sigla ("Ministério da Educação"), Jaccard 0.75 < 0.85 (threshold subiu).
        Deve reusar a entidade existente via _is_acronym_variant (sem mintar nova).
        """
        db = FakeDB()
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O ministério anunciou..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})
        bedrock = make_bedrock(
            canon_json(
                canonical_name="Ministério da Educação",  # sem a sigla
                type="ORG",
                is_br_gov_org=True,
                confidence=0.95,
            )
        )
        J.resolve_form(
            conn, "ministerio da educacao", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        reused_id = db.alias.get(("ministerio da educacao", "ORG"))
        assert reused_id == "dgb_mec"
        org_entries = [r for r in db.registry.values() if r.get("type") == "ORG"]
        assert len(org_entries) == 1

    def test_org_distinct_bank_mints_new_at_mint_time(self):
        """Mint-time ORG: 'Banco do Brasil' NÃO reusa 'Banco Central do Brasil' (0.75<0.85)."""
        db = FakeDB()
        db.seed_registry("dgb_bcb", "Banco Central do Brasil", "ORG",
                         provenance="agencies_seed")
        conn = db.conn()
        db.content["uid"] = "O banco anunciou..."
        wikidata = FakeWikidata(candidates_by_query={"*": []})
        bedrock = make_bedrock(
            canon_json(
                canonical_name="Banco do Brasil",
                type="ORG",
                is_br_gov_org=True,
                confidence=0.95,
            )
        )
        J.resolve_form(
            conn, "banco do brasil", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Duas ORGs distintas no registry (mintou nova, não reusou o BCB).
        org_entries = [r for r in db.registry.values() if r.get("type") == "ORG"]
        assert len(org_entries) == 2
        assert db.alias.get(("banco do brasil", "ORG")) != "dgb_bcb"


# ---------------------------------------------------------------------- #
# PER short-circuit — skip Bedrock when Wikidata has no candidates        #
# ---------------------------------------------------------------------- #


class TestPERShortCircuit:
    def test_per_no_wikidata_skips_bedrock(self):
        """PER sem candidatos Wikidata → needs_review direto, Bedrock não chamado."""
        db = FakeDB()
        db.content["uid"] = "José Silva é servidor público federal."
        # FakeWikidata retorna [] para qualquer busca (default)
        wikidata = FakeWikidata()
        bedrock = make_bedrock(canon_json(canonical_name="José Silva", type="PER"))
        conn = db.conn()
        decision = J.resolve_form(
            conn, "jose silva", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Bedrock NÃO deve ter sido chamado
        bedrock.client.invoke_model.assert_not_called()
        # Decisão deve ser needs_review
        assert decision["action"] == "needs_review"
        assert decision["status"] == "needs_review"
        assert decision["entity_id"] is None
        # seen deve estar marcado como needs_review
        seen = db.seen[("jose silva", "PER")]
        assert seen["status"] == "needs_review"

    def test_per_with_wikidata_candidates_calls_bedrock(self):
        """PER com candidatos Wikidata → Bedrock É chamado (caminho normal)."""
        db = FakeDB()
        db.content["uid"] = "Lula anunciou novas medidas econômicas."
        # FakeWikidata retorna candidato para qualquer query (chave especial "*")
        wikidata = FakeWikidata(
            candidates_by_query={
                "*": [{"qid": "Q37181", "label": "Lula", "description": "presidente do Brasil"}]
            }
        )
        bedrock = make_bedrock(
            [
                canon_json(canonical_name="Lula", type="PER", confidence=0.9),
                json.dumps({"qid": "Q37181", "confidence": 0.9}),
            ]
        )
        conn = db.conn()
        J.resolve_form(
            conn, "lula", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Bedrock DEVE ter sido chamado (ao menos 1 vez)
        assert bedrock.client.invoke_model.call_count >= 1

    def test_per_short_circuit_dry_run_does_not_write_seen(self):
        """dry_run=True: short-circuit retorna needs_review mas não escreve no DB."""
        db = FakeDB()
        db.content["uid"] = "ctx"
        wikidata = FakeWikidata()  # retorna [] para qualquer busca
        bedrock = make_bedrock(canon_json(canonical_name="Joao Ninguem", type="PER"))
        conn = db.conn()
        decision = J.resolve_form(
            conn, "joao ninguem", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
            dry_run=True,
        )
        # seen NÃO deve ter sido escrito
        assert ("joao ninguem", "PER") not in db.seen
        # Decisão ainda deve ser needs_review
        assert decision["action"] == "needs_review"
        # Bedrock não chamado
        bedrock.client.invoke_model.assert_not_called()

    def test_org_type_not_short_circuited(self):
        """ORG não sofre short-circuit (apenas PER). Bedrock É chamado."""
        db = FakeDB()
        db.content["uid"] = "ctx"
        # Wikidata retorna [] para qualquer query
        wikidata = FakeWikidata()
        bedrock = make_bedrock(canon_json(canonical_name="Empresa X", type="ORG", confidence=0.9))
        conn = db.conn()
        J.resolve_form(
            conn, "empresa x", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=wikidata, model_id="m",
        )
        # Bedrock DEVE ter sido chamado (ORG não tem short-circuit)
        assert bedrock.client.invoke_model.call_count >= 1

    def test_per_gazetteer_hit_bypasses_short_circuit(self):
        """Gazetteer tem prioridade máxima: se hit, não consulta Wikidata para pre-check."""
        db = FakeDB()
        # Alias "lula" → "Q37181" já no gazetteer
        db.seed_alias("lula", "PER", "Q37181")
        db.content["uid"] = "ctx"
        # FakeWikidata com spy para detectar chamadas de search
        class SpyWikidata(FakeWikidata):
            def __init__(self):
                super().__init__()
                self.search_calls = []

            def search(self, name, type=None, lang="pt", limit=7):
                self.search_calls.append(name)
                return super().search(name, type=type, lang=lang, limit=limit)

        spy_wikidata = SpyWikidata()
        bedrock = make_bedrock(canon_json(canonical_name="Lula", type="PER"))
        conn = db.conn()
        decision = J.resolve_form(
            conn, "lula", "PER", "uid", 0,
            bedrock_client=bedrock, wikidata_client=spy_wikidata, model_id="m",
        )
        # Deve retornar "gazetteer"
        assert decision["action"] == "gazetteer"
        assert decision["entity_id"] == "Q37181"
        # Wikidata NÃO deve ter sido chamado para pre-check
        assert spy_wikidata.search_calls == []
        # Bedrock também não chamado
        bedrock.client.invoke_model.assert_not_called()


# ---------------------------------------------------------------------- #
# --dedup CLI: run_dedup                                                  #
# ---------------------------------------------------------------------- #


class TestDedup:
    def test_dry_run_does_not_merge(self):
        """dry_run=True: near-duplicates são propostos mas não mergeados."""
        db = FakeDB()
        # Dois LAWs near-duplicate: Jaccard("lei estatuto surdocegueira",
        # "lei estatuto surdocegueira 2024") = 3/4 = 0.75 >= threshold 0.75
        db.seed_registry("dgb_lei-estatuto-surdocegueira", "Lei Estatuto Surdocegueira", "LAW")
        db.seed_registry(
            "dgb_lei-do-estatuto-surdocegueira", "Lei do Estatuto Surdocegueira", "LAW"
        )
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=True)
        # Nenhum merge deve ter ocorrido
        assert len(db.registry) == 2
        # Mas deve ter proposto 1 merge
        assert result["proposed"] >= 1
        assert result["merged"] == 0

    def test_apply_merges_near_duplicates(self):
        """dry_run=False: near-duplicates são efetivamente mergeados."""
        db = FakeDB()
        db.seed_registry("dgb_programa-nacional-habitacao", "Programa Nacional Habitacao", "LAW")
        db.seed_registry(
            "dgb_programa-nacional-habitacao-popular",
            "Programa Nacional Habitacao Popular",
            "LAW",
        )
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=False)
        # Após merge: apenas 1 entidade restante
        assert len(db.registry) == 1
        assert result["merged"] >= 1
        assert result["proposed"] >= 1

    def test_dissimilar_entities_not_merged(self):
        """Entidades com nomes muito diferentes não são mergeadas."""
        db = FakeDB()
        # Jaccard("lei 14967 2024", "codigo civil") é muito baixo (< 0.75)
        db.seed_registry("dgb_lei-14967-2024", "Lei 14967 2024", "LAW")
        db.seed_registry("dgb_codigo-civil", "Codigo Civil", "LAW")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=False)
        # Nada deve ter sido mergeado nem proposto
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2

    def test_dedup_all_types_when_no_type_given(self):
        """Sem entity_type: processa todos os tipos em _ENTITY_REUSE_THRESHOLDS."""
        from news_enrichment.canonicalization import _ENTITY_REUSE_THRESHOLDS

        db = FakeDB()
        # Adiciona entidades para dois tipos diferentes
        db.seed_registry("dgb_org-a", "Ministerio Educacao", "ORG")
        db.seed_registry("dgb_org-b", "Ministerio Educacao Federal", "ORG")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type=None, dry_run=True)
        # Deve ter processado pelo menos todos os tipos com threshold definido
        for t in _ENTITY_REUSE_THRESHOLDS:
            assert t in result["types_processed"]

    def test_dedup_target_is_entity_with_more_aliases(self):
        """O target do merge é a entidade com mais aliases (source é a com menos)."""
        db = FakeDB()
        # dgb_lei-a tem 2 aliases; dgb_lei-b tem 0
        db.seed_registry("dgb_lei-a", "Lei Estatuto Surdocegueira", "LAW")
        db.seed_registry("dgb_lei-b", "Lei do Estatuto Surdocegueira", "LAW")
        # Adiciona 2 aliases para dgb_lei-a
        db.seed_alias("lei estatuto surdocegueira", "LAW", "dgb_lei-a")
        db.seed_alias("lei estatuto", "LAW", "dgb_lei-a")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="LAW", dry_run=False)
        # dgb_lei-a deve ter sobrevivido (mais aliases = target)
        assert "dgb_lei-a" in db.registry
        assert "dgb_lei-b" not in db.registry
        assert result["merged"] >= 1


class TestDedupYearGuard:
    """run_dedup: nomes que diferem por ano (edições) nunca fundem."""

    def test_edition_by_year_not_merged(self):
        """'ENGP' vs 'ENGP 2026' NÃO funde (edições distintas), apesar do Jaccard alto."""
        db = FakeDB()
        db.seed_registry("dgb_engp", "Encontro Nacional de Gestao de Pessoas (ENGP)", "EVENT")
        db.seed_registry("dgb_engp-2026", "Encontro Nacional de Gestao de Pessoas (ENGP) 2026", "EVENT")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="EVENT", dry_run=False)
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2

    def test_same_year_still_merges(self):
        """'... de 2026' vs '... 2026' (mesmo ano) ainda funde (Copa)."""
        db = FakeDB()
        db.seed_registry("dgb_copa-de-2026", "Copa do Mundo FIFA de 2026", "EVENT")
        db.seed_registry("dgb_copa-2026", "Copa do Mundo FIFA 2026", "EVENT")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="EVENT", dry_run=False)
        assert result["merged"] >= 1
        assert len(db.registry) == 1

    def test_different_years_not_merged(self):
        db = FakeDB()
        db.seed_registry("dgb_enem-2025", "Enem 2025", "EVENT")
        db.seed_registry("dgb_enem-2026", "Enem 2026", "EVENT")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="EVENT", dry_run=False)
        assert result["merged"] == 0
        assert len(db.registry) == 2


class TestDedupWikidataWins:
    """run_dedup: num par QID×dgb_, o QID Wikidata vence (vira target),
    independentemente da contagem de aliases (regra de identidade do projeto)."""

    def test_is_qid_helper(self):
        assert J._is_qid("Q216330")
        assert J._is_qid("Q5")
        assert not J._is_qid("dgb_ans")
        assert not J._is_qid("Qabc")
        assert not J._is_qid("")
        assert not J._is_qid("XQ123")

    def test_qid_is_target_even_with_fewer_aliases(self):
        """QID vence o dgb_ mesmo tendo MENOS aliases que o dgb_."""
        db = FakeDB()
        # mesma org: "X" vs "X (SIGLA)" → variante por sigla (path a)
        db.seed_registry("dgb_ans", "Agencia Nacional de Saude Suplementar", "ORG")
        db.seed_registry("Q9592631", "Agencia Nacional de Saude Suplementar (ANS)", "ORG")
        # dgb_ tem MAIS aliases — pela heurística antiga seria target (errado)
        db.seed_alias("ans", "ORG", "dgb_ans")
        db.seed_alias("agencia nacional de saude suplementar", "ORG", "dgb_ans")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] >= 1
        # O QID sobreviveu como chave canônica; o dgb_ foi o source removido.
        assert "Q9592631" in db.registry
        assert "dgb_ans" not in db.registry

    def test_qid_is_target_regardless_of_order(self):
        """Direção QID-wins independe da ordem de varredura (QID semeado primeiro
        = eid_a no laço, exercita o ramo `a_qid and not b_qid`)."""
        db = FakeDB()
        db.seed_registry("Q4314917", "Agencia Nacional de Aviacao Civil (Anac)", "ORG")
        db.seed_registry("dgb_anac", "Agencia Nacional de Aviacao Civil", "ORG")
        db.seed_alias("anac", "ORG", "dgb_anac")  # dgb_ tem o alias; QID não
        conn = db.conn()
        J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert "Q4314917" in db.registry
        assert "dgb_anac" not in db.registry

    def test_both_dgb_uses_alias_count_heuristic(self):
        """Par dgb_×dgb_ (sem QID) mantém a heurística de mais-aliases=target."""
        db = FakeDB()
        db.seed_registry("dgb_a", "Lei Estatuto Surdocegueira", "LAW")
        db.seed_registry("dgb_b", "Lei do Estatuto Surdocegueira", "LAW")
        db.seed_alias("lei estatuto surdocegueira", "LAW", "dgb_a")
        db.seed_alias("lei estatuto", "LAW", "dgb_a")
        conn = db.conn()
        J.run_dedup(conn, entity_type="LAW", dry_run=False)
        assert "dgb_a" in db.registry  # mais aliases = target
        assert "dgb_b" not in db.registry


class TestDedupOrgThreshold:
    """run_dedup ORG: threshold dedicado (0.85) + detector de variante por sigla."""

    def test_org_false_positive_banks_not_merged(self):
        """'Banco Central do Brasil' vs 'Banco do Brasil' (Jaccard 0.75) NÃO mergeia.

        Com o threshold de dedup ORG (0.85) e por não serem variante de sigla,
        instituições distintas são preservadas.
        """
        db = FakeDB()
        db.seed_registry("dgb_banco-central-do-brasil", "Banco Central do Brasil", "ORG")
        db.seed_registry("dgb_banco-do-brasil", "Banco do Brasil", "ORG")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2
        assert "dgb_banco-central-do-brasil" in db.registry
        assert "dgb_banco-do-brasil" in db.registry

    def test_org_police_false_positive_not_merged(self):
        """'Polícia Federal' vs 'Polícia Rodoviária Federal' NÃO mergeia."""
        db = FakeDB()
        db.seed_registry("dgb_policia-federal", "Polícia Federal", "ORG")
        db.seed_registry(
            "dgb_policia-rodoviaria-federal", "Polícia Rodoviária Federal", "ORG"
        )
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] == 0
        assert result["proposed"] == 0
        assert len(db.registry) == 2

    def test_org_acronym_variant_merged_below_threshold(self):
        """'Ministério da Educação' vs 'Ministério da Educação (MEC)' mergeia.

        Jaccard = 3/4 = 0.75 < 0.85 (threshold dedup ORG), mas é variante por
        sigla → deve mergear assim mesmo. dgb_mec (mais aliases) é o target.
        """
        db = FakeDB()
        db.seed_registry("dgb_min-educacao", "Ministério da Educação", "ORG")
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG")
        # dgb_mec tem mais aliases → sobrevive como target.
        db.seed_alias("ministerio da educacao (mec)", "ORG", "dgb_mec")
        db.seed_alias("mec", "ORG", "dgb_mec")
        db.seed_alias("ministerio da educacao", "ORG", "dgb_min-educacao")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False)
        assert result["merged"] == 1
        assert result["proposed"] == 1
        assert len(db.registry) == 1
        assert "dgb_mec" in db.registry
        assert "dgb_min-educacao" not in db.registry
        # alias do source migrado para o target.
        assert db.alias[("ministerio da educacao", "ORG")] == "dgb_mec"

    def test_org_explicit_threshold_overrides(self):
        """O arg threshold= explícito ainda sobrepõe tudo (banks com thr 0.70 → mergeia)."""
        db = FakeDB()
        db.seed_registry("dgb_banco-central-do-brasil", "Banco Central do Brasil", "ORG")
        db.seed_registry("dgb_banco-do-brasil", "Banco do Brasil", "ORG")
        conn = db.conn()
        # Jaccard = 3/4 = 0.75 >= 0.70 explícito → mergeia (override do default 0.85).
        result = J.run_dedup(conn, entity_type="ORG", dry_run=False, threshold=0.70)
        assert result["merged"] == 1
        assert len(db.registry) == 1

    def test_org_acronym_variant_dry_run_merges_nothing(self):
        """dry_run=True: variante por sigla é proposta mas NÃO mergeada."""
        db = FakeDB()
        db.seed_registry("dgb_min-educacao", "Ministério da Educação", "ORG")
        db.seed_registry("dgb_mec", "Ministério da Educação (MEC)", "ORG")
        conn = db.conn()
        result = J.run_dedup(conn, entity_type="ORG", dry_run=True)
        assert result["proposed"] >= 1
        assert result["merged"] == 0
        assert len(db.registry) == 2


# ---------------------------------------------------------------------- #
# Fallback de sigla — Step B (antes do LLM) e passo retroativo           #
# ---------------------------------------------------------------------- #

STF = "supremo tribunal federal (stf)"


class TestSiglaFallbackStepB:
    def test_forma_pending_liga_a_base_sem_chamar_llm(self):
        db = FakeDB()
        db.seed_alias("supremo tribunal federal", "ORG", "Q519138")
        db.seed_seen(STF, "ORG", sample_unique_id="uid")
        bedrock = make_bedrock(canon_json())
        decision = J.resolve_form(
            db.conn(), STF, "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=FakeWikidata(), model_id="m",
        )
        assert decision["action"] == "fallback_sigla"
        assert decision["status"] == "resolved"
        assert decision["entity_id"] == "Q519138"
        assert decision["usage"] == {"input_tokens": 0, "output_tokens": 0}
        bedrock.client.invoke_model.assert_not_called()
        # alias materializado, com origem identificável → o Step C propaga.
        assert db.alias[(STF, "ORG")] == "Q519138"
        assert db.alias_source[(STF, "ORG")] == "fallback_sigla"
        assert db.seen[(STF, "ORG")]["status"] == "resolved"
        assert db.seen[(STF, "ORG")]["entity_id"] == "Q519138"
        assert db.llm_raw == []

    def test_conflito_de_sigla_segue_para_o_llm(self):
        db = FakeDB()
        db.seed_alias("confederacao nacional da industria", "ORG", "Q_CNI")
        db.seed_alias("cni", "ORG", "Q_OUTRA")
        form = "confederacao nacional da industria (cni)"
        db.seed_seen(form, "ORG", sample_unique_id="uid")
        bedrock = make_bedrock(canon_json(canonical_name="CNI", confidence=0.95))
        decision = J.resolve_form(
            db.conn(), form, "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=FakeWikidata(), model_id="m",
        )
        assert decision["action"] != "fallback_sigla"
        assert bedrock.client.invoke_model.called
        assert db.alias_source.get((form, "ORG")) != "fallback_sigla"

    def test_type_diferente_da_base_segue_para_o_llm(self):
        """SUS tipado como POLICY não herda o alias ORG da base."""
        db = FakeDB()
        db.seed_alias("sistema unico de saude", "ORG", "Q_SUS")
        form = "sistema unico de saude (sus)"
        db.seed_seen(form, "POLICY", sample_unique_id="uid")
        bedrock = make_bedrock(canon_json(canonical_name="SUS", type="POLICY", confidence=0.95))
        decision = J.resolve_form(
            db.conn(), form, "POLICY", "uid", 0,
            bedrock_client=bedrock, wikidata_client=FakeWikidata(), model_id="m",
        )
        assert decision["action"] != "fallback_sigla"
        assert bedrock.client.invoke_model.called
        assert db.alias_source.get((form, "POLICY")) != "fallback_sigla"

    def test_dry_run_nao_escreve(self):
        db = FakeDB()
        db.seed_alias("supremo tribunal federal", "ORG", "Q519138")
        db.seed_seen(STF, "ORG", sample_unique_id="uid")
        decision = J.resolve_form(
            db.conn(), STF, "ORG", "uid", 0,
            bedrock_client=make_bedrock(canon_json()), wikidata_client=FakeWikidata(),
            model_id="m", dry_run=True,
        )
        assert decision["action"] == "fallback_sigla"
        assert (STF, "ORG") not in db.alias
        assert db.seen[(STF, "ORG")]["status"] == "pending"


class TestLinkSiglaFallbacks:
    """Passo retroativo: liga formas já pending/needs_review/resolved-sem-alias."""

    def _db(self):
        db = FakeDB()
        db.seed_alias("supremo tribunal federal", "ORG", "Q519138")
        db.seed_alias("agencia nacional de telecomunicacoes", "ORG", "Q4056893")
        db.seed_seen(STF, "ORG", status="needs_review")
        db.seed_seen("agencia nacional de telecomunicacoes (anatel)", "ORG", status="pending")
        return db

    def test_liga_needs_review_e_pending_sem_mexer_no_status(self):
        db = self._db()
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats["linked"] == 2
        assert db.alias[(STF, "ORG")] == "Q519138"
        assert db.alias_source[(STF, "ORG")] == "fallback_sigla"
        anatel = ("agencia nacional de telecomunicacoes (anatel)", "ORG")
        assert db.alias[anatel] == "Q4056893"
        # needs_review continua needs_review (a decisão original fica auditável);
        # a pending é resolvida pelo gazetteer no Step B, sem LLM.
        assert db.seen[(STF, "ORG")]["status"] == "needs_review"
        assert db.seen[anatel]["status"] == "pending"

    def test_resolved_sem_alias_tambem_liga(self):
        db = FakeDB()
        db.seed_alias("diario oficial da uniao", "ORG", "Q3712237")
        form = "diario oficial da uniao (dou)"
        db.seen[(form, "ORG")] = {
            "surface_norm": form, "type": "ORG", "status": "resolved",
            "entity_id": None, "attempts": 1, "sample_unique_id": None,
        }
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats["linked"] == 1
        assert db.alias[(form, "ORG")] == "Q3712237"

    def test_nao_toca_alias_exato_conflito_nem_type_trocado(self):
        db = FakeDB()
        # forma com alias exato do canon → intocada.
        db.seed_alias("ministerio da educacao", "ORG", "Q_MEC")
        db.seed_alias("ministerio da educacao (mec)", "ORG", "Q_MEC_CANON")
        db.seed_seen("ministerio da educacao (mec)", "ORG", status="resolved")
        # conflito: a sigla aponta para outra entidade do mesmo type.
        db.seed_alias("confederacao nacional da industria", "ORG", "Q_CNI")
        db.seed_alias("cni", "ORG", "Q_OUTRA")
        db.seed_seen("confederacao nacional da industria (cni)", "ORG", status="needs_review")
        # type trocado (SUS como POLICY; alias da base só em ORG).
        db.seed_alias("sistema unico de saude", "ORG", "Q_SUS")
        db.seed_seen("sistema unico de saude (sus)", "POLICY", status="needs_review")
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats["linked"] == 0
        assert db.alias[("ministerio da educacao (mec)", "ORG")] == "Q_MEC_CANON"
        assert db.alias_source[("ministerio da educacao (mec)", "ORG")] == "canon"
        assert ("confederacao nacional da industria (cni)", "ORG") not in db.alias
        assert ("sistema unico de saude (sus)", "POLICY") not in db.alias

    def test_idempotente(self):
        db = self._db()
        J.link_sigla_fallbacks(db.conn())
        n_log = len(db.log)
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats == {"linked": 0, "resynced": 0, "removed": 0, "skipped_resolved": 0}
        writes = [s for (s, _p) in db.log[n_log:] if not s.lower().startswith("select")]
        assert writes == []

    def test_resincroniza_quando_o_alias_da_base_e_corrigido(self):
        db = FakeDB()
        db.seed_alias("tribunal superior eleitoral", "ORG", "Q_TOULOUSE")
        form = "tribunal superior eleitoral (tse)"
        db.seed_seen(form, "ORG", status="needs_review")
        J.link_sigla_fallbacks(db.conn())
        assert db.alias[(form, "ORG")] == "Q_TOULOUSE"
        # correção do vínculo da base (re-apontar o alias) → o derivado acompanha.
        db.alias[("tribunal superior eleitoral", "ORG")] = "Q_TSE"
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats["resynced"] == 1
        assert db.alias[(form, "ORG")] == "Q_TSE"
        assert db.alias_source[(form, "ORG")] == "fallback_sigla"

    def test_remove_derivado_quando_a_base_perde_o_alias(self):
        db = FakeDB()
        db.seed_alias("ministerio da pesca e aquicultura", "ORG", "Q_ERRADO")
        db.seed_seen("ministerio da pesca e aquicultura (mpa)", "ORG", status="needs_review")
        db.seed_seen("ministerio da pesca e aquicultura (m.p.a)", "ORG", status="pending")
        conn = db.conn()
        J.link_sigla_fallbacks(conn)
        # a pending foi resolvida (pelo gazetteer) para o alvo derivado.
        J.resolve_form(
            conn, "ministerio da pesca e aquicultura (m.p.a)", "ORG", None, 0,
            bedrock_client=make_bedrock(canon_json()), wikidata_client=FakeWikidata(),
            model_id="m",
        )
        assert db.seen[("ministerio da pesca e aquicultura (m.p.a)", "ORG")]["status"] == "resolved"
        # alias errado da base removido → derivados removidos; a resolvida volta à fila.
        del db.alias[("ministerio da pesca e aquicultura", "ORG")]
        stats = J.link_sigla_fallbacks(conn)
        assert stats["removed"] == 2
        assert ("ministerio da pesca e aquicultura (mpa)", "ORG") not in db.alias
        assert ("ministerio da pesca e aquicultura (m.p.a)", "ORG") not in db.alias
        mpa = db.seen[("ministerio da pesca e aquicultura (mpa)", "ORG")]
        assert mpa["status"] == "needs_review"
        mpa2 = db.seen[("ministerio da pesca e aquicultura (m.p.a)", "ORG")]
        assert mpa2["status"] == "pending"
        assert mpa2["entity_id"] is None

    def test_dry_run_conta_sem_escrever(self):
        db = self._db()
        stats = J.link_sigla_fallbacks(db.conn(), dry_run=True)
        assert stats["linked"] == 2
        assert (STF, "ORG") not in db.alias

    # -- re-apontamento: a correção tem de convergir (revisão do #46, item 1) --

    SESU = "secretaria de educacao superior (sesu)"

    def _sesu_ligada_ao_alvo_errado(self):
        """Base e sigla apontam para o mesmo alvo errado; a menção já herdou o id."""
        db = FakeDB()
        db.seed_alias("secretaria de educacao superior", "ORG", "Q_UCR")
        db.seed_alias("sesu", "ORG", "Q_UCR")
        db.seed_seen(self.SESU, "ORG", status="needs_review")
        db.features_rows = [("uid-1", {"entities": [
            {"text": "SESu", "forma_canonica": "Secretaria de Educação Superior (SESu)",
             "type": "ORG"},
        ]})]
        conn = db.conn()
        assert J.link_sigla_fallbacks(conn)["linked"] == 1
        J.backfill_canonical_ids(conn, datetime(2018, 1, 1, tzinfo=timezone.utc),
                                 datetime(2027, 1, 1, tzinfo=timezone.utc))
        assert json.loads(db.backfilled["uid-1"])[0]["canonical_id"] == "Q_UCR"
        db.features_rows = [("uid-1", {"entities": json.loads(db.backfilled["uid-1"])})]
        return db, conn

    def test_reapontar_so_a_base_com_a_sigla_no_alvo_antigo_resincroniza(self):
        """A sigla ainda aponta para o alvo atual do derivado: o derivado segue a base
        (não é removido), e o Step C leva a menção para o id novo."""
        db, conn = self._sesu_ligada_ao_alvo_errado()
        db.alias[("secretaria de educacao superior", "ORG")] = "Q_SESU"
        stats = J.link_sigla_fallbacks(conn)
        assert stats["resynced"] == 1
        assert stats["removed"] == 0
        assert db.alias[(self.SESU, "ORG")] == "Q_SESU"
        assert db.alias_source[(self.SESU, "ORG")] == "fallback_sigla"
        J.backfill_canonical_ids(conn, datetime(2018, 1, 1, tzinfo=timezone.utc),
                                 datetime(2027, 1, 1, tzinfo=timezone.utc))
        assert json.loads(db.backfilled["uid-1"])[0]["canonical_id"] == "Q_SESU"

    def test_reapontamento_converge_em_uma_execucao(self):
        """Depois de re-sincronizar, a execução seguinte não muda nada (sem oscilar
        entre re-sincronizar e remover enquanto a sigla continua no alvo antigo)."""
        db, conn = self._sesu_ligada_ao_alvo_errado()
        db.alias[("secretaria de educacao superior", "ORG")] = "Q_SESU"
        J.link_sigla_fallbacks(conn)
        n_log = len(db.log)
        stats = J.link_sigla_fallbacks(conn)
        assert stats == {"linked": 0, "resynced": 0, "removed": 0, "skipped_resolved": 0}
        assert db.alias[(self.SESU, "ORG")] == "Q_SESU"
        writes = [s for (s, _p) in db.log[n_log:] if not s.lower().startswith("select")]
        assert writes == []

    def test_mover_base_e_sigla_juntas_resincroniza(self):
        db, conn = self._sesu_ligada_ao_alvo_errado()
        db.alias[("secretaria de educacao superior", "ORG")] = "Q_SESU"
        db.alias[("sesu", "ORG")] = "Q_SESU"
        stats = J.link_sigla_fallbacks(conn)
        assert stats["resynced"] == 1
        assert db.alias[(self.SESU, "ORG")] == "Q_SESU"

    def test_sigla_reapontada_sozinha_mantem_o_derivado_na_base(self):
        """O derivado acompanha a base; o conflito de sigla só barra a criação."""
        db, conn = self._sesu_ligada_ao_alvo_errado()
        db.alias[("sesu", "ORG")] = "Q_OUTRA"
        stats = J.link_sigla_fallbacks(conn)
        assert stats == {"linked": 0, "resynced": 0, "removed": 0, "skipped_resolved": 0}
        assert db.alias[(self.SESU, "ORG")] == "Q_UCR"

    def test_resync_atualiza_o_seen_da_forma_resolvida_pelo_derivado(self):
        """Forma resolvida (gazetteer) para o alvo antigo: a re-sincronização move também
        seen.entity_id, para que uma remoção futura a devolva à fila."""
        db, conn = self._sesu_ligada_ao_alvo_errado()
        form = "secretaria de educacao superior (s.esu)"
        db.seed_seen(form, "ORG", status="pending")
        J.link_sigla_fallbacks(conn)
        J.resolve_form(
            conn, form, "ORG", None, 0,
            bedrock_client=make_bedrock(canon_json()), wikidata_client=FakeWikidata(),
            model_id="m",
        )
        assert db.seen[(form, "ORG")]["entity_id"] == "Q_UCR"
        db.alias[("secretaria de educacao superior", "ORG")] = "Q_SESU"
        J.link_sigla_fallbacks(conn)
        assert db.alias[(form, "ORG")] == "Q_SESU"
        assert db.seen[(form, "ORG")]["status"] == "resolved"
        assert db.seen[(form, "ORG")]["entity_id"] == "Q_SESU"
        # a base perde o alias → o derivado sai e a forma volta à fila.
        del db.alias[("secretaria de educacao superior", "ORG")]
        J.link_sigla_fallbacks(conn)
        assert (form, "ORG") not in db.alias
        assert db.seen[(form, "ORG")]["status"] == "pending"
        assert db.seen[(form, "ORG")]["entity_id"] is None

    # -- formas resolved: não contrariar a decisão anterior (item 3) --

    def test_resolved_para_outra_entidade_nao_liga(self):
        db = FakeDB()
        db.seed_alias("procedimentos de distribuicao", "LAW", "Q_MODULO_11")
        form = "procedimentos de distribuicao (prodist)"
        db.seen[(form, "LAW")] = {
            "surface_norm": form, "type": "LAW", "status": "resolved",
            "entity_id": "dgb_prodist", "attempts": 1, "sample_unique_id": None,
        }
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats["linked"] == 0
        assert stats["skipped_resolved"] == 1
        assert (form, "LAW") not in db.alias

    def test_resolved_para_o_mesmo_alvo_liga(self):
        db = FakeDB()
        db.seed_alias("diario oficial da uniao", "ORG", "Q3712237")
        form = "diario oficial da uniao (dou)"
        db.seen[(form, "ORG")] = {
            "surface_norm": form, "type": "ORG", "status": "resolved",
            "entity_id": "Q3712237", "attempts": 1, "sample_unique_id": None,
        }
        stats = J.link_sigla_fallbacks(db.conn())
        assert stats["linked"] == 1
        assert stats["skipped_resolved"] == 0
        assert db.alias[(form, "ORG")] == "Q3712237"


class TestRunCanonicalizationSiglaFallback:
    def test_ponta_a_ponta_liga_mencao_antiga_sem_llm(self, monkeypatch):
        """needs_review antiga → alias derivado → Step C grava canonical_id na menção."""
        db = FakeDB()
        db.seed_alias("supremo tribunal federal", "ORG", "Q519138")
        db.seed_seen(STF, "ORG", status="needs_review")
        db.features_rows = [
            ("uid-1", {"entities": [
                {"text": "STF", "forma_canonica": "Supremo Tribunal Federal (STF)",
                 "type": "ORG", "count": 3},
            ]}),
        ]
        monkeypatch.setattr(J.psycopg2, "connect", lambda _url: db.conn())
        monkeypatch.delenv("BEDROCK_DAILY_TOKEN_QUOTA", raising=False)
        bedrock = make_bedrock(canon_json())
        result = J.run_canonicalization(
            "postgresql://fake", since="2026-01-01T00:00:00+00:00",
            until="2026-02-01T00:00:00+00:00", limit=10,
            bedrock_client=bedrock, wikidata_client=FakeWikidata(), model_id="m",
        )
        assert result["sigla_fallback"]["linked"] == 1
        assert result["backfill"]["mentions_linked"] == 1
        written = json.loads(db.backfilled["uid-1"])
        assert written[0]["canonical_id"] == "Q519138"
        bedrock.client.invoke_model.assert_not_called()

    def test_excecao_no_a2_nao_aborta_os_steps_b_e_c(self, monkeypatch, caplog):
        """Falha no fallback de sigla vai para o log; Step B e Step C rodam mesmo assim."""
        db = FakeDB()
        db.seed_alias("supremo tribunal federal", "ORG", "Q519138")
        db.seed_seen("finep", "ORG", sample_unique_id="uid-1")
        db.features_rows = [
            ("uid-1", {"entities": [
                {"text": "Supremo Tribunal Federal", "type": "ORG", "count": 1},
            ]}),
        ]
        conns = []

        def _connect(_url):
            conns.append(db.conn())
            return conns[-1]

        def _boom(conn, dry_run=False):
            raise RuntimeError("falha simulada no A2")

        monkeypatch.setattr(J.psycopg2, "connect", _connect)
        monkeypatch.setattr(J, "link_sigla_fallbacks", _boom)
        monkeypatch.delenv("BEDROCK_DAILY_TOKEN_QUOTA", raising=False)
        bedrock = make_bedrock(canon_json(not_an_entity=True))
        with caplog.at_level("ERROR"):
            result = J.run_canonicalization(
                "postgresql://fake", since="2026-01-01T00:00:00+00:00",
                until="2026-02-01T00:00:00+00:00", limit=10,
                bedrock_client=bedrock, wikidata_client=FakeWikidata(), model_id="m",
            )
        assert "falha simulada no A2" in result["sigla_fallback"]["error"]
        assert "falha simulada no A2" in caplog.text
        assert conns[0].rolled_back >= 1  # transação limpa antes do Step B
        assert result["resolve"]["total"] == 1  # Step B rodou
        assert result["backfill"]["mentions_linked"] == 1  # Step C rodou
        assert json.loads(db.backfilled["uid-1"])[0]["canonical_id"] == "Q519138"


# ---------------------------------------------------------------------- #
# Causa raiz: siglas soltas sugeridas pelo LLM e fusão Wikidata-wins     #
# ---------------------------------------------------------------------- #


def _wikidata_unico(qid, label, country="Q142"):
    return FakeWikidata(
        candidates_by_query={"*": [{"qid": qid, "label": label, "description": "x"}]},
        claims_by_qid={qid: {"country": country, "country_is_br": country == "Q155",
                             "instance_of": []}},
    )


class TestAliasesSugeridosPeloLlm:
    def _resolve_toulouse(self, db):
        db.content["uid"] = "Pesquisadores da Toulouse School of Economics (TSE)..."
        bedrock = make_bedrock(canon_json(
            canonical_name="Toulouse School of Economics", type="ORG", confidence=0.95,
            aliases=["TSE", "École d'Économie de Toulouse", "Toulouse School of Economics (TSE)",
                     "Toulouse"],
            wikidata_query="Toulouse School of Economics",
        ))
        return J.resolve_form(
            db.conn(), "toulouse school of economics", "ORG", "uid", 0,
            bedrock_client=bedrock, wikidata_client=_wikidata_unico("Q3532921", "TSE"),
            model_id="m",
        )

    def test_sigla_coerente_e_palavra_do_llm_viram_alias(self):
        """TSE é acrônimo coerente de Toulouse School of Economics e entra; "Toulouse" não
        é sigla e segue a regra anterior. A colisão com o Tribunal fica com a guarda de
        fusão (teste seguinte)."""
        db = FakeDB()
        decision = self._resolve_toulouse(db)
        assert decision["action"] == "link"
        assert db.alias[("toulouse school of economics", "ORG")] == "Q3532921"
        assert db.alias[("ecole d'economie de toulouse", "ORG")] == "Q3532921"
        assert db.alias[("toulouse school of economics (tse)", "ORG")] == "Q3532921"
        assert db.alias[("tse", "ORG")] == "Q3532921"
        assert db.alias[("toulouse", "ORG")] == "Q3532921"

    def _resolve(self, db, form, type_, qid, canonical_name, aliases):
        db.content["uid"] = f"Texto sobre {canonical_name}."
        bedrock = make_bedrock(canon_json(
            canonical_name=canonical_name, type=type_, confidence=0.95, aliases=aliases,
        ))
        return J.resolve_form(
            db.conn(), form, type_, "uid", 0, bedrock_client=bedrock,
            wikidata_client=_wikidata_unico(qid, canonical_name, "Q155"), model_id="m",
        )

    def test_sigla_incoerente_do_llm_nao_vira_alias(self):
        """Caso 'pis' → Cofins: PIS não é acrônimo de Contribuição para o Financiamento da
        Seguridade Social; nenhuma grafia de 'pis' entra. O resto entra."""
        db = FakeDB()
        self._resolve(
            db, "contribuicao para o financiamento da seguridade social (cofins)", "POLICY",
            "Q18481381", "Contribuição para o Financiamento da Seguridade Social (Cofins)",
            ["Cofins", "COFINS", "PIS", "pis",
             "Contribuição para o Financiamento da Seguridade Social"],
        )
        assert ("pis", "POLICY") not in db.alias
        assert db.alias[("cofins", "POLICY")] == "Q18481381"
        assert db.alias[("contribuicao para o financiamento da seguridade social", "POLICY")] == (
            "Q18481381"
        )

    def test_sigla_de_outra_entidade_nao_vira_alias(self):
        """Caso 'sc' → Carolina do Sul: SC (Santa Catarina) não sai de "Carolina do Sul"."""
        db = FakeDB()
        self._resolve(db, "carolina do sul", "LOC", "Q1456", "Carolina do Sul",
                      ["SC", "sc", "South Carolina", "Carolina do Sul"])
        assert ("sc", "LOC") not in db.alias
        assert db.alias[("south carolina", "LOC")] == "Q1456"

    def test_siglas_coerentes_do_llm_viram_alias(self):
        db = FakeDB()
        self._resolve(
            db, "politica nacional de desenvolvimento regional", "POLICY", "Q_PNDR",
            "Política Nacional de Desenvolvimento Regional (PNDR)", ["PNDR", "pndr"],
        )
        self._resolve(db, "imposto sobre bens e servicos", "POLICY", "Q_IBS",
                      "Imposto sobre Bens e Serviços", ["IBS"])
        self._resolve(db, "agencia nacional de vigilancia sanitaria", "ORG", "Q_ANVISA",
                      "Agência Nacional de Vigilância Sanitária", ["ANVISA", "Anvisa"])
        assert db.alias[("pndr", "POLICY")] == "Q_PNDR"
        assert db.alias[("ibs", "POLICY")] == "Q_IBS"
        assert db.alias[("anvisa", "ORG")] == "Q_ANVISA"

    def test_palavra_que_nao_e_sigla_segue_regra_anterior(self):
        """Nomes de uma palavra que não são sigla entram como em main, mesmo sem relação
        de acrônimo com o nome canônico."""
        db = FakeDB()
        self._resolve(db, "praia de copacabana", "LOC", "Q_COPA", "Praia de Copacabana",
                      ["Copacabana"])
        self._resolve(db, "empresa brasileira de correios e telegrafos", "ORG", "Q_ECT",
                      "Empresa Brasileira de Correios e Telégrafos (ECT)", ["Correios", "ECT"])
        self._resolve(db, "programa pe-de-meia", "POLICY", "Q_PDM", "Programa Pé-de-Meia",
                      ["Pé-de-Meia"])
        assert db.alias[("copacabana", "LOC")] == "Q_COPA"
        assert db.alias[("correios", "ORG")] == "Q_ECT"
        assert db.alias[("ect", "ORG")] == "Q_ECT"
        assert db.alias[("pe-de-meia", "POLICY")] == "Q_PDM"

    def test_sigla_do_llm_nao_funde_a_entidade_interna_que_ja_tem_a_sigla(self):
        """Caso TSE: 'tse' (menção real) já aponta para o Tribunal; a Toulouse não o absorve."""
        db = FakeDB()
        db.seed_registry("dgb_tse", "Tribunal Superior Eleitoral", "ORG")
        db.seed_alias("tse", "ORG", "dgb_tse")
        db.seed_alias("tribunal superior eleitoral", "ORG", "dgb_tse")
        self._resolve_toulouse(db)
        assert "dgb_tse" in db.registry
        assert db.alias[("tse", "ORG")] == "dgb_tse"
        assert db.alias[("tribunal superior eleitoral", "ORG")] == "dgb_tse"

    def test_nome_completo_do_llm_com_nome_incompativel_nao_funde(self):
        """Caso MRE: alias por extenso colide com a entidade interna; nomes incompatíveis."""
        db = FakeDB()
        db.seed_registry("dgb_mre", "Ministério das Relações Exteriores", "ORG")
        db.seed_alias("ministerio das relacoes exteriores", "ORG", "dgb_mre")
        db.seed_registry("Q1135605", "instituto rio branco", "ORG", wikidata_id="Q1135605")
        db.content["uid"] = "O Itamaraty e o Instituto Rio Branco..."
        bedrock = make_bedrock(canon_json(
            canonical_name="Ministério das Relações Exteriores (MRE)", type="ORG",
            confidence=0.95, aliases=["Ministério das Relações Exteriores", "MRE"],
            wikidata_query="Ministério das Relações Exteriores",
        ))
        J.resolve_form(
            db.conn(), "ministerio de relacoes exteriores (mre)", "ORG", "uid", 0,
            bedrock_client=bedrock,
            wikidata_client=_wikidata_unico("Q1135605", "Instituto Rio Branco", "Q155"),
            model_id="m",
        )
        assert "dgb_mre" in db.registry
        assert db.alias[("ministerio das relacoes exteriores", "ORG")] == "dgb_mre"

    def test_sigla_que_e_a_propria_forma_continua_sendo_gravada(self):
        """A sigla entra quando vem de menção real (a forma resolvida), não do LLM."""
        db = FakeDB()
        db.content["uid"] = "O TSE divulgou..."
        bedrock = make_bedrock(canon_json(
            canonical_name="Tribunal Superior Eleitoral", type="ORG", confidence=0.95,
            aliases=["TSE", "Tribunal Superior Eleitoral"],
            wikidata_query="Tribunal Superior Eleitoral",
        ))
        J.resolve_form(
            db.conn(), "tse", "ORG", "uid", 0, bedrock_client=bedrock,
            wikidata_client=_wikidata_unico("Q3656204", "Tribunal Superior Eleitoral", "Q155"),
            model_id="m",
        )
        assert db.alias[("tse", "ORG")] == "Q3656204"
        assert db.alias[("tribunal superior eleitoral", "ORG")] == "Q3656204"
