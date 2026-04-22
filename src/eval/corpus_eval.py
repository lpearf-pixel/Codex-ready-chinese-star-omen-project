from __future__ import annotations

from pathlib import Path
from typing import Any

from src.connectors.kb_search_retriever import KBSearchRetriever

PRIMARY_TYPES = {"fenjuan", "fulltext"}
POLLUTION_TYPES = {"prompt_asset", "nav", "qa_example"}


def _parse_scalar(raw: str) -> Any:
    val = raw.strip().strip('"')
    if val.lower() in {"true", "false"}:
        return val.lower() == "true"
    if val.startswith("[") and val.endswith("]"):
        body = val[1:-1].strip()
        if not body:
            return []
        return [item.strip().strip('"') for item in body.split(",")]
    return val


def load_eval_cases(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return parsed.get("cases", [])
    except Exception:
        cases: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line == "cases:":
                continue
            if line.startswith("- "):
                if current:
                    cases.append(current)
                current = {}
                line = line[2:]
            if ":" in line and current is not None:
                k, v = line.split(":", 1)
                current[k.strip()] = _parse_scalar(v)
        if current:
            cases.append(current)
        return cases


def run_corpus_eval(
    *,
    eval_path: Path = Path("eval/corpus_eval_cases.yaml"),
    retriever: KBSearchRetriever | None = None,
    collection: str | None = None,
    top_k: int | None = None,
) -> dict[str, Any]:
    r = retriever or KBSearchRetriever()
    cases = load_eval_cases(eval_path)
    rows: list[dict[str, Any]] = []

    for case in cases:
        query = str(case.get("query") or "")
        expected_mode = str(case.get("query_mode") or "")
        expected_path_contains = str(case.get("expected_top1_path_contains") or "")
        must_hit_primary = bool(case.get("must_hit_primary"))

        stage = r.two_stage_retrieve(query, collection=collection, top_k=top_k)
        stage1 = stage.get("stage1", {})
        stage2 = stage.get("stage2", {})

        query_mode = stage1.get("query_mode")
        top1 = (stage2.get("hits") or stage1.get("hits") or [None])[0] or {}
        actual_top1_path = str(top1.get("path") or "")
        top1_match = expected_path_contains in actual_top1_path if expected_path_contains else True

        primary_candidates = stage2.get("primary_candidates") or []
        primary_hit = any(h.get("card_type") in PRIMARY_TYPES for h in primary_candidates)
        structured_fallbacks = stage2.get("structured_fallbacks") or []
        used_structured_fallback = bool(structured_fallbacks)

        evidence_outputs = (stage2.get("hits") or []) + primary_candidates + structured_fallbacks
        pollution_detected = any(h.get("card_type") in POLLUTION_TYPES for h in evidence_outputs)

        mode_match = query_mode == expected_mode
        pass_case = mode_match and top1_match and (primary_hit or not must_hit_primary) and not pollution_detected

        rows.append(
            {
                "query": query,
                "query_mode": query_mode,
                "expected_query_mode": expected_mode,
                "expected_top1_path_contains": expected_path_contains,
                "actual_top1_path": actual_top1_path,
                "top1_match": top1_match,
                "must_hit_primary": must_hit_primary,
                "primary_hit": primary_hit,
                "used_structured_fallback": used_structured_fallback,
                "pollution_detected": pollution_detected,
                "pass": pass_case,
            }
        )

    passed = sum(1 for row in rows if row["pass"])
    return {
        "eval_path": str(eval_path),
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "all_passed": passed == len(rows),
        "rows": rows,
    }
