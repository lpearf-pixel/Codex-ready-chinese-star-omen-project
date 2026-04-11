import pytest

pytest.importorskip("httpx")

from src.connectors.kb_search_retriever import KBSearchRetriever


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"hits": [{"id": "n1"}]}


class DummyClient:
    def __init__(self, timeout):
        self.timeout = timeout
        self.payload = None
        self.last_url = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
        self.last_url = url
        self.payload = json
        assert url.endswith("/kb-search")
        return DummyResponse()


def test_kb_search_payload_filters(monkeypatch):
    created = {}

    def _client(timeout):
        cli = DummyClient(timeout)
        created["cli"] = cli
        return cli

    monkeypatch.setattr("src.connectors.kb_search_retriever.httpx.Client", _client)
    r = KBSearchRetriever("http://localhost:9000")
    out = r.search("荧惑", book_id="kaiyuan_zhanjing", card_types=["term_card"], evidence_level="structured")
    assert out["hits"][0]["id"] == "n1"
    assert created["cli"].payload["filters"]["book_id"] == "kaiyuan_zhanjing"


def test_kb_search_uses_config_default_url(monkeypatch):
    created = {}

    def _client(timeout):
        cli = DummyClient(timeout)
        created["cli"] = cli
        return cli

    class Cfg:
        base_url = "http://localhost:8008"
        timeout_seconds = 5.0

    monkeypatch.setattr("src.connectors.kb_search_retriever.httpx.Client", _client)
    monkeypatch.setattr("src.connectors.kb_search_retriever.load_kb_search_config", lambda: Cfg())

    r = KBSearchRetriever()
    r.search("荧惑")
    assert created["cli"].timeout == 5.0
    assert created["cli"].last_url == "http://localhost:8008/kb-search"
