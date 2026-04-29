# Threshold Profile Spec (Sprint 10)

配置文件：`config/event_threshold_profiles.yaml`

默认 profile：
- baseline
- strict
- loose
- visibility_relaxed

CLI：

```bash
python -m src.cli compare-thresholds --cases data/examples/historical_benchmark --profiles baseline --profiles strict --profiles loose
```

输出按 profile 汇总：
- `window_count`
- `detected_event_count`
- `clustered_event_count`
- `matched_rule_count`
- `primary_evidence_hit_rate`
- `candidate_only_rate`
- `review_accept_rate`
- `review_reject_rate`
- `needs_more_evidence_rate`
