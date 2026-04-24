from src.astronomy.event_detector import MinimalCelestialEventDetector


def test_event_detector_detects_guarding():
    detector = MinimalCelestialEventDetector()
    points = [{"body": "mars", "ecliptic_lon": 241.0}, {"body": "moon", "ecliptic_lon": 250.0}, {"body": "jupiter", "ecliptic_lon": 120.0}, {"body": "saturn", "ecliptic_lon": 130.0}]
    matches = [{"body": "mars", "matched_asterism_id": "xin_xiu", "angular_distance_deg": 0.8}]
    events = detector.detect(datetime_utc="2026-08-18T12:00:00Z", lon=116.4, lat=39.9, body="mars", target="xin_xiu", points=points, matches=matches)
    assert any(e["event_type"] == "guarding" for e in events)
