# 自动化天象分析接口边界（Sprint 3）

> 本文档只定义接口边界，不包含完整天文算法实现。

## 接口
- `EphemerisProvider`
- `AsterismMatcher`
- `CelestialEventDetector`
- `OmenRuleExecutor`

定义见：`src/interfaces/astronomy.py`

## 与现有 schema 对齐
- `AsterismMatcher` 对接 `Asterism`
- `CelestialEventDetector` 产出需对齐 `CelestialEvent`
- `OmenRuleExecutor` 输入对接 `OmenRule`
- 执行结果可拼装 `BacktestRecord`

## 非目标
- 不实现完整天文计算
- 不实现自动推演/自动报告
- 不扩展历史回测系统
