from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_rule_leaderboard(review_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        rules = row.get("matched_rule_ids") or ["__no_rule__"]
        for rule_id in rules:
            grouped[str(rule_id)].append(row)

    rows: list[dict[str, Any]] = []
    for rule_id, items in grouped.items():
        match_count = len(items)
        accepted_count = sum(1 for r in items if r.get("review_status") == "accepted")
        rejected_count = sum(1 for r in items if r.get("review_status") == "rejected")
        needs_more_evidence_count = sum(1 for r in items if r.get("review_status") == "needs_more_evidence")
        primary_count = sum(1 for r in items if r.get("primary_evidence_found"))
        candidate_count = sum(1 for r in items if r.get("candidate_only"))
        score_rows = [float(r.get("match_score", 0.0)) for r in items]
        rows.append(
            {
                "rule_id": rule_id,
                "match_count": match_count,
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "needs_more_evidence_count": needs_more_evidence_count,
                "primary_hit_rate": (primary_count / match_count) if match_count else 0.0,
                "candidate_only_rate": (candidate_count / match_count) if match_count else 0.0,
                "average_match_score": (sum(score_rows) / len(score_rows)) if score_rows else 0.0,
                "accept_rate": (accepted_count / match_count) if match_count else 0.0,
                "reject_rate": (rejected_count / match_count) if match_count else 0.0,
            }
        )
    rows.sort(key=lambda x: (x["accept_rate"], -x["reject_rate"], -x["match_count"]), reverse=True)
    return rows


def leaderboard_to_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Rule Leaderboard",
        "",
        "| rule_id | match_count | accept_rate | reject_rate | candidate_only_rate | avg_score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['rule_id']} | {r['match_count']} | {r['accept_rate']:.3f} | {r['reject_rate']:.3f} | {r['candidate_only_rate']:.3f} | {r['average_match_score']:.3f} |"
        )
    lines.append("")
    return "\n".join(lines)
