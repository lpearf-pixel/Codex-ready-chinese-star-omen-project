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

## 配置与环境变量

本项目已改为**环境变量驱动**，统一由 `src/config/settings.py` 读取。默认配置文件为 `config/config.yaml`（可用 `APP_CONFIG_PATH` 覆盖），并支持 `${VAR}` / `${VAR:-default}` 插值。`KB_SEARCH_BASE_URL` 存在时优先使用；否则回退到 `http://127.0.0.1:${KB_SEARCH_API_PORT}`。

常用变量（完整示例见 `.env.example` / `.env.test.example`）：

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

> 安全提示：日志会对 API key 做脱敏显示，不会打印完整密钥。


## 短词/短语检索策略

- **entity mode**（短实体词：如 `心宿`、`角宿`、`太白`、`荧惑`）：默认只展示 1 条最佳 `exact_hit`，`related_hits` 默认隐藏（可用 `--show-related` 打开）。
- **evidence mode**（占象短语：如 `荧惑守心`、`月犯心宿`、`五星聚`）：默认优先展示 `primary_candidates`；若无 primary，则 structured 回落结果会标记 `status=candidate_only`。
- **exact fallback**：当 exact 不足时，会在本地只读扫描 primary 文档（`分卷/`、`全文合併版/全文合并版`），并输出扫描统计：`files_scanned`、`matched_files`、`matched_headings`、`fallback_used`。
- **默认输出收敛**：非 `--show-raw` 模式下不输出 `stage1.raw_hits`/`stage1.inferred_hits`/`stage1.filtered_hits`/`stage2.raw_hits`。

## 简繁体检索策略与 evidence fallback

- evidence 查询会生成简繁体与空格变体（如：`荧惑守心` / `熒惑守心` / `荧惑 守心` / `熒惑 守心`）。
- fallback 仅扫描当前 `book_id` 下 primary 原文目录：`分卷/`、`全文合併版`、`全文合并版`。
- `primary_candidates` 只允许 `fenjuan/fulltext`；structured 结果进入 `structured_fallbacks` 并标记 `status=candidate_only`。
- 当 `fallback_used=true` 时会输出真实扫描统计：`files_scanned`、`matched_files`、`matched_headings`。

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
# 默认输出 JSON；若需人类可读格式可追加 --pretty
```

### 5) 调用 kb-search 进行召回

```bash
python -m src.cli search-kb "荧惑守心" --book-id kaiyuan_zhanjing --card-type term_card --top-k 5
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

## 本地联调（kb-search 对接）

### 1) 启动 kb-search

```bash
make up
```

### 2) 确保知识已入库

```bash
make ingest
```

### 3) 健康检查示例

```bash
python - <<'PY'
from src.connectors.kb_search_retriever import KBSearchRetriever
print(KBSearchRetriever().health())
PY
```

### 4) inspect-kb 调用示例

> `inspect-kb` 现在是结果整理器：负责将 stage1/stage2 输出按 structured / primary 展示，不再承担底层检索参数编排。

```bash
export KB_SEARCH_API_KEY=your_key
python -m src.cli inspect-kb \
  --query "荧惑守心" \
  --book-id kaiyuan_zhanjing \
  --card-type term_card \
  --evidence-level structured \
  --limit 10 \
  --show-raw
```

## 新版 kb-search API 对接

- `search-kb` 已直接映射新版 `/v1/retrieve` 参数：
  - `query`
  - `top_k`
  - `collection`
  - `filters`
  - `query_mode`
  - `literal_first`
  - `literal_pool_factor`
  - `retrieval_pool`（下游固化 pool spec，按 `query_mode` 自动给出 stage1/stage2 card_type 池）
- query intent 会收敛到 `query_mode`：
  - entity query → `knowledge`
  - evidence query → `evidence`
  - support query → `support`
- evidence query 默认行为：
  - `query_mode = evidence`
  - `literal_first = true`
- `inspect-kb` 语义约束：
  - `primary_candidates` 只能来自 `fenjuan/fulltext`
  - 当 `query_mode = evidence` 且无 primary 命中时，`structured_fallbacks` 作为候选线索输出，条目会标记 `status = candidate_only`
- 检索输出固定包含：
  - `payload_contract_version = v2`
  - `retrieval_pool_spec`
  - 锚点字段优先补齐：`volume / section / source_locator / heading_path / anchor_text`
- 元数据优先级：
  - 优先消费上游 flatten 后命中结果的顶层 metadata（`book_id/card_type/evidence_level`）；
  - 仅缺失时才退回路径推断。

### 最小检索评测集

- 评测样例文件：`data/examples/min_retrieval_eval_set.json`
- Sprint 2 评测集（用于可执行验收）：`eval/corpus_eval_cases.yaml`
- 评测规范：`docs/corpus-eval-spec.md`
- 当前包含 5 个最小 query：
  - `心宿`
  - `荧惑`
  - `荧惑守心`
  - `月犯心宿`
  - `五星聚`

### 原文锚点化（Sprint 2）

- 原文层输出字段：`volume / section / source_locator / heading_path / anchor_text / paragraph_index(可选)`
- `resolve-evidence` 输出将携带这些字段，定位粒度可达卷/节/heading，不再仅是文件级。

### 排除规则与切块策略

- 排除规则文档：`docs/retrieval-exclusion-rules.md`
- 切块策略文档：`docs/chunking-strategy-spec.md`

### 5) resolve-evidence 调用示例

```bash
python -m src.cli resolve-evidence \
  --rule data/processed/corpus/sample_rules.json
```

### 6) 常见报错与排查

- `Missing API key`：未设置 `KB_SEARCH_API_KEY`，请先 `export KB_SEARCH_API_KEY=...`。
- `Connection refused`：kb-search 未启动或端口不对，检查 `make up` 和 `KB_SEARCH_API_PORT`。
- 只有 `structured_hits` 没有 `primary_hits`：当前只能作为“线索/候选解释”，不可作为最终事实证据。

## Smoke 检查脚本（health / knowledge / evidence / Qdrant payload）

- 脚本位置：`scripts/kb_search_smoke.py`
- payload 合约检查（默认，不依赖在线服务）：

```bash
python scripts/kb_search_smoke.py --mode payload-check
```

- 在线检查（需要可访问 kb-search）：

```bash
python scripts/kb_search_smoke.py --mode live --collection local_kb_default
```

- 评测集模式（离线校验 `eval/corpus_eval_cases.yaml` 的 query_mode 预期）：

```bash
python scripts/kb_search_smoke.py --mode corpus-eval
```

## Eval 回归命令（Sprint 3）

```bash
python -m src.cli eval-corpus
```

- `smoke`：链路活性检查（健康检查、payload flatten、基础 query 可用性）
- `eval`：质量回归检查（固定 query 集 + 期望对比 + pass/fail 摘要）

## Corpus 版本追踪（Sprint 3）

- manifest：`data/corpus_manifest.json`
- 变更记录：`docs/corpus-change-log.md`
- 版本规则：`docs/corpus-versioning.md`

## 自动化天象分析接口边界（仅接口）

- 接口定义：`src/interfaces/astronomy.py`
- 说明文档：`docs/automation-interface-boundary.md`
- 当前仅定义边界，不含完整天文计算实现。

## Sprint 4：最小可计算闭环（非完整天文实现）

- 本阶段目标：
  - 定义最小 `CelestialEvent` 输入协议与样例
  - 跑通 `CelestialEvent -> OmenRule -> evidence` 最小闭环
  - 增加规则匹配评测集与 demo CLI
- 非目标：
  - 不实现完整天文计算
  - 不做批量自动推演
  - 不扩展大规模回测

### 最小事件输入示例

- `data/examples/events/mars_guarding_xin_demo.json`
- `data/examples/events/moon_invading_xin_demo.json`
- `data/examples/events/five_planets_gathering_demo.json`

### match-rule demo

```bash
python -m src.cli match-rule --event data/examples/events/mars_guarding_xin_demo.json
```

规则匹配评测集：
- `eval/rule_match_eval_cases.yaml`
- `docs/rule-match-eval-spec.md`

输出包含：
- `matched_rule_ids`
- `trigger_match_reason`
- `effect_domain`
- `severity`
- `time_window`
- `evidence_summary`
- `primary_evidence_found`
- `candidate_only`

## Sprint 5：规则执行增强与可计算语义收口

- 事件阈值配置：`config/event_thresholds.yaml`
- 阈值加载：`src/rule_engine/thresholds.py`
- 说明文档：`docs/event-thresholds-spec.md`
- 这些阈值当前为工程默认值，后续可依据回测与专家反馈调整。

`match-rule` 输出增强字段（按规则项）：
- `match_status`
- `match_score`
- `trigger_match_reason`
- `missing_conditions`
- `conflicting_conditions`
- `thresholds_used`
- `effect_domain`
- `severity`
- `time_window`
- `evidence_summary`
- `primary_evidence_found`
- `candidate_only`

冲突处理文档：`docs/rule-conflict-resolution.md`

## 测试报告入口

- 最新本地测试报告见：`docs/test_report.md`
- 《开元占经》本地联调示例见：`docs/kaiyuan_integration_example.md`

### 最新测试结论（2026-04-11）

- `pytest -q`：**14 passed, 4 skipped**
- `python -m src.cli validate-data`：成功
- 建议在本地 Python 3.12 虚拟环境复现测试流程（详见 `docs/test_report.md`）
