from pathlib import Path

from src.eval.corpus_eval import load_eval_cases


def test_rule_match_eval_cases_has_expected_status_field():
    cases = load_eval_cases(Path("eval/rule_match_eval_cases.yaml"))
    assert len(cases) >= 10
    for case in cases:
        assert "expected_match_status" in case
        assert "input_event_id" in case
