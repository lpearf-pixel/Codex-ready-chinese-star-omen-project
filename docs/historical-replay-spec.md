# Historical Replay Spec (Sprint 7 后半段)

最小重演链路：

`历史时间 -> provider -> matcher -> detector -> cluster -> rule matcher -> evidence`

目录：`data/examples/historical_replay/`

当前提供样例：
- `mars_guarding_xin_case.json`
- `moon_invading_xin_case.json`
- `jupiter_saturn_conjunction_case.json`
- `multi_gathering_case.json`

CLI：

```bash
python -m src.cli replay-event --case data/examples/historical_replay/mars_guarding_xin_case.json
```

输出最小字段：
- `input_case_id`, `input_datetime_utc`, `location`
- `calc_source`, `calc_quality`
- `generated_events`, `clustered_events`
- `matched_rule_ids`, `match_status`, `match_score`
- `evidence_summary`, `primary_evidence_found`, `candidate_only`

范围限制：
- 不等同完整 backtest 系统
- 不做批量统计报告
- 当前仅供链路回放与人工审阅
