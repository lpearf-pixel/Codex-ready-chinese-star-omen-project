# Detector / Matcher Calibration Spec (Sprint 7 后半段)

本阶段目标：在不启动全量历史回测的前提下，提供可重复、可审阅的最小校准资产。

评测用例文件：`eval/detector_calibration_eval_cases.yaml`

每条 case 最小字段：
- `case_id`
- `input_datetime_utc`
- `location`
- `bodies`
- `expected_event_type`
- `expected_target`
- `expected_confidence_range`
- `expected_calc_quality`
- `expected_visibility`
- `expected_cluster_behavior`

覆盖点：
1. matcher confidence 范围是否合理（0~1）
2. threshold 边界是否改变事件生成
3. `skyfield` 与 `fallback_approx` 的质量标识差异是否可解释
4. visibility 条件是否影响触发
5. cluster 前后事件数量是否收敛到“现象级”数量

范围限制：
- 当前仅做最小行为契约校验
- 不产出统计结论
- 不做全量历史扫描
