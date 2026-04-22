import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_eval_corpus_command_outputs_summary(monkeypatch, tmp_path):
    eval_path = tmp_path / "cases.yaml"
    eval_path.write_text(
        """
cases:
  - query: "心宿"
    query_mode: knowledge
    expected_top1_path_contains: "心宿"
    must_hit_primary: false
    allowed_fallback_types: ["zhusu_card"]
""",
        encoding="utf-8",
    )

    def fake_two_stage(self, query, **kwargs):
        return {
            "stage1": {
                "query_mode": "knowledge",
                "hits": [{"path": "/docs/逐宿卡/心宿.md", "card_type": "zhusu_card"}],
            },
            "stage2": {"hits": [], "primary_candidates": [], "structured_fallbacks": []},
        }

    monkeypatch.setattr("src.eval.corpus_eval.KBSearchRetriever.two_stage_retrieve", fake_two_stage)

    runner = CliRunner()
    result = runner.invoke(app, ["eval-corpus", "--eval-path", str(eval_path)])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["total"] == 1
    assert body["passed"] == 1
    assert body["rows"][0]["top1_match"] is True
