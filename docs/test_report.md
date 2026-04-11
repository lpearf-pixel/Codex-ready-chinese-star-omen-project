# 测试报告（本地）

> 日期：2026-04-11  
> 分支：`work`  
> 范围：初始化脚手架（schema / connector / CLI / sample data）

## 1. 测试环境

- Python：3.10.19（容器默认）
- 目标版本：Python 3.12（见 `pyproject.toml`）
- 测试框架：pytest

## 2. 执行命令

```bash
pytest -q
python -m src.cli validate-data
```

## 3. 结果摘要

- `pytest -q`：**14 passed, 4 skipped**
- `python -m src.cli validate-data`：成功（fallback CLI 可运行）

## 4. 已覆盖能力

1. **知识库契约规则**：`final_citable` / `evidence_level` 映射逻辑。
2. **证据解析**：是否可回链、是否可作为最终引用。
3. **manifest 读取**：`manifest:<name>` 的载入与巡检。
4. **检索器请求构造**：`kb-search` payload 过滤参数构造。
5. **CLI 校验命令**：在依赖可用时可执行 `validate-data`。
6. **配置读取**：`config/app_config.yaml` 中 `kb_search.base_url/timeout_seconds` 可被加载并用于默认检索配置。
7. **CLI 检索命令**：`search-kb` 命令参数传递与输出序列化。
8. **CLI 规则审计命令**：`audit-rules` 对规则证据链进行批量状态统计（`citable/candidate_only/missing_evidence`）。
9. **CLI 参数联调**：`inspect-kb` 支持 `--root/--query/--book-id/--card-type/--evidence-level/--limit/--show-raw` 参数解析。
10. **证据回链字段**：`resolve-evidence` 输出 `relative_path/locator/quote/card_type/evidence_level`，并在 strict 模式拒绝候选证据。

## 5. 风险与建议

- 当前容器无法联网安装依赖，kb-search 联调需确保本地服务已启动并配置 API key。
- 建议在本地 Python 3.12 环境执行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
python -m src.cli validate-data
```
