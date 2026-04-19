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


def main() -> None:
    parser = argparse.ArgumentParser(description="kb-search smoke script")
    parser.add_argument("--mode", choices=["live", "payload-check"], default="payload-check")
    parser.add_argument("--collection", default=None)
    args = parser.parse_args()

    if args.mode == "live":
        out = run_live(collection=args.collection)
    else:
        out = run_payload_check()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
