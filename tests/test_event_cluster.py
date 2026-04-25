from src.astronomy.event_cluster import cluster_events


def test_event_cluster_groups_nearby_events():
    events = [
        {"id": "e1", "datetime_utc": "2026-08-18T00:00:00Z", "body": "mars", "event_type": "guarding", "target_asterism": "xin_xiu", "angular_distance_deg": 0.9},
        {"id": "e2", "datetime_utc": "2026-08-19T00:00:00Z", "body": "mars", "event_type": "guarding", "target_asterism": "xin_xiu", "angular_distance_deg": 0.7},
        {"id": "e3", "datetime_utc": "2026-08-28T00:00:00Z", "body": "mars", "event_type": "guarding", "target_asterism": "xin_xiu", "angular_distance_deg": 0.8},
    ]
    out = cluster_events(events, window_days=3)
    assert len(out["clusters"]) == 2
    first_cluster = out["clusters"][0]
    assert first_cluster["member_event_ids"] == ["e1", "e2"]
    assert first_cluster["peak_time"] == "2026-08-19T00:00:00Z"
    assert all("event_cluster_id" in item for item in out["events"])


def test_event_cluster_reduces_unique_phenomena_count():
    events = [
        {"id": "e1", "datetime_utc": "2026-08-18T00:00:00Z", "body": "moon", "event_type": "invading", "target_asterism": "xin_xiu", "angular_distance_deg": 1.1},
        {"id": "e2", "datetime_utc": "2026-08-19T00:00:00Z", "body": "moon", "event_type": "invading", "target_asterism": "xin_xiu", "angular_distance_deg": 1.2},
        {"id": "e3", "datetime_utc": "2026-08-20T00:00:00Z", "body": "moon", "event_type": "invading", "target_asterism": "xin_xiu", "angular_distance_deg": 1.0},
    ]
    out = cluster_events(events, window_days=7)
    assert len(events) == 3
    assert len(out["clusters"]) == 1
