from __future__ import annotations

from typing import Any


def render_layered_template(*, level: str, row: dict[str, Any]) -> str:
    event = row.get("representative_event") or {}
    return "\n".join(
        [
            f"# {level}",
            "",
            f"- 时间窗口: {row.get('window')}",
            f"- 代表事件: {event.get('event_type')} / {event.get('body')} / {event.get('target_asterism')}",
            f"- 命中规则: {row.get('matched_rule_ids', [])}",
            f"- 证据链摘要: primary_hit_rate={row.get('primary_evidence_hit_rate')} candidate_only_rate={row.get('candidate_only_rate')}",
            f"- calc_source/calc_quality: {event.get('calc_source')} / {event.get('calc_quality')}",
            f"- output_level: {row.get('output_level')}",
            f"- recommendation_summary: {row.get('level_reason')}",
            f"- 风险提示: 本输出仅供研究，不构成正式预测结论。",
            "",
        ]
    )
