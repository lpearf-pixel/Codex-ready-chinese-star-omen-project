# Event Thresholds Spec (Sprint 5)

配置文件：`config/event_thresholds.yaml`

每个 event_type 至少包含：
- `angular_distance_threshold_deg`
- `min_duration_days`
- `visibility_required`
- `priority`

这些值是**工程默认值**，后续应基于回测与专家审校迭代调整。

加载入口：`src/rule_engine/thresholds.py`
