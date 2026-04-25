from pathlib import Path

from src.eval.corpus_eval import load_eval_cases


def test_detector_calibration_eval_cases_schema_minimal():
    cases = load_eval_cases(Path("eval/detector_calibration_eval_cases.yaml"))
    assert len(cases) >= 4
    required = {
        "case_id",
        "input_datetime_utc",
        "location",
        "bodies",
        "expected_event_type",
        "expected_target",
        "expected_confidence_range",
        "expected_calc_quality",
        "expected_visibility",
        "expected_cluster_behavior",
    }
    for case in cases:
        for field in required:
            assert field in case
