from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.astronomy.asterism_matcher_impl import MinimalAsterismMatcher
from src.astronomy.event_cluster import cluster_events
from src.astronomy.event_detector import MinimalCelestialEventDetector
from src.astronomy.providers.skyfield_provider import SkyfieldEphemerisProvider
from src.rule_engine.minimal_matcher import load_json, match_event_to_rules
from src.rule_engine.thresholds import load_event_thresholds

ALLOWED_BODIES = {"mars", "moon", "jupiter", "saturn"}
ALLOWED_TARGETS = {"xin_xiu", "jiao_xiu", "fang_xiu"}
ALLOWED_EVENT_TYPES = {"guarding", "invading", "conjunction", "gathering"}


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class MinimalWindowScanner:
    def __init__(
        self,
        *,
        ephemeris_path: str | None = None,
        force_fallback: bool = False,
        cluster_window_days: int = 3,
        peak_selection_rule: str = "min_angular_distance",
    ) -> None:
        self.provider = SkyfieldEphemerisProvider(ephemeris_path=ephemeris_path, force_fallback=force_fallback)
        self.matcher = MinimalAsterismMatcher()
        self.detector = MinimalCelestialEventDetector()
        self.thresholds = load_event_thresholds()
        self.cluster_window_days = cluster_window_days
        self.peak_selection_rule = peak_selection_rule

    def scan(
        self,
        *,
        start_datetime_utc: str,
        end_datetime_utc: str,
        lon: float,
        lat: float,
        bodies: list[str],
        targets: list[str],
        event_types: list[str],
        rules_path: Path = Path("data/processed/corpus/sample_rules.json"),
        kb_root: Path | None = None,
        step_hours: int = 24,
    ) -> dict[str, Any]:
        bodies = [x for x in bodies if x in ALLOWED_BODIES]
        targets = [x for x in targets if x in ALLOWED_TARGETS]
        event_types = [x for x in event_types if x in ALLOWED_EVENT_TYPES]
        start = _parse_utc(start_datetime_utc)
        end = _parse_utc(end_datetime_utc)
        rules = load_json(rules_path)
        all_events: list[dict[str, Any]] = []
        total_points: list[dict[str, Any]] = []
        visibility_filtered_count = 0
        event_seen: set[tuple[str, str, str, str, str]] = set()

        t = start
        while t <= end:
            dt_str = t.isoformat().replace("+00:00", "Z")
            points = self.provider.get_points(bodies=bodies, datetime_utc=dt_str, lon=lon, lat=lat)
            total_points.extend(points)
            matches = self.matcher.match(points=points, targets=targets)
            point_map = {str(p.get("body")): p for p in points}
            for body in bodies:
                for target in targets:
                    detected = self.detector.detect(
                        datetime_utc=dt_str,
                        lon=lon,
                        lat=lat,
                        body=body,
                        target=target,
                        points=points,
                        matches=matches,
                    )
                    for event in detected:
                        if event.get("event_type") not in event_types:
                            continue
                        key = (
                            str(event.get("id")),
                            str(event.get("datetime_utc")),
                            str(event.get("event_type")),
                            str(event.get("body")),
                            str(event.get("target_asterism")),
                        )
                        if key in event_seen:
                            continue
                        event_seen.add(key)
                        event_match = next(
                            (
                                m
                                for m in matches
                                if m.get("body") == event.get("body")
                                and m.get("matched_asterism_id") == event.get("target_asterism")
                            ),
                            {},
                        )
                        body_point = point_map.get(str(event.get("body")), {})
                        all_events.append(
                            {
                                **event,
                                "calc_source": event.get("calc_source") or body_point.get("calc_source"),
                                "calc_quality": event.get("calc_quality") or body_point.get("calc_quality"),
                                "ephemeris_provider": event.get("ephemeris_provider") or body_point.get("ephemeris_provider"),
                                "is_visible": ((event.get("visibility") or {}).get("is_visible") if isinstance(event.get("visibility"), dict) else None),
                                "visibility_reason": ((event.get("visibility") or {}).get("visibility_reason") if isinstance(event.get("visibility"), dict) else None),
                                "asterism_match_confidence": event_match.get("confidence"),
                            }
                        )

            visibility_filtered_count += self._estimate_visibility_filtered(points=points, matches=matches, event_types=event_types)
            t += timedelta(hours=step_hours)

        clustering = cluster_events(
            all_events,
            window_days=self.cluster_window_days,
            peak_selection_rule=self.peak_selection_rule,
        )
        clustered_events = clustering["events"]
        rule_matches = [match_event_to_rules(event=ev, rules=rules, kb_root=kb_root) for ev in clustered_events]
        matched_rule_ids = sorted({rid for m in rule_matches for rid in m.get("matched_rule_ids", [])})
        representative_events = [c.get("representative_event", {}) for c in clustering["clusters"]]
        if not representative_events:
            representative_events = clustered_events[:5]

        total_rule_matches = len(rule_matches)
        primary_hits = sum(1 for m in rule_matches if m.get("primary_evidence_found"))
        candidate_only_hits = sum(1 for m in rule_matches if m.get("candidate_only"))
        fallback_points = sum(1 for p in total_points if p.get("calc_source") == "fallback_approx")
        metrics = {
            "detected_event_count": len(all_events),
            "clustered_event_count": len(clustered_events),
            "matched_rule_count": len(matched_rule_ids),
            "primary_evidence_hit_rate": (primary_hits / total_rule_matches) if total_rule_matches else 0.0,
            "candidate_only_rate": (candidate_only_hits / total_rule_matches) if total_rule_matches else 0.0,
            "visibility_filtered_count": visibility_filtered_count,
            "fallback_approx_rate": (fallback_points / len(total_points)) if total_points else 0.0,
        }

        first_rep = representative_events[0] if representative_events else {}
        first_match = rule_matches[0] if rule_matches else {}
        return {
            "scan_params": {
                "start_datetime_utc": start_datetime_utc,
                "end_datetime_utc": end_datetime_utc,
                "location": {"lon": lon, "lat": lat},
                "bodies": bodies,
                "targets": targets,
                "event_types": event_types,
                "step_hours": step_hours,
            },
            "raw_events": all_events,
            "clustered_events": clustered_events,
            "rule_matches": rule_matches,
            "raw_event_count": len(all_events),
            "clustered_event_count": len(clustered_events),
            "representative_events": representative_events,
            "matched_rule_ids": matched_rule_ids,
            "calc_source": first_rep.get("calc_source"),
            "calc_quality": first_rep.get("calc_quality"),
            "is_visible": first_rep.get("is_visible"),
            "match_status": first_match.get("match_status", "not_matched"),
            "match_score": first_match.get("match_score", 0.0),
            "primary_evidence_found": first_match.get("primary_evidence_found", False),
            "metrics": metrics,
        }

    def _estimate_visibility_filtered(
        self,
        *,
        points: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        event_types: list[str],
    ) -> int:
        point_map = {str(p.get("body")): p for p in points}
        count = 0

        if "guarding" in event_types:
            th = float((self.thresholds.get("guarding") or {}).get("angular_distance_threshold_deg", 1.2))
            for m in matches:
                if m.get("body") != "mars":
                    continue
                if float(m.get("angular_distance_deg", 999)) <= th and not bool(point_map.get("mars", {}).get("is_visible", True)):
                    count += 1
                    break

        if "invading" in event_types:
            th = float((self.thresholds.get("invading") or {}).get("angular_distance_threshold_deg", 1.5))
            for m in matches:
                if m.get("body") != "moon":
                    continue
                if float(m.get("angular_distance_deg", 999)) <= th and not bool(point_map.get("moon", {}).get("is_visible", True)):
                    count += 1
                    break
        return count
