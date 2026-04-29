from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.review.review_queue import load_jsonl


def _rate(rows: list[dict[str, Any]], *, status: str) -> float:
    total = len(rows)
    if total == 0:
        return 0.0
    return sum(1 for r in rows if r.get("review_status") == status) / total


def _group_status_rates(rows: list[dict[str, Any]], key_name: str) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(row.get(key_name) or "__missing__")
        grouped[key].append(row)
    out: dict[str, float] = {}
    for key, items in grouped.items():
        out[key] = _rate(items, status="accepted")
    return out


def analyze_review_data(
    *,
    review_queue_path: Path,
    reviewed_path: Path,
    benchmark_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    queue_rows = load_jsonl(review_queue_path)
    reviewed_rows = load_jsonl(reviewed_path)
    base = reviewed_rows if reviewed_rows else queue_rows

    enriched: list[dict[str, Any]] = []
    for row in base:
        event = row.get("representative_event") or {}
        targets = str(event.get("target_asterism") or "__missing__")
        event_type = str(event.get("event_type") or "__missing__")
        rules = row.get("matched_rule_ids") or []
        primary = bool(row.get("primary_evidence_found"))
        candidate_only = bool(row.get("candidate_only"))
        if not rules:
            enriched.append({**row, "rule_id": "__no_rule__", "event_type": event_type, "target": targets, "primary": primary, "candidate_only": candidate_only})
        for rule in rules:
            enriched.append({**row, "rule_id": str(rule), "event_type": event_type, "target": targets, "primary": primary, "candidate_only": candidate_only})

    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_event_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        by_rule[row["rule_id"]].append(row)
        by_event_type[row["event_type"]].append(row)
        by_target[row["target"]].append(row)

    rule_accept_rate = {k: _rate(v, status="accepted") for k, v in by_rule.items()}
    rule_reject_rate = {k: _rate(v, status="rejected") for k, v in by_rule.items()}
    event_type_accept_rate = {k: _rate(v, status="accepted") for k, v in by_event_type.items()}
    event_type_reject_rate = {k: _rate(v, status="rejected") for k, v in by_event_type.items()}
    target_accept_rate = {k: _rate(v, status="accepted") for k, v in by_target.items()}
    target_reject_rate = {k: _rate(v, status="rejected") for k, v in by_target.items()}

    primary_rows = [r for r in enriched if r.get("primary")]
    candidate_rows = [r for r in enriched if r.get("candidate_only")]
    primary_evidence_accept_rate = _rate(primary_rows, status="accepted")
    candidate_only_reject_rate = _rate(candidate_rows, status="rejected")

    return {
        "row_count": len(base),
        "review_status_counts": {
            "accepted": sum(1 for r in base if r.get("review_status") == "accepted"),
            "rejected": sum(1 for r in base if r.get("review_status") == "rejected"),
            "needs_more_evidence": sum(1 for r in base if r.get("review_status") == "needs_more_evidence"),
            "pending": sum(1 for r in base if r.get("review_status") == "pending"),
        },
        "rule_accept_rate": rule_accept_rate,
        "rule_reject_rate": rule_reject_rate,
        "event_type_accept_rate": event_type_accept_rate,
        "event_type_reject_rate": event_type_reject_rate,
        "target_accept_rate": target_accept_rate,
        "target_reject_rate": target_reject_rate,
        "primary_evidence_accept_rate": primary_evidence_accept_rate,
        "candidate_only_reject_rate": candidate_only_reject_rate,
        "benchmark_case_count": len(benchmark_rows or []),
    }
