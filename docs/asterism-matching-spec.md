# Asterism Matching Spec (Sprint 6)

当前 `MinimalAsterismMatcher` 是工程最小实现：
- 支持目标：心宿、角宿、房宿
- 方法：锚星近似（基于黄经中心点距离）
- 输出：`matched_asterism_id/name`, `angular_distance_deg`, `match_basis`, `confidence`

限制：
- 非完整传统宿/官边界模型
- 不含完整星表拟合与岁差修正
