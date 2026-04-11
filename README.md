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
  - `python -m src.cli inspect-kb --root <path> [--query ...]`
  - `python -m src.cli resolve-evidence --rule <path> [--kb-root ...]`
  - `python -m src.cli search-kb "<query>" --book-id <book_id>`
  - `python -m src.cli audit-rules --rules-path <rules.json>`
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

## 接口配置

外部对接接口统一放在配置文件 `config/app_config.yaml`：

```yaml
kb_search:
  base_url: "http://localhost:8008"
  timeout_seconds: 10
```

`KBSearchRetriever` 默认读取该配置，避免在代码中硬编码接口地址。

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

按查询条件联调 `kb-search`：

```bash
python -m src.cli inspect-kb \
  --root /data/obsidian-kb \
  --query "荧惑守心" \
  --book-id kaiyuan_zhanjing \
  --card-type term_card \
  --card-type extract_card \
  --evidence-level structured
```

### 4) 解析单条规则中的证据链

```bash
python -m src.cli resolve-evidence --rule data/processed/corpus/sample_rule_one.json
```

### 5) 调用 kb-search 进行召回

```bash
python -m src.cli search-kb "荧惑守心" --book-id kaiyuan_zhanjing --card-type term_card --limit 5
```

### 6) 批量审计规则证据可引用状态

```bash
python -m src.cli audit-rules --rules-path data/processed/corpus/sample_rules.json
```

## 本地联调命令（开元占经）

> 以下命令用于与你本地《开元占经》知识库联调（M0 阶段）。

1) 用 `inspect-kb` 通过检索条件召回候选卡片：

```bash
python -m src.cli inspect-kb \
  --root /data/obsidian-kb \
  --query "荧惑守心" \
  --book-id kaiyuan_zhanjing \
  --card-type term_card \
  --card-type extract_card \
  --evidence-level structured
```

2) 对规则执行证据回链（关注 `relative_path/locator/quote/card_type/evidence_level`）：

```bash
python -m src.cli resolve-evidence \
  --rule data/processed/corpus/sample_rule_one.json \
  --kb-root /data/obsidian-kb
```

3) 批量检查规则是否可直接引用为最终证据：

```bash
python -m src.cli audit-rules --rules-path data/processed/corpus/sample_rules.json --kb-root /data/obsidian-kb
```

## 测试报告入口

- 最新本地测试报告见：`docs/test_report.md`
- 《开元占经》本地联调示例见：`docs/kaiyuan_integration_example.md`

### 最新测试结论（2026-04-11）

- `pytest -q`：**8 passed, 5 skipped**
- `python -m src.cli validate-data`：当前容器缺少 `typer`，因此命令失败
- 建议在本地 Python 3.12 虚拟环境复现测试流程（详见 `docs/test_report.md`）
