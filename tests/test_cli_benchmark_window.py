import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_benchmark_window_cli_outputs_required_fields():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "benchmark-window",
            "--case",
            "data/examples/historical_benchmark/case_mars_guarding_xin_001.json",
            "--force-fallback",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    for field in [
        "case_id",
        "window",
        "raw_event_count",
        "clustered_event_count",
        "matched_rule_ids",
        "primary_evidence_hit_rate",
        "candidate_only_rate",
        "benchmark_summary",
        "metrics",
    ]:
        assert field in payload
    for metric in [
        "window_count",
        "detected_event_count",
        "clustered_event_count",
        "matched_rule_count",
        "primary_evidence_hit_rate",
        "candidate_only_rate",
        "review_accept_rate",
        "review_reject_rate",
        "needs_more_evidence_rate",
    ]:
        assert metric in payload["metrics"]
