# Corpus Change Log

## 2026-04-19 (Sprint 3 baseline)
- 补充并固化原文锚点字段：`volume/section/source_locator/heading_path/anchor_text`。
- 新增最小检索评测集执行入口（`eval-corpus`）。
- 固化检索排除规则（prompt/nav/qa/support）。
- 新增 `eval/corpus_eval_cases.yaml` 回归集执行链路。
- 完成 smoke 与 eval 责任分离（链路活性 vs 质量回归）。

## 2026-04-18
- 新增 aliases / variant_terms / normalized_terms 的 ingest flatten 基础支持。
- 更新 chunking 规范并重跑 ingest（分卷与全文层 heading+段落切块）。
