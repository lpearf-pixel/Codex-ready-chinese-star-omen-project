from __future__ import annotations


def compute_match_score(*, trigger_ratio: float, primary_evidence_found: bool, used_structured_fallback: bool) -> float:
    score = trigger_ratio * 0.7
    if primary_evidence_found:
        score += 0.3
    elif used_structured_fallback:
        score += 0.1
    return round(min(score, 1.0), 4)
