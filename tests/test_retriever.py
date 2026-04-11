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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json):
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
