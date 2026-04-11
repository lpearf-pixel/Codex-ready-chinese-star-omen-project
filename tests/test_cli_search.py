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
        assert kwargs["book_id"] == "kaiyuan_zhanjing"
        assert kwargs["card_types"] == ["term_card"]
        assert kwargs["limit"] == 5
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
            "--limit",
            "5",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["hits"][0]["id"] == "x1"
