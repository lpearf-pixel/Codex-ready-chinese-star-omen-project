# Asterism Matching Spec (Sprint 6)

当前 `MinimalAsterismMatcher` 是工程最小实现：
- 支持目标：心宿、角宿、房宿
- 方法：锚星近似（基于黄经中心点距离）
- 输出：`matched_asterism_id/name`, `angular_distance_deg`, `match_basis`, `confidence`

限制：
- 非完整传统宿/官边界模型
- 不含完整星表拟合与岁差修正

## Sprint 7 后半段补充

- `detect-and-match` / `replay-event` 输出中，matcher 结果会透出 `asterism_match_confidence` 以便做校准对照。
- confidence 仍是最小近似值（由黄经距离线性映射得到），当前用途是工程校准，不是天文精度结论。
