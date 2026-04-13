import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_search_kb_command(monkeypatch):
    def fake_search(self, query, **kwargs):
        assert query == "荧惑守心"
        assert kwargs["top_k"] == 5
        assert kwargs["filters"]["book_id"] == "kaiyuan_zhanjing"
        assert kwargs["filters"]["card_type"] == ["term_card"]
        return {"hits": [{"id": "x1"}]}

    monkeypatch.setattr("src.cli.KBSearchRetriever.search", fake_search)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "search-kb",
            "荧惑守心",
            "--book-id",
            "kaiyuan_zhanjing",
            "--card-type",
            "term_card",
            "--top-k",
            "5",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["hits"][0]["id"] == "x1"


def test_cli_limit_overrides_env(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LIMIT", "8")

    def fake_two_stage(self, query, **kwargs):
        assert kwargs["top_k"] == 3
        return {"stage1": {"hits": []}, "stage2": {"hits": []}}

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)

    runner = CliRunner()
    result = runner.invoke(app, ["inspect-kb", "--query", "荧惑守心", "--limit", "3"])
    assert result.exit_code == 0
