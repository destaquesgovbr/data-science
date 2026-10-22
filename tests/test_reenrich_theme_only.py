"""
Testes da reclassificação SÓ de tema (scripts/reenrich_combined_window.py
--theme-only), para o tema 26 "Defesa Civil e Gestão de Desastres" (DS-1).

Seleções novas:
  - `--select theme-code --theme-code <código>`: artigos com qualquer nível de
    tema (l1/l2/l3/mais específico) na subárvore do código;
  - `--select theme26-candidates`: L1 19, mais artigos em 04 / 05.02.01 /
    15.02.03 que sejam do MDR ou tenham termo-chave no título/conteúdo.

Modo --theme-only: a mesma chamada combinada do worker, mas grava SÓ os ids de
tema (nunca resumo, sentimento ou NER), com guarda do tema antigo no UPDATE e
registro na auditoria `news_theme_changes` (migração 034 do data-platform),
na mesma transação. Idempotente por campanha. Bedrock mockado; Postgres via
tests/fakedb.py.
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
USAGE = {"input_tokens": 19000, "output_tokens": 300}
TODAY_BRT = datetime.date(2026, 11, 11)
CAMPAIGN = "tema26-llm-d1"
WINDOW = ["--date-from", "2023-01-01"]

# Taxonomia do banco depois da 034 (19.03/19.04 viraram 26.01/26.02).
CODE_TO_ID = {
    "01": 30,
    "01.02": 31,
    "01.02.03": 32,
    "04": 1,
    "04.03": 2,
    "04.03.01": 3,
    "05": 4,
    "05.02": 5,
    "05.02.01": 6,
    "05.02.02": 25,
    "15": 7,
    "15.02": 8,
    "15.02.03": 9,
    "19": 10,
    "19.01": 11,
    "19.01.01": 12,
    "19.05": 13,
    "19.05.01": 14,
    "26": 20,
    "26.01": 21,
    "26.01.03": 22,
    "26.02": 23,
    "26.02.01": 24,
}
AUDIT_COLUMNS = {
    "campaign",
    "unique_id",
    "old_l1_code",
    "old_l2_code",
    "old_l3_code",
    "old_most_specific_code",
    "new_l1_code",
    "new_l2_code",
    "new_l3_code",
    "new_most_specific_code",
    "source",
    "changed_at",
}
# Tabela da 034 (contrato final de 22/10): as 12 colunas exigidas mais id, note e
# reverted_at (aceitas como extras; usadas quando existem).
CONTRACT_COLUMNS = AUDIT_COLUMNS | {"id", "note", "reverted_at"}
SOURCE = f"llm:{HAIKU45}"
EOL_ERROR = (
    "ResourceNotFoundException: This model version has reached the end of its life. "
    "Please refer to the AWS documentation for more details."
)


def _taxonomy(codes):
    """Árvore no formato de load_taxonomy_from_postgres a partir dos códigos."""
    tree = {}
    for code in sorted(codes):
        parts = code.split(".")
        if len(parts) == 1:
            tree[code] = {"label": f"L {code}", "subcategories": {}}
        elif len(parts) == 2:
            tree[parts[0]]["subcategories"][code] = {"label": f"L {code}", "subcategories": {}}
        else:
            l2 = ".".join(parts[:2])
            tree[parts[0]]["subcategories"][l2]["subcategories"][code] = {"label": f"L {code}"}
    return tree


TAXONOMY = _taxonomy(CODE_TO_ID)


def _ids(*codes):
    """kwargs de seed_news com os ids de tema (l1, l2, l3 e mais específico)."""
    keys = ("theme_l1_id", "theme_l2_id", "theme_l3_id")
    kw = {k: CODE_TO_ID[c] for k, c in zip(keys, codes) if c}
    kw["most_specific_theme_id"] = CODE_TO_ID[[c for c in codes if c][-1]]
    return kw


def _result(l1, l2, l3, most_specific=None, **extra):
    result = {
        "theme_1_level_1": f"L {l1}" if l1 else None,
        "theme_1_level_1_code": l1,
        "theme_1_level_1_label": f"L {l1}" if l1 else None,
        "theme_1_level_2_code": l2,
        "theme_1_level_2_label": f"L {l2}" if l2 else None,
        "theme_1_level_3_code": l3,
        "theme_1_level_3_label": f"L {l3}" if l3 else None,
        "most_specific_theme_code": most_specific
        if most_specific is not None
        else (l3 or l2 or l1),
        "most_specific_theme_label": "x",
        "summary": "Resumo NOVO que nunca deve ser gravado.",
        "sentiment": {"label": "negative", "score": -0.4},
        "_usage": dict(USAGE),
        "_model_id": HAIKU45,
        "_error": None,
    }
    result.update(extra)
    return result


TO_26 = _result("26", "26.01", "26.01.03")


@pytest.fixture(scope="module")
def rec():
    spec = importlib.util.spec_from_file_location("reenrich_combined_window", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(monkeypatch, rec):
    db = FakeDB()
    db.seed_themes(CODE_TO_ID)
    db.theme_changes_columns = set(CONTRACT_COLUMNS)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("ENRICHMENT_MODEL_ID", HAIKU45)
    monkeypatch.delenv("BEDROCK_DAILY_TOKEN_QUOTA", raising=False)
    monkeypatch.delenv("BACKFILL_QUOTA_FRACTION", raising=False)
    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: db.conn())
    monkeypatch.setattr(rec, "_today_brt", lambda: TODAY_BRT, raising=False)

    clf = MagicMock()
    clf.llm_client.model_id = HAIKU45
    clf.llm_client.taxonomy = TAXONOMY
    clf.classify_single.side_effect = lambda article, return_format="dict": dict(TO_26)
    monkeypatch.setattr(handler, "_get_classifier", lambda: clf)
    monkeypatch.setattr(handler, "_get_code_to_id", lambda: dict(CODE_TO_ID))
    monkeypatch.setattr(
        handler, "fetch_article", lambda uid: {"unique_id": uid, "title": "T", "content": "C"}
    )
    publish = MagicMock()
    monkeypatch.setattr(handler, "publish_enriched_event", publish)
    upsert = MagicMock()
    monkeypatch.setattr(handler, "_upsert_ai_features", upsert)
    update_enrichment = MagicMock()
    monkeypatch.setattr(rec, "update_news_enrichment", update_enrichment)
    return SimpleNamespace(
        db=db, clf=clf, publish=publish, upsert=upsert, update_enrichment=update_enrichment
    )


def _process(rec, campaign=CAMPAIGN, audit_columns=CONTRACT_COLUMNS):
    return rec.make_theme_only_process(
        campaign=campaign,
        source=SOURCE,
        code_to_id=dict(CODE_TO_ID),
        parents=rec.build_theme_parents(TAXONOMY),
        audit=rec.AuditSchema.from_columns(audit_columns),
    )


def _run(rec, uids, campaign=CAMPAIGN, audit_columns=CONTRACT_COLUMNS, **kw):
    params = dict(model_id=HAIKU45, daily_quota=None, quota_fraction=0.8, workers=1)
    params.update(kw)
    return rec.run_reenrich(uids, process=_process(rec, campaign, audit_columns), **params)


def _norm(sql):
    return " ".join(sql.split()).lower()


def _news_updates(db):
    return [(sql.lower(), p) for sql, p in db.log if sql.lower().startswith("update news ")]


def _audit(db, uid):
    rows = [r for r in db.theme_changes if r["unique_id"] == uid]
    assert len(rows) == 1, rows
    return rows[0]


# ---------------------------------------------------------------------- #
# SQL das seleções                                                       #
# ---------------------------------------------------------------------- #


class TestSelectSqlTema:
    _THEME_EXISTS = (
        "exists ( select 1 from themes t where t.id in "
        "(n.theme_l1_id, n.theme_l2_id, n.theme_l3_id, n.most_specific_theme_id)"
    )
    # Idempotência: sai da seleção o artigo auditado na campanha e NÃO revertido (o
    # rollback da 034 marca reverted_at; o artigo revertido volta a ser candidato).
    _NOT_AUDITED = (
        "not exists ( select 1 from news_theme_changes c "
        "where c.campaign = %(campaign)s and c.unique_id = n.unique_id "
        "and c.reverted_at is null )"
    )
    _NOT_AUDITED_SEM_REVERTED_AT = (
        "not exists ( select 1 from news_theme_changes c "
        "where c.campaign = %(campaign)s and c.unique_id = n.unique_id )"
    )

    def test_auditoria_sem_reverted_at_exclui_todo_auditado(self, rec):
        # Tabela só com as 12 colunas exigidas: nenhuma linha é "revertida".
        for select in ("theme-code", "theme26-candidates"):
            sql = _norm(
                rec.build_select_sql(select, with_date_to=False, audit_has_reverted_at=False)
            )
            assert self._NOT_AUDITED_SEM_REVERTED_AT in sql
            assert "reverted_at" not in sql

    def test_theme_code(self, rec):
        sql = _norm(rec.build_select_sql("theme-code", with_date_to=False))
        assert sql.startswith("select n.unique_id from news n where")
        assert self._THEME_EXISTS in sql
        assert "and (t.code = %(theme_code)s or t.code like %(theme_prefix)s)" in sql
        assert self._NOT_AUDITED in sql
        assert "n.published_at >= (%(date_from)s::date::timestamp at time zone" in sql
        assert "date_to" not in sql  # --date-to é opcional nas seleções de tema
        assert "order by n.published_at desc" in sql
        assert "limit %(limit)s" in sql
        assert "agency_key" not in sql and "ilike" not in sql

    def test_theme_code_params(self, rec):
        params = rec.build_select_params(
            "theme-code", "2023-01-01", None, 50, theme_code="19", campaign=CAMPAIGN
        )
        assert params == {
            "date_from": "2023-01-01",
            "limit": 50,
            "theme_code": "19",
            "theme_prefix": "19.%",
            "campaign": CAMPAIGN,
        }

    # WHERE completo: ((bloco 19) OR (bloco extra AND (MDR OR termos))) AND NOT EXISTS
    # AND janela. Igualdade exata: troca de precedência AND/OR, NOT EXISTS preso a um
    # só ramo do OR ou janela fora do lugar quebram este teste.
    _THEMES_OF = (
        "select 1 from themes t where t.id in "
        "(n.theme_l1_id, n.theme_l2_id, n.theme_l3_id, n.most_specific_theme_id)"
    )
    _WINDOW = (
        "n.published_at >= (%(date_from)s::date::timestamp at time zone 'america/sao_paulo') "
        "and n.published_at < (%(date_to)s::date::timestamp at time zone 'america/sao_paulo')"
    )

    def _expected_theme26(self, term_clause):
        return (
            "select n.unique_id from news n where ( exists ( "
            + self._THEMES_OF
            + " and (t.code = %(theme_code)s or t.code like %(theme_prefix)s) ) or ( exists ( "
            + self._THEMES_OF
            + " and (t.code = any(%(extra_codes)s::text[]) "
            "or t.code like any(%(extra_prefixes)s::text[])) ) and ("
            + term_clause
            + ") ) ) and "
            + self._NOT_AUDITED
            + " and "
            + self._WINDOW
            + " order by n.published_at desc limit %(limit)s"
        )

    def test_theme26_candidates_estrutura_completa_do_where(self, rec):
        sql = _norm(rec.build_select_sql("theme26-candidates", with_date_to=True))
        assert sql == self._expected_theme26(
            "n.agency_key = any(%(agency_keys)s::text[]) "
            "or n.title ilike any(%(term_patterns)s::text[])"
        )

    def test_theme26_termos_no_titulo_e_no_conteudo(self, rec):
        sql = _norm(
            rec.build_select_sql(
                "theme26-candidates", with_date_to=True, term_fields="title-content"
            )
        )
        assert sql == self._expected_theme26(
            "n.agency_key = any(%(agency_keys)s::text[]) "
            "or n.title ilike any(%(term_patterns)s::text[]) "
            "or n.content ilike any(%(term_patterns)s::text[])"
        )

    def test_campo_de_busca_padrao_e_so_o_titulo(self, rec):
        assert rec.DEFAULT_TERM_FIELDS == "title"
        sql = _norm(rec.build_select_sql("theme26-candidates", with_date_to=False))
        assert "n.content" not in sql

    def test_campo_de_busca_invalido(self, rec):
        with pytest.raises(ValueError, match="term_fields"):
            rec.build_select_sql("theme26-candidates", with_date_to=False, term_fields="resumo")

    def test_theme26_params(self, rec):
        params = rec.build_select_params(
            "theme26-candidates", "2023-01-01", "2026-11-11", 10, campaign=CAMPAIGN
        )
        assert params["theme_code"] == "19"
        assert params["theme_prefix"] == "19.%"
        assert params["extra_codes"] == ["04", "05.02.01", "15.02.03"]
        assert params["extra_prefixes"] == ["04.%", "05.02.01.%", "15.02.03.%"]
        assert params["agency_keys"] == ["mdr"]
        for term in (
            "defesa civil",
            "calamidade",
            "situação de emergência",
            "estado de emergência",
            "desastre",
        ):
            assert f"%{term}%" in params["term_patterns"]
        # Sem unaccent no banco: as variantes sem acento entram também.
        assert "%situacao de emergencia%" in params["term_patterns"]
        assert "%estado de emergencia%" in params["term_patterns"]
        assert params["campaign"] == CAMPAIGN
        assert params["date_to"] == "2026-11-11"

    @pytest.mark.parametrize(
        "extra, codes, prefixes",
        [
            (("04",), ["04"], ["04.%"]),
            (("04", "05.02.01"), ["04", "05.02.01"], ["04.%", "05.02.01.%"]),
            ((), [], []),
        ],
    )
    def test_theme26_codigos_extras_configuraveis(self, rec, extra, codes, prefixes):
        params = rec.build_select_params(
            "theme26-candidates", "2023-01-01", None, 10, campaign=CAMPAIGN, extra_codes=extra
        )
        assert params["extra_codes"] == codes
        assert params["extra_prefixes"] == prefixes

    def test_selecoes_de_tema_exigem_campanha(self, rec):
        with pytest.raises(ValueError, match="campanha"):
            rec.build_select_params("theme26-candidates", "2023-01-01", None, 10)

    def test_theme_code_exige_codigo(self, rec):
        with pytest.raises(ValueError, match="theme-code"):
            rec.build_select_params("theme-code", "2023-01-01", None, 10, campaign=CAMPAIGN)


# ---------------------------------------------------------------------- #
# Seleção sobre o banco fake                                             #
# ---------------------------------------------------------------------- #


class TestSelecao:
    def test_theme_code_pega_a_subarvore_em_qualquer_nivel(self, rec, env):
        db = env.db
        db.seed_news("l1-so", "2026-10-01", **_ids("19"))
        db.seed_news("l3", "2026-10-02", **_ids("19", "19.05", "19.05.01"))
        # Hierarquia inconsistente: só o L3 está no 19.
        db.seed_news("inconsistente", "2026-10-03", **_ids("15", "15.02", "19.01.01"))
        db.seed_news("ja-26", "2026-10-04", **_ids("26", "26.01", "26.01.03"))
        db.seed_news("outro", "2026-10-05", **_ids("01", "01.02", "01.02.03"))
        db.seed_news("sem-tema", "2026-10-06")

        uids = rec.get_window_uids(
            "theme-code", "2023-01-01", None, 100, theme_code="19", campaign=CAMPAIGN
        )

        assert uids == ["inconsistente", "l3", "l1-so"]

    def test_theme_code_exclui_os_ja_auditados_na_campanha(self, rec, env):
        env.db.seed_news("feito", "2026-10-01", **_ids("19"))
        env.db.seed_news("feito-em-outra", "2026-10-02", **_ids("19"))
        env.db.seed_news("pendente", "2026-10-03", **_ids("19"))
        env.db.theme_changes += [
            {"campaign": CAMPAIGN, "unique_id": "feito"},
            {"campaign": "outra", "unique_id": "feito-em-outra"},
        ]

        uids = rec.get_window_uids(
            "theme-code", "2023-01-01", None, 100, theme_code="19", campaign=CAMPAIGN
        )

        assert uids == ["pendente", "feito-em-outra"]

    def test_auditado_e_revertido_volta_a_ser_candidato(self, rec, env):
        env.db.seed_news("feito", "2026-10-01", **_ids("19"))
        env.db.seed_news("revertido", "2026-10-02", **_ids("19"))
        env.db.theme_changes += [
            {"campaign": CAMPAIGN, "unique_id": "feito", "reverted_at": None},
            {"campaign": CAMPAIGN, "unique_id": "revertido", "reverted_at": "2026-11-12"},
        ]

        uids = rec.get_window_uids(
            "theme-code", "2023-01-01", None, 100, theme_code="19", campaign=CAMPAIGN
        )

        assert uids == ["revertido"]

    @staticmethod
    def _seed_theme26_corpus(db):
        db.seed_news("l1-19", "2026-10-01", agency_key="defesa", **_ids("19", "19.05", "19.05.01"))
        db.seed_news("mdr-04", "2026-10-02", agency_key="mdr", **_ids("04", "04.03", "04.03.01"))
        db.seed_news(
            "titulo-05",
            "2026-10-03",
            agency_key="mma",
            title="Defesa Civil alerta para chuvas",
            **_ids("05", "05.02", "05.02.01"),
        )
        db.seed_news(
            "conteudo-15",
            "2026-10-04",
            agency_key="mds",
            content="O município decretou situação de emergência.",
            **_ids("15", "15.02", "15.02.03"),
        )
        db.seed_news(
            "maiusculas-04",
            "2026-10-05",
            agency_key="agencia-brasil",
            content="ESTADO DE CALAMIDADE PÚBLICA",
            **_ids("04"),
        )
        db.seed_news(
            "desastres-04",
            "2026-10-06",
            agency_key="agencia-brasil",
            title="Resposta a desastres naturais",
            **_ids("04", "04.03", "04.03.01"),
        )
        # Fora:
        db.seed_news("04-sem-termo", "2026-10-07", agency_key="mj", **_ids("04", "04.03"))
        db.seed_news(
            "mdr-05-irmao", "2026-10-08", agency_key="mdr", **_ids("05", "05.02", "05.02.02")
        )
        db.seed_news(
            "termo-fora",
            "2026-10-09",
            title="Desastre ambiental",
            **_ids("01", "01.02", "01.02.03"),
        )
        db.seed_news("ja-26", "2026-10-10", agency_key="mdr", **_ids("26", "26.01", "26.01.03"))
        db.seed_news("sem-tema", "2026-10-11", agency_key="mdr", title="Defesa Civil")
        db.seed_news("auditado", "2026-10-12", **_ids("19"))
        db.seed_news("auditado-mdr-04", "2026-10-13", agency_key="mdr", **_ids("04"))
        db.theme_changes += [
            {"campaign": CAMPAIGN, "unique_id": "auditado"},
            {"campaign": CAMPAIGN, "unique_id": "auditado-mdr-04"},
        ]

    def test_theme26_candidates_termo_so_no_titulo_por_padrao(self, rec, env):
        self._seed_theme26_corpus(env.db)

        uids = rec.get_window_uids("theme26-candidates", "2023-01-01", None, 100, campaign=CAMPAIGN)

        # "maiusculas-04" e "conteudo-15" têm o termo só no conteúdo: ficam de fora.
        assert uids == ["desastres-04", "titulo-05", "mdr-04", "l1-19"]

    def test_theme26_candidates_termo_no_titulo_e_no_conteudo(self, rec, env):
        self._seed_theme26_corpus(env.db)

        uids = rec.get_window_uids(
            "theme26-candidates",
            "2023-01-01",
            None,
            100,
            campaign=CAMPAIGN,
            term_fields="title-content",
        )

        assert uids == [
            "desastres-04",
            "maiusculas-04",
            "conteudo-15",
            "titulo-05",
            "mdr-04",
            "l1-19",
        ]

    def test_theme26_candidates_sem_codigos_extras_e_so_o_19(self, rec, env):
        self._seed_theme26_corpus(env.db)

        uids = rec.get_window_uids(
            "theme26-candidates", "2023-01-01", None, 100, campaign=CAMPAIGN, extra_codes=()
        )

        assert uids == ["l1-19"]


# ---------------------------------------------------------------------- #
# Cadeia de tema (hierarquia consistente a partir da resposta)           #
# ---------------------------------------------------------------------- #


class TestCadeiaDeTema:
    @pytest.fixture
    def parents(self, rec):
        return rec.build_theme_parents(TAXONOMY)

    def test_parents_da_taxonomia(self, parents):
        assert parents["26"] is None
        assert parents["26.01"] == "26"
        assert parents["26.01.03"] == "26.01"
        assert "19.03" not in parents

    def test_resposta_consistente(self, rec, parents):
        assert rec.resolve_theme_chain(TO_26, parents) == ("26", "26.01", "26.01.03", "26.01.03")

    def test_l1_e_l2_inconsistentes_seguem_o_mais_profundo(self, rec, parents):
        result = _result("04", "26.02", "26.01.03")
        assert rec.resolve_theme_chain(result, parents) == ("26", "26.01", "26.01.03", "26.01.03")

    # Regra do fallback (MAX_LEVEL_DROP = 1): vale o código válido mais profundo da
    # resposta, mas ele pode estar no máximo UM nível acima do mais profundo que o LLM
    # pediu. Cair mais que isso (ex.: pediu um L3, só o L1 existe) é resposta
    # inválida: nada é gravado nem auditado e o artigo volta no próximo run.
    def test_regra_de_fallback_documentada(self, rec):
        assert rec.MAX_LEVEL_DROP == 1
        assert "MAX_LEVEL_DROP" in rec.resolve_theme_chain.__doc__

    @pytest.mark.parametrize(
        "resposta, esperado",
        [
            # L3 pedido inexistente, L2 válido: cai um nível.
            (("26", "26.01", "26.01.09"), ("26", "26.01", None, "26.01")),
            # L2 pedido inexistente (sem L3): cai um nível, para o L1.
            (("26", "26.07", None), ("26", None, None, "26")),
            # L3 pedido, só o L1 válido: cairia dois níveis → inválida.
            (("19", "19.03", "19.03.03"), None),
            (("26", "26.07", "26.07.01"), None),
            # O nível acima de um código inexistente é o prefixo dele, mesmo quando o
            # LLM não preencheu o campo do L2.
            ((None, None, "26.01.09"), ("26", "26.01", None, "26.01")),
            (("26", None, "26.01.09"), ("26", "26.01", None, "26.01")),
            ((None, "26.07", None), ("26", None, None, "26")),
            # Prefixo também inexistente: cairia dois níveis → inválida.
            ((None, None, "26.07.01"), None),
        ],
    )
    def test_cai_no_maximo_um_nivel(self, rec, parents, resposta, esperado):
        assert rec.resolve_theme_chain(_result(*resposta), parents) == esperado

    def test_codigo_valido_explicito_vence_o_prefixo_no_empate(self, rec, parents):
        # L2 válido escolhido pelo LLM (04.03) e L3 inexistente de outro ramo
        # (26.01.09 → 26.01): mesma profundidade, vale o código explícito.
        result = _result("04", "04.03", "26.01.09")
        assert rec.resolve_theme_chain(result, parents) == ("04", "04.03", None, "04.03")

    def test_codigo_mal_formado_e_ignorado(self, rec, parents):
        result = _result("26", "Defesa Civil", "26.01.03")
        assert rec.resolve_theme_chain(result, parents) == ("26", "26.01", "26.01.03", "26.01.03")

    def test_l3_inexistente_cai_para_o_l2(self, rec, parents):
        # 19.03.03 não existe mais depois da 034.
        result = _result("26", "26.01", "19.03.03")
        assert rec.resolve_theme_chain(result, parents) == ("26", "26.01", None, "26.01")

    def test_codigo_l2_no_campo_l3(self, rec, parents):
        result = _result("26", None, "26.02")
        assert rec.resolve_theme_chain(result, parents) == ("26", "26.02", None, "26.02")

    def test_mais_especifico_l3_sem_campo_l3(self, rec, parents):
        result = _result("26", "26.02", None, most_specific="26.02.01")
        assert rec.resolve_theme_chain(result, parents) == ("26", "26.02", "26.02.01", "26.02.01")

    def test_so_l1(self, rec, parents):
        assert rec.resolve_theme_chain(_result("19", None, None), parents) == (
            "19",
            None,
            None,
            "19",
        )

    def test_nenhum_codigo_valido(self, rec, parents):
        result = _result("19.03", "19.03.03", "99.01.01")
        assert rec.resolve_theme_chain(result, parents) is None
        assert rec.resolve_theme_chain(_result(None, None, None), parents) is None


# ---------------------------------------------------------------------- #
# Fluxo por artigo                                                       #
# ---------------------------------------------------------------------- #


class TestFluxoThemeOnly:
    def _seed_19(self, db, *uids, summary="Resumo antigo."):
        for uid in uids:
            db.seed_news(uid, "2026-10-01", summary=summary, **_ids("19", "19.05", "19.05.01"))

    def test_grava_so_os_ids_de_tema_e_audita(self, rec, env):
        self._seed_19(env.db, "u1")

        stats = _run(rec, ["u1"])

        assert stats["ok"] == 1
        news = env.db.news["u1"]
        assert (
            news["theme_l1_id"],
            news["theme_l2_id"],
            news["theme_l3_id"],
            news["most_specific_theme_id"],
        ) == (20, 21, 22, 22)
        assert news["summary"] == "Resumo antigo."
        assert _audit(env.db, "u1") == {
            "campaign": CAMPAIGN,
            "unique_id": "u1",
            "old_l1_code": "19",
            "old_l2_code": "19.05",
            "old_l3_code": "19.05.01",
            "old_most_specific_code": "19.05.01",
            "new_l1_code": "26",
            "new_l2_code": "26.01",
            "new_l3_code": "26.01.03",
            "new_most_specific_code": "26.01.03",
            "source": SOURCE,
            "note": "ok: reclassificado pelo LLM",
        }

    def test_insert_da_auditoria_com_upsert_so_sobre_linha_revertida(self, rec, env):
        self._seed_19(env.db, "u1")

        _run(rec, ["u1"])

        [insert] = [
            _norm(sql)
            for sql, _ in env.db.log
            if sql.lower().startswith("insert into news_theme_changes")
        ]
        assert "on conflict (campaign, unique_id) do update set" in insert
        assert "reverted_at = null" in insert
        assert "where news_theme_changes.reverted_at is not null" in insert
        assert insert.endswith("returning 1")

    def test_update_com_guarda_do_tema_antigo_e_sem_resumo(self, rec, env):
        self._seed_19(env.db, "u1")

        _run(rec, ["u1"])

        [(sql, params)] = _news_updates(env.db)
        sql = _norm(sql)
        assert sql.startswith("update news set theme_l1_id = %(new_l1)s")
        assert "updated_at = now()" in sql
        assert "where unique_id = %(unique_id)s" in sql
        for col, old in (
            ("theme_l1_id", "old_l1"),
            ("theme_l2_id", "old_l2"),
            ("theme_l3_id", "old_l3"),
            ("most_specific_theme_id", "old_most_specific"),
        ):
            assert f"and {col} is not distinct from %({old})s" in sql
        assert "summary" not in sql
        assert "embedding" not in sql
        assert params["old_l1"] == 10 and params["new_l1"] == 20

    def test_nunca_resumo_sentimento_ner_nem_evento(self, rec, env):
        self._seed_19(env.db, "u1", "u2")

        stats = _run(rec, ["u1", "u2"])

        assert stats["ok"] == 2
        assert env.clf.classify_single.call_count == 2
        env.clf.llm_client.extract_entities.assert_not_called()
        env.clf.llm_client.summarize_single.assert_not_called()
        env.update_enrichment.assert_not_called()  # caminho que grava o resumo
        env.upsert.assert_not_called()  # sentimento/entidades em news_features
        env.publish.assert_not_called()
        assert env.db.features_upserts == []
        assert env.db.llm_raw == []
        assert env.db.news["u1"]["summary"] == "Resumo antigo."

    def test_registra_usage_no_ledger(self, rec, env):
        self._seed_19(env.db, "u1", "u2")

        _run(rec, ["u1", "u2"])

        assert env.db.ledger == {HAIKU45: {"input_tokens": 38000, "output_tokens": 600}}

    def test_hierarquia_da_resposta_e_normalizada(self, rec, env):
        self._seed_19(env.db, "u1")
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            "04", "26.02", "26.01.03"
        )

        _run(rec, ["u1"])

        assert _audit(env.db, "u1")["new_l1_code"] == "26"
        assert _audit(env.db, "u1")["new_l2_code"] == "26.01"
        assert env.db.news["u1"]["theme_l2_id"] == 21

    def test_tema_alterado_no_meio_do_run_nao_e_sobrescrito(self, rec, env):
        self._seed_19(env.db, "u1")

        def _classify_and_race(article, return_format="dict"):
            # Outro processo muda o tema entre a leitura e o UPDATE.
            env.db.news["u1"].update(_ids("01", "01.02", "01.02.03"))
            return dict(TO_26)

        env.clf.classify_single.side_effect = _classify_and_race

        stats = _run(rec, ["u1"])

        assert stats["theme_changed"] == 1
        assert "ok" not in stats
        assert env.db.news["u1"]["theme_l1_id"] == 30
        assert env.db.theme_changes == []
        assert env.db.ledger[HAIKU45] == USAGE  # tokens gastos contam

    def test_sem_mudanca_audita_sem_update(self, rec, env):
        env.db.seed_news("u1", "2026-10-01", **_ids("26", "26.01", "26.01.03"))

        stats = _run(rec, ["u1"])

        assert stats["unchanged"] == 1
        assert _news_updates(env.db) == []
        row = _audit(env.db, "u1")
        assert row["old_most_specific_code"] == row["new_most_specific_code"] == "26.01.03"
        assert row["note"] == "unchanged: o LLM manteve o tema"

    def test_sem_mudanca_confere_o_tema_atual_antes_de_auditar(self, rec, env):
        env.db.seed_news("u1", "2026-10-01", **_ids("26", "26.01", "26.01.03"))

        _run(rec, ["u1"])

        [check] = [
            _norm(sql) for sql, _ in env.db.log if sql.lower().startswith("select 1 from news")
        ]
        assert "most_specific_theme_id is not distinct from %(old_most_specific)s" in check
        assert check.endswith("for update")

    def test_sem_mudanca_com_tema_alterado_no_meio_do_run(self, rec, env):
        env.db.seed_news("u1", "2026-10-01", **_ids("26", "26.01", "26.01.03"))

        def _classify_and_race(article, return_format="dict"):
            env.db.news["u1"].update(_ids("01", "01.02", "01.02.03"))
            return dict(TO_26)

        env.clf.classify_single.side_effect = _classify_and_race

        stats = _run(rec, ["u1"])

        assert stats["theme_changed"] == 1
        assert env.db.theme_changes == []
        assert _news_updates(env.db) == []

    def test_id_de_tema_antigo_fora_do_mapa_nao_grava(self, rec, env):
        env.db.seed_news("u1", "2026-10-01", theme_l1_id=999, most_specific_theme_id=999)

        stats = _run(rec, ["u1"])

        assert stats["unknown_old_theme"] == 1
        assert _news_updates(env.db) == []
        assert env.db.theme_changes == []

    def test_artigo_que_perdeu_o_tema_nao_ganha_tema_aqui(self, rec, env):
        # Sem tema, o artigo é do worker ao vivo (NER + evento); este script não o toca.
        env.db.seed_news("u1", "2026-10-01")

        stats = _run(rec, ["u1"])

        assert stats["no_theme"] == 1
        env.clf.classify_single.assert_not_called()
        assert _news_updates(env.db) == []
        assert env.db.theme_changes == []

    def test_tema_invalido_nao_grava_nem_audita(self, rec, env):
        self._seed_19(env.db, "u1")
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            "19", "19.03", "19.03.03"
        )

        stats = _run(rec, ["u1"])

        assert stats["invalid_theme"] == 1
        assert _news_updates(env.db) == []
        assert env.db.theme_changes == []
        assert env.db.ledger[HAIKU45] == USAGE

    def test_falha_da_combinada_nao_grava(self, rec, env):
        self._seed_19(env.db, "u1", "u2")
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            None, None, None, _error="ThrottlingException: Rate exceeded"
        )

        stats = _run(rec, ["u1", "u2"])

        assert stats["classification_failed"] == 2
        assert stats["model_unavailable"] is False
        assert _news_updates(env.db) == []
        assert env.db.theme_changes == []

    def test_modelo_indisponivel_aborta(self, rec, env):
        self._seed_19(env.db, "u1", "u2", "u3")
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            None, None, None, _error=EOL_ERROR
        )

        stats = _run(rec, ["u1", "u2", "u3"])

        assert stats["model_unavailable"] is True
        assert env.clf.classify_single.call_count == 1

    def test_ja_auditado_por_run_concorrente_desfaz_o_update(self, rec, env):
        # Mesma campanha já registrada (não revertida) por um run concorrente: o
        # ON CONFLICT não devolve linha e o UPDATE é desfeito.
        self._seed_19(env.db, "u1")
        env.db.theme_changes.append(
            {"campaign": CAMPAIGN, "unique_id": "u1", "source": SOURCE, "reverted_at": None}
        )

        stats = _run(rec, ["u1"])

        assert stats["already_audited"] == 1
        assert "ok" not in stats
        assert env.db.news["u1"]["theme_l1_id"] == 10  # UPDATE desfeito (rollback)
        assert env.db.rollbacks >= 1
        assert env.db.theme_changes == [
            {"campaign": CAMPAIGN, "unique_id": "u1", "source": SOURCE, "reverted_at": None}
        ]
        assert env.db.ledger[HAIKU45] == USAGE  # tokens gastos contam

    def test_falha_na_auditoria_desfaz_o_update(self, rec, env):
        # Tabela removida no meio do run: o INSERT falha e o UPDATE é desfeito.
        self._seed_19(env.db, "u1")
        env.db.theme_changes_columns = None

        stats = _run(rec, ["u1"])

        assert stats["error"] == 1
        assert env.db.news["u1"]["theme_l1_id"] == 10  # UPDATE desfeito (rollback)
        assert env.db.rollbacks >= 1

    def test_linha_revertida_e_reaproveitada(self, rec, env):
        # Rollback da 034 marcou reverted_at: o artigo volta à seleção e a nova
        # gravação reaproveita a linha (UNIQUE (campaign, unique_id)).
        self._seed_19(env.db, "u1")
        env.db.theme_changes.append(
            {
                "campaign": CAMPAIGN,
                "unique_id": "u1",
                "old_l1_code": "04",
                "new_l1_code": "26",
                "source": SOURCE,
                "note": "ok: reclassificado pelo LLM",
                "reverted_at": "2026-11-12T10:00:00Z",
            }
        )

        stats = _run(rec, ["u1"])

        assert stats["ok"] == 1
        row = _audit(env.db, "u1")
        assert row["reverted_at"] is None
        assert (row["old_l1_code"], row["new_l1_code"]) == ("19", "26")
        assert env.db.news["u1"]["theme_l1_id"] == 20

    def test_auditoria_so_com_as_12_colunas(self, rec, env):
        # Sem note nem reverted_at: grava sem note e ON CONFLICT DO NOTHING.
        self._seed_19(env.db, "u1", "u2")
        env.db.theme_changes_columns = set(AUDIT_COLUMNS)
        env.db.theme_changes.append({"campaign": CAMPAIGN, "unique_id": "u2", "source": SOURCE})

        stats = _run(rec, ["u1", "u2"], audit_columns=AUDIT_COLUMNS)

        assert stats["ok"] == 1 and stats["already_audited"] == 1
        assert "note" not in _audit(env.db, "u1")
        inserts = [
            _norm(sql)
            for sql, _ in env.db.log
            if sql.lower().startswith("insert into news_theme_changes")
        ]
        assert all("on conflict (campaign, unique_id) do nothing returning 1" in i for i in inserts)
        assert env.db.news["u2"]["theme_l1_id"] == 10

    # ------------------------------------------------------------------ #
    # Guarda: artigo fora do 19 só muda se o novo L1 for 26               #
    # ------------------------------------------------------------------ #

    def test_fora_do_19_e_novo_l1_nao_26_mantem_o_tema(self, rec, env):
        env.db.seed_news("mdr-04", "2026-10-01", agency_key="mdr", **_ids("04", "04.03"))
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            "05", "05.02", "05.02.01"
        )

        stats = _run(rec, ["mdr-04"])

        assert stats["kept"] == 1
        assert "ok" not in stats
        assert _news_updates(env.db) == []
        assert env.db.news["mdr-04"]["theme_l1_id"] == 1
        row = _audit(env.db, "mdr-04")
        old = [row[f"old_{k}_code"] for k in ("l1", "l2", "l3", "most_specific")]
        new = [row[f"new_{k}_code"] for k in ("l1", "l2", "l3", "most_specific")]
        assert old == new == ["04", "04.03", None, "04.03"]
        assert row["note"].startswith("kept: ")
        assert "05.02.01" in row["note"]
        assert env.db.ledger[HAIKU45] == USAGE

    def test_fora_do_19_kept_confere_o_tema_atual(self, rec, env):
        env.db.seed_news("mdr-04", "2026-10-01", agency_key="mdr", **_ids("04", "04.03"))

        def _classify_and_race(article, return_format="dict"):
            env.db.news["mdr-04"].update(_ids("01", "01.02", "01.02.03"))
            return _result("05", "05.02", "05.02.01")

        env.clf.classify_single.side_effect = _classify_and_race

        stats = _run(rec, ["mdr-04"])

        assert stats["theme_changed"] == 1
        assert env.db.theme_changes == []

    def test_fora_do_19_e_novo_l1_26_grava(self, rec, env):
        env.db.seed_news("titulo-05", "2026-10-01", **_ids("05", "05.02", "05.02.01"))

        stats = _run(rec, ["titulo-05"])

        assert stats["ok"] == 1
        assert env.db.news["titulo-05"]["most_specific_theme_id"] == 22
        assert _audit(env.db, "titulo-05")["new_l1_code"] == "26"

    def test_fora_do_19_sem_mudanca_e_unchanged(self, rec, env):
        env.db.seed_news("u1", "2026-10-01", **_ids("15", "15.02", "15.02.03"))
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            "15", "15.02", "15.02.03"
        )

        stats = _run(rec, ["u1"])

        assert stats["unchanged"] == 1

    @pytest.mark.parametrize(
        "codes",
        [
            ("19", "19.05", "19.05.01"),
            ("19",),
            # Hierarquia incoerente com o 19 em algum nível: é do bloco do 19.
            ("15", "15.02", "19.01.01"),
        ],
    )
    def test_artigo_do_19_sempre_recebe_a_nova_classificacao(self, rec, env, codes):
        env.db.seed_news("u1", "2026-10-01", **_ids(*codes))
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            "05", "05.02", "05.02.01"
        )

        stats = _run(rec, ["u1"])

        assert stats["ok"] == 1
        assert env.db.news["u1"]["most_specific_theme_id"] == 6

    def test_kept_sem_coluna_note(self, rec, env):
        env.db.theme_changes_columns = set(AUDIT_COLUMNS)
        env.db.seed_news("mdr-04", "2026-10-01", agency_key="mdr", **_ids("04"))
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            "01", "01.02", "01.02.03"
        )

        stats = _run(rec, ["mdr-04"], audit_columns=AUDIT_COLUMNS)

        assert stats["kept"] == 1
        assert "note" not in _audit(env.db, "mdr-04")

    def test_excecao_no_classificador_nao_derruba_o_run(self, rec, env):
        self._seed_19(env.db, "u1", "u2")
        env.clf.classify_single.side_effect = [RuntimeError("boom"), dict(TO_26)]

        stats = _run(rec, ["u1", "u2"])

        assert stats["error"] == 1
        assert stats["ok"] == 1

    def test_artigo_ausente(self, rec, env, monkeypatch):
        monkeypatch.setattr(handler, "fetch_article", lambda uid: None)

        stats = _run(rec, ["u1"])

        assert stats["missing"] == 1
        env.clf.classify_single.assert_not_called()

    def test_governador_para_antes_quando_budget_esgotado(self, rec, env):
        self._seed_19(env.db, "u1", "u2")
        env.db.ledger[HAIKU45] = {"input_tokens": 800, "output_tokens": 0}

        stats = _run(rec, ["u1", "u2"], daily_quota=1000, quota_fraction=0.8)

        assert stats["budget_exhausted"] is True
        env.clf.classify_single.assert_not_called()

    def test_concorrente(self, rec, env):
        uids = [f"u{i}" for i in range(6)]
        self._seed_19(env.db, *uids)

        stats = _run(rec, uids, workers=3)

        assert stats["ok"] == 6
        assert sorted(r["unique_id"] for r in env.db.theme_changes) == uids


# ---------------------------------------------------------------------- #
# CLI                                                                    #
# ---------------------------------------------------------------------- #


class TestMainThemeOnly:
    def _seed(self, db):
        db.seed_news("u1", "2026-10-01", summary="R1", **_ids("19", "19.05", "19.05.01"))
        db.seed_news("u2", "2026-10-02", summary="R2", agency_key="mdr", **_ids("04", "04.03"))
        db.seed_news("fora", "2026-10-03", summary="R3", **_ids("01", "01.02", "01.02.03"))

    def _argv(self, *extra, select="theme26-candidates"):
        return ["--select", select, *WINDOW, "--theme-only", "--campaign", CAMPAIGN, *extra]

    def test_execucao_completa_e_idempotente(self, rec, env, capsys):
        self._seed(env.db)
        # Continuam no 19 depois do run: sem a exclusão pela auditoria, voltariam.
        env.db.seed_news("fica-19", "2026-10-04", summary="R4", **_ids("19", "19.05", "19.05.01"))
        env.db.seed_news("19-para-19x", "2026-10-05", summary="R5", **_ids("19"))
        # Extra (MDR em 04) que o LLM manda para fora do 26: a guarda mantém o tema.
        env.db.seed_news("mdr-fica-04", "2026-10-06", agency_key="mdr", **_ids("04", "04.03"))
        respostas = {
            "u1": TO_26,
            "u2": TO_26,
            "fica-19": _result("19", "19.05", "19.05.01"),  # unchanged
            "19-para-19x": _result("19", "19.01", "19.01.01"),  # muda, mas fica no 19
            "mdr-fica-04": _result("05", "05.02", "05.02.01"),  # kept
        }
        env.clf.classify_single.side_effect = lambda a, return_format="dict": dict(
            respostas[a["unique_id"]]
        )

        code = rec.main(self._argv())

        assert code == 0
        assert sorted(r["unique_id"] for r in env.db.theme_changes) == [
            "19-para-19x",
            "fica-19",
            "mdr-fica-04",
            "u1",
            "u2",
        ]
        assert {r["campaign"] for r in env.db.theme_changes} == {"tema26-llm-d1"}
        assert {r["source"] for r in env.db.theme_changes} == {SOURCE}
        assert env.db.news["u1"]["most_specific_theme_id"] == 22
        assert env.db.news["u1"]["summary"] == "R1"
        assert env.db.news["fica-19"]["most_specific_theme_id"] == 14
        assert env.db.news["19-para-19x"]["most_specific_theme_id"] == 12
        assert env.db.news["mdr-fica-04"]["most_specific_theme_id"] == 2
        assert env.db.news["fora"]["most_specific_theme_id"] == 32
        env.publish.assert_not_called()
        assert env.clf.classify_single.call_count == 5

        capsys.readouterr()
        assert rec.main(self._argv()) == 0  # segundo run: nada pendente
        assert "selecionados=0" in capsys.readouterr().out
        assert env.clf.classify_single.call_count == 5  # ninguém foi reclassificado

        # Sem a campanha, os que não mudaram de tema voltariam a ser candidatos.
        uids = rec.get_window_uids(
            "theme26-candidates", "2023-01-01", None, 100, campaign="outra-campanha"
        )
        assert set(uids) == {"fica-19", "19-para-19x", "mdr-fica-04"}

    def test_revertido_pelo_rollback_e_reclassificado_de_novo(self, rec, env):
        self._seed(env.db)
        env.db.theme_changes += [
            {"campaign": CAMPAIGN, "unique_id": "u1", "source": SOURCE, "reverted_at": "x"},
            {"campaign": CAMPAIGN, "unique_id": "u2", "source": SOURCE, "reverted_at": None},
        ]

        assert rec.main(self._argv()) == 0

        assert env.clf.classify_single.call_count == 1  # só o u1
        assert _audit(env.db, "u1")["reverted_at"] is None
        assert env.db.news["u1"]["most_specific_theme_id"] == 22

    # Flags do DAG enrichment_backfill (contrato de 22/10): --select theme-code
    # --theme-code <c> | --select theme26-candidates, --date-from obrigatório,
    # --date-to opcional, --limit/--workers/[--dry-run], e --term-fields. Sem
    # --theme-only nem --campaign: as seleções de tema implicam o modo e a campanha
    # padrão tema26-llm-d1.
    @pytest.mark.parametrize(
        "argv",
        [
            ["--select", "theme-code", "--theme-code", "19", "--date-from", "2023-01-01"],
            ["--select", "theme26-candidates", "--date-from", "2023-01-01"],
            [
                "--select",
                "theme26-candidates",
                "--term-fields",
                "title-content",
                "--date-from",
                "2023-01-01",
                "--date-to",
                "2026-12-31",
                "--limit",
                "400",
                "--workers",
                "2",
            ],
            # O que o DAG do DP-2 (build_overrides) monta hoje.
            [
                "--select",
                "theme26-candidates",
                "--theme-only",
                "--campaign",
                "tema26-llm-d1",
                "--term-fields",
                "title-content",
                "--date-from",
                "2023-01-01",
                "--limit",
                "400",
                "--workers",
                "2",
            ],
        ],
    )
    def test_flags_do_contrato_do_dag(self, rec, env, argv):
        self._seed(env.db)

        assert rec.main(argv) == 0

        assert "u1" in {r["unique_id"] for r in env.db.theme_changes}
        assert {r["campaign"] for r in env.db.theme_changes} == {"tema26-llm-d1"}
        assert {r["source"] for r in env.db.theme_changes} == {SOURCE}

    def test_flags_do_contrato_com_dry_run(self, rec, env, capsys):
        self._seed(env.db)

        code = rec.main(
            [
                "--select",
                "theme-code",
                "--theme-code",
                "19",
                "--date-from",
                "2023-01-01",
                "--limit",
                "10",
                "--workers",
                "1",
                "--dry-run",
            ]
        )

        assert code == 0
        out = capsys.readouterr().out
        assert "campanha=tema26-llm-d1" in out
        assert "u1" in out
        env.clf.classify_single.assert_not_called()
        assert env.db.theme_changes == []

    def test_theme_code(self, rec, env):
        self._seed(env.db)

        code = rec.main(self._argv("--theme-code", "19", select="theme-code"))

        assert code == 0
        assert [r["unique_id"] for r in env.db.theme_changes] == ["u1"]

    def test_dry_run_nao_chama_bedrock_nem_escreve(self, rec, env, capsys):
        self._seed(env.db)

        code = rec.main(self._argv("--dry-run"))

        assert code == 0
        out = capsys.readouterr().out
        assert "u1" in out and "u2" in out and "fora" not in out
        env.clf.classify_single.assert_not_called()
        assert _news_updates(env.db) == []
        assert env.db.theme_changes == []
        assert env.db.ledger == {}

    def test_tabela_de_auditoria_ausente_falha_com_mensagem_clara(self, rec, env, capsys):
        self._seed(env.db)
        env.db.theme_changes_columns = None

        code = rec.main(self._argv())

        assert code == 1
        err = capsys.readouterr().err
        assert "news_theme_changes" in err and "034" in err
        assert not any(sql.lower().startswith("select n.unique_id") for sql, _ in env.db.log)
        env.clf.classify_single.assert_not_called()

    def test_tabela_de_auditoria_sem_colunas(self, rec, env, capsys):
        self._seed(env.db)
        env.db.theme_changes_columns = AUDIT_COLUMNS - {"source", "old_l3_code"}

        code = rec.main(self._argv())

        assert code == 1
        err = capsys.readouterr().err
        assert "old_l3_code" in err and "source" in err
        env.clf.classify_single.assert_not_called()

    def test_tabela_de_auditoria_sem_unique(self, rec, env, capsys):
        self._seed(env.db)
        env.db.theme_changes_unique = False

        code = rec.main(self._argv())

        assert code == 1
        err = capsys.readouterr().err
        assert "UNIQUE (campaign, unique_id)" in err
        assert not any(sql.lower().startswith("select n.unique_id") for sql, _ in env.db.log)
        env.clf.classify_single.assert_not_called()

    def test_colunas_extras_na_auditoria_sao_aceitas(self, rec, env):
        # O env já usa a tabela da 034 (12 colunas + id, note, reverted_at).
        self._seed(env.db)
        env.db.theme_changes_columns = set(CONTRACT_COLUMNS) | {"outra_coluna"}

        assert rec.main(self._argv()) == 0
        assert len(env.db.theme_changes) == 2
        assert all(r["note"] for r in env.db.theme_changes)

    def test_preflight_exige_so_as_12_colunas(self, rec, env):
        self._seed(env.db)
        env.db.theme_changes_columns = set(AUDIT_COLUMNS)

        assert rec.main(self._argv()) == 0
        assert len(env.db.theme_changes) == 2
        assert not any("note" in r for r in env.db.theme_changes)

    def test_preflight_lista_as_12_colunas_do_contrato(self, rec):
        assert set(rec.AUDIT_REQUIRED_COLUMNS) == AUDIT_COLUMNS
        assert len(rec.AUDIT_REQUIRED_COLUMNS) == 12

    def test_campanha_ja_usada_por_outra_fonte(self, rec, env, capsys):
        # Ex.: a campanha da migração 034. Reusá-la tiraria da seleção os artigos que a
        # 034 auditou e que continuam no 19.
        self._seed(env.db)
        env.db.theme_changes.append(
            {"campaign": CAMPAIGN, "unique_id": "x", "source": "migration-034"}
        )

        code = rec.main(self._argv())

        assert code == 1
        err = capsys.readouterr().err
        assert "migration-034" in err and CAMPAIGN in err
        env.clf.classify_single.assert_not_called()

    def test_campanha_retomada_pela_mesma_fonte_llm(self, rec, env):
        self._seed(env.db)
        env.db.theme_changes.append(
            {"campaign": CAMPAIGN, "unique_id": "u1", "source": f"llm:{HAIKU45}"}
        )

        assert rec.main(self._argv()) == 0
        assert sorted(r["unique_id"] for r in env.db.theme_changes) == ["u1", "u2"]
        assert env.clf.classify_single.call_count == 1  # só o u2

    def test_tabela_de_auditoria_ausente_tambem_no_dry_run(self, rec, env):
        env.db.theme_changes_columns = None

        assert rec.main(self._argv("--dry-run")) == 1

    def test_theme26_exige_o_tema_26_na_taxonomia(self, rec, env, monkeypatch, capsys):
        self._seed(env.db)
        sem_26 = {c: i for c, i in CODE_TO_ID.items() if not c.startswith("26")}
        monkeypatch.setattr(handler, "_get_code_to_id", lambda: dict(sem_26))

        code = rec.main(self._argv())

        assert code == 1
        assert "26" in capsys.readouterr().err
        env.clf.classify_single.assert_not_called()

    def test_theme26_exige_o_tema_26_na_taxonomia_do_classificador(self, rec, env):
        self._seed(env.db)
        env.clf.llm_client.taxonomy = _taxonomy(c for c in CODE_TO_ID if not c.startswith("26"))

        code = rec.main(self._argv())

        assert code == 1
        env.clf.classify_single.assert_not_called()

    def test_theme_code_inexistente(self, rec, env, capsys):
        code = rec.main(self._argv("--theme-code", "19.03", select="theme-code"))

        assert code == 1
        assert "19.03" in capsys.readouterr().err
        env.clf.classify_single.assert_not_called()

    @pytest.mark.parametrize("select", ["theme-code", "theme26-candidates"])
    def test_selecoes_de_tema_implicam_theme_only(self, rec, env, select):
        self._seed(env.db)
        extra = ["--theme-code", "19"] if select == "theme-code" else []

        code = rec.main(["--select", select, *WINDOW, *extra])

        assert code == 0
        row = _audit(env.db, "u1")
        assert (row["campaign"], row["source"]) == ("tema26-llm-d1", SOURCE)
        assert env.db.news["u1"]["summary"] == "R1"  # só o tema
        env.upsert.assert_not_called()
        env.update_enrichment.assert_not_called()

    def test_source_maior_que_a_coluna_falha_antes_de_chamar_o_bedrock(
        self, rec, env, monkeypatch, capsys
    ):
        # source VARCHAR(50) na 034: 'llm:' + um perfil global passaria do limite e cada
        # INSERT falharia depois da chamada paga.
        model = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        assert len(f"llm:{model}") > 50
        monkeypatch.setenv("ENRICHMENT_MODEL_ID", model)
        env.clf.llm_client.model_id = model
        self._seed(env.db)

        code = rec.main(self._argv())

        assert code == 1
        assert "50" in capsys.readouterr().err
        env.clf.classify_single.assert_not_called()
        assert not any(sql.lower().startswith("select n.unique_id") for sql, _ in env.db.log)

    def test_campanha_padrao(self, rec):
        assert rec.DEFAULT_THEME_CAMPAIGN == "tema26-llm-d1"

    @pytest.mark.parametrize("select", ["null-theme", "mock", "null-summary"])
    def test_theme_only_so_com_selecoes_de_tema(self, rec, env, select):
        code = rec.main(
            [
                "--select",
                select,
                "--date-from",
                "2026-09-25",
                "--date-to",
                "2026-10-06",
                "--theme-only",
                "--campaign",
                CAMPAIGN,
            ]
        )

        assert code == 1
        assert env.db.log == []

    def test_theme_only_sem_campanha_usa_a_padrao(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "theme26-candidates", *WINDOW, "--theme-only"])

        assert code == 0
        assert {r["campaign"] for r in env.db.theme_changes} == {"tema26-llm-d1"}

    def test_outra_campanha_do_llm_do_tema26(self, rec, env):
        self._seed(env.db)

        code = rec.main(["--select", "theme26-candidates", *WINDOW, "--campaign", "tema26-llm-d1b"])

        assert code == 0
        assert {r["campaign"] for r in env.db.theme_changes} == {"tema26-llm-d1b"}

    # A campanha tem de ser tema26-llm-*: o rollback da 034 e o MERGE do BigQuery só
    # leem tema26-*, e tema26-034/tema26-rollback são da própria migração.
    @pytest.mark.parametrize(
        "campaign",
        [
            "",
            "Tema 26",
            "../x",
            "a" * 80,
            "outra-campanha",
            "tema26-034",
            "tema26-rollback",
            "tema26-d1",
            "tema26-llm-",
            "tema26-llm-" + "a" * 40,
        ],
    )
    def test_campanha_invalida(self, rec, env, campaign):
        code = rec.main(
            ["--select", "theme26-candidates", *WINDOW, "--theme-only", "--campaign", campaign]
        )

        assert code == 1
        assert env.db.log == []

    def test_campanha_sem_theme_only(self, rec, env):
        code = rec.main(
            [
                "--select",
                "null-theme",
                "--date-from",
                "2026-09-25",
                "--date-to",
                "2026-10-06",
                "--campaign",
                CAMPAIGN,
            ]
        )

        assert code == 1
        assert env.db.log == []

    def test_theme_code_exige_codigo(self, rec, env):
        code = rec.main(self._argv(select="theme-code"))

        assert code == 1
        assert env.db.log == []

    def test_theme_code_so_com_select_theme_code(self, rec, env):
        code = rec.main(self._argv("--theme-code", "19"))

        assert code == 1
        assert env.db.log == []

    @pytest.mark.parametrize("value", ["19.", "1", "19.3", "abc", "19.03.01.01", "19%"])
    def test_theme_code_formato_invalido(self, rec, value):
        with pytest.raises(SystemExit):
            rec.build_arg_parser().parse_args(
                [
                    "--select",
                    "theme-code",
                    *WINDOW,
                    "--theme-only",
                    "--campaign",
                    CAMPAIGN,
                    "--theme-code",
                    value,
                ]
            )

    def test_term_fields_titulo_e_conteudo_pela_cli(self, rec, env, capsys):
        self._seed(env.db)
        env.db.seed_news(
            "so-conteudo",
            "2026-10-04",
            agency_key="mj",
            content="decretou estado de calamidade",
            **_ids("04", "04.03"),
        )

        assert rec.main(self._argv("--dry-run")) == 0  # padrão: só o título
        assert "so-conteudo" not in capsys.readouterr().out

        assert rec.main(self._argv("--term-fields", "title-content")) == 0
        assert "so-conteudo" in {r["unique_id"] for r in env.db.theme_changes}

    def test_extra_codes_pela_cli(self, rec, env):
        self._seed(env.db)

        assert rec.main(self._argv("--extra-codes", "")) == 0
        assert [r["unique_id"] for r in env.db.theme_changes] == ["u1"]

    @pytest.mark.parametrize("value", ["04,19%", "4", "04;05", "04,,05.02.01x"])
    def test_extra_codes_formato_invalido(self, rec, value):
        with pytest.raises(SystemExit):
            rec.build_arg_parser().parse_args(
                [
                    "--select",
                    "theme26-candidates",
                    *WINDOW,
                    "--theme-only",
                    "--campaign",
                    CAMPAIGN,
                    "--extra-codes",
                    value,
                ]
            )

    @pytest.mark.parametrize("extra", [["--term-fields", "title-content"], ["--extra-codes", "04"]])
    def test_opcoes_do_theme26_so_com_theme26(self, rec, env, extra):
        code = rec.main(self._argv("--theme-code", "19", *extra, select="theme-code"))

        assert code == 1
        assert env.db.log == []

    def test_aborta_se_classificador_usa_outro_modelo(self, rec, env):
        self._seed(env.db)
        env.clf.llm_client.model_id = "anthropic.claude-3-haiku-20240307-v1:0"

        code = rec.main(self._argv())

        assert code != 0
        env.clf.classify_single.assert_not_called()

    def test_modelo_indisponivel_sai_com_erro(self, rec, env):
        self._seed(env.db)
        env.clf.classify_single.side_effect = lambda a, return_format="dict": _result(
            None, None, None, _error=EOL_ERROR
        )

        assert rec.main(self._argv()) == 1

    def test_cota_lida_da_env(self, rec, env, monkeypatch):
        self._seed(env.db)
        monkeypatch.setenv("BEDROCK_DAILY_TOKEN_QUOTA", f'{{"{HAIKU45}": 1000}}')
        env.db.ledger[HAIKU45] = {"input_tokens": 900, "output_tokens": 0}

        code = rec.main(self._argv())

        assert code == 0  # parada graciosa, retomável
        env.clf.classify_single.assert_not_called()

    def test_date_to_opcional_e_sem_teto_de_hoje(self, rec, env):
        # As seleções de tema só pegam artigos que JÁ têm tema (o worker ao vivo os
        # pula), então não há disputa com ele: --date-to é opcional e livre.
        self._seed(env.db)

        code = rec.main(self._argv("--date-to", "2026-12-31"))

        assert code == 0
        assert len(env.db.theme_changes) == 2
