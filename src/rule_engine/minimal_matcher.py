from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.connectors.evidence_resolver import resolve_evidence


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

    for rule in rules:
        trigger = rule.get("trigger") or {}
        trigger_body = str(trigger.get("body") or "")
        trigger_event_type = str(trigger.get("event_type") or "")
        trigger_target = trigger.get("target")

        body_ok = trigger_body == str(event.get("body") or "") or (trigger_body == "other" and str(event.get("body") or "") == "other")
        event_type_ok = trigger_event_type == str(event.get("event_type") or "")
        target_ok = _target_match(str(trigger_target) if trigger_target is not None else None, event)

        if not (body_ok and event_type_ok and target_ok):
            continue

        evidence_obj = rule.get("evidence")
        resolved_evidence = resolve_evidence(evidence_obj, kb_root=kb_root) if isinstance(evidence_obj, dict) else None
        primary_evidence_found = bool(resolved_evidence and resolved_evidence.get("status") == "citable")

        matches.append(
            {
                "rule_id": rule.get("id"),
                "trigger_match_reason": {
                    "body": f"{event.get('body')} == {trigger_body}",
                    "event_type": f"{event.get('event_type')} == {trigger_event_type}",
                    "target": trigger_target,
                },
                "effect_domain": rule.get("effect_domain", []),
                "severity": rule.get("severity"),
                "time_window": rule.get("time_window"),
                "evidence_summary": {
                    "status": (resolved_evidence or {}).get("status", "missing"),
                    "card_type": (resolved_evidence or {}).get("card_type"),
                    "source_locator": (resolved_evidence or {}).get("source_locator"),
                    "anchor_text": (resolved_evidence or {}).get("anchor_text"),
                },
                "primary_evidence_found": primary_evidence_found,
                "candidate_only": not primary_evidence_found,
            }
        )

    return {
        "event_id": event.get("id"),
        "matched_rule_ids": [m["rule_id"] for m in matches],
        "matches": matches,
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
