# Window Scan Spec (Sprint 8)

最小窗口扫描链路：

`window -> provider -> matcher -> detector -> cluster -> rule matcher`

实现：`src/astronomy/window_scanner.py`
CLI：`python -m src.cli scan-window ...`

输入参数（最小）：
- `start_datetime_utc`, `end_datetime_utc`
- `location(lon/lat)`
- `bodies`, `targets`, `event_types`

当前支持范围：
- bodies: `mars/moon/jupiter/saturn`
- targets: `xin_xiu/jiao_xiu/fang_xiu`
- event_types: `guarding/invading/conjunction/gathering`

输出最小结构：
- `raw_events`
- `clustered_events`
- `rule_matches`
- `metrics`

限制：
- 默认按 24h step 扫描
- 非全量长期扫描器
- 非完整历史回测系统
