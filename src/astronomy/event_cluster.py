from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


CLUSTERABLE_EVENT_TYPES = {"guarding", "conjunction", "gathering", "invading"}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _pick_peak_event(events: list[dict[str, Any]], rule: str) -> dict[str, Any]:
    if not events:
        return {}
    if rule == "earliest":
        return min(events, key=lambda x: _parse_dt(str(x.get("datetime_utc"))))
    if rule == "latest":
        return max(events, key=lambda x: _parse_dt(str(x.get("datetime_utc"))))
    # default: min_angular_distance
    return min(events, key=lambda x: float(x.get("angular_distance_deg", 9999.0)))


def cluster_events(
    events: list[dict[str, Any]],
    *,
    window_days: int = 3,
    peak_selection_rule: str = "min_angular_distance",
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    passthrough: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type") or "")
        if event_type not in CLUSTERABLE_EVENT_TYPES:
            passthrough.append({**event, "event_cluster_id": None})
            continue
        key = (
            str(event.get("body") or ""),
            event_type,
            str(event.get("target_asterism") or ""),
        )
        grouped[key].append(event)

    clusters: list[dict[str, Any]] = []
    clustered_events: list[dict[str, Any]] = passthrough[:]

    for key, rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda x: _parse_dt(str(x.get("datetime_utc"))))
        segment: list[dict[str, Any]] = []
        cluster_index = 0

        def _flush_segment(members: list[dict[str, Any]]) -> None:
            nonlocal cluster_index
            if not members:
                return
            cluster_index += 1
            start = str(members[0].get("datetime_utc"))
            end = str(members[-1].get("datetime_utc"))
            cluster_id = f"cluster_{key[0]}_{key[1]}_{key[2]}_{start[:10]}_{cluster_index:02d}"
            peak = _pick_peak_event(members, peak_selection_rule)
            member_ids = [str(item.get("id") or f"{cluster_id}_member_{idx+1}") for idx, item in enumerate(members)]
            cluster = {
                "event_cluster_id": cluster_id,
                "body": key[0],
                "event_type": key[1],
                "target_asterism": key[2],
                "window_start": start,
                "window_end": end,
                "peak_time": peak.get("datetime_utc"),
                "representative_event": peak,
                "member_event_ids": member_ids,
                "cluster_reason": f"same body/event_type/target within {window_days}d window",
            }
            clusters.append(cluster)
            for item in members:
                merged = {**item, "event_cluster_id": cluster_id}
                clustered_events.append(merged)

        for row in rows_sorted:
            if not segment:
                segment = [row]
                continue
            prev = segment[-1]
            delta = abs((_parse_dt(str(row.get("datetime_utc"))) - _parse_dt(str(prev.get("datetime_utc")))).total_seconds()) / 86400.0
            if delta <= window_days:
                segment.append(row)
            else:
                _flush_segment(segment)
                segment = [row]
        _flush_segment(segment)

    clustered_events = sorted(clustered_events, key=lambda x: _parse_dt(str(x.get("datetime_utc"))))
    clusters = sorted(clusters, key=lambda x: _parse_dt(str(x.get("window_start"))))
    return {"clusters": clusters, "events": clustered_events}
