from __future__ import annotations

from pathlib import Path
from typing import Any


def analyze_errors(compare_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    false_positive_cases: list[dict[str, Any]] = []
    missed_expected_cases: list[dict[str, Any]] = []
    for profile_row in compare_payload.get("profile_case_results", []):
        profile_name = str(profile_row.get("profile_name"))
        for case_result in profile_row.get("case_results", []):
            case_id = str(case_result.get("case_id") or "")
            summary = case_result.get("benchmark_summary") or {}
            rep = (case_result.get("representative_events") or [{}])[0]
            event_type = rep.get("event_type")
            target = rep.get("target_asterism")
            for rule_id in summary.get("unexpected_rule_hits", []):
                false_positive_cases.append(
                    {
                        "case_id": case_id,
                        "rule_id": rule_id,
                        "event_type": event_type,
                        "target": target,
                        "profile_name": profile_name,
                        "reason_summary": "unexpected rule hit vs benchmark expectation",
                    }
                )
            if summary.get("actual_primary_hit") is False and summary.get("expected_primary_hit") is True:
                missed_expected_cases.append(
                    {
                        "case_id": case_id,
                        "rule_id": "__primary_expected__",
                        "event_type": event_type,
                        "target": target,
                        "profile_name": profile_name,
                        "reason_summary": "expected_primary_hit=true but actual primary hit not achieved",
                    }
                )
            for rule_id in summary.get("expected_rule_missed", []):
                missed_expected_cases.append(
                    {
                        "case_id": case_id,
                        "rule_id": rule_id,
                        "event_type": event_type,
                        "target": target,
                        "profile_name": profile_name,
                        "reason_summary": "expected rule missing in matched results",
                    }
                )

            for m in case_result.get("rule_matches", []):
                if m.get("match_status") == "rejected":
                    false_positive_cases.append(
                        {
                            "case_id": case_id,
                            "rule_id": m.get("recommended_rule_id") or "__rejected__",
                            "event_type": event_type,
                            "target": target,
                            "profile_name": profile_name,
                            "reason_summary": "review rejected this matched item",
                        }
                    )

    return {
        "false_positive_cases": false_positive_cases,
        "missed_expected_cases": missed_expected_cases,
    }


def write_error_outputs(error_payload: dict[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = out_dir / "false_positive_cases.json"
    fn = out_dir / "missed_expected_cases.json"
    fp.write_text(__import__("json").dumps(error_payload.get("false_positive_cases", []), ensure_ascii=False, indent=2), encoding="utf-8")
    fn.write_text(__import__("json").dumps(error_payload.get("missed_expected_cases", []), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"false_positive_cases": str(fp), "missed_expected_cases": str(fn)}
