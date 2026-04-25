import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_replay_event_cli_outputs_required_fields():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "replay-event",
            "--case",
            "data/examples/historical_replay/mars_guarding_xin_case.json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    for field in [
        "input_case_id",
        "input_datetime_utc",
        "location",
        "calc_source",
        "calc_quality",
        "generated_events",
        "clustered_events",
        "matched_rule_ids",
        "match_status",
        "match_score",
        "evidence_summary",
        "primary_evidence_found",
        "candidate_only",
    ]:
        assert field in payload
