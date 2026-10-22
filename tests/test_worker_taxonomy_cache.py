"""
Cache da taxonomia no worker de enriquecimento (tema 26, DS-1).

O worker (Cloud Run) carrega a taxonomia e o mapa código→id do banco na
primeira requisição de cada instância e os reutiliza até a instância morrer:
não há TTL nem recarga. Depois da migração 034 (tema 26, remoção de 19.03/
19.04), as instâncias antigas seguem com a taxonomia velha até uma nova
revisão (redeploy) ou um novo start de instância. Estes testes travam esse
contrato, que a ordem operacional do D0 pressupõe.
"""

from unittest.mock import MagicMock

import pytest

from news_enrichment.worker import handler

ANTES = {"19": {"label": "Defesa e Forças Armadas", "subcategories": {}}}
DEPOIS = {
    "19": {"label": "Defesa e Forças Armadas", "subcategories": {}},
    "26": {"label": "Defesa Civil e Gestão de Desastres", "subcategories": {}},
}


@pytest.fixture
def fresh_instance(monkeypatch):
    """Simula uma instância nova do worker (caches vazios)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.setenv("ENRICHMENT_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    monkeypatch.setattr(handler, "_classifier", None)
    monkeypatch.setattr(handler, "_code_to_id", None)
    monkeypatch.setattr(handler, "NewsClassifier", MagicMock(name="NewsClassifier"))


def test_taxonomia_carregada_do_banco_uma_vez_por_instancia(fresh_instance, monkeypatch):
    loads = []
    monkeypatch.setattr(
        handler, "load_taxonomy_from_postgres", lambda url: loads.append(url) or ANTES
    )

    handler._get_classifier()
    handler._get_classifier()

    assert loads == ["postgresql://fake"]  # cache por instância, sem recarga
    assert handler.NewsClassifier.call_args.kwargs["taxonomy"] == ANTES


def test_instancia_nova_recarrega_a_taxonomia(fresh_instance, monkeypatch):
    taxonomias = iter([ANTES, DEPOIS])
    monkeypatch.setattr(handler, "load_taxonomy_from_postgres", lambda url: next(taxonomias))

    handler._get_classifier()
    # A 034 muda o banco: a instância antiga continua com a taxonomia velha...
    handler._get_classifier()
    assert handler.NewsClassifier.call_args.kwargs["taxonomy"] == ANTES

    # ...e só uma instância nova (redeploy / novo start) enxerga o tema 26.
    monkeypatch.setattr(handler, "_classifier", None)
    handler._get_classifier()
    assert handler.NewsClassifier.call_args.kwargs["taxonomy"] == DEPOIS


def test_mapa_codigo_id_tambem_e_cache_por_instancia(fresh_instance, monkeypatch):
    mapas = iter([{"19.03": 100}, {"26.01": 200}])
    calls = []

    def _build(url):
        calls.append(url)
        return next(mapas)

    monkeypatch.setattr(handler, "build_theme_code_to_id_map", _build)

    assert handler._get_code_to_id() == {"19.03": 100}
    assert handler._get_code_to_id() == {"19.03": 100}
    assert len(calls) == 1

    monkeypatch.setattr(handler, "_code_to_id", None)
    assert handler._get_code_to_id() == {"26.01": 200}
