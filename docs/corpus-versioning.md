# Corpus Versioning

## 版本语义
- `major`: 语料结构或证据语义发生不兼容变化（字段删除、含义重定义）。
- `minor`: 新增书目、批量 frontmatter 增强、chunking 规则变化、排除规则变化。
- `patch`: 文档修订、非语义性修正、重新导出 manifest 且结果等价。

## 什么时候升级版本
- 变更 `query_mode` 默认策略：至少 `minor`。
- 调整排除规则（prompt/nav/qa/support）：至少 `minor`。
- 重跑 ingest 且 chunk 边界变化：至少 `minor`。
- 新增/删除 card_type 或 evidence_level：`major`。

## 追踪 ingest 变化
1. 每次 ingest 后更新 `data/corpus_manifest.json`：
   - `corpus_version`
   - `generated_at`
   - `ingest_version`
2. 在 `docs/corpus-change-log.md` 记录：
   - frontmatter 增补范围
   - alias/variant_terms/normalized_terms 变化
   - chunking 策略调整
   - query_mode/exclusion 规则调整
3. 用 `eval-corpus` 对比回归结果差异，判断是否可接受。
