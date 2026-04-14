# ancient-chinese-astro-model

中国传统星占研究引擎（Codex-ready，Python 3.12）。

本项目不是黑盒预测器，而是一套**证据可回链、规则可校验、检索可调试**的研究型系统。它默认**只读消费外部古籍知识库**（如 Obsidian + 本地 RAG 中台），并将古文规则转换为可结构化、可验证、可回测的对象。

## 项目定位

核心目标有四个：

1. 只读消费外部古籍知识库，不重做上游整理工程。
2. 将星占规则表达为可校验的数据模型。
3. 通过 `kb-search` + 原文回证，保证最终证据可追溯。
4. 将研究、检索、证据解析、后续天文计算与回测解耦，便于长期迭代。

## 当前范围（M0）

当前仓库重点在 **知识源接入与证据链**，已经覆盖：

- 四大核心模型：`Asterism` / `CelestialEvent` / `OmenRule` / `BacktestRecord`
- 外部知识库契约：`card_type`、`evidence_level`、`final_citable`
- `kb-search` 检索接入
- 证据解析与原文回链
- CLI 联调命令
- 样例 schema / 样例规则 / 样例知识库契约

当前还**不以大规模预测为目标**；优先把“接入层 + 检索层 + 证据链”做稳。

## 设计约束

1. 不改造外部知识库目录结构。
2. 运行期默认通过 `kb-search` 做召回。
3. 最终事实引用必须回证到 `fenjuan` 或 `fulltext`。
4. `prompt_asset` 与 `qa_example` 不得作为最终事实证据。

## 项目结构

```text
ancient-chinese-astro-model/
├─ README.md
├─ config/
│  └─ config.yaml
├─ docs/
├─ data/
│  ├─ examples/
│  └─ processed/
├─ schemas/
├─ src/
│  ├─ cli.py
│  ├─ config/
│  └─ connectors/
├─ tests/
└─ prompts/
```

## 快速开始

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

运行基础校验：

```bash
pytest -q
python -m src.cli validate-data
```

## 配置与环境变量

项目采用**环境变量驱动**，统一由 `src/config/settings.py` 读取。默认配置文件是 `config/config.yaml`，也可通过 `APP_CONFIG_PATH` 覆盖。

支持 `${VAR}` / `${VAR:-default}` 插值，且：

- 若设置了 `KB_SEARCH_BASE_URL`，优先使用完整 URL
- 否则回退到 `http://127.0.0.1:${KB_SEARCH_API_PORT}`

常用环境变量：

- `KB_SEARCH_BASE_URL`
- `KB_SEARCH_API_PORT`
- `KB_SEARCH_API_KEY`
- `KB_SEARCH_DEFAULT_COLLECTION`
- `KB_SEARCH_TIMEOUT_SECONDS`
- `KB_SOURCES_ROOT`
- `KB_ENABLE_OBSIDIAN_SOURCE`
- `KB_OBSIDIAN_ROOT`
- `KB_OBSIDIAN_INGEST_SOURCE_LABEL`
- `KB_OBSIDIAN_SOURCE_ROOT_LABEL`
- `APP_ENV`
- `APP_DEBUG`
- `APP_LOG_LEVEL`
- `APP_TIMEZONE`
- `APP_DEFAULT_LIMIT`
- `ASTRO_DEFAULT_EPOCH`
- `ASTRO_DEFAULT_LON`
- `ASTRO_DEFAULT_LAT`
- `ASTRO_DEFAULT_LOCATION_NAME`
- `ASTRO_VISIBILITY_MIN_ALT_DEG`

建议先复制：

```bash
cp .env.example .env
```

> 安全提示：日志应对 API key 做脱敏，README 与提交记录中不要放真实密钥。

## 外部知识库契约

本项目把上游知识库按四层理解：

| 层级 | 典型目录 | card_type | evidence_level | 是否可直接作最终证据 |
|---|---|---|---|---|
| 原始证据层 | `分卷/`、`全文合并版` | `fenjuan` / `fulltext` | `primary` | 是 |
| 结构化知识层 | `逐宿卡/`、`星官卡/`、`术语卡片/`、`知识抽取卡/` | `zhusu_card` / `xingguan_card` / `term_card` / `extract_card` | `structured` | 否 |
| 索引辅助层 | `主题索引/`、`章节摘要卡/`、`导航/` | `topic_index` / `chapter_summary` / `nav` | `index` | 否 |
| 流程资产层 | `agent/`、`prompts/`、`问答样例库/` | `prompt_asset` / `qa_example` | `prompt` / `example` | 否 |

下游优先读取上游元数据：

- `kb_book_id`
- `book_title`
- `card_type`
- `evidence_level`
- `final_citable`
- `query_mode_hint`
- `aliases`
- `variant_terms`
- `normalized_terms`
- `source_locator`

若命中结果缺少这些字段，才退回路径推断。

## kb-search 对接

### 前置条件

你需要先准备好本地 `kb-search` 服务：

```bash
make up
make ingest
```

健康检查：

```bash
curl -sS "http://127.0.0.1:${KB_SEARCH_API_PORT:-8008}/v1/health"
```

### 新版 retrieve API 关键参数

当前下游默认对接新版 `/v1/retrieve`，重点使用这些参数：

- `query`
- `top_k`
- `collection`
- `filters`
- `query_mode`
- `literal_first`
- `literal_pool_factor`

其中：

- `query_mode = knowledge`：更适合实体/概念查询，如 `心宿`、`荧惑`
- `query_mode = evidence`：更适合原文短语查询，如 `荧惑守心`
- `query_mode = support`：更适合索引/摘要/导航类辅助查询
- `literal_first = true`：对古籍整句原文非常重要，可让全文子串命中优先

### 推荐查询模式

#### 1. entity mode
适用于：
- `心宿`
- `角宿`
- `荧惑`
- `太白`

默认策略：
- `query_mode = knowledge`
- `literal_first = false`
- 优先返回结构化知识卡

#### 2. evidence mode
适用于：
- `荧惑守心`
- `月犯心宿`
- `五星聚`
- `土木合`

默认策略：
- `query_mode = evidence`
- `literal_first = true`
- 优先返回 `fenjuan` / `fulltext`

## 简繁体与原文回证

本项目默认假设上游知识库可能是繁体环境，因此 evidence 查询应支持：

- 简繁体归一
- 空格变体
- 上游 `aliases / variant_terms / normalized_terms`

例如 `荧惑守心` 应支持：
- `荧惑守心`
- `熒惑守心`
- `荧惑 守心`
- `熒惑 守心`

对于 evidence 查询：

- `primary_candidates` **只能**包含 `fenjuan` / `fulltext`
- 若没有 primary，structured 结果应进入 `structured_fallbacks`
- structured fallback 必须标记 `status = candidate_only`

## CLI 命令

### 1. 数据校验

```bash
python -m src.cli validate-data
```

### 2. 直接调用 kb-search

适合调试 retrieve 参数本身。

实体查询：

```bash
python -m src.cli search-kb "心宿" \
  --book-id kaiyuan_zhanjing \
  --query-mode knowledge \
  --limit 5
```

原文证据查询：

```bash
python -m src.cli search-kb "荧惑守心" \
  --book-id kaiyuan_zhanjing \
  --query-mode evidence \
  --literal-first \
  --limit 8
```

### 3. 结果整理与回证视图

`inspect-kb` 是更高层的“结果整理器”，负责把检索结果整理成：
- `exact_hits`
- `primary_candidates`
- `structured_fallbacks`
- 调试统计信息

实体查询示例：

```bash
python -m src.cli inspect-kb --query "心宿"
```

原文证据查询示例：

```bash
python -m src.cli inspect-kb --query "荧惑守心"
```

若需要完整调试输出：

```bash
python -m src.cli inspect-kb --query "荧惑守心" --show-raw
```

### 4. 证据链解析

```bash
python -m src.cli resolve-evidence --rule data/processed/corpus/sample_rules.json
```

默认输出 JSON；若代码已支持人类可读输出，可追加 `--pretty`。

### 5. 批量审计规则可引用状态

```bash
python -m src.cli audit-rules --rules-path data/processed/corpus/sample_rules.json
```

## 本地联调建议

### A. 先验证服务状态

```bash
curl -sS "http://127.0.0.1:${KB_SEARCH_API_PORT:-8008}/v1/health"
```

### B. 先测上游 retrieve，再测下游 CLI

```bash
curl -sS "http://127.0.0.1:${KB_SEARCH_API_PORT:-8008}/v1/retrieve" \
  -H "Authorization: Bearer ${KB_SEARCH_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query":"荧惑守心","top_k":8,"query_mode":"evidence","literal_first":true}'
```

然后再测：

```bash
python -m src.cli search-kb "荧惑守心" \
  --book-id kaiyuan_zhanjing \
  --query-mode evidence \
  --literal-first \
  --limit 8

python -m src.cli inspect-kb --query "荧惑守心" --show-raw
```

### C. 推荐调试顺序

1. `validate-data`
2. `search-kb` 验证底层 retrieve 参数
3. `inspect-kb` 观察 exact / primary / structured fallback 是否合理
4. `resolve-evidence` 验证规则到原文的回链
5. `audit-rules` 看规则是否可直接引用

## 常见问题

### 1. `Missing API key`
未设置 `KB_SEARCH_API_KEY`，或仍在使用占位值（如 `dev_change_me`、`change_me`）。

### 2. `Connection refused`
`kb-search` 未启动，或端口配置错误。先检查：

```bash
make up
```

以及 `KB_SEARCH_API_PORT`。

### 3. evidence query 只有 structured，没有 primary
说明当前只能作为“候选解释”，不能作为最终事实证据。优先排查：

- 上游 `fenjuan/fulltext` 是否已入库
- 是否已补 `card_type` 并重新 `make ingest`
- 是否已启用 `query_mode=evidence`
- 是否已启用 `literal_first=true`
- 是否存在简繁体差异

### 4. `fallback_used=true` 但没有命中
这通常表示已经进入 fallback，但原文层仍未找到目标短语。应检查：

- `variant_terms` 是否补齐
- 原文层文件是否属于 `fenjuan/fulltext`
- `source_locator` / heading / chunk 是否可被扫描

## 测试

运行核心测试集：

```bash
pytest -q tests/test_cli_inspect_resolve.py tests/test_cli_search.py tests/test_retriever.py tests/test_config.py
```

或全量运行：

```bash
pytest -q
```

建议不要在 README 中长期写死通过数量，因为它会随开发变化而过期。

## 相关文档

- `docs/methodology.md`
- `docs/upstream-kb-structure-spec.md`
- `docs/upstream-frontmatter-spec.md`
- `docs/upstream-kb-minimal-enhancement-checklist.md`
- `docs/retrieval-pool-spec.md`
- `docs/term-normalization-spec.md`
- `docs/corpus-optimization-roadmap-v1.md`

## 当前开发建议

先把这三件事做稳：

1. 上游 frontmatter 与最小补数
2. `kb-search` 的 `query_mode + literal_first` 下游对接
3. `inspect-kb / resolve-evidence / audit-rules` 的证据链闭环

在这些稳定之前，不建议把重点转到大规模自动预测或复杂回测。
