import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_inspect_kb_with_query_filters(monkeypatch, tmp_path):
    def fake_two_stage(self, query, **kwargs):
        assert query == "荧惑守心"
        assert kwargs["book_id"] == "kaiyuan_zhanjing"
        return {
            "stage1": {"hits": [{"id": "n1", "card_type": "term_card"}]},
            "stage2": {"hits": [{"id": "n2", "card_type": "fenjuan"}]},
        }

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)

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
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["mode"] == "search"
    assert body["stage1"]["structured_hits"][0]["id"] == "n1"
    assert body["stage2"]["primary_hits"][0]["id"] == "n2"


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


def test_resolve_evidence_strict_rejects_candidate(tmp_path):
    rule = {"id": "r2", "evidence": {"card_type": "term_card"}}
    p = tmp_path / "rule2.json"
    p.write_text(json.dumps(rule, ensure_ascii=False), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["resolve-evidence", "--rule", str(p), "--strict"])
    assert result.exit_code != 0
