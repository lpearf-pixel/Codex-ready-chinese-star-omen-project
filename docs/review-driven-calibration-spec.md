# Review-driven Calibration Spec (Sprint 10)

输入来源：
- `data/reviews/review_queue.jsonl`
- `data/reviews/reviewed_cases.jsonl`
- benchmark 结果（可选）

输出最小统计：
- `rule_accept_rate` / `rule_reject_rate`
- `event_type_accept_rate` / `event_type_reject_rate`
- `target_accept_rate` / `target_reject_rate`
- `primary_evidence_accept_rate`
- `candidate_only_reject_rate`

状态区分：`accepted` / `rejected` / `needs_more_evidence`。
