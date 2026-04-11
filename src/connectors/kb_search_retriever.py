from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

from src.config.settings import Settings, SettingsError, get_settings, mask_secret, require_api_key
from src.connectors.kb_contract import infer_metadata_from_path

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

    @staticmethod
    def _normalize_hits(raw_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        inferred_hits: list[dict[str, Any]] = []
        for hit in raw_hits:
            inferred = infer_metadata_from_path(hit.get("path"))
            inferred_hits.append(
                {
                    **hit,
                    "book_title": inferred.get("book_title"),
                    "book_id": inferred.get("book_id"),
                    "card_type": inferred.get("card_type"),
                    "evidence_level": inferred.get("evidence_level"),
                }
            )
        return inferred_hits

    @staticmethod
    def _rank_hit(query: str, hit: dict[str, Any]) -> int:
        query_norm = query.strip().lower()
        title = str(hit.get("title") or "").strip()
        title_norm = title.lower()
        snippet = str(hit.get("snippet") or "")
        path = str(hit.get("path") or "")
        basename = Path(path.replace("\\", "/")).stem.lower()

        score = 0
        if title_norm == query_norm:
            score += 100
        if basename == query_norm:
            score += 90
        if f"# {query}" in snippet or f"【{query}】" in snippet or f"《{query}》" in snippet:
            score += 80
        if query_norm and query_norm in title_norm:
            score += 30
        if query_norm and query_norm in basename:
            score += 30
        score += int(float(hit.get("score") or 0) * 10)
        return score

    @classmethod
    def _rerank_hits(cls, query: str, inferred_hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        ranked = [{**h, "_rank": cls._rank_hit(query, h)} for h in inferred_hits]
        ranked.sort(key=lambda x: x.get("_rank", 0), reverse=True)
        exact_hits = [h for h in ranked if h.get("_rank", 0) >= 90]
        related_hits = [h for h in ranked if h.get("_rank", 0) < 90]

        # 精确优先：短 query 且存在精确命中时，仅保留少量 related
        is_short_query = len(query.strip()) <= 4
        if is_short_query and exact_hits:
            ordered = exact_hits + related_hits[:3]
        else:
            ordered = ranked
        return ordered, exact_hits, related_hits

    @staticmethod
    def _apply_local_filters(
        inferred_hits: list[dict[str, Any]],
        *,
        book_id: str | None = None,
        card_types: list[str] | None = None,
        evidence_level: str | None = None,
    ) -> list[dict[str, Any]]:
        out = inferred_hits
        if book_id:
            out = [h for h in out if h.get("book_id") == book_id]
        if card_types:
            allowed = set(card_types)
            out = [h for h in out if h.get("card_type") in allowed]
        if evidence_level:
            out = [h for h in out if h.get("evidence_level") == evidence_level]
        return out

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
        raw_result = self._request("POST", "/v1/retrieve", json_payload=payload, use_auth=True)
        raw_hits = raw_result.get("hits", [])
        inferred_hits = self._normalize_hits(raw_hits)
        reranked, exact_hits, related_hits = self._rerank_hits(query, inferred_hits)
        filtered_hits = self._apply_local_filters(
            reranked,
            book_id=book_id,
            card_types=card_types,
            evidence_level=evidence_level,
        )
        return {
            **raw_result,
            "raw_hits": raw_hits,
            "inferred_hits": inferred_hits,
            "exact_hits": exact_hits,
            "related_hits": related_hits,
            "hits": filtered_hits,
        }

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

        primary_query = query
        if stage1.get("exact_hits"):
            top_exact = stage1["exact_hits"][0]
            primary_query = str(top_exact.get("title") or Path(str(top_exact.get("path") or "")).stem or query)

        stage2 = self.retrieve(
            primary_query,
            book_id=book_id,
            card_types=["fenjuan", "fulltext"],
            evidence_level="primary",
            limit=limit,
            collection=collection,
        )

        stage2["primary_candidates"] = stage2.get("hits", [])
        stage2["only_structured_no_primary"] = bool(stage1.get("hits")) and not bool(stage2.get("hits"))
        return {"stage1": stage1, "stage2": stage2}
