from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REVIEW_STATUSES = {"pending", "accepted", "rejected", "needs_more_evidence"}
DEFAULT_QUEUE_PATH = Path("data/reviews/review_queue.jsonl")
DEFAULT_REVIEWED_PATH = Path("data/reviews/reviewed_cases.jsonl")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _ensure_parent(path)
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def compute_review_rates(reviewed_rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(reviewed_rows)
    if total == 0:
        return {
            "review_accept_rate": 0.0,
            "review_reject_rate": 0.0,
            "needs_more_evidence_rate": 0.0,
        }
    accepted = sum(1 for r in reviewed_rows if r.get("review_status") == "accepted")
    rejected = sum(1 for r in reviewed_rows if r.get("review_status") == "rejected")
    need_more = sum(1 for r in reviewed_rows if r.get("review_status") == "needs_more_evidence")
    return {
        "review_accept_rate": accepted / total,
        "review_reject_rate": rejected / total,
        "needs_more_evidence_rate": need_more / total,
    }


def build_review_queue_from_benchmark(
    benchmark_payload: dict[str, Any],
    *,
    queue_path: Path = DEFAULT_QUEUE_PATH,
) -> dict[str, Any]:
    case_id = str(benchmark_payload.get("case_id") or "")
    reps = benchmark_payload.get("representative_events") or []
    first_match = (benchmark_payload.get("rule_matches") or [{}])[0]
    queue_rows = load_jsonl(queue_path)
    existing_ids = {str(r.get("review_item_id")) for r in queue_rows}
    created: list[dict[str, Any]] = []

    if not reps:
        reps = [{}]
    for idx, rep in enumerate(reps, start=1):
        review_item_id = f"review_{case_id}_{idx:02d}"
        if review_item_id in existing_ids:
            continue
        row = {
            "review_item_id": review_item_id,
            "case_id": case_id,
            "representative_event": rep,
            "matched_rule_ids": benchmark_payload.get("matched_rule_ids", []),
            "match_status": first_match.get("match_status", benchmark_payload.get("match_status", "not_matched")),
            "match_score": first_match.get("match_score", benchmark_payload.get("match_score", 0.0)),
            "primary_evidence_found": first_match.get("primary_evidence_found", benchmark_payload.get("primary_evidence_found", False)),
            "candidate_only": first_match.get("candidate_only", True),
            "review_status": "pending",
            "review_notes": "",
            "created_at": _now_utc(),
            "updated_at": _now_utc(),
        }
        created.append(row)
        queue_rows.append(row)

    write_jsonl(queue_path, queue_rows)
    return {
        "ok": True,
        "case_id": case_id,
        "queue_path": str(queue_path),
        "created_count": len(created),
        "total_queue_items": len(queue_rows),
        "items": created,
    }


def update_review_item(
    *,
    review_item_id: str,
    status: str,
    notes: str,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    reviewed_path: Path = DEFAULT_REVIEWED_PATH,
) -> dict[str, Any]:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"invalid review status: {status}")

    queue_rows = load_jsonl(queue_path)
    target: dict[str, Any] | None = None
    for row in queue_rows:
        if str(row.get("review_item_id")) == review_item_id:
            target = row
            break
    if target is None:
        raise ValueError(f"review item not found: {review_item_id}")

    target["review_status"] = status
    target["review_notes"] = notes
    target["updated_at"] = _now_utc()
    write_jsonl(queue_path, queue_rows)

    history_row = {
        **target,
        "review_action_at": _now_utc(),
    }
    append_jsonl(reviewed_path, history_row)

    reviewed_rows = load_jsonl(reviewed_path)
    return {
        "ok": True,
        "review_item_id": review_item_id,
        "queue_path": str(queue_path),
        "reviewed_path": str(reviewed_path),
        "item": target,
        "review_metrics": compute_review_rates(reviewed_rows),
    }


def export_review_markdown(
    *,
    queue_rows: list[dict[str, Any]],
    benchmark_payloads: list[dict[str, Any]] | None = None,
) -> str:
    lines = ["# Review Queue Summary", ""]
    bench_map = {str(x.get("case_id")): x for x in (benchmark_payloads or [])}
    for row in queue_rows:
        case_id = str(row.get("case_id") or "")
        bench = bench_map.get(case_id, {})
        event = row.get("representative_event") or {}
        lines.append(f"## {row.get('review_item_id')}")
        lines.append(f"- 窗口: {bench.get('window', {}) or {'start': bench.get('start_datetime_utc'), 'end': bench.get('end_datetime_utc')}}")
        lines.append(f"- 代表事件: {event.get('event_type')} / {event.get('body')} / {event.get('target_asterism')}")
        lines.append(f"- 命中规则: {row.get('matched_rule_ids', [])}")
        lines.append(f"- 证据情况: primary={row.get('primary_evidence_found')} candidate_only={row.get('candidate_only')}")
        lines.append(f"- review 状态: {row.get('review_status')}")
        lines.append(f"- 备注: {row.get('review_notes', '')}")
        lines.append("")
    return "\n".join(lines)
