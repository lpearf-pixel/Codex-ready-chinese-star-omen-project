from src.connectors.kb_search_retriever import KBSearchError, KBSearchRetriever


def test_health_calls_health_endpoint(monkeypatch):
    called = {}

    def fake_request(self, method, path, **kwargs):
        called["method"] = method
        called["path"] = path
        return {"ok": True}

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.health()
    assert out["ok"] is True
    assert called["method"] == "GET"
    assert called["path"] == "/v1/health"


def test_retrieve_request_payload(monkeypatch):
    captured = {}

    def fake_request(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs["json_payload"]
        captured["use_auth"] = kwargs["use_auth"]
        return {"hits": []}

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k", default_collection="local_kb_default")
    r.retrieve("荧惑", book_id="kaiyuan_zhanjing", card_types=["term_card"], evidence_level="structured", limit=5)
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/retrieve"
    assert captured["use_auth"] is True
    assert captured["payload"]["filters"]["book_id"] == "kaiyuan_zhanjing"
    assert captured["payload"]["collection"] == "local_kb_default"


def test_api_key_required():
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key=None)
    try:
        r._auth_headers()
        raise AssertionError("expected error")
    except KBSearchError as exc:
        assert "KB_SEARCH_API_KEY" in str(exc)


def test_api_key_headers_shape():
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="abc")
    headers = r._auth_headers()
    assert headers["Authorization"] == "Bearer abc"
    assert headers["X-API-Key"] == "abc"


def test_two_stage_retrieve(monkeypatch):
    calls = []

    def fake_retrieve(self, query, **kwargs):
        calls.append(kwargs)
        return {"hits": []}

    monkeypatch.setattr(KBSearchRetriever, "retrieve", fake_retrieve)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.two_stage_retrieve("荧惑守心", book_id="kaiyuan_zhanjing", limit=3)
    assert "stage1" in out and "stage2" in out
    assert calls[0]["card_types"] == ["xingguan_card", "zhusu_card", "term_card", "extract_card", "topic_index", "chapter_summary"]
    assert calls[1]["card_types"] == ["fenjuan", "fulltext"]
