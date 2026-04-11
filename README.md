# ancient-chinese-astro-model

中国传统星占长期模型（Codex-ready）初始化版本。

## 目标

本仓库聚焦于：

- 只读消费外部古籍知识库标准化结果
- 星官-现代恒星对齐与历元/岁差处理
- 占辞规则结构化与证据回链
- 历史回测与月/季度报告支撑

## 当前范围（M0）

- 四大核心 Schema
- 外部知识库契约定义
- `kb-search` 检索接入
- 证据解析器（回链与最终可引用检查）
- CLI：
  - `python -m src.cli validate-data`
  - `python -m src.cli inspect-kb --root <path>`
  - `python -m src.cli resolve-evidence --rule <path>`

## 设计约束

1. 不改造外部知识库目录结构。
2. 运行期默认通过 `kb-search` 做召回。
3. 最终事实引用必须回证到 `fenjuan` 或 `fulltext`。
4. `prompt_asset` 与 `qa_example` 不得作为最终事实证据。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest
python -m src.cli validate-data
```
