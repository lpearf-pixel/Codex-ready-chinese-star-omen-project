# Chunking Strategy Spec (Sprint 2)

## 原文层（分卷 / 全文合并版）
- 采用 `heading + 段落` 切块。
- 输出锚点字段：`volume/section/source_locator/heading_path/anchor_text`。

## 结构化卡层
- 逐宿卡 / 术语卡：整卡优先。
- 知识抽取卡：按 `摘要/定义/占辞/来源` 切块。

## 导航与索引层
- `nav/topic_index` 尽量少切块，仅保留必要定位信息。
