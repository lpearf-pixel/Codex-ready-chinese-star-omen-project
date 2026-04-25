import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_scan_window_cli_outputs_json_contract():
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "scan-window",
            "--start",
            "2026-01-31T00:00:00Z",
            "--end",
            "2026-02-02T00:00:00Z",
            "--lon",
            "116.4",
            "--lat",
            "39.9",
            "--bodies",
            "mars",
            "--bodies",
            "moon",
            "--bodies",
            "jupiter",
            "--bodies",
            "saturn",
            "--targets",
            "xin_xiu",
            "--targets",
            "jiao_xiu",
            "--targets",
            "fang_xiu",
            "--event-types",
            "guarding",
            "--event-types",
            "invading",
            "--event-types",
            "conjunction",
            "--event-types",
            "gathering",
            "--force-fallback",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    for field in [
        "scan_params",
        "raw_event_count",
        "clustered_event_count",
        "representative_events",
        "matched_rule_ids",
        "calc_source",
        "calc_quality",
        "is_visible",
        "match_status",
        "match_score",
        "primary_evidence_found",
        "metrics",
    ]:
        assert field in payload
