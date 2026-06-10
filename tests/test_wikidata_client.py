"""
Testes do WikidataClient (Fase 3).

Todo o HTTP é mockado (httpx.Client injetado). Nenhuma chamada real à Wikidata.
"""

from unittest.mock import MagicMock

from news_enrichment.wikidata_client import (
    QID_BRAZIL,
    Candidate,
    WikidataClient,
)


def _mock_httpx_client(payloads):
    """httpx.Client falso cujo .get(...).json() devolve payloads em sequência.

    payloads: lista de dicts (um por chamada GET) OU um único dict (repetido).
    """
    client = MagicMock()

    if isinstance(payloads, dict):
        payloads = [payloads]
    state = {"i": 0}

    def _get(url, params=None):
        resp = MagicMock()
        idx = min(state["i"], len(payloads) - 1)
        resp.json.return_value = payloads[idx]
        resp.raise_for_status.return_value = None
        state["i"] += 1
        return resp

    client.get.side_effect = _get
    return client


class TestSearch:
    def test_returns_candidates(self):
        payload = {
            "search": [
                {"id": "Q42", "label": "Foo", "description": "uma org"},
                {"id": "Q43", "label": "Bar", "description": "outra"},
            ]
        }
        wc = WikidataClient(client=_mock_httpx_client(payload))
        out = wc.search("foo", type="ORG")
        assert [c.qid for c in out] == ["Q42", "Q43"]
        assert isinstance(out[0], Candidate)
        assert out[0].label == "Foo"

    def test_empty_name_returns_empty_without_http(self):
        client = _mock_httpx_client({"search": []})
        wc = WikidataClient(client=client)
        assert wc.search("") == []
        client.get.assert_not_called()

    def test_caches_repeated_search(self):
        client = _mock_httpx_client({"search": [{"id": "Q1", "label": "x", "description": ""}]})
        wc = WikidataClient(client=client)
        wc.search("mesma coisa")
        wc.search("mesma coisa")
        # apenas uma chamada HTTP (cache em memória).
        assert client.get.call_count == 1

    def test_http_failure_returns_empty_never_raises(self):
        client = MagicMock()
        client.get.side_effect = Exception("network down")
        wc = WikidataClient(client=client, max_retries=2)
        out = wc.search("qualquer")
        assert out == []
        # tentou retries.
        assert client.get.call_count == 2


class TestGetClaims:
    def test_extracts_country_and_instance_of(self):
        claims_payload = {
            "entities": {
                "Q100": {
                    "claims": {
                        "P17": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "wikibase-entityid",
                                        "value": {"id": QID_BRAZIL},
                                    }
                                }
                            }
                        ],
                        "P31": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "wikibase-entityid",
                                        "value": {"id": "Q327333"},
                                    }
                                }
                            }
                        ],
                    },
                    "labels": {"pt": {"value": "Ministério X"}},
                    "descriptions": {"pt": {"value": "órgão brasileiro"}},
                }
            }
        }
        wc = WikidataClient(client=_mock_httpx_client(claims_payload))
        claims = wc.get_claims("Q100")
        assert claims["country"] == QID_BRAZIL
        assert claims["country_is_br"] is True
        assert claims["instance_of"] == ["Q327333"]
        assert claims["label"] == "Ministério X"
        assert claims["description"] == "órgão brasileiro"

    def test_foreign_country_not_br(self):
        claims_payload = {
            "entities": {
                "Q200": {
                    "claims": {
                        "P17": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "wikibase-entityid",
                                        "value": {"id": "Q822"},  # Líbano
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        wc = WikidataClient(client=_mock_httpx_client(claims_payload))
        claims = wc.get_claims("Q200")
        assert claims["country"] == "Q822"
        assert claims["country_is_br"] is False

    def test_missing_claims_returns_partial(self):
        wc = WikidataClient(client=_mock_httpx_client({"entities": {"Q5": {}}}))
        claims = wc.get_claims("Q5")
        assert claims["country"] is None
        assert claims["instance_of"] == []

    def test_caches_claims(self):
        client = _mock_httpx_client({"entities": {"Q9": {"claims": {}}}})
        wc = WikidataClient(client=client)
        wc.get_claims("Q9")
        wc.get_claims("Q9")
        assert client.get.call_count == 1

    def test_http_failure_returns_empty_dict(self):
        client = MagicMock()
        client.get.side_effect = Exception("boom")
        wc = WikidataClient(client=client, max_retries=1)
        assert wc.get_claims("Q1") == {}

    def test_empty_qid_returns_empty(self):
        client = MagicMock()
        wc = WikidataClient(client=client)
        assert wc.get_claims("") == {}
        client.get.assert_not_called()
