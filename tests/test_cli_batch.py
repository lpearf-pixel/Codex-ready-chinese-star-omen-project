import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_cli_batch_and_index_and_layered_report():
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["run-batch", "--cases", "data/examples/historical_benchmark", "--profiles", "baseline"],
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    run_id = payload["run_id"]
    assert "summary" in payload

    idx = runner.invoke(app, ["export-batch-index", "--run", run_id, "--format", "json"])
    assert idx.exit_code == 0
    idx_payload = json.loads(idx.stdout)
    assert idx_payload["format"] == "json"

    stab = runner.invoke(app, ["profile-stability", "--profile", "baseline"])
    assert stab.exit_code == 0
    stab_payload = json.loads(stab.stdout)
    assert "promotion_confidence" in stab_payload

    layer = runner.invoke(app, ["export-layered-report", "--run", run_id, "--level", "research_draft"])
    assert layer.exit_code == 0
    layer_payload = json.loads(layer.stdout)
    assert "files" in layer_payload
