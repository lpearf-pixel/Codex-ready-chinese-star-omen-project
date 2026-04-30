# Profile Governance Spec (Sprint 11)

Profile registry:
- `data/calibration/profile_registry.json`

状态：
- draft
- candidate
- baseline
- deprecated

命令：
- `propose-profile`
- `promote-profile`
- `rollback-profile`

规则：
- 同一时刻只允许一个 baseline
- promotion 需已有 experiment 与 compare 文件（最小校验）
- 所有治理动作写入 `data/calibration/profile_governance_log.jsonl`
