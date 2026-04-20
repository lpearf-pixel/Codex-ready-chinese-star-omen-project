import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_match_rule_command_outputs_json():
    runner = CliRunner()
    result = runner.invoke(app, ["match-rule", "--event", "data/examples/events/mars_guarding_xin_demo.json"])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert "matched_rule_ids" in body
    assert "rule_mars_guarding_xin_001" in body["matched_rule_ids"]
