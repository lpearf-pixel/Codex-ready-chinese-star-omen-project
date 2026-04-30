from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.calibration.error_analysis import analyze_errors
from src.calibration.profile_compare_report import build_profile_compare_report
from src.calibration.profile_runner import run_profile_compare
from src.calibration.rule_leaderboard import build_rule_leaderboard
from src.review.review_queue import DEFAULT_REVIEWED_PATH, load_jsonl


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_calibration_experiment(
    *,
    profile_name: str,
    cases_path: Path,
    review_source: Path = DEFAULT_REVIEWED_PATH,
    baseline_profile: str = "baseline",
    out_dir: Path = Path("data/calibration/experiments"),
) -> dict[str, Any]:
    compare_payload = run_profile_compare(
        cases_path=cases_path,
        profiles_path=Path("config/event_threshold_profiles.yaml"),
        profile_names=[baseline_profile, profile_name] if profile_name != baseline_profile else [baseline_profile],
    )
    err = analyze_errors(compare_payload)
    reviewed_rows = load_jsonl(review_source)
    leaderboard = build_rule_leaderboard(reviewed_rows)
    summary_row = next((x for x in compare_payload.get("profiles", []) if x.get("profile_name") == profile_name), {})
    compare_report = (
        build_profile_compare_report(compare_payload, baseline=baseline_profile, candidate=profile_name)
        if profile_name != baseline_profile
        else {"baseline_profile": baseline_profile, "candidate_profile": profile_name}
    )
    experiment_id = f"exp_{profile_name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    row = {
        "experiment_id": experiment_id,
        "profile_name": profile_name,
        "benchmark_source": str(cases_path),
        "review_source": str(review_source),
        "metrics_summary": summary_row,
        "false_positive_count": len(err.get("false_positive_cases", [])),
        "false_negative_count": len(err.get("missed_expected_cases", [])),
        "leaderboard_delta": {"top_rule": leaderboard[0]["rule_id"] if leaderboard else None},
        "compare_report": compare_report,
        "created_at": _now(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{experiment_id}.json"
    p.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"experiment": row, "output_file": str(p)}


def create_calibration_snapshot(
    *,
    experiment_payload: dict[str, Any],
    recommendation_summary: dict[str, Any],
    out_dir: Path = Path("data/calibration/snapshots"),
) -> dict[str, Any]:
    exp = experiment_payload.get("experiment", experiment_payload)
    snapshot_id = f"snap_{exp.get('experiment_id')}"
    top_rules = []
    if exp.get("leaderboard_delta", {}).get("top_rule"):
        top_rules = [exp["leaderboard_delta"]["top_rule"]]
    row = {
        "snapshot_id": snapshot_id,
        "profile_name": exp.get("profile_name"),
        "benchmark_source": exp.get("benchmark_source"),
        "review_source": exp.get("review_source"),
        "metrics_summary": exp.get("metrics_summary", {}),
        "top_false_positives": exp.get("false_positive_count"),
        "top_false_negatives": exp.get("false_negative_count"),
        "top_rules_needing_attention": top_rules,
        "recommendation_summary": recommendation_summary,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{snapshot_id}.json"
    p.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"snapshot": row, "output_file": str(p)}
