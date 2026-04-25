from __future__ import annotations

from typing import Any

from src.rule_engine.thresholds import load_event_thresholds


class MinimalCelestialEventDetector:
    def __init__(self) -> None:
        self.thresholds = load_event_thresholds()

    def detect(
        self,
        *,
        datetime_utc: str,
        lon: float,
        lat: float,
        body: str,
        target: str,
        points: list[dict[str, Any]],
        matches: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        point_map = {p["body"]: p for p in points if p.get("body")}
        target_match = next((m for m in matches if m.get("body") == body and m.get("matched_asterism_id") == target), None)
        target_point = point_map.get(body, {})

        def _event_base(event_id: str, *, event_type: str, event_target: str, related: list[str], angular_distance: float) -> dict[str, Any]:
            visibility_payload = {
                "is_visible": bool(target_point.get("is_visible", True)),
                "altitude_deg": target_point.get("altitude_deg"),
                "azimuth_deg": target_point.get("azimuth_deg"),
                "visibility_reason": target_point.get("visibility_reason"),
                "visibility_confidence": target_point.get("visibility_confidence"),
            }
            return {
                "id": event_id,
                "datetime_utc": datetime_utc,
                "body": body,
                "event_type": event_type,
                "target_asterism": event_target,
                "related_asterisms": related,
                "angular_distance_deg": angular_distance,
                "location": {"lon": lon, "lat": lat, "name": "observer"},
                "epoch": "J2000",
                "raw_calc_source": "sprint6_minimal_detector",
                "calc_source": target_point.get("calc_source"),
                "calc_quality": target_point.get("calc_quality"),
                "ephemeris_provider": target_point.get("ephemeris_provider"),
                "visibility": visibility_payload,
            }

        if target_match and body == "mars":
            th = self.thresholds.get("guarding", {})
            visible_ok = (not bool(th.get("visibility_required", False))) or bool(target_point.get("is_visible", True))
            if target_match["angular_distance_deg"] <= float(th.get("angular_distance_threshold_deg", 1.2)) and visible_ok:
                events.append(_event_base(f"event_{body}_guarding_{target}", event_type="guarding", event_target=target, related=[target], angular_distance=float(target_match["angular_distance_deg"])))

        if target_match and body == "moon":
            th = self.thresholds.get("invading", {})
            visible_ok = (not bool(th.get("visibility_required", False))) or bool(target_point.get("is_visible", True))
            if target_match["angular_distance_deg"] <= float(th.get("angular_distance_threshold_deg", 1.5)) and visible_ok:
                events.append(_event_base(f"event_{body}_invading_{target}", event_type="invading", event_target=target, related=[target], angular_distance=float(target_match["angular_distance_deg"])))

        if body in {"jupiter", "saturn"}:
            other = "saturn" if body == "jupiter" else "jupiter"
            if body in point_map and other in point_map:
                lon1 = float(point_map[body]["ecliptic_lon"])
                lon2 = float(point_map[other]["ecliptic_lon"])
                dist = min(abs(lon1 - lon2), 360 - abs(lon1 - lon2))
                th = self.thresholds.get("conjunction", {})
                if dist <= float(th.get("angular_distance_threshold_deg", 1.0)):
                    events.append(
                        {
                            "id": f"event_{body}_conjunction_{other}",
                            "datetime_utc": datetime_utc,
                            "body": body,
                            "event_type": "conjunction",
                            "target_asterism": other,
                            "related_asterisms": [other],
                            "angular_distance_deg": dist,
                            "location": {"lon": lon, "lat": lat, "name": "observer"},
                            "epoch": "J2000",
                            "raw_calc_source": "sprint6_minimal_detector",
                            "calc_source": point_map.get(body, {}).get("calc_source"),
                            "calc_quality": point_map.get(body, {}).get("calc_quality"),
                            "ephemeris_provider": point_map.get(body, {}).get("ephemeris_provider"),
                            "visibility": {
                                "is_visible": bool(point_map.get(body, {}).get("is_visible", True)),
                                "visibility_reason": point_map.get(body, {}).get("visibility_reason"),
                            },
                        }
                    )

        if all(name in point_map for name in ["moon", "mars", "jupiter", "saturn"]):
            lons = [float(point_map[name]["ecliptic_lon"]) for name in ["moon", "mars", "jupiter", "saturn"]]
            span = max(lons) - min(lons)
            span = min(span, 360 - span)
            th = self.thresholds.get("gathering", {})
            visible_ok = all(bool(point_map.get(name, {}).get("is_visible", True)) for name in ["moon", "mars", "jupiter", "saturn"])
            if span <= float(th.get("angular_distance_threshold_deg", 8.0)) and ((not bool(th.get("visibility_required", False))) or visible_ok):
                events.append(
                    {
                        "id": "event_multi_planet_gathering",
                        "datetime_utc": datetime_utc,
                        "body": "other",
                        "event_type": "gathering",
                        "target_asterism": "multi_planet",
                        "related_asterisms": ["moon", "mars", "jupiter", "saturn"],
                        "angular_distance_deg": span,
                        "location": {"lon": lon, "lat": lat, "name": "observer"},
                        "epoch": "J2000",
                        "raw_calc_source": "sprint6_minimal_detector",
                        "calc_source": "mixed_points",
                        "calc_quality": "mixed",
                        "ephemeris_provider": "multi_body",
                        "visibility": {"is_visible": visible_ok, "visibility_reason": "all_required_bodies_visible" if visible_ok else "some_required_bodies_below_horizon"},
                    }
                )

        return events
