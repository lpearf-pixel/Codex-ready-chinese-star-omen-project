import json
from pathlib import Path

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
    assert captured["payload"]["retrieval_pool"]["stage1"]
    assert captured["payload"]["retrieval_pool"]["stage2"] == ["fenjuan", "fulltext"]
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


def test_qa_example_excluded_from_knowledge(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {"chunk_id": "q1", "title": "样例", "path": "/docs/问答样例库/x.md", "snippet": "心宿", "card_type": "qa_example"},
                {"chunk_id": "k1", "title": "心宿", "path": "/docs/古籍/唐開元占經/逐宿卡/心宿.md", "snippet": "心宿", "card_type": "zhusu_card"},
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("心宿")
    assert [h["chunk_id"] for h in out["hits"]] == ["k1"]


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


def test_flattened_top_level_metadata_is_preferred(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {
                    "chunk_id": "x1",
                    "title": "荧惑守心",
                    "path": "/docs/古籍/唐開元占經/术语卡片/荧惑守心.md",
                    "snippet": "荧惑守心",
                    "book_id": "top_level_book",
                    "card_type": "fenjuan",
                    "evidence_level": "primary",
                    "metadata": {
                        "book_id": "nested_book",
                        "card_type": "term_card",
                        "evidence_level": "structured",
                    },
                }
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("荧惑守心")
    assert out["hits"][0]["book_id"] == "top_level_book"
    assert out["hits"][0]["card_type"] == "fenjuan"
    assert out["hits"][0]["evidence_level"] == "primary"


def test_anchor_fields_are_present_in_normalized_hit(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {
            "hits": [
                {
                    "chunk_id": "x1",
                    "title": "卷十二",
                    "path": "/docs/古籍/唐開元占經/分卷/卷十二.md",
                    "snippet": "荧惑守心",
                    "card_type": "fenjuan",
                    "evidence_level": "primary",
                }
            ]
        }

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("荧惑守心")
    hit = out["hits"][0]
    assert hit["volume"] == "卷十二"
    assert hit["section"] == "卷十二"
    assert hit["source_locator"] == "卷十二/卷十二"
    assert hit["heading_path"] == ["卷十二"]
    assert hit["anchor_text"].startswith("荧惑守心")


def test_retrieve_output_contains_payload_contract_spec(monkeypatch):
    def fake_request(self, method, path, **kwargs):
        return {"hits": []}

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.retrieve("心宿")
    assert out["payload_contract_version"] == "v2"
    assert out["retrieval_pool_spec"]["stage2"] == ["fenjuan", "fulltext"]


def test_support_mode_not_output_primary_candidates(monkeypatch):
    monkeypatch.setattr(KBSearchRetriever, "_request", lambda self, method, path, **kwargs: {"hits": []})
    monkeypatch.setattr(
        KBSearchRetriever,
        "_scan_primary_files",
        lambda self, query, book_id, mode, limit=3, query_variants=None: (
            [{"chunk_id": "p1", "card_type": "fenjuan", "title": "卷十二", "snippet": "说明性内容"}],
            {"files_scanned": 1, "matched_files": [], "matched_headings": []},
        ),
    )
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")
    out = r.two_stage_retrieve("如何理解荧惑守心", query_mode="support")
    assert out["stage2"]["primary_candidates"] == []


def test_min_retrieval_eval_set_defaults():
    eval_path = Path("data/examples/min_retrieval_eval_set.json")
    rows = json.loads(eval_path.read_text(encoding="utf-8"))
    assert [item["query"] for item in rows] == ["心宿", "荧惑", "荧惑守心", "月犯心宿", "五星聚"]

    for item in rows:
        mode = KBSearchRetriever._query_mode(item["query"])
        assert mode == item["expected_query_mode"]


def test_min_retrieval_eval_set_literal_first_defaults(monkeypatch):
    captured_payloads = []

    def fake_request(self, method, path, **kwargs):
        captured_payloads.append(kwargs["json_payload"])
        return {"hits": []}

    monkeypatch.setattr(KBSearchRetriever, "_request", fake_request)
    r = KBSearchRetriever(base_url="http://127.0.0.1:8008", api_key="k")

    rows = json.loads(Path("data/examples/min_retrieval_eval_set.json").read_text(encoding="utf-8"))
    for item in rows:
        r.retrieve(item["query"])

    assert len(captured_payloads) == 5
    for row, payload in zip(rows, captured_payloads):
        assert payload["query_mode"] == row["expected_query_mode"]
        assert payload["literal_first"] == row["expected_literal_first"]
