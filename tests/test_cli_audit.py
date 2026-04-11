import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")

from typer.testing import CliRunner

from src.cli import app


def test_audit_rules_command(tmp_path):
    rules = [
        {
            "id": "r1",
            "evidence": {
                "card_type": "fenjuan",
                "relative_path": "docs/a.md",
            },
        },
        {
            "id": "r2",
            "evidence": {
                "card_type": "term_card",
            },
        },
        {
            "id": "r3",
        },
    ]
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["audit-rules", "--rules-path", str(p)])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["total_rules"] == 3
    assert body["citable"] == 1
    assert body["candidate_only"] == 1
    assert body["missing_evidence"] == 1
