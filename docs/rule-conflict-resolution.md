# Rule Conflict Resolution (Sprint 5)

当一个事件命中多条规则时：
1. 输出所有命中规则（非 `not_matched`）。
2. 按 `rule_priority`（升序）+ `match_score`（降序）排序。
3. 若同一 `conflict_group` 出现多条命中，标记 `conflict_detected=true` 并写入 `conflict_reasons`。
4. 输出 `recommended_rule_id` 作为最小可解释推荐。

默认策略：`resolution_policy = highest_score`（可扩展）。
