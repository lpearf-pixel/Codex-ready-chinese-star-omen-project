from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.calibration.profile_stability import analyze_profile_stability
from src.eval.historical_benchmark import load_benchmark_case, run_benchmark_case
from src.pipeline.output_layering import classify_output_level


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_batch(*, cases_dir: Path, profiles: list[str], out_root: Path = Path("data/runs")) -> dict[str, Any]:
    case_files = sorted(cases_dir.glob("*.json"))
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for profile in profiles:
        stability = analyze_profile_stability(profile_name=profile)
        profile_rows = []
        for p in case_files:
            case = load_benchmark_case(p)
            result = run_benchmark_case(case=case, force_fallback=bool(case.get("force_fallback", False)))
            match_score = float(((result.get("rule_matches") or [{}])[0]).get("match_score", 0.0))
            first_event = (result.get("representative_events") or [{}])[0]
            primary = float(result.get("primary_evidence_hit_rate", 0.0)) > 0
            candidate_only = float(result.get("candidate_only_rate", 0.0)) >= 1.0
            level = classify_output_level(
                primary_evidence_found=primary,
                match_score=match_score,
                calc_quality=str(first_event.get("calc_quality") or "low"),
                candidate_only=candidate_only,
                review_accept_rate=float((result.get("metrics") or {}).get("review_accept_rate", 0.0)),
                profile_stability_confidence=float(stability.get("promotion_confidence", 0.0)),
            )
            row = {
                "profile_name": profile,
                "case_id": result.get("case_id"),
                "window": result.get("window"),
                "matched_rule_ids": result.get("matched_rule_ids", []),
                "primary_evidence_hit_rate": result.get("primary_evidence_hit_rate", 0.0),
                "candidate_only_rate": result.get("candidate_only_rate", 0.0),
                "representative_event": first_event,
                "metrics": result.get("metrics", {}),
                **level,
            }
            profile_rows.append(row)
            all_rows.append(row)
        formal_count = sum(1 for r in profile_rows if r["output_level"] == "formal_candidate")
        matched_case_count = sum(1 for r in profile_rows if r.get("matched_rule_ids"))
        summary_rows.append(
            {
                "run_id": run_id,
                "profile_name": profile,
                "case_count": len(profile_rows),
                "window_count": len(profile_rows),
                "matched_case_count": matched_case_count,
                "formal_candidate_count": formal_count,
                "created_at": _now(),
            }
        )
    report_index = {
        "run_id": run_id,
        "profiles": summary_rows,
        "window_count": len(all_rows),
        "matched_case_count": sum(1 for r in all_rows if r.get("matched_rule_ids")),
        "research_draft_count": sum(1 for r in all_rows if r["output_level"] == "research_draft"),
        "internal_observation_count": sum(1 for r in all_rows if r["output_level"] == "internal_observation"),
        "formal_candidate_count": sum(1 for r in all_rows if r["output_level"] == "formal_candidate"),
    }
    (run_dir / "results.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report_index.json").write_text(json.dumps(report_index, ensure_ascii=False, indent=2), encoding="utf-8")
    md = "\n".join(
        [
            f"# Batch Report Index {run_id}",
            "",
            f"- run_id: {run_id}",
            f"- window_count: {report_index['window_count']}",
            f"- matched_case_count: {report_index['matched_case_count']}",
            f"- research_draft_count: {report_index['research_draft_count']}",
            f"- internal_observation_count: {report_index['internal_observation_count']}",
            f"- formal_candidate_count: {report_index['formal_candidate_count']}",
            "",
        ]
    )
    (run_dir / "report_index.md").write_text(md, encoding="utf-8")
    return {"run_id": run_id, "run_dir": str(run_dir), "summary": report_index, "profile_runs": summary_rows}
