from __future__ import annotations

import json
import logging
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

from src.config.settings import (
    Settings,
    SettingsError,
    get_settings,
    mask_secret,
    require_api_key,
)

logger = logging.getLogger(__name__)


class KBSearchError(RuntimeError):
    pass


class KBSearchRetriever:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        default_collection: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.base_url = (base_url or cfg.kb_search_effective_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else cfg.kb_search_timeout_seconds
        self.api_key = api_key if api_key is not None else cfg.kb_search_api_key
        self.default_collection = default_collection or cfg.kb_search_default_collection
        self.default_limit = cfg.app_default_limit

    def _auth_headers(self) -> dict[str, str]:
        key = self.api_key
        if not key:
            try:
                key = require_api_key()
            except SettingsError as exc:
                raise KBSearchError(str(exc)) from exc
        return {"Authorization": f"Bearer {key}", "X-API-Key": key}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        use_auth: bool = False,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers() if use_auth else {}
        try:
            if httpx is not None:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.request(method, url, json=json_payload, headers=headers)
                    resp.raise_for_status()
                    return resp.json()

            import urllib.request

            data = json.dumps(json_payload).encode("utf-8") if json_payload is not None else None
            req = urllib.request.Request(
                url,
                data=data,
                method=method,
                headers={**headers, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as exc:  # pragma: no cover
            logger.error(
                "kb-search request failed method=%s url=%s api_key=%s error=%s",
                method,
                url,
                mask_secret(self.api_key),
                exc,
            )
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
        limit: int | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit if limit is not None else self.default_limit,
            "collection": collection or self.default_collection,
        }
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

    def rag_query(
        self,
        query: str,
        *,
        book_id: str | None = None,
        limit: int | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit if limit is not None else self.default_limit,
            "collection": collection or self.default_collection,
        }
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
        limit: int | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        return self.retrieve(
            query,
            book_id=book_id,
            card_types=card_types,
            evidence_level=evidence_level,
            limit=limit,
            collection=collection,
        )

    def two_stage_retrieve(
        self,
        query: str,
        *,
        book_id: str | None = None,
        limit: int | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        stage1 = self.retrieve(
            query,
            book_id=book_id,
            card_types=["xingguan_card", "zhusu_card", "term_card", "extract_card", "topic_index", "chapter_summary"],
            limit=limit,
            collection=collection,
        )
        stage2 = self.retrieve(
            query,
            book_id=book_id,
            card_types=["fenjuan", "fulltext"],
            evidence_level="primary",
            limit=limit,
            collection=collection,
        )
        return {"stage1": stage1, "stage2": stage2}
