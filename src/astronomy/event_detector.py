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

        if target_match and body == "mars":
            th = self.thresholds.get("guarding", {})
            if target_match["angular_distance_deg"] <= float(th.get("angular_distance_threshold_deg", 1.2)):
                events.append(
                    {
                        "id": f"event_{body}_guarding_{target}",
                        "datetime_utc": datetime_utc,
                        "body": body,
                        "event_type": "guarding",
                        "target_asterism": target,
                        "related_asterisms": [target],
                        "angular_distance_deg": target_match["angular_distance_deg"],
                        "location": {"lon": lon, "lat": lat, "name": "observer"},
                        "epoch": "J2000",
                        "raw_calc_source": "sprint6_minimal_detector",
                    }
                )

        if target_match and body == "moon":
            th = self.thresholds.get("invading", {})
            if target_match["angular_distance_deg"] <= float(th.get("angular_distance_threshold_deg", 1.5)):
                events.append(
                    {
                        "id": f"event_{body}_invading_{target}",
                        "datetime_utc": datetime_utc,
                        "body": body,
                        "event_type": "invading",
                        "target_asterism": target,
                        "related_asterisms": [target],
                        "angular_distance_deg": target_match["angular_distance_deg"],
                        "location": {"lon": lon, "lat": lat, "name": "observer"},
                        "epoch": "J2000",
                        "raw_calc_source": "sprint6_minimal_detector",
                    }
                )

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
                        }
                    )

        if all(name in point_map for name in ["moon", "mars", "jupiter", "saturn"]):
            lons = [float(point_map[name]["ecliptic_lon"]) for name in ["moon", "mars", "jupiter", "saturn"]]
            span = max(lons) - min(lons)
            span = min(span, 360 - span)
            th = self.thresholds.get("gathering", {})
            if span <= float(th.get("angular_distance_threshold_deg", 8.0)):
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
                    }
                )

        return events
