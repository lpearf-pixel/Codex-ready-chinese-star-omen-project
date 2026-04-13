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
    r.retrieve(
        "荧惑",
        top_k=5,
        filters={"book_id": "kaiyuan_zhanjing", "card_type": ["term_card"], "evidence_level": "structured"},
        query_mode="knowledge",
        literal_first=False,
        literal_pool_factor=3,
    )
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/retrieve"
    assert captured["use_auth"] is True
    assert captured["payload"]["query"] == "荧惑"
    assert captured["payload"]["top_k"] == 5
    assert captured["payload"]["filters"]["book_id"] == "kaiyuan_zhanjing"
    assert captured["payload"]["query_mode"] == "knowledge"
    assert captured["payload"]["literal_first"] is False
    assert captured["payload"]["literal_pool_factor"] == 3
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
    out = r.retrieve("心宿", filters={"card_type": ["zhusu_card"]})
    assert out["hits"][0]["chunk_id"] == "c1"
    assert out["exact_hits"][0]["chunk_id"] == "c1"
    assert out["query_mode"] == "knowledge"


def test_evidence_mode_filters_prompt_and_nav(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {"chunk_id": "p1", "title": "Agent", "path": "/docs/古籍/唐開元占經/prompts/x.md", "snippet": "荧惑守心"},
                {"chunk_id": "n1", "title": "导航", "path": "/docs/古籍/唐開元占經/导航/总览.md", "snippet": "荧惑守心"},
                {"chunk_id": "t1", "title": "荧惑守心", "path": "/docs/古籍/唐開元占經/术语卡片/荧惑守心.md", "snippet": "荧惑守心"},
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("荧惑守心")
    ids = [h["chunk_id"] for h in out["hits"]]
    assert "p1" not in ids and "n1" not in ids


def test_phrase_fallback_finds_primary_candidate(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {"chunk_id": "s1", "title": "心宿", "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md", "snippet": "心宿相关"},
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    calls = {"count": 0}
    def fake_scan(self, query, book_id, mode, limit=3, query_variants=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return ([{"chunk_id": "p0", "card_type": "fenjuan", "title": "卷十二", "snippet": "相关记载"}], {"files_scanned": 3, "matched_files": [], "matched_headings": []})
        return ([{"chunk_id": "p1", "card_type": "fenjuan", "title": "卷十二", "snippet": "荧惑守心"}], {"files_scanned": 2, "matched_files": ["/docs/古籍/唐開元占經/分卷/卷十二.md"], "matched_headings": ["卷十二"]})

    monkeypatch.setattr(KBSearchRetriever, "_scan_primary_files", fake_scan)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")

    out = r.two_stage_retrieve("荧惑守心", filters={"book_id": "kaiyuan_zhanjing"})
    assert out["stage2"]["primary_candidates"]
    assert out["stage2"]["primary_candidates"][0]["card_type"] in {"fenjuan", "fulltext"}
    assert out["stage2"]["fallback_used"] is True


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


def test_stage2_uses_primary_not_structured(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {"chunk_id": "s1", "title": "心宿", "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md", "snippet": "心宿"},
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    monkeypatch.setattr(
        KBSearchRetriever,
        "_scan_primary_files",
        lambda self, query, book_id, mode, limit=3, query_variants=None: (
            [{"chunk_id": "p1", "card_type": "fenjuan", "title": "卷十二", "snippet": "荧惑守心"}],
            {"files_scanned": 1, "matched_files": ["/docs/古籍/唐開元占經/分卷/卷十二.md"], "matched_headings": ["卷十二"]},
        ),
    )

    out = r.two_stage_retrieve("心宿", filters={"book_id": "kaiyuan_zhanjing"}, top_k=3)
    assert out["stage2"]["primary_candidates"][0]["card_type"] == "fenjuan"
    assert out["stage2"]["only_structured_no_primary"] is False


def test_evidence_defaults_literal_first(monkeypatch):
    captured = {}

    def fake_request(self, method, path, **kwargs):
        captured["payload"] = kwargs["json_payload"]
        return {"hits": []}

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    r.retrieve("荧惑守心")
    assert captured["payload"]["query_mode"] == "evidence"
    assert captured["payload"]["literal_first"] is True


def test_primary_candidates_excludes_structured(monkeypatch):
    monkeypatch.setattr(KBSearchRetriever, "_request", lambda self, method, path, **kwargs: {"hits": []})

    def fake_scan(self, query, book_id, mode, limit=3, query_variants=None):
        return (
            [
                {"chunk_id": "s1", "card_type": "term_card", "title": "术语", "snippet": "荧惑守心"},
                {"chunk_id": "p1", "card_type": "fenjuan", "title": "卷十二", "snippet": "荧惑守心"},
            ],
            {"files_scanned": 1, "matched_files": [], "matched_headings": []},
        )

    monkeypatch.setattr(KBSearchRetriever, "_scan_primary_files", fake_scan)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.two_stage_retrieve("荧惑守心")
    assert [h["card_type"] for h in out["stage2"]["primary_candidates"]] == ["fenjuan"]


def test_hit_metadata_priority_over_path_inference(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {
                    "chunk_id": "x1",
                    "title": "心宿",
                    "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md",
                    "snippet": "心宿",
                    "card_type": "fenjuan",
                    "book_id": "override_book",
                    "evidence_level": "primary",
                }
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("心宿")
    assert out["hits"][0]["card_type"] == "fenjuan"
    assert out["hits"][0]["book_id"] == "override_book"
