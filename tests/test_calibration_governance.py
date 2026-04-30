import json
from pathlib import Path

from src.calibration.experiment_runner import create_calibration_snapshot, run_calibration_experiment
from src.calibration.profile_compare_report import build_profile_compare_report
from src.calibration.profile_registry import load_registry, promote_profile, propose_profile, rollback_profile
from src.calibration.profile_runner import run_profile_compare


def test_experiment_runner_writes_output(tmp_path: Path):
    out = run_calibration_experiment(
        profile_name="baseline",
        cases_path=Path("data/examples/historical_benchmark"),
        out_dir=tmp_path / "experiments",
    )
    assert "experiment" in out
    assert Path(out["output_file"]).exists()


def test_profile_registry_propose_promote_rollback(tmp_path: Path):
    from src.calibration import profile_registry as pr

    reg_path = tmp_path / "registry.json"
    log_path = tmp_path / "gov.jsonl"
    pr.save_registry({"profiles": [{"profile_name": "baseline", "source_file": "x", "status": "baseline", "parent_profile": None, "change_summary": "init", "created_at": "t", "updated_at": "t"}]}, path=reg_path)
    propose_profile(profile_name="strict", source_file="config/event_threshold_profiles.yaml", parent_profile="baseline", change_summary="test", registry_path=reg_path, log_path=log_path)
    out = promote_profile(profile_name="strict", experiment_exists=True, compare_exists=True, registry_path=reg_path, log_path=log_path)
    assert out["status"] == "baseline"
    rb = rollback_profile(to_profile="baseline", registry_path=reg_path, log_path=log_path)
    assert rb["baseline"] == "baseline"
    reg = load_registry(reg_path)
    assert sum(1 for p in reg["profiles"] if p["status"] == "baseline") == 1


def test_profile_compare_and_snapshot(tmp_path: Path):
    compare = run_profile_compare(
        cases_path=Path("data/examples/historical_benchmark"),
        profiles_path=Path("config/event_threshold_profiles.yaml"),
        profile_names=["baseline", "strict"],
    )
    report = build_profile_compare_report(compare, baseline="baseline", candidate="strict")
    assert "improved_case_ids" in report
    exp = {"experiment": {"experiment_id": "exp_test", "profile_name": "strict", "benchmark_source": "x", "review_source": "y", "metrics_summary": {}, "false_positive_count": 1, "false_negative_count": 2, "leaderboard_delta": {"top_rule": "rule_a"}}}
    snap = create_calibration_snapshot(experiment_payload=exp, recommendation_summary={"suggestion_count": 1}, out_dir=tmp_path / "snapshots")
    assert Path(snap["output_file"]).exists()
