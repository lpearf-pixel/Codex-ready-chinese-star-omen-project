# Event Thresholds Spec (Sprint 5)

配置文件：`config/event_thresholds.yaml`

每个 event_type 至少包含：
- `angular_distance_threshold_deg`
- `min_duration_days`
- `visibility_required`
- `priority`

这些值是**工程默认值**，后续应基于回测与专家审校迭代调整。

加载入口：`src/rule_engine/thresholds.py`

## Sprint 7 后半段补充

- detector 现在会显式读取 `visibility_required`，对 `guarding / invading / gathering` 事件做最小可见性约束。
- 配套新增事件聚类层（时间窗口去重）用于把连续多日同象收敛为“单个现象簇”。
- 聚类窗口参数在 CLI 侧可配置：`--cluster-window-days`，峰值选择规则：`--peak-selection-rule`。
