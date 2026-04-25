from src.astronomy.window_scanner import MinimalWindowScanner


def test_window_scanner_returns_core_sections():
    scanner = MinimalWindowScanner(force_fallback=True)
    out = scanner.scan(
        start_datetime_utc="2026-01-31T00:00:00Z",
        end_datetime_utc="2026-02-02T00:00:00Z",
        lon=116.4,
        lat=39.9,
        bodies=["mars", "moon", "jupiter", "saturn"],
        targets=["xin_xiu", "jiao_xiu", "fang_xiu"],
        event_types=["guarding", "invading", "conjunction", "gathering"],
    )
    for field in ["raw_events", "clustered_events", "rule_matches", "metrics", "scan_params"]:
        assert field in out


def test_window_scanner_outputs_metric_fields():
    scanner = MinimalWindowScanner(force_fallback=True)
    out = scanner.scan(
        start_datetime_utc="2026-02-16T00:00:00Z",
        end_datetime_utc="2026-02-16T00:00:00Z",
        lon=116.4,
        lat=39.9,
        bodies=["jupiter", "saturn"],
        targets=["xin_xiu"],
        event_types=["conjunction"],
    )
    metrics = out["metrics"]
    for field in [
        "detected_event_count",
        "clustered_event_count",
        "matched_rule_count",
        "primary_evidence_hit_rate",
        "candidate_only_rate",
        "visibility_filtered_count",
        "fallback_approx_rate",
    ]:
        assert field in metrics


def test_window_scanner_cluster_and_match_integration():
    scanner = MinimalWindowScanner(force_fallback=True)
    out = scanner.scan(
        start_datetime_utc="2026-01-31T00:00:00Z",
        end_datetime_utc="2026-02-02T00:00:00Z",
        lon=116.4,
        lat=39.9,
        bodies=["mars", "moon", "jupiter", "saturn"],
        targets=["xin_xiu", "jiao_xiu", "fang_xiu"],
        event_types=["guarding"],
    )
    assert out["clustered_event_count"] <= out["raw_event_count"]
    assert isinstance(out["matched_rule_ids"], list)
