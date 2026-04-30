# Profile Stability Spec (Sprint 12)

实现：`src/calibration/profile_stability.py`

输出字段：
- `profile_name`
- `experiment_count`
- `metric_variance_summary`
- `promotion_confidence`
- `rollback_risk`

用途：
- 支持 output layering
- 作为 profile promotion 的风险参考
