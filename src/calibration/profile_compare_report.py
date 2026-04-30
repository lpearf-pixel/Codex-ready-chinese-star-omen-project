from __future__ import annotations

from typing import Any


def build_profile_compare_report(compare_payload: dict[str, Any], *, baseline: str, candidate: str) -> dict[str, Any]:
    by_name = {x.get("profile_name"): x for x in compare_payload.get("profile_case_results", [])}
    base_cases = {c.get("case_id"): c for c in (by_name.get(baseline, {}) or {}).get("case_results", [])}
    cand_cases = {c.get("case_id"): c for c in (by_name.get(candidate, {}) or {}).get("case_results", [])}
    ids = sorted(set(base_cases).intersection(cand_cases))
    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []
    for cid in ids:
        b = bool((base_cases[cid].get("benchmark_summary") or {}).get("pass", False))
        c = bool((cand_cases[cid].get("benchmark_summary") or {}).get("pass", False))
        if (not b) and c:
            improved.append(cid)
        elif b and (not c):
            regressed.append(cid)
        else:
            unchanged.append(cid)
    base_summary = next((x for x in compare_payload.get("profiles", []) if x.get("profile_name") == baseline), {})
    cand_summary = next((x for x in compare_payload.get("profiles", []) if x.get("profile_name") == candidate), {})
    rule_level_deltas: dict[str, int] = {}
    for cid in ids:
        br = set(base_cases[cid].get("matched_rule_ids", []))
        cr = set(cand_cases[cid].get("matched_rule_ids", []))
        for r in cr - br:
            rule_level_deltas[r] = rule_level_deltas.get(r, 0) + 1
        for r in br - cr:
            rule_level_deltas[r] = rule_level_deltas.get(r, 0) - 1
    return {
        "baseline_profile": baseline,
        "candidate_profile": candidate,
        "improved_case_ids": improved,
        "regressed_case_ids": regressed,
        "unchanged_case_ids": unchanged,
        "primary_hit_rate_delta": float(cand_summary.get("primary_evidence_hit_rate", 0.0)) - float(base_summary.get("primary_evidence_hit_rate", 0.0)),
        "candidate_only_rate_delta": float(cand_summary.get("candidate_only_rate", 0.0)) - float(base_summary.get("candidate_only_rate", 0.0)),
        "review_accept_rate_delta": float(cand_summary.get("review_accept_rate", 0.0)) - float(base_summary.get("review_accept_rate", 0.0)),
        "review_reject_rate_delta": float(cand_summary.get("review_reject_rate", 0.0)) - float(base_summary.get("review_reject_rate", 0.0)),
        "rule_level_deltas": rule_level_deltas,
    }


def profile_compare_markdown(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Baseline vs Candidate Compare",
            "",
            f"- baseline: {row.get('baseline_profile')}",
            f"- candidate: {row.get('candidate_profile')}",
            f"- improved_case_ids: {row.get('improved_case_ids')}",
            f"- regressed_case_ids: {row.get('regressed_case_ids')}",
            f"- unchanged_case_ids: {row.get('unchanged_case_ids')}",
            f"- primary_hit_rate_delta: {row.get('primary_hit_rate_delta')}",
            f"- candidate_only_rate_delta: {row.get('candidate_only_rate_delta')}",
            f"- review_accept_rate_delta: {row.get('review_accept_rate_delta')}",
            f"- review_reject_rate_delta: {row.get('review_reject_rate_delta')}",
            "",
        ]
    )
