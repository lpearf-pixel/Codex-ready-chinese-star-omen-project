from pathlib import Path

from src.calibration.profile_stability import analyze_profile_stability
from src.pipeline.batch_runner import run_batch
from src.pipeline.output_layering import classify_output_level


def test_output_level_classification_contract():
    row = classify_output_level(
        primary_evidence_found=True,
        match_score=0.95,
        calc_quality="high",
        candidate_only=False,
        review_accept_rate=0.8,
        profile_stability_confidence=0.8,
    )
    assert row["output_level"] in {"research_draft", "internal_observation", "formal_candidate"}
    assert "promotion_ready" in row


def test_batch_runner_outputs_contract(tmp_path: Path):
    out = run_batch(cases_dir=Path("data/examples/historical_benchmark"), profiles=["baseline"], out_root=tmp_path / "runs")
    assert "run_id" in out
    assert "summary" in out
    run_dir = Path(out["run_dir"])
    assert (run_dir / "report_index.json").exists()
    assert (run_dir / "report_index.md").exists()


def test_profile_stability_output_contract():
    out = analyze_profile_stability(profile_name="baseline")
    for field in ["profile_name", "experiment_count", "metric_variance_summary", "promotion_confidence", "rollback_risk"]:
        assert field in out
