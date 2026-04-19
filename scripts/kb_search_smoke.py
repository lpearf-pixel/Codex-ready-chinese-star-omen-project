#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.connectors.kb_search_retriever import KBSearchRetriever


MIN_QUERIES = ["心宿", "荧惑", "荧惑守心", "月犯心宿", "五星聚"]
EVAL_PATH = ROOT / "eval" / "corpus_eval_cases.yaml"


def run_live(collection: str | None = None) -> dict[str, Any]:
    retriever = KBSearchRetriever()
    health = retriever.health()

    knowledge = retriever.retrieve(MIN_QUERIES[0], collection=collection)
    evidence = retriever.retrieve(MIN_QUERIES[2], collection=collection)

    return {
        "mode": "live",
        "health": health,
        "knowledge": {
            "query": MIN_QUERIES[0],
            "query_mode": knowledge.get("query_mode"),
            "literal_first": knowledge.get("literal_first"),
            "payload_contract_version": knowledge.get("payload_contract_version"),
            "retrieval_pool_spec": knowledge.get("retrieval_pool_spec"),
            "top_hit": (knowledge.get("hits") or [None])[0],
        },
        "evidence": {
            "query": MIN_QUERIES[2],
            "query_mode": evidence.get("query_mode"),
            "literal_first": evidence.get("literal_first"),
            "payload_contract_version": evidence.get("payload_contract_version"),
            "retrieval_pool_spec": evidence.get("retrieval_pool_spec"),
            "top_hit": (evidence.get("hits") or [None])[0],
        },
    }


def run_payload_check() -> dict[str, Any]:
    retriever = KBSearchRetriever(base_url="http://127.0.0.1:9999", api_key="smoke_key")
    captured: list[dict[str, Any]] = []

    def fake_request(self, method, path, **kwargs):
        captured.append(kwargs.get("json_payload") or {})
        return {"hits": []}

    retriever._request = fake_request.__get__(retriever, KBSearchRetriever)  # type: ignore[attr-defined]
    retriever.retrieve(MIN_QUERIES[0])
    retriever.retrieve(MIN_QUERIES[2])

    return {
        "mode": "payload_check",
        "captured_payloads": captured,
        "qdrant_payload_keys": sorted(list(captured[0].keys())) if captured else [],
        "checks": {
            "knowledge_mode": captured[0].get("query_mode") == "knowledge" if len(captured) > 0 else False,
            "evidence_mode": captured[1].get("query_mode") == "evidence" if len(captured) > 1 else False,
            "evidence_literal_first": captured[1].get("literal_first") is True if len(captured) > 1 else False,
            "retrieval_pool_present": "retrieval_pool" in captured[0] if len(captured) > 0 else False,
        },
    }


def _load_eval_cases() -> list[dict[str, Any]]:
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(EVAL_PATH.read_text(encoding="utf-8")) or {}
        return parsed.get("cases", [])
    except Exception:
        cases: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw in EVAL_PATH.read_text(encoding="utf-8").splitlines():
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
                current[k.strip()] = v.strip().strip('"')
        if current:
            cases.append(current)
        return cases


def run_corpus_eval() -> dict[str, Any]:
    retriever = KBSearchRetriever(base_url="http://127.0.0.1:9999", api_key="smoke_key")
    captured: list[dict[str, Any]] = []

    def fake_request(self, method, path, **kwargs):
        captured.append(kwargs.get("json_payload") or {})
        return {"hits": []}

    retriever._request = fake_request.__get__(retriever, KBSearchRetriever)  # type: ignore[attr-defined]
    cases = _load_eval_cases()
    rows = []
    for case in cases:
        q = case.get("query")
        if not q:
            continue
        out = retriever.retrieve(str(q))
        rows.append(
            {
                "query": q,
                "expected_mode": case.get("query_mode"),
                "actual_mode": out.get("query_mode"),
                "mode_match": out.get("query_mode") == case.get("query_mode"),
            }
        )
    return {"mode": "corpus_eval", "cases": rows, "all_mode_match": all(row["mode_match"] for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description="kb-search smoke script")
    parser.add_argument("--mode", choices=["live", "payload-check", "corpus-eval"], default="payload-check")
    parser.add_argument("--collection", default=None)
    args = parser.parse_args()

    if args.mode == "live":
        out = run_live(collection=args.collection)
    elif args.mode == "corpus-eval":
        out = run_corpus_eval()
    else:
        out = run_payload_check()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
