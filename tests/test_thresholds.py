from pathlib import Path

from src.rule_engine.scoring import compute_match_score
from src.rule_engine.thresholds import load_event_thresholds


def test_thresholds_config_loads_required_event_types():
    cfg = load_event_thresholds(Path("config/event_thresholds.yaml"))
    for key in ["guarding", "invading", "conjunction", "gathering", "retrograde", "stationary", "entering_mansion"]:
        assert key in cfg
        for field in ["angular_distance_threshold_deg", "min_duration_days", "visibility_required", "priority"]:
            assert field in cfg[key]


def test_compute_match_score_basics():
    matched = compute_match_score(trigger_ratio=1.0, primary_evidence_found=True, used_structured_fallback=False)
    candidate = compute_match_score(trigger_ratio=1.0, primary_evidence_found=False, used_structured_fallback=True)
    partial = compute_match_score(trigger_ratio=0.5, primary_evidence_found=False, used_structured_fallback=False)
    assert matched > candidate > partial
