from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.astronomy.window_scanner import MinimalWindowScanner
from src.review.review_queue import DEFAULT_REVIEWED_PATH, compute_review_rates, load_jsonl


def load_benchmark_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_benchmark_case(
    *,
    case: dict[str, Any],
    rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
    ephemeris_path: str | None = None,
    force_fallback: bool = False,
    reviewed_path: Path = DEFAULT_REVIEWED_PATH,
    threshold_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scanner = MinimalWindowScanner(
        ephemeris_path=ephemeris_path,
        force_fallback=force_fallback or bool(case.get("force_fallback", False)),
        cluster_window_days=int(case.get("event_cluster_window_days", 3)),
        peak_selection_rule=str(case.get("peak_selection_rule", "min_angular_distance")),
    )
    scan = scanner.scan(
        start_datetime_utc=str(case["start_datetime_utc"]),
        end_datetime_utc=str(case["end_datetime_utc"]),
        lon=float(case["location"]["lon"]),
        lat=float(case["location"]["lat"]),
        bodies=list(case.get("bodies") or ["mars", "moon", "jupiter", "saturn"]),
        targets=list(case.get("targets") or ["xin_xiu", "jiao_xiu", "fang_xiu"]),
        event_types=list(case.get("event_types") or ["guarding", "invading", "conjunction", "gathering"]),
        rules_path=rules_path,
    )
    if threshold_profile:
        scanner.thresholds = threshold_profile
        scanner.detector.thresholds = threshold_profile
        scan = scanner.scan(
            start_datetime_utc=str(case["start_datetime_utc"]),
            end_datetime_utc=str(case["end_datetime_utc"]),
            lon=float(case["location"]["lon"]),
            lat=float(case["location"]["lat"]),
            bodies=list(case.get("bodies") or ["mars", "moon", "jupiter", "saturn"]),
            targets=list(case.get("targets") or ["xin_xiu", "jiao_xiu", "fang_xiu"]),
            event_types=list(case.get("event_types") or ["guarding", "invading", "conjunction", "gathering"]),
            rules_path=rules_path,
        )
    expected_rule_ids = set(case.get("expected_rule_ids") or [])
    matched_rule_ids = set(scan.get("matched_rule_ids") or [])
    expected_primary = bool(case.get("expected_primary_hit", False))
    actual_primary = bool(scan.get("metrics", {}).get("primary_evidence_hit_rate", 0.0) > 0)
    reviewed_rows = load_jsonl(reviewed_path)
    review_rates = compute_review_rates(reviewed_rows)

    benchmark_summary = {
        "expected_rule_overlap": sorted(expected_rule_ids.intersection(matched_rule_ids)),
        "expected_rule_missed": sorted(expected_rule_ids - matched_rule_ids),
        "unexpected_rule_hits": sorted(matched_rule_ids - expected_rule_ids),
        "expected_primary_hit": expected_primary,
        "actual_primary_hit": actual_primary,
        "pass": (expected_primary == actual_primary),
    }
    return {
        "case_id": case.get("case_id"),
        "window": {
            "start_datetime_utc": case.get("start_datetime_utc"),
            "end_datetime_utc": case.get("end_datetime_utc"),
        },
        "notes": case.get("notes"),
        "raw_event_count": scan.get("raw_event_count", 0),
        "clustered_event_count": scan.get("clustered_event_count", 0),
        "matched_rule_ids": scan.get("matched_rule_ids", []),
        "primary_evidence_hit_rate": scan.get("metrics", {}).get("primary_evidence_hit_rate", 0.0),
        "candidate_only_rate": scan.get("metrics", {}).get("candidate_only_rate", 0.0),
        "benchmark_summary": benchmark_summary,
        "representative_events": scan.get("representative_events", []),
        "rule_matches": scan.get("rule_matches", []),
        "metrics": {
            "window_count": 1,
            "detected_event_count": scan.get("metrics", {}).get("detected_event_count", 0),
            "clustered_event_count": scan.get("metrics", {}).get("clustered_event_count", 0),
            "matched_rule_count": scan.get("metrics", {}).get("matched_rule_count", 0),
            "primary_evidence_hit_rate": scan.get("metrics", {}).get("primary_evidence_hit_rate", 0.0),
            "candidate_only_rate": scan.get("metrics", {}).get("candidate_only_rate", 0.0),
            "review_accept_rate": review_rates.get("review_accept_rate", 0.0),
            "review_reject_rate": review_rates.get("review_reject_rate", 0.0),
            "needs_more_evidence_rate": review_rates.get("needs_more_evidence_rate", 0.0),
        },
    }


def export_benchmark_markdown(result: dict[str, Any]) -> str:
    rep = (result.get("representative_events") or [{}])[0]
    lines = [
        f"# Benchmark Case {result.get('case_id')}",
        "",
        f"- 窗口: {result.get('window')}",
        f"- 代表事件: {rep.get('event_type')} / {rep.get('body')} / {rep.get('target_asterism')}",
        f"- 命中规则: {result.get('matched_rule_ids', [])}",
        f"- 证据情况: primary_hit_rate={result.get('primary_evidence_hit_rate')} candidate_only_rate={result.get('candidate_only_rate')}",
        f"- benchmark 结论: {result.get('benchmark_summary', {})}",
        "",
    ]
    return "\n".join(lines)
