import json
import shutil
from pathlib import Path

from src.cli import generate_candidate_card_impl
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
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["candidates"]
        assert manifest[0]["id"] == "kaiyuan_zhanjing:熒惑守心:KR3g0018_031:12345"
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
