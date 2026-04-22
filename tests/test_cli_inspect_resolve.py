import json

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")
pytest.importorskip("httpx")

from typer.testing import CliRunner

from src.cli import app


def test_inspect_knowledge_default_only_one_exact_and_no_related(monkeypatch, tmp_path):
    def fake_two_stage(self, query, **kwargs):
        return {
            "stage1": {
                "query_mode": "knowledge",
                "hits": [{"id": "n1", "book_title": "唐開元占經", "book_id": "kaiyuan_zhanjing", "card_type": "zhusu_card"}],
                "exact_hits": [{"id": "n1"}, {"id": "n2"}],
                "related_hits": [{"id": "r1"}],
            },
            "stage2": {
                "hits": [],
                "primary_candidates": [],
                "fallback_used": False,
                "files_scanned": 0,
                "matched_files": [],
                "matched_headings": [],
            },
        }

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)

    runner = CliRunner()
    result = runner.invoke(app, ["inspect-kb", "--query", "心宿"])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["query_mode"] == "knowledge"
    assert len(body["exact_hits"]) == 1
    assert body["related_hits"] == []


def test_inspect_evidence_primary_missing_marks_candidate_only(monkeypatch):
    def fake_two_stage(self, query, **kwargs):
        return {
            "stage1": {
                "query_mode": "evidence",
                "hits": [{"id": "s1", "card_type": "zhusu_card", "evidence_level": "structured"}],
                "exact_hits": [{"id": "s1", "card_type": "zhusu_card", "evidence_level": "structured"}],
                "related_hits": [],
            },
            "stage2": {
                "hits": [],
                "primary_candidates": [],
                "fallback_used": True,
                "files_scanned": 12,
                "matched_files": [],
                "matched_headings": [],
            },
        }

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)
    runner = CliRunner()
    result = runner.invoke(app, ["inspect-kb", "--query", "荧惑守心"])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["query_mode"] == "evidence"
    assert body["structured_fallbacks"][0]["status"] == "candidate_only"


def test_inspect_fallback_stats_present_when_used(monkeypatch):
    def fake_two_stage(self, query, **kwargs):
        return {
            "stage1": {"query_mode": "evidence", "hits": [], "exact_hits": [], "related_hits": []},
            "stage2": {
                "hits": [],
                "primary_candidates": [],
                "fallback_used": True,
                "files_scanned": 8,
                "matched_files": ["/docs/古籍/唐開元占經/分卷/卷十二.md"],
                "matched_headings": ["卷十二"],
            },
        }

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)
    runner = CliRunner()
    result = runner.invoke(app, ["inspect-kb", "--query", "荧惑守心"])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["stage2"]["fallback_used"] is True
    assert body["stage2"]["files_scanned"] == 8


def test_inspect_evidence_output_has_normalized_and_variants(monkeypatch):
    def fake_two_stage(self, query, **kwargs):
        return {
            "stage1": {
                "query_mode": "evidence",
                "normalized_query": "熒惑守心",
                "query_variants": ["荧惑守心", "熒惑守心"],
                "hits": [],
                "exact_hits": [],
                "related_hits": [],
            },
            "stage2": {"hits": [], "primary_candidates": [], "fallback_used": True, "files_scanned": 2, "matched_files": [], "matched_headings": []},
        }

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)
    runner = CliRunner()
    result = runner.invoke(app, ["inspect-kb", "--query", "荧惑守心"])
    body = json.loads(result.stdout)
    assert body["normalized_query"] == "熒惑守心"
    assert "荧惑守心" in body["query_variants"]


def test_inspect_structured_fallback_comes_from_stage2(monkeypatch):
    def fake_two_stage(self, query, **kwargs):
        return {
            "stage1": {"query_mode": "evidence", "hits": [], "exact_hits": [], "related_hits": []},
            "stage2": {
                "hits": [],
                "primary_candidates": [],
                "structured_fallbacks": [{"id": "s1", "card_type": "term_card", "status": "candidate_only"}],
                "fallback_used": True,
                "files_scanned": 1,
                "matched_files": [],
                "matched_headings": [],
            },
        }

    monkeypatch.setattr("src.cli.KBSearchRetriever.two_stage_retrieve", fake_two_stage)
    runner = CliRunner()
    result = runner.invoke(app, ["inspect-kb", "--query", "荧惑守心"])
    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["structured_fallbacks"][0]["card_type"] == "term_card"


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
    for field in [
        "relative_path",
        "locator",
        "quote",
        "card_type",
        "evidence_level",
        "volume",
        "section",
        "source_locator",
        "heading_path",
        "anchor_text",
    ]:
        assert field in body


def test_resolve_evidence_strict_rejects_candidate(tmp_path):
    rule = {"id": "r2", "evidence": {"card_type": "term_card"}}
    p = tmp_path / "rule2.json"
    p.write_text(json.dumps(rule, ensure_ascii=False), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["resolve-evidence", "--rule", str(p), "--strict"])
    assert result.exit_code != 0
