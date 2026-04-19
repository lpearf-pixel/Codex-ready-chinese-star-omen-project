# Retrieval Exclusion Rules (Sprint 2)

## 固化规则
1. `prompt_asset` 不进入 evidence mode 结果。
2. `qa_example` 不进入事实检索（knowledge/evidence）。
3. `nav` 不进入 `primary_candidates`。
4. support 类结果默认不进入最终证据输出。

## 说明
- `primary_candidates` 只允许 `fenjuan/fulltext`。
- support query 可以用于解释性召回，但不应被直接投影为最终事实证据。
