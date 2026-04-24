from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.connectors.evidence_resolver import resolve_evidence
from src.rule_engine.match_result import RuleMatchResult
from src.rule_engine.scoring import compute_match_score
from src.rule_engine.thresholds import load_event_thresholds


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_match(trigger_target: str | None, event: dict[str, Any]) -> bool:
    if not trigger_target:
        return True
    target_asterism = str(event.get("target_asterism") or "")
    related = [str(x) for x in (event.get("related_asterisms") or [])]
    notes = str(event.get("notes") or "")

    if trigger_target == "multi_planet":
        return len(related) >= 5 or "五星" in notes
    return trigger_target == target_asterism or trigger_target in related


def match_event_to_rules(
    *,
    event: dict[str, Any],
    rules: list[dict[str, Any]],
    kb_root: str | Path | None = None,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    thresholds = load_event_thresholds()
    event_thresholds = thresholds.get(str(event.get("event_type") or ""), {})

    for rule in rules:
        trigger = rule.get("trigger") or {}
        trigger_body = str(trigger.get("body") or "")
        trigger_event_type = str(trigger.get("event_type") or "")
        trigger_target = trigger.get("target")

        body_ok = trigger_body == str(event.get("body") or "") or (trigger_body == "other" and str(event.get("body") or "") == "other")
        event_type_ok = trigger_event_type == str(event.get("event_type") or "")
        target_ok = _target_match(str(trigger_target) if trigger_target is not None else None, event)

        angular_threshold = event_thresholds.get("angular_distance_threshold_deg")
        angular_value = event.get("angular_distance_deg")
        angular_ok = True if angular_threshold is None or angular_value is None else float(angular_value) <= float(angular_threshold)

        min_duration = event_thresholds.get("min_duration_days")
        duration_value = event.get("duration_days")
        duration_ok = True if min_duration is None or duration_value is None else float(duration_value) >= float(min_duration)

        visibility_required = bool(event_thresholds.get("visibility_required", False))
        visibility_flag = ((event.get("visibility") or {}).get("is_visible") if isinstance(event.get("visibility"), dict) else None)
        visibility_ok = True if not visibility_required else bool(visibility_flag)

        trigger_conditions = [body_ok, event_type_ok, target_ok, angular_ok, duration_ok, visibility_ok]
        trigger_ratio = sum(1 for x in trigger_conditions if x) / len(trigger_conditions)
        missing_conditions: list[str] = []
        if not body_ok:
            missing_conditions.append("body")
        if not event_type_ok:
            missing_conditions.append("event_type")
        if not target_ok:
            missing_conditions.append("target")
        if not angular_ok:
            missing_conditions.append("angular_distance")
        if not duration_ok:
            missing_conditions.append("duration")
        if not visibility_ok:
            missing_conditions.append("visibility")

        evidence_obj = rule.get("evidence")
        resolved_evidence = resolve_evidence(evidence_obj, kb_root=kb_root) if isinstance(evidence_obj, dict) else None
        primary_evidence_found = bool(resolved_evidence and resolved_evidence.get("status") == "citable")
        used_structured_fallback = bool(resolved_evidence and resolved_evidence.get("status") == "candidate_only")

        if not (body_ok and event_type_ok and target_ok):
            match_status = "not_matched"
        elif body_ok and event_type_ok and target_ok and angular_ok and duration_ok and visibility_ok and primary_evidence_found:
            match_status = "matched"
        elif body_ok and event_type_ok and target_ok and angular_ok and duration_ok and visibility_ok:
            match_status = "candidate_only"
        else:
            match_status = "partial_match"

        match_score = compute_match_score(
            trigger_ratio=trigger_ratio,
            primary_evidence_found=primary_evidence_found,
            used_structured_fallback=used_structured_fallback,
        )

        result = RuleMatchResult(
            rule_id=rule.get("id"),
            match_status=match_status,
            match_score=match_score,
            trigger_match_reason={
                "body": f"{event.get('body')} == {trigger_body}",
                "event_type": f"{event.get('event_type')} == {trigger_event_type}",
                "target": trigger_target,
            },
            missing_conditions=missing_conditions,
            conflicting_conditions=[],
            thresholds_used=event_thresholds,
            effect_domain=rule.get("effect_domain", []),
            severity=rule.get("severity"),
            time_window=rule.get("time_window"),
            evidence_summary={
                "status": (resolved_evidence or {}).get("status", "missing"),
                "card_type": (resolved_evidence or {}).get("card_type"),
                "source_locator": (resolved_evidence or {}).get("source_locator"),
                "anchor_text": (resolved_evidence or {}).get("anchor_text"),
            },
            primary_evidence_found=primary_evidence_found,
            candidate_only=not primary_evidence_found,
            rule_priority=int(rule.get("rule_priority", 100)),
            conflict_group=rule.get("conflict_group"),
            resolution_policy=str(rule.get("resolution_policy", "highest_score")),
        )
        matches.append(result.to_dict())

    ranked_matches = [m for m in matches if m.get("match_status") != "not_matched"]
    ranked_matches.sort(key=lambda m: (m.get("rule_priority", 100), -float(m.get("match_score", 0))), reverse=False)

    conflict_happened = False
    conflict_reasons: list[str] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in ranked_matches:
        group = str(row.get("conflict_group") or "")
        if not group:
            continue
        groups.setdefault(group, []).append(row)
    for group, rows in groups.items():
        if len(rows) > 1:
            conflict_happened = True
            conflict_reasons.append(f"conflict_group={group} has {len(rows)} rules")
            for row in rows:
                row["conflicting_conditions"] = conflict_reasons

    recommended = ranked_matches[0] if ranked_matches else {}
    return {
        "event_id": event.get("id"),
        "matched_rule_ids": [m["rule_id"] for m in ranked_matches],
        "match_status": recommended.get("match_status", "not_matched"),
        "match_score": recommended.get("match_score", 0.0),
        "trigger_match_reason": recommended.get("trigger_match_reason", {}),
        "missing_conditions": recommended.get("missing_conditions", []),
        "conflicting_conditions": recommended.get("conflicting_conditions", []),
        "effect_domain": recommended.get("effect_domain", []),
        "severity": recommended.get("severity"),
        "time_window": recommended.get("time_window"),
        "evidence_summary": recommended.get("evidence_summary", {}),
        "primary_evidence_found": recommended.get("primary_evidence_found", False),
        "candidate_only": recommended.get("candidate_only", True),
        "matches": ranked_matches,
        "conflict_detected": conflict_happened,
        "conflict_reasons": conflict_reasons,
        "recommended_rule_id": recommended.get("rule_id"),
    }


def run_match_rule(
    *,
    event_path: Path,
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    kb_root: str | Path | None = None,
) -> dict[str, Any]:
    event = load_json(event_path)
    rules = load_json(rules_path)
    if not isinstance(rules, list):
        raise ValueError("rules file must be a list")
    return match_event_to_rules(event=event, rules=rules, kb_root=kb_root)
