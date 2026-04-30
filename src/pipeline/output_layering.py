from __future__ import annotations

from typing import Any


def classify_output_level(
    *,
    primary_evidence_found: bool,
    match_score: float,
    calc_quality: str | None,
    candidate_only: bool,
    review_accept_rate: float,
    profile_stability_confidence: float,
) -> dict[str, Any]:
    if primary_evidence_found and match_score >= 0.9 and calc_quality == "high" and (not candidate_only) and review_accept_rate >= 0.6 and profile_stability_confidence >= 0.6:
        return {"output_level": "formal_candidate", "level_reason": "high score + primary evidence + stable profile", "promotion_ready": True}
    if match_score >= 0.6 and review_accept_rate >= 0.3:
        return {"output_level": "internal_observation", "level_reason": "moderate confidence and review support", "promotion_ready": False}
    return {"output_level": "research_draft", "level_reason": "insufficient evidence/stability for higher level", "promotion_ready": False}
