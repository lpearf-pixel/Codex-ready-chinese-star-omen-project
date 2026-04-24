from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import cos, pi
from pathlib import Path
from typing import Any


@dataclass
class SkyfieldEphemerisProvider:
    """Minimal runnable ephemeris provider.

    - Prefers local skyfield eph file when available.
    - Falls back to deterministic approximation when skyfield/de421 unavailable.
    """

    ephemeris_path: str | None = None
    force_fallback: bool = False

    def _approx_point(self, body: str, at: datetime) -> dict[str, Any]:
        body_phase = {
            "moon": 13.0,
            "mars": 2.0,
            "jupiter": 0.7,
            "saturn": 0.4,
        }.get(body, 1.0)
        ts = at.replace(tzinfo=timezone.utc).timestamp() / 86400.0
        lon = (ts * body_phase * 12.0) % 360
        lat = 5.0 * cos(ts / 27.0)
        ra = (lon * 0.9) % 360
        dec = lat * 1.2
        motion = body_phase * 0.8
        altitude = max(-30.0, min(80.0, dec - 10.0))
        azimuth = (lon + 180.0) % 360
        is_visible = altitude > 0
        return {
            "body": body,
            "datetime_utc": at.isoformat().replace("+00:00", "Z"),
            "ra": ra,
            "dec": dec,
            "ecliptic_lon": lon,
            "ecliptic_lat": lat,
            "distance": 1.0,
            "apparent_motion": motion,
            "is_visible": is_visible,
            "altitude_deg": altitude,
            "azimuth_deg": azimuth,
            "visibility_reason": "above_horizon" if is_visible else "below_horizon",
            "visibility_confidence": 0.6,
            "calc_source": "fallback_approx",
            "calc_quality": "low",
            "ephemeris_provider": "SkyfieldEphemerisProvider(fallback)",
            "source": "approx_stub",
        }

    def _skyfield_available(self) -> bool:
        if self.ephemeris_path and Path(self.ephemeris_path).exists():
            return True
        return False

    def get_points(self, *, bodies: list[str], datetime_utc: str, lon: float, lat: float) -> list[dict[str, Any]]:
        at = datetime.fromisoformat(datetime_utc.replace("Z", "+00:00"))
        results: list[dict[str, Any]] = []

        if self._skyfield_available() and not self.force_fallback:
            try:
                from skyfield.api import load, wgs84  # type: ignore

                ts = load.timescale()
                t0 = ts.from_datetime(at)
                t1 = ts.from_datetime(at + timedelta(days=1))
                eph = load(self.ephemeris_path) if self.ephemeris_path else load("de421.bsp")
                observer = eph["earth"] + wgs84.latlon(lat, lon)
                mapping = {
                    "moon": "moon",
                    "mars": "mars",
                    "jupiter": "jupiter barycenter",
                    "saturn": "saturn barycenter",
                }
                for body in bodies:
                    key = mapping.get(body)
                    if not key:
                        continue
                    target = eph[key]
                    astrometric = observer.at(t0).observe(target).apparent()
                    ra, dec, _ = astrometric.radec()
                    lonlat = astrometric.ecliptic_latlon()
                    dist = astrometric.distance().au
                    astrometric_next = observer.at(t1).observe(target).apparent()
                    lonlat_next = astrometric_next.ecliptic_latlon()
                    motion = float(lonlat_next[1].degrees - lonlat[1].degrees)
                    alt, az, _ = astrometric.altaz()
                    is_visible = float(alt.degrees) > 0
                    results.append(
                        {
                            "body": body,
                            "datetime_utc": datetime_utc,
                            "ra": float(ra.hours * 15.0),
                            "dec": float(dec.degrees),
                            "ecliptic_lon": float(lonlat[1].degrees),
                            "ecliptic_lat": float(lonlat[0].degrees),
                            "distance": float(dist),
                            "apparent_motion": motion,
                            "is_visible": is_visible,
                            "altitude_deg": float(alt.degrees),
                            "azimuth_deg": float(az.degrees),
                            "visibility_reason": "above_horizon" if is_visible else "below_horizon",
                            "visibility_confidence": 0.9 if is_visible else 0.7,
                            "calc_source": "skyfield",
                            "calc_quality": "high",
                            "ephemeris_provider": "SkyfieldEphemerisProvider(skyfield)",
                            "source": "skyfield_local",
                        }
                    )
                if results:
                    return results
            except Exception:
                pass

        for body in bodies:
            results.append(self._approx_point(body, at))
        return results
