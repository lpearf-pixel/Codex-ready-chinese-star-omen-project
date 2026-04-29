# Tuning Report Spec (Sprint 10)

输入：
- review analysis
- threshold profile compare
- rule leaderboard
- error analysis（可选）

输出：
- JSON
- Markdown 摘要

建议类型（最小）：
- threshold 偏宽/偏严
- event_type reject rate 偏高
- target 匹配漂移
- rule candidate_only 偏高
- fallback_approx 依赖高的 case（建议人工复核优先）

说明：仅工程调参建议，不是正式预测结论。
