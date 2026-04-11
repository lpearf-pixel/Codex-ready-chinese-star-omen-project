# ancient-chinese-astro-model

中国传统星占长期模型（Codex-ready）初始化版本（Python 3.12）。

## 项目介绍

本项目的定位是“证据可回链”的中国传统星占研究引擎，而不是直接产出黑盒预测结果。核心思路：

1. **只读消费外部古籍知识库**（如 Obsidian + RAG 中台产物）。
2. 将古文规则转换为可校验的结构化对象（Schema + Pydantic）。
3. 用“两段式检索”保证证据可追溯：先高召回，再强制回到原文证据。
4. 把研究、推演、验证流程解耦，支持后续长期迭代。

## 当前能力（M0）

- 四大核心 Schema：`Asterism` / `CelestialEvent` / `OmenRule` / `BacktestRecord`
- 外部知识库契约：`card_type`、`evidence_level`、`final_citable`
- Connector 接入层：`kb-search` 检索、manifest 读取、证据解析回链
- CLI 命令：
  - `python -m src.cli validate-data`
  - `python -m src.cli inspect-kb --root <path>`
  - `python -m src.cli resolve-evidence --rule <path>`
- 样例数据：星官样例、规则样例、外部知识库契约样例

## 设计约束

1. 不改造外部知识库目录结构。
2. 运行期默认通过 `kb-search` 做召回。
3. 最终事实引用必须回证到 `fenjuan` 或 `fulltext`。
4. `prompt_asset` 与 `qa_example` 不得作为最终事实证据。

## 快速开始

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 测试手册（README 版）

### 1) 运行单元测试

```bash
pytest -q
```

### 2) 运行数据校验 CLI

```bash
python -m src.cli validate-data
```

### 3) 巡检外部知识库 manifest

```bash
python -m src.cli inspect-kb --root <你的知识库根目录>
```

### 4) 解析单条规则中的证据链

```bash
python -m src.cli resolve-evidence --rule data/processed/corpus/sample_rule_one.json
```

## 测试报告入口

- 最新本地测试报告见：`docs/test_report.md`

### 最新测试结论（2026-04-11）

- `pytest -q`：**6 passed, 2 skipped**
- `python -m src.cli validate-data`：当前容器缺少 `typer`，因此命令失败
- 建议在本地 Python 3.12 虚拟环境复现测试流程（详见 `docs/test_report.md`）
