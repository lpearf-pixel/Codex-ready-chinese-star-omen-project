import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_cli_build_review_and_review_item(tmp_path):
    runner = CliRunner()
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(
        json.dumps(
            {
                "case_id": "bench_cli_001",
                "window": {"start_datetime_utc": "2026-01-01T00:00:00Z", "end_datetime_utc": "2026-01-02T00:00:00Z"},
                "matched_rule_ids": ["rule_mars_guarding_xin_001"],
                "match_status": "matched",
                "match_score": 0.8,
                "primary_evidence_found": True,
                "candidate_only": False,
                "representative_events": [{"event_type": "guarding", "body": "mars", "target_asterism": "xin_xiu"}],
                "rule_matches": [{"match_status": "matched", "match_score": 0.8, "primary_evidence_found": True, "candidate_only": False}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    queue_path = tmp_path / "review_queue.jsonl"
    reviewed_path = tmp_path / "reviewed_cases.jsonl"
    out = runner.invoke(
        app,
        ["build-review-queue", "--from-benchmark", str(benchmark_path), "--queue-path", str(queue_path)],
    )
    assert out.exit_code == 0
    payload = json.loads(out.stdout)
    assert payload["created_count"] >= 1
    item_id = payload["items"][0]["review_item_id"]

    out2 = runner.invoke(
        app,
        [
            "review-item",
            "--id",
            item_id,
            "--status",
            "accepted",
            "--notes",
            "manual pass",
            "--queue-path",
            str(queue_path),
            "--reviewed-path",
            str(reviewed_path),
        ],
    )
    assert out2.exit_code == 0
    payload2 = json.loads(out2.stdout)
    assert payload2["item"]["review_status"] == "accepted"
