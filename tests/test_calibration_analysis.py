import json
from pathlib import Path

from src.calibration.error_analysis import analyze_errors
from src.calibration.profile_runner import run_profile_compare
from src.calibration.review_analysis import analyze_review_data
from src.calibration.rule_leaderboard import build_rule_leaderboard, leaderboard_to_markdown
from src.calibration.tuning_recommendations import generate_tuning_recommendations


def test_review_driven_analysis_outputs_required_stats(tmp_path: Path):
    queue = tmp_path / "review_queue.jsonl"
    reviewed = tmp_path / "reviewed_cases.jsonl"
    reviewed.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "review_item_id": "r1",
                        "review_status": "accepted",
                        "matched_rule_ids": ["rule_mars_guarding_xin_001"],
                        "representative_event": {"event_type": "guarding", "target_asterism": "xin_xiu"},
                        "primary_evidence_found": True,
                        "candidate_only": False,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "review_item_id": "r2",
                        "review_status": "rejected",
                        "matched_rule_ids": ["rule_mars_guarding_xin_001"],
                        "representative_event": {"event_type": "guarding", "target_asterism": "xin_xiu"},
                        "primary_evidence_found": False,
                        "candidate_only": True,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = analyze_review_data(review_queue_path=queue, reviewed_path=reviewed)
    for field in [
        "rule_accept_rate",
        "rule_reject_rate",
        "event_type_accept_rate",
        "event_type_reject_rate",
        "target_accept_rate",
        "target_reject_rate",
        "primary_evidence_accept_rate",
        "candidate_only_reject_rate",
    ]:
        assert field in out


def test_profile_compare_and_error_analysis_contract():
    compare = run_profile_compare(
        cases_path=Path("data/examples/historical_benchmark"),
        profiles_path=Path("config/event_threshold_profiles.yaml"),
        profile_names=["baseline", "strict"],
    )
    assert "profiles" in compare and len(compare["profiles"]) == 2
    for row in compare["profiles"]:
        for field in [
            "profile_name",
            "window_count",
            "detected_event_count",
            "clustered_event_count",
            "matched_rule_count",
            "primary_evidence_hit_rate",
            "candidate_only_rate",
            "review_accept_rate",
            "review_reject_rate",
            "needs_more_evidence_rate",
        ]:
            assert field in row
    err = analyze_errors(compare)
    assert "false_positive_cases" in err
    assert "missed_expected_cases" in err


def test_rule_leaderboard_and_tuning_recommendations():
    review_rows = [
        {
            "matched_rule_ids": ["rule_mars_guarding_xin_001"],
            "review_status": "rejected",
            "primary_evidence_found": False,
            "candidate_only": True,
            "match_score": 0.3,
        }
    ]
    leaderboard = build_rule_leaderboard(review_rows)
    assert len(leaderboard) == 1
    assert "Rule Leaderboard" in leaderboard_to_markdown(leaderboard)
    payload = generate_tuning_recommendations(
        review_analysis={
            "event_type_reject_rate": {"guarding": 0.8},
            "target_reject_rate": {"xin_xiu": 0.7},
        },
        profile_compare={"profiles": [{"profile_name": "baseline", "primary_evidence_hit_rate": 0.5, "candidate_only_rate": 0.2}], "profile_case_results": []},
        rule_leaderboard=leaderboard,
    )
    assert "suggestions" in payload
