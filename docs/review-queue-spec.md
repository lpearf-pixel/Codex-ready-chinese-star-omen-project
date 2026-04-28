# Review Queue Spec (Sprint 9)

最小人工复核队列字段：
- `review_item_id`
- `case_id`
- `representative_event`
- `matched_rule_ids`
- `match_status`, `match_score`
- `primary_evidence_found`, `candidate_only`
- `review_status`
- `review_notes`

`review_status` 支持：
- `pending`
- `accepted`
- `rejected`
- `needs_more_evidence`

CLI：

```bash
python -m src.cli build-review-queue --from-benchmark <benchmark_json>
python -m src.cli review-item --id <review_item_id> --status accepted --notes "..."
```

落盘：
- 队列：`data/reviews/review_queue.jsonl`
- 审阅历史：`data/reviews/reviewed_cases.jsonl`

保证：
- queue 可重建
- reviewed 可追溯
- 追加写入，不覆盖历史记录
