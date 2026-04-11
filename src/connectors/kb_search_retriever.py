from __future__ import annotations

from typing import Any

import httpx

from src.config import load_kb_search_config


class KBSearchRetriever:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        cfg = load_kb_search_config()
        self.base_url = (base_url or cfg.base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else cfg.timeout_seconds

    def search(
        self,
        query: str,
        *,
        book_id: str | None = None,
        card_types: list[str] | None = None,
        evidence_level: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        filters: dict[str, Any] = {}
        if book_id:
            filters["book_id"] = book_id
        if card_types:
            filters["card_type"] = card_types
        if evidence_level:
            filters["evidence_level"] = evidence_level
        if filters:
            payload["filters"] = filters

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/kb-search", json=payload)
            resp.raise_for_status()
            return resp.json()
