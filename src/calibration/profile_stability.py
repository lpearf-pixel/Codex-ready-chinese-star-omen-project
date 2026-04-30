from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _variance(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = sum(values) / len(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def analyze_profile_stability(*, profile_name: str, experiments_dir: Path = Path("data/calibration/experiments")) -> dict[str, Any]:
    rows = []
    for p in sorted(experiments_dir.glob("*.json")):
        payload = json.loads(p.read_text(encoding="utf-8"))
        exp = payload.get("experiment", payload)
        if exp.get("profile_name") == profile_name:
            rows.append(exp)
    primary = [float((r.get("metrics_summary") or {}).get("primary_evidence_hit_rate", 0.0)) for r in rows]
    candidate_only = [float((r.get("metrics_summary") or {}).get("candidate_only_rate", 0.0)) for r in rows]
    matched = [float((r.get("metrics_summary") or {}).get("matched_rule_count", 0.0)) for r in rows]
    var_summary = {
        "primary_evidence_hit_rate_var": _variance(primary),
        "candidate_only_rate_var": _variance(candidate_only),
        "matched_rule_count_var": _variance(matched),
    }
    total_var = sum(var_summary.values())
    promotion_confidence = max(0.0, min(1.0, 1.0 - total_var))
    rollback_risk = max(0.0, min(1.0, total_var))
    return {
        "profile_name": profile_name,
        "experiment_count": len(rows),
        "metric_variance_summary": var_summary,
        "promotion_confidence": promotion_confidence,
        "rollback_risk": rollback_risk,
    }
