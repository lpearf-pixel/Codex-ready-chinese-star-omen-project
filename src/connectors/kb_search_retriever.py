from __future__ import annotations

from typing import Any

import httpx


class KBSearchRetriever:
    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

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
