# Rule Match Eval Spec (Sprint 4)

评测文件：`eval/rule_match_eval_cases.yaml`

每条 case 至少包含：
- `input_event_id`
- `event_path`
- `expected_rule_ids`
- `must_have_primary_evidence`
- `allow_structured_fallback`
- `expected_match_status`

最小规则覆盖：
- 荧惑守心
- 月犯心宿
- 五星聚
- 土木合

评测集需覆盖三类：
- 正例：规则应命中
- 负例：body/target/event_type 不匹配
- 边界例：阈值边界、多规则冲突、only structured fallback

运行示例：

```bash
python -m src.cli match-rule --event data/examples/events/mars_guarding_xin_demo.json
```
