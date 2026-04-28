import json
from pathlib import Path

from src.review.review_queue import (
    build_review_queue_from_benchmark,
    export_review_markdown,
    load_jsonl,
    update_review_item,
)


def _sample_benchmark() -> dict:
    return {
        "case_id": "bench_demo_001",
        "window": {"start_datetime_utc": "2026-01-01T00:00:00Z", "end_datetime_utc": "2026-01-02T00:00:00Z"},
        "matched_rule_ids": ["rule_mars_guarding_xin_001"],
        "match_status": "matched",
        "match_score": 0.9,
        "primary_evidence_found": True,
        "candidate_only": False,
        "representative_events": [
            {"id": "e1", "event_type": "guarding", "body": "mars", "target_asterism": "xin_xiu"},
        ],
        "rule_matches": [{"match_status": "matched", "match_score": 0.9, "primary_evidence_found": True, "candidate_only": False}],
    }


def test_build_review_queue_and_update_persist(tmp_path: Path):
    queue_path = tmp_path / "review_queue.jsonl"
    reviewed_path = tmp_path / "reviewed_cases.jsonl"

    out = build_review_queue_from_benchmark(_sample_benchmark(), queue_path=queue_path)
    assert out["created_count"] >= 1
    rows = load_jsonl(queue_path)
    assert len(rows) >= 1
    item_id = rows[0]["review_item_id"]

    updated = update_review_item(
        review_item_id=item_id,
        status="accepted",
        notes="looks good",
        queue_path=queue_path,
        reviewed_path=reviewed_path,
    )
    assert updated["item"]["review_status"] == "accepted"
    reviewed_rows = load_jsonl(reviewed_path)
    assert len(reviewed_rows) == 1


def test_export_review_markdown_contains_summary():
    queue_rows = [
        {
            "review_item_id": "review_bench_demo_001_01",
            "case_id": "bench_demo_001",
            "representative_event": {"event_type": "guarding", "body": "mars", "target_asterism": "xin_xiu"},
            "matched_rule_ids": ["rule_mars_guarding_xin_001"],
            "primary_evidence_found": True,
            "candidate_only": False,
            "review_status": "pending",
            "review_notes": "",
        }
    ]
    markdown = export_review_markdown(queue_rows=queue_rows, benchmark_payloads=[_sample_benchmark()])
    assert "# Review Queue Summary" in markdown
    assert "review_bench_demo_001_01" in markdown
