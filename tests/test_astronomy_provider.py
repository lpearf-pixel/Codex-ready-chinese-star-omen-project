from src.astronomy.providers.skyfield_provider import SkyfieldEphemerisProvider


def test_provider_returns_required_fields():
    p = SkyfieldEphemerisProvider(ephemeris_path=None)
    points = p.get_points(bodies=["moon", "mars", "jupiter", "saturn"], datetime_utc="2026-08-18T12:00:00Z", lon=116.4, lat=39.9)
    assert len(points) == 4
    for row in points:
        for field in ["body", "ra", "dec", "ecliptic_lon", "ecliptic_lat", "distance", "apparent_motion"]:
            assert field in row


def test_provider_returns_visibility_and_quality_fields_in_fallback_mode():
    p = SkyfieldEphemerisProvider(ephemeris_path=None, force_fallback=True)
    points = p.get_points(bodies=["moon"], datetime_utc="2026-08-18T12:00:00Z", lon=116.4, lat=39.9)
    assert len(points) == 1
    row = points[0]
    for field in [
        "is_visible",
        "altitude_deg",
        "azimuth_deg",
        "visibility_reason",
        "visibility_confidence",
        "calc_source",
        "calc_quality",
        "ephemeris_provider",
    ]:
        assert field in row
    assert row["calc_source"] == "fallback_approx"
    assert row["calc_quality"] == "low"


def test_provider_calc_quality_contract_for_auto_mode():
    p = SkyfieldEphemerisProvider(ephemeris_path=None, force_fallback=False)
    points = p.get_points(bodies=["moon"], datetime_utc="2026-08-18T12:00:00Z", lon=116.4, lat=39.9)
    row = points[0]
    assert row["calc_source"] in {"fallback_approx", "skyfield"}
    assert row["calc_quality"] in {"low", "high"}
