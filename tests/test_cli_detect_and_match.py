import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_detect_and_match_cli_returns_json():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "detect-and-match",
            "--datetime",
            "2026-08-18T12:00:00Z",
            "--lon",
            "116.4",
            "--lat",
            "39.9",
            "--body",
            "mars",
            "--target",
            "xin_xiu",
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert "detected_events" in body
    assert "rule_matches" in body
    assert "clustered_events" in body
    assert "event_clusters" in body
    for field in [
        "calc_source",
        "calc_quality",
        "ephemeris_provider",
        "is_visible",
        "visibility_reason",
        "asterism_match_confidence",
        "event_cluster_id",
        "matched_rule_ids",
        "match_status",
        "match_score",
        "primary_evidence_found",
        "candidate_only",
    ]:
        assert field in body
    for event in body["clustered_events"]:
        for field in [
            "calc_source",
            "calc_quality",
            "ephemeris_provider",
            "is_visible",
            "visibility_reason",
            "asterism_match_confidence",
            "event_cluster_id",
        ]:
            assert field in event
