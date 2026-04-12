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
        self.settings = cfg
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
    def _query_mode(query: str) -> str:
        q = query.strip()
        phrase_markers = {"守", "犯", "合", "聚", "逆", "留", "蚀", "蝕", "入"}
        if any(m in q for m in phrase_markers):
            return "phrase"
        if len(q) <= 3:
            return "entity"
        return "phrase"

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
    def _basename(path: str | None) -> str:
        return Path(str(path or "").replace("\\", "/")).stem

    @classmethod
    def _rank_hit(cls, query: str, hit: dict[str, Any], mode: str) -> int:
        q = query.strip()
        qn = q.lower()
        title = str(hit.get("title") or "").strip()
        t = title.lower()
        snippet = str(hit.get("snippet") or "")
        basename = cls._basename(hit.get("path")).lower()
        path = str(hit.get("path") or "").replace("\\", "/")

        score = int(float(hit.get("score") or 0) * 10)
        if mode == "entity":
            if t == qn:
                score += 120
            if basename == qn:
                score += 110
            if f"# {q}" in snippet or f"## {q}" in snippet:
                score += 100
            if qn in t:
                score += 30
            if qn in basename:
                score += 30
            if "/逐宿卡/" in path and basename != qn:
                score -= 20
        else:
            if q and q in snippet:
                score += 120
            if q and q in title:
                score += 90
            keywords = [k for k in ["荧惑", "守", "心", "月", "犯", "五星", "聚"] if k in q]
            keyword_hits = sum(1 for k in keywords if k in snippet or k in title)
            score += keyword_hits * 15
            if q and q not in snippet and q not in title:
                score -= 10
        return score

    @classmethod
    def _rerank_hits(cls, query: str, inferred_hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
        mode = cls._query_mode(query)
        ranked = [{**h, "_rank": cls._rank_hit(query, h, mode)} for h in inferred_hits]
        ranked.sort(key=lambda x: x.get("_rank", 0), reverse=True)

        if mode == "entity":
            exact_hits = [h for h in ranked if cls._basename(h.get("path")) == query or str(h.get("title") or "") == query]
        else:
            exact_hits = [h for h in ranked if query in str(h.get("snippet") or "") or query in str(h.get("title") or "")]
        related_hits = [h for h in ranked if h not in exact_hits]

        ordered = exact_hits[:3] + related_hits[:3] if exact_hits else ranked[:6]
        return ordered, exact_hits[:3], related_hits[:3], mode

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

    def _scan_primary_files(self, query: str, *, book_id: str | None, mode: str, limit: int = 3) -> list[dict[str, Any]]:
        roots = [Path(self.settings.kb_sources_root)]
        if self.settings.kb_enable_obsidian_source:
            roots.append(Path(self.settings.kb_obsidian_root))

        hits: list[dict[str, Any]] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                normalized = str(path).replace("\\", "/")
                if "/分卷/" not in normalized and "全文合併版" not in normalized and "全文合并版" not in normalized:
                    continue
                meta = infer_metadata_from_path(normalized)
                if meta.get("card_type") not in {"fenjuan", "fulltext"}:
                    continue
                if book_id and meta.get("book_id") != book_id:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue

                matched = query in text if mode == "phrase" else query in text or self._basename(normalized) == query
                if not matched:
                    continue
                hits.append(
                    {
                        "chunk_id": f"fallback:{path.name}",
                        "score": 1.0,
                        "path": normalized,
                        "snippet": text[:200],
                        "source_type": "docs",
                        "title": self._basename(normalized),
                        "book_title": meta.get("book_title"),
                        "book_id": meta.get("book_id"),
                        "card_type": meta.get("card_type"),
                        "evidence_level": meta.get("evidence_level"),
                    }
                )
                if len(hits) >= limit:
                    return hits
        return hits

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
        reranked, exact_hits, related_hits, mode = self._rerank_hits(query, inferred_hits)
        filtered_hits = self._apply_local_filters(
            reranked,
            book_id=book_id,
            card_types=card_types,
            evidence_level=evidence_level,
        )
        return {
            **raw_result,
            "query_mode": mode,
            "raw_hits": raw_hits,
            "inferred_hits": inferred_hits,
            "exact_hits": exact_hits[:3],
            "related_hits": related_hits[:3],
            "hits": filtered_hits[:6],
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

        mode = stage1.get("query_mode") or self._query_mode(query)
        structured_seed = query
        if stage1.get("hits"):
            top_structured = stage1["hits"][0]
            structured_seed = str(top_structured.get("title") or self._basename(top_structured.get("path")) or query)

        # stage2: structured -> primary backchain
        primary_candidates = self._scan_primary_files(structured_seed, book_id=book_id, mode=self._query_mode(structured_seed), limit=3)
        fallback_used = False

        stage2_exact = [h for h in primary_candidates if query in str(h.get("snippet") or "") or str(h.get("title") or "") == query][:3]
        if not stage2_exact:
            fallback_used = True
            fallback_candidates = self._scan_primary_files(query, book_id=book_id, mode=mode, limit=3)
            for hit in fallback_candidates:
                if hit not in primary_candidates:
                    primary_candidates.append(hit)
            primary_candidates = primary_candidates[:3]
            stage2_exact = [h for h in primary_candidates if query in str(h.get("snippet") or "") or str(h.get("title") or "") == query][:3]
        stage2_related = [h for h in primary_candidates if h not in stage2_exact][:3]

        stage2 = {
            "raw_hits": [],
            "inferred_hits": primary_candidates,
            "query_mode": mode,
            "exact_hits": stage2_exact,
            "related_hits": stage2_related,
            "hits": primary_candidates[:3],
            "primary_candidates": primary_candidates[:3],
            "fallback_used": fallback_used,
            "only_structured_no_primary": bool(stage1.get("hits")) and not bool(primary_candidates),
        }
        return {"stage1": stage1, "stage2": stage2}
