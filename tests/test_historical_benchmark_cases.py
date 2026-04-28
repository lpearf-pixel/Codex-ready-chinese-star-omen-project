import json
from pathlib import Path


def test_historical_benchmark_cases_have_required_fields():
    root = Path("data/examples/historical_benchmark")
    files = sorted(root.glob("*.json"))
    assert 5 <= len(files) <= 10
    required = {
        "case_id",
        "start_datetime_utc",
        "end_datetime_utc",
        "location",
        "bodies",
        "targets",
        "event_types",
        "notes",
        "expected_rule_ids",
        "expected_primary_hit",
    }
    for p in files:
        case = json.loads(p.read_text(encoding="utf-8"))
        for field in required:
            assert field in case
