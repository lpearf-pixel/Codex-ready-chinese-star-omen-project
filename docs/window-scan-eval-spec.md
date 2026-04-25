# Window Scan Eval Spec (Sprint 8)

评测集：`eval/window_scan_eval_cases.yaml`

case 类型：
1. 正例窗口（应触发高价值事件）
2. 负例窗口（应基本无触发）
3. 边界窗口（单时刻或极短窗口）

每条 case 最小字段：
- `start_datetime_utc`
- `end_datetime_utc`
- `location`
- `bodies`
- `targets`
- `expected_event_types`
- `expected_cluster_count_range`
- `expected_rule_ids`
- `expected_primary_hit`

用途：
- 保证 scan-window 行为契约稳定
- 关注事件/聚类/规则命中基本一致性
- 不做复杂统计或可视化
