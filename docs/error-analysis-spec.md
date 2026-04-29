# Error Analysis Spec (Sprint 10)

输出文件：
- `false_positive_cases.json`
- `missed_expected_cases.json`

最小定义：
- False Positive：不期望命中却命中；或 review rejected
- False Negative：期望命中未命中；或 expected_primary_hit=true 但未达成

每条分析项至少包含：
- `case_id`
- `rule_id`
- `event_type`
- `target`
- `profile_name`
- `reason_summary`
