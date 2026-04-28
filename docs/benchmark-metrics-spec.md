# Benchmark Metrics Spec (Sprint 9)

最小 benchmark/backtest 指标：
- `window_count`
- `detected_event_count`
- `clustered_event_count`
- `matched_rule_count`
- `primary_evidence_hit_rate`
- `candidate_only_rate`
- `review_accept_rate`
- `review_reject_rate`
- `needs_more_evidence_rate`

说明：
- 当前为可解释最小实现
- 不含复杂统计学指标
- 默认 JSON 输出，可被后续流程直接消费
