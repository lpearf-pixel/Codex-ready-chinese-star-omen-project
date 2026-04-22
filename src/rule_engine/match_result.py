from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RuleMatchResult:
    rule_id: str | None
    match_status: str
    match_score: float
    trigger_match_reason: dict[str, Any]
    missing_conditions: list[str]
    conflicting_conditions: list[str]
    thresholds_used: dict[str, Any]
    effect_domain: list[str]
    severity: str | None
    time_window: str | None
    evidence_summary: dict[str, Any]
    primary_evidence_found: bool
    candidate_only: bool
    rule_priority: int
    conflict_group: str | None
    resolution_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
