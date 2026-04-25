from pathlib import Path

from src.eval.corpus_eval import load_eval_cases


def test_window_scan_eval_cases_schema_minimal():
    cases = load_eval_cases(Path("eval/window_scan_eval_cases.yaml"))
    assert len(cases) >= 3
    required = {
        "start_datetime_utc",
        "end_datetime_utc",
        "location",
        "bodies",
        "targets",
        "expected_event_types",
        "expected_cluster_count_range",
        "expected_rule_ids",
        "expected_primary_hit",
    }
    for case in cases:
        for field in required:
            assert field in case
