# Corpus Eval Spec (Sprint 2)

最小检索评测集定义在 `eval/corpus_eval_cases.yaml`。

每条 case 至少包含：
- `query`
- `query_mode`
- `expected_top1_path_contains`
- `must_hit_primary`
- `allowed_fallback_types`

## 评测目标
- 验证 entity query 默认 `knowledge`
- 验证 evidence query 默认 `evidence` 且 `literal_first=true`
- 验证 evidence 输出主证据仅来自 `fenjuan/fulltext`
- 验证 structured fallback 只作为 `candidate_only` 线索
