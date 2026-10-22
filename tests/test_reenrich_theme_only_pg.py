"""
Integração da reclassificação só de tema (--theme-only) contra PostgreSQL REAL.

O tests/fakedb.py emula a seleção pelos params, sem interpretar o SQL. Aqui o SQL
de verdade roda num banco descartável: precedência AND/OR entre o bloco do 19 e o
bloco extra + (MDR ou termos), NOT EXISTS da campanha valendo para os dois ramos,
janela BRT, ILIKE com acento e maiúsculas, guarda do UPDATE, UNIQUE da auditoria e
o preflight (information_schema / pg_index).

Só roda com REENRICH_PG_TEST_URL apontando para um banco cujo nome termina em
`_test` (as tabelas themes, news e news_theme_changes são apagadas e recriadas):

    docker run -d --name ds1-reclass-pg -p 55447:5432 \\
        -e POSTGRES_PASSWORD=ds1 -e POSTGRES_DB=reenrich_test postgres:15
    REENRICH_PG_TEST_URL=postgresql://postgres:ds1@localhost:55447/reenrich_test \\
    PYTHONPATH=src .venv/bin/python -m pytest tests/test_reenrich_theme_only_pg.py -q

O Bedrock é mockado (classify_single); o resto é o código do script.
"""

import importlib.util
import os
from unittest.mock import MagicMock
from urllib.parse import urlparse

import psycopg2
import pytest

from news_enrichment.taxonomy import load_taxonomy_from_postgres
from news_enrichment.worker import handler

PG_URL = os.environ.get("REENRICH_PG_TEST_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="REENRICH_PG_TEST_URL não definida (Postgres descartável)"
)

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "reenrich_combined_window.py")

HAIKU45 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
CAMPAIGN = "tema26-llm-d1"
USAGE = {"input_tokens": 19000, "output_tokens": 300}

# Taxonomia depois da 034 (recorte).
THEMES = [
    ("01", "Economia", 1, None),
    ("04", "Segurança Pública", 1, None),
    ("05", "Meio Ambiente e Sustentabilidade", 1, None),
    ("15", "Desenvolvimento Social", 1, None),
    ("19", "Defesa e Forças Armadas", 1, None),
    ("26", "Defesa Civil e Gestão de Desastres", 1, None),
    ("01.02", "Tributação", 2, "01"),
    ("04.03", "Prevenção e Combate ao Crime", 2, "04"),
    ("05.02", "Mudanças Climáticas", 2, "05"),
    ("15.02", "Combate à Pobreza", 2, "15"),
    ("19.01", "Segurança Nacional", 2, "19"),
    ("19.05", "Políticas e Estratégias de Defesa", 2, "19"),
    ("26.01", "Defesa Civil", 2, "26"),
    ("26.02", "Situações de Emergência", 2, "26"),
    ("01.02.03", "Reforma Tributária", 3, "01.02"),
    ("04.03.01", "Prevenção à Violência", 3, "04.03"),
    ("05.02.01", "Catástrofes Climáticas", 3, "05.02"),
    ("05.02.02", "Adaptação Climática", 3, "05.02"),
    ("15.02.03", "Apoio Emergencial", 3, "15.02"),
    ("19.01.01", "Inteligência e Contrainteligência", 3, "19.01"),
    ("19.05.01", "Planejamento de Defesa Nacional", 3, "19.05"),
    ("26.01.03", "Resposta a Desastres", 3, "26.01"),
    ("26.02.01", "Resgate e Salvamento", 3, "26.02"),
]

# Contrato final (22/10), igual ao CREATE_AUDIT_SQL da migração 034 do data-platform
# (DP-2): códigos, não ids; id, note e reverted_at; índice UNIQUE (campaign, unique_id).
AUDIT_DDL = """
CREATE TABLE news_theme_changes (
    id                      BIGSERIAL PRIMARY KEY,
    campaign                VARCHAR(50)  NOT NULL,
    unique_id               VARCHAR(120) NOT NULL,
    old_l1_code             VARCHAR(20),
    old_l2_code             VARCHAR(20),
    old_l3_code             VARCHAR(20),
    old_most_specific_code  VARCHAR(20),
    new_l1_code             VARCHAR(20),
    new_l2_code             VARCHAR(20),
    new_l3_code             VARCHAR(20),
    new_most_specific_code  VARCHAR(20),
    source                  VARCHAR(50)  NOT NULL,
    note                    TEXT,
    changed_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    reverted_at             TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_news_theme_changes_campaign_uid
    ON news_theme_changes (campaign, unique_id);
"""

# Só as 12 colunas exigidas pelo preflight (sem id, note e reverted_at).
AUDIT_DDL_12 = """
DROP TABLE news_theme_changes;
CREATE TABLE news_theme_changes (
    campaign                TEXT NOT NULL,
    unique_id               TEXT NOT NULL,
    old_l1_code             VARCHAR(20),
    old_l2_code             VARCHAR(20),
    old_l3_code             VARCHAR(20),
    old_most_specific_code  VARCHAR(20),
    new_l1_code             VARCHAR(20),
    new_l2_code             VARCHAR(20),
    new_l3_code             VARCHAR(20),
    new_most_specific_code  VARCHAR(20),
    source                  TEXT NOT NULL,
    changed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT news_theme_changes_campaign_unique_id_key UNIQUE (campaign, unique_id)
);
"""

SCHEMA_DDL = """
DROP TABLE IF EXISTS news_theme_changes, news, themes CASCADE;
CREATE TABLE themes (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(20) NOT NULL UNIQUE,
    label       VARCHAR(500) NOT NULL,
    level       SMALLINT NOT NULL CHECK (level IN (1, 2, 3)),
    parent_code VARCHAR(20) REFERENCES themes(code)
);
CREATE TABLE news (
    id                     SERIAL PRIMARY KEY,
    unique_id              VARCHAR(120) NOT NULL UNIQUE,
    agency_key             VARCHAR(100),
    title                  TEXT NOT NULL,
    subtitle               TEXT,
    editorial_lead         TEXT,
    content                TEXT,
    summary                TEXT,
    published_at           TIMESTAMPTZ NOT NULL,
    theme_l1_id            INTEGER REFERENCES themes(id),
    theme_l2_id            INTEGER REFERENCES themes(id),
    theme_l3_id            INTEGER REFERENCES themes(id),
    most_specific_theme_id INTEGER REFERENCES themes(id),
    updated_at             TIMESTAMPTZ DEFAULT now()
);
"""


def _is_test_db(url):
    return (urlparse(url).path or "").lstrip("/").endswith("_test")


@pytest.fixture(scope="module")
def rec():
    spec = importlib.util.spec_from_file_location("reenrich_combined_window_pg", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg(monkeypatch):
    """Banco limpo com a taxonomia e a auditoria do contrato. Devolve code→id."""
    if not _is_test_db(PG_URL):
        pytest.fail("REENRICH_PG_TEST_URL deve apontar para um banco *_test (descartável)")
    conn = psycopg2.connect(PG_URL)
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA_DDL)
        cur.execute(AUDIT_DDL)
        for code, label, level, parent in THEMES:
            cur.execute(
                "INSERT INTO themes (code, label, level, parent_code) VALUES (%s, %s, %s, %s)",
                (code, label, level, parent),
            )
        cur.execute("SELECT code, id FROM themes")
        code_to_id = dict(cur.fetchall())
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("ENRICHMENT_MODEL_ID", HAIKU45)
    monkeypatch.delenv("BEDROCK_DAILY_TOKEN_QUOTA", raising=False)
    monkeypatch.delenv("BACKFILL_QUOTA_FRACTION", raising=False)
    monkeypatch.setattr(handler, "_code_to_id", None)  # mapa real, lido do banco
    return code_to_id


def _sql(query, params=None, fetch=True):
    conn = psycopg2.connect(PG_URL)
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    finally:
        conn.close()


def _seed(code_to_id, uid, published_at, codes=(), agency="x", title="Título", content=""):
    ids = [code_to_id[c] if c else None for c in (list(codes) + [None, None, None])[:3]]
    most_specific = code_to_id[[c for c in codes if c][-1]] if codes else None
    _sql(
        """
        INSERT INTO news (unique_id, agency_key, title, content, summary, published_at,
                          theme_l1_id, theme_l2_id, theme_l3_id, most_specific_theme_id)
        VALUES (%s, %s, %s, %s, 'Resumo antigo.', %s, %s, %s, %s, %s)
        """,
        (uid, agency, title, content, published_at, *ids, most_specific),
        fetch=False,
    )


def _audit_row(uid, campaign=CAMPAIGN, source="migration-034", reverted=False):
    _sql(
        "INSERT INTO news_theme_changes (campaign, unique_id, source) VALUES (%s, %s, %s)",
        (campaign, uid, source),
        fetch=False,
    )
    if reverted:
        _sql(
            "UPDATE news_theme_changes SET reverted_at = now() "
            "WHERE campaign = %s AND unique_id = %s",
            (campaign, uid),
            fetch=False,
        )


def _themes_of(uid):
    [row] = _sql(
        """
        SELECT l1.code, l2.code, l3.code, ms.code, n.summary
        FROM news n
        LEFT JOIN themes l1 ON l1.id = n.theme_l1_id
        LEFT JOIN themes l2 ON l2.id = n.theme_l2_id
        LEFT JOIN themes l3 ON l3.id = n.theme_l3_id
        LEFT JOIN themes ms ON ms.id = n.most_specific_theme_id
        WHERE n.unique_id = %s
        """,
        (uid,),
    )
    return row


def _result(l1, l2, l3, **extra):
    result = {
        "theme_1_level_1_code": l1,
        "theme_1_level_2_code": l2,
        "theme_1_level_3_code": l3,
        "most_specific_theme_code": l3 or l2 or l1,
        "summary": "Resumo NOVO que nunca deve ser gravado.",
        "sentiment": {"label": "negative", "score": -0.4},
        "_usage": dict(USAGE),
        "_model_id": HAIKU45,
        "_error": None,
    }
    result.update(extra)
    return result


@pytest.fixture
def classifier(monkeypatch):
    """Classificador mockado com a taxonomia REAL do banco; Bedrock nunca é chamado."""
    clf = MagicMock()
    clf.llm_client.model_id = HAIKU45
    clf.llm_client.taxonomy = load_taxonomy_from_postgres(PG_URL)
    clf.classify_single.side_effect = lambda a, return_format="dict": _result(
        "26", "26.01", "26.01.03"
    )
    monkeypatch.setattr(handler, "_get_classifier", lambda: clf)
    monkeypatch.setattr(handler, "publish_enriched_event", MagicMock())
    monkeypatch.setattr(handler, "_upsert_ai_features", MagicMock())
    return clf


# ---------------------------------------------------------------------- #
# Seleção: o SQL real                                                     #
# ---------------------------------------------------------------------- #

# Dia BRT 2026-10-01 começa em 2026-10-01 03:00Z.
DENTRO = "2026-10-05 12:00:00+00"


def _seed_selection_corpus(c):
    # Entram (título, padrão):
    _seed(c, "19-l3", DENTRO, ("19", "19.05", "19.05.01"), agency="defesa")
    _seed(c, "19-l1-sem-termo", DENTRO, ("19",), agency="defesa")
    _seed(c, "19-inconsistente", DENTRO, ("15", "15.02", "19.01.01"), agency="mds")
    _seed(c, "mdr-04", DENTRO, ("04", "04.03", "04.03.01"), agency="mdr")
    _seed(
        c,
        "titulo-maiusculo-acento",
        DENTRO,
        ("05", "05.02", "05.02.01"),
        agency="mma",
        title="Município decreta SITUAÇÃO DE EMERGÊNCIA",
    )
    _seed(
        c,
        "titulo-sem-acento",
        DENTRO,
        ("15", "15.02", "15.02.03"),
        agency="mds",
        title="Prefeitura declara situacao de emergencia",
    )
    _seed(c, "auditado-em-outra", DENTRO, ("19",), agency="defesa")
    _seed(c, "borda-inicio", "2026-10-01 03:00:00+00", ("19",), agency="defesa")
    # Só com --term-fields title-content:
    _seed(
        c,
        "termo-so-no-conteudo",
        DENTRO,
        ("04", "04.03"),
        agency="mj",
        content="O governador decretou estado de calamidade.",
    )
    # Ficam de fora:
    _seed(c, "auditado-19", DENTRO, ("19", "19.05"), agency="defesa")
    _seed(c, "auditado-mdr-04", DENTRO, ("04",), agency="mdr")
    _seed(c, "04-sem-mdr-nem-termo", DENTRO, ("04", "04.03"), agency="mj")
    _seed(c, "irmao-05.02.02-mdr", DENTRO, ("05", "05.02", "05.02.02"), agency="mdr")
    _seed(
        c,
        "termo-fora-dos-temas",
        DENTRO,
        ("01", "01.02", "01.02.03"),
        agency="mdr",
        title="Defesa Civil e desastre",
    )
    _seed(c, "ja-26", DENTRO, ("26", "26.01", "26.01.03"), agency="mdr")
    _seed(c, "sem-tema", DENTRO, (), agency="mdr", title="Defesa Civil")
    _seed(c, "borda-antes-19", "2026-10-01 02:59:59+00", ("19",), agency="defesa")
    _seed(c, "borda-antes-mdr", "2026-10-01 02:59:59+00", ("04",), agency="mdr")
    _seed(c, "borda-fim-19", "2026-11-01 03:00:00+00", ("19",), agency="defesa")
    _seed(c, "borda-fim-mdr", "2026-11-01 03:00:00+00", ("04",), agency="mdr")
    _audit_row("auditado-19")
    _audit_row("auditado-mdr-04")
    _audit_row("auditado-em-outra", campaign="outra-campanha")
    # Auditado na campanha, mas revertido pelo rollback da 034: volta a ser candidato.
    _seed(c, "revertido-19", DENTRO, ("19", "19.05"), agency="defesa")
    _audit_row("revertido-19", source=f"llm:{HAIKU45}", reverted=True)


SELECIONADOS_TITULO = {
    "19-l3",
    "19-l1-sem-termo",
    "19-inconsistente",
    "mdr-04",
    "titulo-maiusculo-acento",
    "titulo-sem-acento",
    "auditado-em-outra",
    "revertido-19",
    "borda-inicio",
}


def test_theme26_candidates_sql_real(rec, pg):
    _seed_selection_corpus(pg)

    uids = rec.get_window_uids(
        "theme26-candidates", "2026-10-01", "2026-11-01", 100, campaign=CAMPAIGN
    )

    assert set(uids) == SELECIONADOS_TITULO
    assert len(uids) == len(set(uids))  # EXISTS, não JOIN: sem duplicatas


def test_theme26_candidates_titulo_e_conteudo_sql_real(rec, pg):
    _seed_selection_corpus(pg)

    uids = rec.get_window_uids(
        "theme26-candidates",
        "2026-10-01",
        "2026-11-01",
        100,
        campaign=CAMPAIGN,
        term_fields="title-content",
    )

    assert set(uids) == SELECIONADOS_TITULO | {"termo-so-no-conteudo"}


def test_theme26_candidates_sem_extras_sql_real(rec, pg):
    _seed_selection_corpus(pg)

    uids = rec.get_window_uids(
        "theme26-candidates", "2026-10-01", "2026-11-01", 100, campaign=CAMPAIGN, extra_codes=()
    )

    assert set(uids) == {
        "19-l3",
        "19-l1-sem-termo",
        "19-inconsistente",
        "auditado-em-outra",
        "revertido-19",
        "borda-inicio",
    }


def test_theme_code_sql_real(rec, pg):
    _seed_selection_corpus(pg)

    uids = rec.get_window_uids(
        "theme-code", "2026-10-01", None, 100, theme_code="19", campaign=CAMPAIGN
    )

    assert set(uids) == {
        "19-l3",
        "19-l1-sem-termo",
        "19-inconsistente",
        "auditado-em-outra",
        "revertido-19",
        "borda-inicio",
        "borda-fim-19",  # sem --date-to
    }


# ---------------------------------------------------------------------- #
# Escrita e preflight: o SQL real                                         #
# ---------------------------------------------------------------------- #


def _argv(*extra):
    return [
        "--select",
        "theme26-candidates",
        "--date-from",
        "2026-10-01",
        "--theme-only",
        "--campaign",
        CAMPAIGN,
        *extra,
    ]


# Flags do contrato do DAG enrichment_backfill: sem --theme-only nem --campaign.
CONTRACT_ARGV = [
    "--select",
    "theme26-candidates",
    "--term-fields",
    "title-content",
    "--date-from",
    "2026-10-01",
    "--limit",
    "100",
    "--workers",
    "2",
]


@pytest.mark.parametrize("argv", [_argv(), CONTRACT_ARGV], ids=["dag-dp2", "contrato"])
def test_fluxo_completo_e_idempotente(rec, pg, classifier, capsys, argv):
    _seed(pg, "vai-26", DENTRO, ("19", "19.05", "19.05.01"))
    _seed(pg, "fica-19", DENTRO, ("19", "19.05", "19.05.01"))
    _seed(pg, "mdr-04", DENTRO, ("04", "04.03"), agency="mdr")
    # Extra que o LLM manda para fora do 26: a guarda mantém o tema e audita 'kept'.
    _seed(pg, "mdr-fica-04", DENTRO, ("04", "04.03", "04.03.01"), agency="mdr")
    respostas = {
        "vai-26": _result("26", "26.01", "26.01.03"),
        "fica-19": _result("19", "19.05", "19.05.01"),
        "mdr-04": _result("04", "26.02", "26.02.01"),  # L1 incoerente: segue o L3
        "mdr-fica-04": _result("05", "05.02", "05.02.01"),
    }
    classifier.classify_single.side_effect = lambda a, return_format="dict": respostas[
        a["unique_id"]
    ]

    assert rec.main(argv) == 0

    assert _themes_of("vai-26") == ("26", "26.01", "26.01.03", "26.01.03", "Resumo antigo.")
    assert _themes_of("fica-19") == ("19", "19.05", "19.05.01", "19.05.01", "Resumo antigo.")
    assert _themes_of("mdr-04") == ("26", "26.02", "26.02.01", "26.02.01", "Resumo antigo.")
    assert _themes_of("mdr-fica-04") == (
        "04",
        "04.03",
        "04.03.01",
        "04.03.01",
        "Resumo antigo.",
    )
    audit = _sql(
        """
        SELECT unique_id, old_l1_code, old_l2_code, old_l3_code, old_most_specific_code,
               new_l1_code, new_l2_code, new_l3_code, new_most_specific_code, source,
               split_part(note, ':', 1), reverted_at IS NULL, campaign
        FROM news_theme_changes ORDER BY unique_id
        """,
    )
    src = f"llm:{HAIKU45}"
    c = CAMPAIGN
    assert audit == [
        ("fica-19", *("19", "19.05", "19.05.01", "19.05.01") * 2, src, "unchanged", True, c),
        ("mdr-04", "04", "04.03", None, "04.03", "26", "26.02", "26.02.01", "26.02.01")
        + (src, "ok", True, c),
        ("mdr-fica-04", *("04", "04.03", "04.03.01", "04.03.01") * 2, src, "kept", True, c),
        ("vai-26", "19", "19.05", "19.05.01", "19.05.01", "26", "26.01", "26.01.03", "26.01.03")
        + (src, "ok", True, c),
    ]
    [(note,)] = _sql(
        "SELECT note FROM news_theme_changes WHERE unique_id = 'mdr-fica-04'",
    )
    assert "05.02.01" in note

    capsys.readouterr()
    assert rec.main(argv) == 0
    assert "selecionados=0" in capsys.readouterr().out
    assert classifier.classify_single.call_count == 4


def test_revertido_volta_e_reaproveita_a_linha_sql_real(rec, pg, classifier):
    _seed(pg, "u1", DENTRO, ("19", "19.05", "19.05.01"))
    _audit_row("u1", source=f"llm:{HAIKU45}", reverted=True)

    assert rec.main(_argv()) == 0

    assert _themes_of("u1")[:4] == ("26", "26.01", "26.01.03", "26.01.03")
    rows = _sql(
        "SELECT old_l1_code, new_l1_code, reverted_at IS NULL, note FROM news_theme_changes "
        "WHERE campaign = %s AND unique_id = 'u1'",
        (CAMPAIGN,),
    )
    assert rows == [("19", "26", True, "ok: reclassificado pelo LLM")]


def test_guarda_do_tema_antigo_sql_real(rec, pg, classifier):
    _seed(pg, "u1", DENTRO, ("19", "19.05", "19.05.01"))

    def _classify_and_race(article, return_format="dict"):
        _sql(
            "UPDATE news SET theme_l1_id = %s, theme_l2_id = NULL, theme_l3_id = NULL, "
            "most_specific_theme_id = %s WHERE unique_id = 'u1'",
            (pg["01"], pg["01"]),
            fetch=False,
        )
        return _result("26", "26.01", "26.01.03")

    classifier.classify_single.side_effect = _classify_and_race

    assert rec.main(_argv()) == 0

    assert _themes_of("u1")[:4] == ("01", None, None, "01")
    assert _sql("SELECT count(*) FROM news_theme_changes") == [(0,)]


def test_unique_da_auditoria_desfaz_o_update_sql_real(rec, pg, classifier, capsys):
    _seed(pg, "u1", DENTRO, ("19", "19.05", "19.05.01"))

    def _classify_and_race(article, return_format="dict"):
        # Run concorrente da mesma campanha grava a auditoria do u1 antes deste.
        _audit_row("u1", source=f"llm:{HAIKU45}")
        return _result("26", "26.01", "26.01.03")

    classifier.classify_single.side_effect = _classify_and_race

    assert rec.main(_argv()) == 0

    assert _themes_of("u1")[:4] == ("19", "19.05", "19.05.01", "19.05.01")  # rollback
    assert _sql("SELECT count(*), max(note) FROM news_theme_changes") == [(1, None)]
    assert "already_audited" in capsys.readouterr().out


def test_preflight_sem_unique_sql_real(rec, pg, classifier, capsys):
    _seed(pg, "u1", DENTRO, ("19",))
    _sql("DROP INDEX uq_news_theme_changes_campaign_uid", fetch=False)
    # Um índice comum (não UNIQUE) não basta.
    _sql("CREATE INDEX idx_ntc ON news_theme_changes (campaign, unique_id)", fetch=False)

    assert rec.main(_argv()) == 1
    assert "UNIQUE (campaign, unique_id)" in capsys.readouterr().err
    classifier.classify_single.assert_not_called()


def test_preflight_unique_parcial_nao_basta_sql_real(rec, pg, classifier):
    _sql("DROP INDEX uq_news_theme_changes_campaign_uid", fetch=False)
    _sql(
        "CREATE UNIQUE INDEX uq_ntc ON news_theme_changes (campaign, unique_id) "
        "WHERE reverted_at IS NULL",
        fetch=False,
    )

    assert rec.main(_argv("--dry-run")) == 1


def test_preflight_aceita_unique_index_em_outra_ordem_sql_real(rec, pg, classifier):
    _seed(pg, "u1", DENTRO, ("19",))
    _sql("DROP INDEX uq_news_theme_changes_campaign_uid", fetch=False)
    _sql("CREATE UNIQUE INDEX uq_ntc ON news_theme_changes (unique_id, campaign)", fetch=False)

    assert rec.main(_argv()) == 0
    assert _themes_of("u1")[0] == "26"


def test_auditoria_so_com_as_12_colunas_sql_real(rec, pg, classifier, capsys):
    # Sem id, note e reverted_at: o preflight aceita; grava sem note, ON CONFLICT DO
    # NOTHING, e todo auditado sai da seleção.
    _sql(AUDIT_DDL_12, fetch=False)
    _seed(pg, "u1", DENTRO, ("19", "19.05", "19.05.01"))
    _seed(pg, "u2", DENTRO, ("19",))
    _audit_row("u2", source=f"llm:{HAIKU45}")

    assert rec.main(CONTRACT_ARGV) == 0

    assert _themes_of("u1")[:4] == ("26", "26.01", "26.01.03", "26.01.03")
    assert _themes_of("u2")[:4] == ("19", None, None, "19")
    assert classifier.classify_single.call_count == 1
    assert _sql("SELECT count(*) FROM news_theme_changes") == [(2,)]


def test_kept_com_tema_alterado_no_meio_do_run_sql_real(rec, pg, classifier):
    _seed(pg, "mdr-04", DENTRO, ("04", "04.03"), agency="mdr")

    def _classify_and_race(article, return_format="dict"):
        _sql(
            "UPDATE news SET theme_l1_id = %s, theme_l2_id = NULL, theme_l3_id = NULL, "
            "most_specific_theme_id = %s WHERE unique_id = 'mdr-04'",
            (pg["01"], pg["01"]),
            fetch=False,
        )
        return _result("05", "05.02", "05.02.01")

    classifier.classify_single.side_effect = _classify_and_race

    assert rec.main(_argv()) == 0

    assert _themes_of("mdr-04")[:4] == ("01", None, None, "01")
    assert _sql("SELECT count(*) FROM news_theme_changes") == [(0,)]


def test_preflight_tabela_ausente_sql_real(rec, pg, classifier, capsys):
    _sql("DROP TABLE news_theme_changes", fetch=False)

    assert rec.main(_argv("--dry-run")) == 1
    err = capsys.readouterr().err
    assert "news_theme_changes" in err and "034" in err


def test_campanha_de_outra_fonte_sql_real(rec, pg, classifier, capsys):
    _seed(pg, "u1", DENTRO, ("19",))
    _audit_row("x", source="migration-034")

    assert rec.main(_argv()) == 1
    assert "migration-034" in capsys.readouterr().err
    classifier.classify_single.assert_not_called()
