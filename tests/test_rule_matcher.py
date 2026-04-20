from pathlib import Path

from src.rule_engine.minimal_matcher import run_match_rule


def test_match_rule_minimal_closure_outputs_required_fields():
    out = run_match_rule(event_path=Path("data/examples/events/mars_guarding_xin_demo.json"))
    assert "rule_mars_guarding_xin_001" in out["matched_rule_ids"]
    row = out["matches"][0]
    for field in [
        "trigger_match_reason",
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
