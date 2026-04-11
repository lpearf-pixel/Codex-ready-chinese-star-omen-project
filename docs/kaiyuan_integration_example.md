# 《开元占经》本地联调示例（M0）

> 目标：演示“检索 -> 回证 -> 审计”的最小闭环，不进入天文计算模块。

## 1) 检索阶段（structured）

```bash
python -m src.cli inspect-kb \
  --root /data/obsidian-kb \
  --query "荧惑守心" \
  --book-id kaiyuan_zhanjing \
  --card-type term_card \
  --card-type extract_card \
  --evidence-level structured
```

预期：返回 `mode=search`，并带有 `result.hits`。

## 2) 证据回链阶段（single rule）

```bash
python -m src.cli resolve-evidence \
  --rule data/processed/corpus/sample_rule_one.json \
  --kb-root /data/obsidian-kb
```

预期输出关键字段：

- `relative_path`
- `locator`
- `quote`
- `card_type`
- `evidence_level`
- `status`

## 3) 批量审计阶段（ruleset）

```bash
python -m src.cli audit-rules \
  --rules-path data/processed/corpus/sample_rules.json \
  --kb-root /data/obsidian-kb
```

预期：输出 `citable / candidate_only / missing_evidence` 汇总统计与每条规则状态。
