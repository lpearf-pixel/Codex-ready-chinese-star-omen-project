from __future__ import annotations

import json
import os
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

from src.config import load_kb_search_config


class KBSearchError(RuntimeError):
    pass


class KBSearchRetriever:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float | None = None) -> None:
        cfg = load_kb_search_config()
        port = os.getenv("KB_SEARCH_API_PORT", "8008")
        default_base = f"http://127.0.0.1:{port}"
        self.base_url = (base_url or cfg.base_url or default_base).rstrip("/")
        self.timeout = timeout if timeout is not None else cfg.timeout_seconds
        self.api_key = api_key or os.getenv("KB_SEARCH_API_KEY")

    def _auth_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise KBSearchError(
                "Missing API key. Please set KB_SEARCH_API_KEY or pass api_key to KBSearchRetriever."
            )
        return {"Authorization": f"Bearer {self.api_key}", "X-API-Key": self.api_key}

    def _request(self, method: str, path: str, *, json_payload: dict[str, Any] | None = None, use_auth: bool = False) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers() if use_auth else {}
        try:
            if httpx is not None:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.request(method, url, json=json_payload, headers=headers)
                    resp.raise_for_status()
                    return resp.json()

            # urllib fallback in restricted environments
            import urllib.request
            import urllib.error

            data = json.dumps(json_payload).encode("utf-8") if json_payload is not None else None
            req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as exc:  # pragma: no cover
            raise KBSearchError(f"kb-search request failed: method={method} url={url} error={exc}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", use_auth=False)

    def retrieve(
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
        return self._request("POST", "/v1/retrieve", json_payload=payload, use_auth=True)

    def rag_query(self, query: str, *, book_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query, "limit": limit}
        if book_id:
            payload["book_id"] = book_id
        return self._request("POST", "/v1/rag/query", json_payload=payload, use_auth=True)

    def search(
        self,
        query: str,
        *,
        book_id: str | None = None,
        card_types: list[str] | None = None,
        evidence_level: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return self.retrieve(
            query,
            book_id=book_id,
            card_types=card_types,
            evidence_level=evidence_level,
            limit=limit,
        )

    def two_stage_retrieve(self, query: str, *, book_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        stage1 = self.retrieve(
            query,
            book_id=book_id,
            card_types=["xingguan_card", "zhusu_card", "term_card", "extract_card", "topic_index", "chapter_summary"],
            limit=limit,
        )
        stage2 = self.retrieve(
            query,
            book_id=book_id,
            card_types=["fenjuan", "fulltext"],
            evidence_level="primary",
            limit=limit,
        )
        return {"stage1": stage1, "stage2": stage2}
