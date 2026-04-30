# Batch Runner Spec (Sprint 12)

实现：`src/pipeline/batch_runner.py`

支持批量运行：
- historical benchmark cases
- threshold profiles

输出最小字段：
- `run_id`
- `profile_name`
- `case_count`
- `window_count`
- `matched_case_count`
- `formal_candidate_count`
- `created_at`

落盘目录：`data/runs/<run_id>/`
