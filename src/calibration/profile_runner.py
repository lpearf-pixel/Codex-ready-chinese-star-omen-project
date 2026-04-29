from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.eval.historical_benchmark import load_benchmark_case, run_benchmark_case


def load_threshold_profiles(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        parsed = {"profiles": {}}
    return parsed.get("profiles", {})


def _load_cases(cases_path: Path) -> list[dict[str, Any]]:
    if cases_path.is_dir():
        return [load_benchmark_case(p) for p in sorted(cases_path.glob("*.json"))]
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "cases" in payload:
        return payload["cases"]
    return [payload]


def run_profile_compare(
    *,
    cases_path: Path,
    profiles_path: Path,
    profile_names: list[str],
) -> dict[str, Any]:
    profiles = load_threshold_profiles(profiles_path)
    cases = _load_cases(cases_path)
    rows: list[dict[str, Any]] = []
    per_profile_results: list[dict[str, Any]] = []
    for profile_name in profile_names:
        thresholds = profiles.get(profile_name, {})
        profile_case_results: list[dict[str, Any]] = []
        for case in cases:
            result = run_benchmark_case(
                case=case,
                force_fallback=bool(case.get("force_fallback", False)),
                threshold_profile=thresholds,
            )
            result["profile_name"] = profile_name
            result["threshold_profile"] = thresholds
            profile_case_results.append(result)

        window_count = len(profile_case_results)
        detected_event_count = sum(int(r.get("metrics", {}).get("detected_event_count", 0)) for r in profile_case_results)
        clustered_event_count = sum(int(r.get("metrics", {}).get("clustered_event_count", 0)) for r in profile_case_results)
        matched_rule_count = sum(int(r.get("metrics", {}).get("matched_rule_count", 0)) for r in profile_case_results)
        primary_rates = [float(r.get("metrics", {}).get("primary_evidence_hit_rate", 0.0)) for r in profile_case_results]
        candidate_rates = [float(r.get("metrics", {}).get("candidate_only_rate", 0.0)) for r in profile_case_results]
        review_accept_rates = [float(r.get("metrics", {}).get("review_accept_rate", 0.0)) for r in profile_case_results]
        review_reject_rates = [float(r.get("metrics", {}).get("review_reject_rate", 0.0)) for r in profile_case_results]
        review_needs_rates = [float(r.get("metrics", {}).get("needs_more_evidence_rate", 0.0)) for r in profile_case_results]

        summary = {
            "profile_name": profile_name,
            "window_count": window_count,
            "detected_event_count": detected_event_count,
            "clustered_event_count": clustered_event_count,
            "matched_rule_count": matched_rule_count,
            "primary_evidence_hit_rate": (sum(primary_rates) / len(primary_rates)) if primary_rates else 0.0,
            "candidate_only_rate": (sum(candidate_rates) / len(candidate_rates)) if candidate_rates else 0.0,
            "review_accept_rate": (sum(review_accept_rates) / len(review_accept_rates)) if review_accept_rates else 0.0,
            "review_reject_rate": (sum(review_reject_rates) / len(review_reject_rates)) if review_reject_rates else 0.0,
            "needs_more_evidence_rate": (sum(review_needs_rates) / len(review_needs_rates)) if review_needs_rates else 0.0,
        }
        rows.append(summary)
        per_profile_results.append({"profile_name": profile_name, "case_results": profile_case_results, "summary": summary})

    return {
        "cases_path": str(cases_path),
        "profiles_path": str(profiles_path),
        "profiles": rows,
        "profile_case_results": per_profile_results,
    }
