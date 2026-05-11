import json
import shutil
from pathlib import Path

from src.cli import generate_candidate_card_impl, sync_upstream_status_impl
from src.connectors.kb_search_retriever import KBSearchRetriever


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---", 4)
    assert end > 0
    meta = {}
    for line in text[4:end].splitlines():
        key, value = line.split(":", 1)
        meta[key.strip()] = json.loads(value.strip())
    return meta


def test_generate_candidate_card_frontmatter_manifest_and_no_ingest(monkeypatch):
    out_dir = Path("data/generated_candidates/test_extract_cards/kaiyuan_zhanjing")
    if out_dir.exists():
        shutil.rmtree(out_dir)

    def fake_scan(self, query, *, book_id, mode, limit=3, query_variants=None):
        return (
            [
                {
                    "path": "/kb/docs/古籍/唐開元占經/分卷/KR3g0018_031.md",
                    "title": "KR3g0018_031",
                    "book_title": "唐開元占經",
                    "kb_book_id": "kaiyuan_zhanjing",
                    "book_id": "kaiyuan_zhanjing",
                    "card_type": "fenjuan",
                    "evidence_level": "primary",
                    "match_type": "exact_phrase",
                    "match_offset": 12345,
                    "excerpt": "卷三十一……熒惑守心……",
                    "snippet": "卷三十一……熒惑守心……",
                    "matched_variants": ["熒惑守心"],
                }
            ],
            {"files_scanned": 200, "matched_headings": ["KR3g0018_031"]},
        )

    monkeypatch.setattr(KBSearchRetriever, "_scan_primary_files", fake_scan)
    try:
        out = generate_candidate_card_impl("荧惑守心", "kaiyuan_zhanjing", out_dir, limit=8)
        assert out["generated_count"] == 1
        manifest_path = Path(out["manifest_path"])
        manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "base_corpus_version" in manifest_doc
        assert "base_ingest_run_id" in manifest_doc
        assert "current_upstream_corpus_version" in manifest_doc
        assert "last_synced_at" in manifest_doc
        manifest = manifest_doc["items"]
        assert manifest[0]["id"] == "kaiyuan_zhanjing:熒惑守心:KR3g0018_031:12345"
        assert manifest[0]["sync_status"] == "pending"
        assert manifest[0]["content_hash"]
        assert manifest[0]["anchor_text"] == "卷三十一……熒惑守心……"
        assert manifest[0]["source_locator"] == "KR3g0018_031"
        assert manifest[0]["match_offset"] == 12345
        card_path = Path(manifest[0]["path"])
        meta = _parse_frontmatter(card_path)
        for key in [
            "kb_book_id",
            "book_title",
            "card_type",
            "evidence_level",
            "generated_status",
            "generated_by",
            "review_status",
            "source_namespace",
            "term",
            "aliases",
            "source_file",
            "source_locator",
            "source_volume",
            "page_marker",
            "heading_path",
            "paragraph_index",
            "match_type",
            "match_offset",
            "anchor_text",
            "content_hash",
        ]:
            assert key in meta
        assert meta["card_type"] == "extract_card"
        assert meta["evidence_level"] == "candidate"
        assert meta["generated_by"] == "codex_ready_filesystem_fallback"
        assert meta["review_status"] == "pending"
        assert meta["source_namespace"] == "downstream_generated"
        assert meta["source_file"].endswith("KR3g0018_031.md")
        assert "熒惑守心" in meta["anchor_text"]
    finally:
        if out_dir.parents[0].exists():
            shutil.rmtree(out_dir.parents[0])



def test_sync_upstream_status_marks_merged_and_clears_cache(monkeypatch, tmp_path):
    candidate_root = tmp_path / "generated_candidates"
    out_dir = candidate_root / "extract_cards" / "kaiyuan_zhanjing"
    out_dir.mkdir(parents=True)
    source_file = tmp_path / "KR3g0018_031.md"
    source_file.write_text("熒惑守心", encoding="utf-8")
    cache_dir = Path("data/cache/kb_queries")
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "old.json").write_text("{}", encoding="utf-8")
    manifest_path = out_dir / "candidate_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "base_corpus_version": "v1",
                "base_ingest_run_id": "run1",
                "current_upstream_corpus_version": "v1",
                "last_synced_at": None,
                "items": [
                    {
                        "id": "kaiyuan_zhanjing:熒惑守心:KR3g0018_031:12345",
                        "path": str(out_dir / "candidate.md"),
                        "kb_book_id": "kaiyuan_zhanjing",
                        "term": "荧惑守心",
                        "source_file": str(source_file),
                        "source_locator": "KR3g0018_031",
                        "match_offset": 12345,
                        "review_status": "pending",
                        "sync_status": "pending",
                        "content_hash": "hash-123",
                        "anchor_text": "卷三十一……熒惑守心……",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(KBSearchRetriever, "upstream_meta", lambda self: {"corpus_version": "v2", "ingest_run_id": "run2"})
    monkeypatch.setattr(
        KBSearchRetriever,
        "retrieve",
        lambda self, query, **kwargs: {"hits": [{"content_hash": "hash-123", "snippet": "卷三十一 熒惑守心"}], "exact_hits": [], "related_hits": []},
    )
    try:
        out = sync_upstream_status_impl("kaiyuan_zhanjing", candidate_root, base_url="http://127.0.0.1:8008", api_key="k")
        synced = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert synced["current_upstream_corpus_version"] == "v2"
        assert synced["items"][0]["sync_status"] == "merged"
        assert out["cleared_cache"] == ["data/cache/kb_queries"]
        assert not cache_dir.exists()
    finally:
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


def test_sync_upstream_status_marks_needs_review_pending_and_stale(monkeypatch, tmp_path):
    candidate_root = tmp_path / "generated_candidates"
    out_dir = candidate_root / "extract_cards" / "kaiyuan_zhanjing"
    out_dir.mkdir(parents=True)
    source_file = tmp_path / "KR3g0018_031.md"
    source_file.write_text("熒惑守心", encoding="utf-8")
    missing_source = tmp_path / "missing.md"
    manifest_path = out_dir / "candidate_manifest.json"
    items = [
        {"id": "needs", "path": "needs.md", "kb_book_id": "kaiyuan_zhanjing", "term": "荧惑守心", "source_file": str(source_file), "source_locator": "KR3g0018_031", "match_offset": 1, "sync_status": "pending", "content_hash": "h1", "anchor_text": "原锚点"},
        {"id": "pending", "path": "pending.md", "kb_book_id": "kaiyuan_zhanjing", "term": "五星聚", "source_file": str(source_file), "source_locator": "KR3g0018_032", "match_offset": 2, "sync_status": "pending", "content_hash": "h2", "anchor_text": "五星聚"},
        {"id": "stale", "path": "stale.md", "kb_book_id": "kaiyuan_zhanjing", "term": "月犯心宿", "source_file": str(missing_source), "source_locator": "KR3g0018_033", "match_offset": 3, "sync_status": "pending", "content_hash": "h3", "anchor_text": "月犯心宿"},
    ]
    manifest_path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(KBSearchRetriever, "upstream_meta", lambda self: {"corpus_version": "v1", "ingest_run_id": "run1"})

    def fake_retrieve(self, query, **kwargs):
        if "荧惑守心" in query:
            return {"hits": [{"snippet": "荧惑守心 但锚点不同"}], "exact_hits": [], "related_hits": []}
        return {"hits": [], "exact_hits": [], "related_hits": []}

    monkeypatch.setattr(KBSearchRetriever, "retrieve", fake_retrieve)
    sync_upstream_status_impl("kaiyuan_zhanjing", candidate_root, api_key="k")
    synced = json.loads(manifest_path.read_text(encoding="utf-8"))["items"]
    assert [item["sync_status"] for item in synced] == ["needs_review", "pending", "stale"]
