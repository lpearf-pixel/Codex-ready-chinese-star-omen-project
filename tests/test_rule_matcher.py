from pathlib import Path

from src.rule_engine.minimal_matcher import run_match_rule


def test_match_rule_minimal_closure_outputs_required_fields():
    out = run_match_rule(event_path=Path("data/examples/events/mars_guarding_xin_demo.json"))
    assert "rule_mars_guarding_xin_001" in out["matched_rule_ids"]
    row = out["matches"][0]
    for field in [
        "trigger_match_reason",
        "match_status",
        "match_score",
        "missing_conditions",
        "conflicting_conditions",
        "thresholds_used",
        "effect_domain",
        "severity",
        "time_window",
        "evidence_summary",
        "primary_evidence_found",
        "candidate_only",
    ]:
        assert field in row


def test_match_rule_moon_event_matches_moon_rule():
    out = run_match_rule(event_path=Path("data/examples/events/moon_invading_xin_demo.json"))
    assert "rule_moon_invading_xin_001" in out["matched_rule_ids"]


def test_match_rule_jupiter_saturn_conjunction():
    out = run_match_rule(event_path=Path("data/examples/events/jupiter_saturn_conjunction_demo.json"))
    assert "rule_jupiter_saturn_conjunction_001" in out["matched_rule_ids"]


def test_match_rule_conflict_resolution_and_sorting():
    out = run_match_rule(
        event_path=Path("data/examples/events/mars_guarding_xin_demo.json"),
        rules_path=Path("data/examples/rules/conflict_rules_demo.json"),
    )
    assert out["conflict_detected"] is True
    assert out["recommended_rule_id"] == "rule_mars_guarding_xin_high_priority"
    assert out["matched_rule_ids"][0] == "rule_mars_guarding_xin_high_priority"


def test_match_rule_structured_only_candidate_status():
    out = run_match_rule(
        event_path=Path("data/examples/events/structured_only_demo.json"),
        rules_path=Path("data/examples/rules/structured_only_rules_demo.json"),
    )
    assert out["match_status"] in {"candidate_only", "partial_match"}
    assert out["primary_evidence_found"] is False
