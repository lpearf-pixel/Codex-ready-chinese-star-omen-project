from __future__ import annotations

from typing import Any


def generate_tuning_recommendations(
    *,
    review_analysis: dict[str, Any],
    profile_compare: dict[str, Any],
    rule_leaderboard: list[dict[str, Any]],
) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []

    event_reject = review_analysis.get("event_type_reject_rate", {})
    for event_type, reject_rate in event_reject.items():
        if float(reject_rate) >= 0.5 and event_type != "__missing__":
            suggestions.append(
                {
                    "type": "event_type_reject_high",
                    "event_type": event_type,
                    "reason": f"reject rate {reject_rate:.2f} is high; consider tightening thresholds or matcher confidence gating",
                }
            )

    target_reject = review_analysis.get("target_reject_rate", {})
    for target, reject_rate in target_reject.items():
        if float(reject_rate) >= 0.5 and target != "__missing__":
            suggestions.append(
                {
                    "type": "target_drift_risk",
                    "target": target,
                    "reason": f"target reject rate {reject_rate:.2f} suggests potential matching drift; check anchor mapping and distance threshold",
                }
            )

    for row in rule_leaderboard:
        if float(row.get("candidate_only_rate", 0.0)) >= 0.7 and row.get("rule_id") != "__no_rule__":
            suggestions.append(
                {
                    "type": "rule_candidate_only_high",
                    "rule_id": row.get("rule_id"),
                    "reason": "candidate_only rate is high; prioritize evidence enrichment or stricter trigger constraints",
                }
            )

    profiles = profile_compare.get("profiles", [])
    best = max(profiles, key=lambda x: float(x.get("primary_evidence_hit_rate", 0.0) - x.get("candidate_only_rate", 0.0)), default=None)
    if best:
        suggestions.append(
            {
                "type": "profile_preferred",
                "profile_name": best.get("profile_name"),
                "reason": "best balance by (primary_hit_rate - candidate_only_rate) in current small benchmark set",
            }
        )

    fallback_heavy_cases: list[str] = []
    for p in profile_compare.get("profile_case_results", []):
        for c in p.get("case_results", []):
            fallback_rate = float((c.get("metrics") or {}).get("fallback_approx_rate", 0.0))
            if fallback_rate >= 0.8:
                fallback_heavy_cases.append(str(c.get("case_id")))
    fallback_heavy_cases = sorted(set(fallback_heavy_cases))
    if fallback_heavy_cases:
        suggestions.append(
            {
                "type": "fallback_heavy_cases",
                "case_ids": fallback_heavy_cases,
                "reason": "cases rely heavily on fallback_approx; recommend lower confidence weighting or manual review priority",
            }
        )

    return {
        "suggestion_count": len(suggestions),
        "suggestions": suggestions,
    }


def tuning_to_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Tuning Recommendations", ""]
    for idx, item in enumerate(payload.get("suggestions", []), start=1):
        lines.append(f"## {idx}. {item.get('type')}")
        for k, v in item.items():
            if k == "type":
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")
    if not payload.get("suggestions"):
        lines.append("- No strong suggestions from current small benchmark/review set.")
    return "\n".join(lines)
