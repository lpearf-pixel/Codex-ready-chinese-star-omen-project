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
    assert captured["payload"]["query"] == "荧惑"
    assert "filters" not in captured["payload"]
    assert captured["payload"]["collection"] == "local_kb_default"


def test_retrieve_reranks_exact_hit_first(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {"chunk_id": "c2", "title": "危宿", "path": "/docs/古籍/唐開元占經/逐宿卡/危宿.md", "snippet": "..."},
                {"chunk_id": "c1", "title": "心宿", "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md", "snippet": "..."},
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("心宿", card_types=["zhusu_card"])
    assert out["hits"][0]["chunk_id"] == "c1"
    assert out["exact_hits"][0]["chunk_id"] == "c1"
    assert out["hits"][0]["book_id"] == "kaiyuan_zhanjing"


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


def test_stage2_structured_to_primary_resolution(monkeypatch):
    def fake_retrieve(self, query, **kwargs):
        card_types = kwargs.get("card_types") or []
        if "zhusu_card" in card_types:
            return {
                "hits": [{"chunk_id": "s1", "title": "心宿", "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md", "card_type": "zhusu_card", "evidence_level": "structured"}],
                "exact_hits": [{"chunk_id": "s1", "title": "心宿", "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md"}],
            }
        return {
            "hits": [{"chunk_id": "p1", "title": "卷十二", "path": "/docs/古籍/唐開元占經/分卷/卷十二.md", "card_type": "fenjuan", "evidence_level": "primary"}],
            "exact_hits": [],
        }

    monkeypatch.setattr(KBSearchRetriever, "retrieve", fake_retrieve)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.two_stage_retrieve("心宿", book_id="kaiyuan_zhanjing", limit=3)
    assert out["stage2"]["primary_candidates"][0]["chunk_id"] == "p1"
    assert out["stage2"]["only_structured_no_primary"] is False
