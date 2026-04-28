# Historical Benchmark Spec (Sprint 9)

目标：在小规模窗口集合上做可重复基准回放，并形成可人工复核的数据闭环。

目录：`data/examples/historical_benchmark/`

每个 case 最小字段：
- `case_id`
- `start_datetime_utc`, `end_datetime_utc`
- `location`
- `bodies`, `targets`, `event_types`
- `notes`
- `expected_rule_ids`
- `expected_primary_hit`

运行：

```bash
python -m src.cli benchmark-window --case data/examples/historical_benchmark/case_mars_guarding_xin_001.json
```

输出核心字段：
- `case_id`, `window`
- `raw_event_count`, `clustered_event_count`
- `matched_rule_ids`
- `primary_evidence_hit_rate`, `candidate_only_rate`
- `benchmark_summary`
