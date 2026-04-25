# Event Output Contract (Sprint 8)

`detect-and-match` / `replay-event` / `scan-window` 的事件输出约定（最小）：

## Event-level fields
- `id`, `datetime_utc`, `body`, `event_type`, `target_asterism`
- `calc_source`, `calc_quality`, `ephemeris_provider`
- `is_visible`, `visibility_reason`
- `asterism_match_confidence`
- `event_cluster_id`（聚类后）

## Match-level fields
- `matched_rule_ids`
- `match_status`
- `match_score`
- `primary_evidence_found`
- `candidate_only`

## Scan-level metrics
- `detected_event_count`
- `clustered_event_count`
- `matched_rule_count`
- `primary_evidence_hit_rate`
- `candidate_only_rate`
- `visibility_filtered_count`
- `fallback_approx_rate`

说明：本契约用于最小回归与接口稳定性，不代表终版 schema。
