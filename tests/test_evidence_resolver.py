from pathlib import Path

from src.connectors.evidence_resolver import resolve_evidence


def test_resolve_evidence_marks_candidate_only_for_non_primary(tmp_path: Path):
    e = {"card_type": "term_card", "relative_path": "a.md"}
    out = resolve_evidence(e, tmp_path)
    assert out["status"] == "candidate_only"
    assert out["final_citable"] is False
    assert out["ingest_source"] == "obsidian"
    assert out["source_type"] == "docs"


def test_resolve_evidence_marks_citable_for_fenjuan(tmp_path: Path):
    file_path = tmp_path / "docs" / "x.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("hello", encoding="utf-8")
    e = {"card_type": "fenjuan", "relative_path": "docs/x.md", "locator": "卷十二", "quote": "荧惑守心"}
    out = resolve_evidence(e, tmp_path)
    assert out["status"] == "citable"
    assert out["path_exists"] is True
    assert out["volume"] == "卷十二"
    assert out["section"] == "卷十二"
    assert out["source_locator"] == "卷十二"
    assert out["anchor_text"] == "荧惑守心"


def test_resolve_evidence_includes_anchor_fields():
    out = resolve_evidence(
        {
            "card_type": "fenjuan",
            "relative_path": "docs/卷十二.md",
            "volume": "卷十二",
            "section": "荧惑占",
            "source_locator": "卷十二/荧惑占/第三段",
            "heading_path": ["卷十二", "荧惑占"],
            "anchor_text": "荧惑守心",
            "paragraph_index": 2,
        }
    )
    assert out["volume"] == "卷十二"
    assert out["section"] == "荧惑占"
    assert out["source_locator"] == "卷十二/荧惑占/第三段"
    assert out["heading_path"] == ["卷十二", "荧惑占"]
    assert out["anchor_text"] == "荧惑守心"
    assert out["paragraph_index"] == 2
