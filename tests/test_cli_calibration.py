import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_cli_analyze_reviews_and_compare_thresholds(tmp_path):
    runner = CliRunner()
    reviewed = tmp_path / "reviewed.jsonl"
    reviewed.write_text("", encoding="utf-8")
    queue = tmp_path / "queue.jsonl"
    queue.write_text("", encoding="utf-8")
    r1 = runner.invoke(app, ["analyze-reviews", "--review-queue", str(queue), "--reviewed", str(reviewed)])
    assert r1.exit_code == 0
    body1 = json.loads(r1.stdout)
    assert "rule_accept_rate" in body1

    r2 = runner.invoke(
        app,
        [
            "compare-thresholds",
            "--cases",
            "data/examples/historical_benchmark",
            "--profiles",
            "baseline",
            "--profiles",
            "strict",
        ],
    )
    assert r2.exit_code == 0
    body2 = json.loads(r2.stdout)
    assert "profiles" in body2
