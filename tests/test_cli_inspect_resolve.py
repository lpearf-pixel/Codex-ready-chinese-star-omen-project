import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_inspect_kb_with_query_filters(monkeypatch, tmp_path):
    def fake_search(self, query, **kwargs):
        assert query == "荧惑守心"
        assert kwargs["book_id"] == "kaiyuan_zhanjing"
        assert kwargs["card_types"] == ["term_card"]
        assert kwargs["evidence_level"] == "structured"
        return {"hits": [{"id": "n1"}]}

    monkeypatch.setattr("src.cli.KBSearchRetriever.search", fake_search)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "inspect-kb",
            "--root",
            str(tmp_path),
            "--query",
            "荧惑守心",
            "--book-id",
            "kaiyuan_zhanjing",
            "--card-type",
            "term_card",
            "--evidence-level",
            "structured",
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["mode"] == "search"
    assert body["result"]["hits"][0]["id"] == "n1"


def test_resolve_evidence_output_contains_required_fields(tmp_path):
    rule = {
        "id": "r1",
        "evidence": {
            "relative_path": "docs/古籍/唐開元占經/分卷/卷十二.md",
            "locator": "卷十二/荧惑占/第三段",
            "quote": "荧惑守心",
            "card_type": "fenjuan",
        },
    }
    p = tmp_path / "rule.json"
    p.write_text(json.dumps(rule, ensure_ascii=False), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["resolve-evidence", "--rule", str(p)])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    for field in ["relative_path", "locator", "quote", "card_type", "evidence_level"]:
        assert field in body
