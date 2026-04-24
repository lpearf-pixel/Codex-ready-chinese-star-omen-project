from __future__ import annotations

from typing import Any


ASTERISM_CENTERS = {
    "xin_xiu": {"name": "心宿", "ecliptic_lon": 241.0, "ecliptic_lat": -10.0},
    "jiao_xiu": {"name": "角宿", "ecliptic_lon": 200.0, "ecliptic_lat": -4.0},
    "fang_xiu": {"name": "房宿", "ecliptic_lon": 234.0, "ecliptic_lat": -9.0},
}


class MinimalAsterismMatcher:
    def match(self, *, points: list[dict[str, Any]], targets: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in points:
            for target in targets:
                center = ASTERISM_CENTERS.get(target)
                if not center:
                    continue
                dist = abs(float(p.get("ecliptic_lon", 0.0)) - float(center["ecliptic_lon"]))
                dist = min(dist, 360 - dist)
                confidence = max(0.0, 1.0 - dist / 15.0)
                out.append(
                    {
                        "body": p.get("body"),
                        "matched_asterism_id": target,
                        "matched_asterism_name": center["name"],
                        "angular_distance_deg": round(dist, 4),
                        "match_basis": "anchor_star_approx",
                        "confidence": round(confidence, 4),
                    }
                )
        return out
