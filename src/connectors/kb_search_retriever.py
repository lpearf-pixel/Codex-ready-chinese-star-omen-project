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
    TRADITIONAL_MAP = str.maketrans({"荧": "熒", "并": "併"})
    SIMPLIFIED_MAP = str.maketrans({"熒": "荧", "併": "并"})
    EVIDENCE_EXCLUDED_CARD_TYPES = {"prompt_asset", "nav", "qa_example"}
    FACT_EXCLUDED_CARD_TYPES = {"qa_example"}
    PRIMARY_ONLY_PHRASES = {"荧惑守心", "熒惑守心", "月犯心宿", "五星聚", "土木合"}
    PRIMARY_CARD_TYPES = {"fenjuan", "fulltext"}
    STRUCTURED_CARD_TYPES = {"term_card", "zhusu_card", "extract_card"}
    INVALID_API_KEY_PLACEHOLDERS = {"dev_change_me", "change_me", "please_change_me", "replace_me"}
    RETRIEVAL_POOL_SPEC: dict[str, dict[str, list[str]]] = {
        "knowledge": {
            "stage1": ["xingguan_card", "zhusu_card", "term_card", "extract_card", "topic_index", "chapter_summary"],
            "stage2": ["fenjuan", "fulltext"],
        },
        "evidence": {
            "stage1": ["zhusu_card", "term_card", "extract_card"],
            "stage2": ["fenjuan", "fulltext"],
        },
        "support": {
            "stage1": ["topic_index", "chapter_summary", "extract_card"],
            "stage2": ["fenjuan", "fulltext"],
        },
    }
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
        key = (self.api_key or "").strip()
        if not key:
            try:
                key = require_api_key()
            except SettingsError as exc:
                raise KBSearchError(str(exc)) from exc
        if key.lower() in self.INVALID_API_KEY_PLACEHOLDERS:
            raise KBSearchError("Invalid KB_SEARCH_API_KEY: placeholder value detected, please set a real API key")
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
        support_markers = {"如何", "怎么", "為何", "为何", "解释", "背景", "來源", "来源", "依据"}
        if any(marker in q for marker in support_markers):
            return "support"
        phrase_markers = {"守", "犯", "合", "聚", "逆", "留", "蚀", "蝕", "入"}
        if any(m in q for m in phrase_markers):
            return "evidence"
        if len(q) <= 3:
            return "knowledge"
        return "knowledge"

    @classmethod
    def _normalize_query(cls, query: str) -> str:
        return query.translate(cls.TRADITIONAL_MAP).replace(" ", "")

    @classmethod
    def _query_variants(cls, query: str) -> list[str]:
        q = query.replace(" ", "")
        simp = q.translate(cls.SIMPLIFIED_MAP)
        trad = q.translate(cls.TRADITIONAL_MAP)
        variants = [q, trad, simp, f"{q[:2]} {q[2:]}" if len(q) > 2 else q, f"{trad[:2]} {trad[2:]}" if len(trad) > 2 else trad]
        dedup: list[str] = []
        for v in variants:
            if v and v not in dedup:
                dedup.append(v)
        return dedup

    @staticmethod
    def _normalize_hits(raw_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        inferred_hits: list[dict[str, Any]] = []
        for hit in raw_hits:
            upstream_meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
            inferred = infer_metadata_from_path(hit.get("path"))
            path = str(hit.get("path") or "")
            title = str(hit.get("title") or "")
            heading_path = hit.get("heading_path") or upstream_meta.get("heading_path") or [title] if title else []
            volume = hit.get("volume") or upstream_meta.get("volume")
            if not volume and "卷" in title:
                volume = title
            section = hit.get("section") or upstream_meta.get("section") or (heading_path[-1] if heading_path else title or None)
            source_locator = hit.get("source_locator") or upstream_meta.get("source_locator")
            if not source_locator:
                source_locator = f"{volume}/{section}" if volume and section else section or volume or None
            anchor_text = hit.get("anchor_text") or upstream_meta.get("anchor_text")
            if not anchor_text:
                anchor_text = str(hit.get("snippet") or "")[:120]
            inferred_hits.append(
                {
                    **hit,
                    "book_title": hit.get("book_title") or upstream_meta.get("book_title") or inferred.get("book_title"),
                    "book_id": hit.get("book_id") or upstream_meta.get("book_id") or inferred.get("book_id"),
                    "card_type": hit.get("card_type") or upstream_meta.get("card_type") or inferred.get("card_type"),
                    "evidence_level": hit.get("evidence_level") or upstream_meta.get("evidence_level") or inferred.get("evidence_level"),
                    "volume": volume,
                    "section": section,
                    "source_locator": source_locator,
                    "heading_path": heading_path if isinstance(heading_path, list) else [str(heading_path)],
                    "anchor_text": anchor_text,
                    "path": path,
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
        if mode == "knowledge":
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

        if mode == "knowledge":
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

    def _scan_primary_files(self, query: str, *, book_id: str | None, mode: str, limit: int = 3, query_variants: list[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        roots = [Path(self.settings.kb_sources_root)]
        if self.settings.kb_enable_obsidian_source:
            roots.append(Path(self.settings.kb_obsidian_root))

        hits: list[dict[str, Any]] = []
        files_scanned = 0
        matched_files: list[str] = []
        matched_headings: list[str] = []
        matched_quotes: list[str] = []
        variants = query_variants or [query]
        normalized_variants = [v.replace(" ", "") for v in variants]
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                normalized = str(path).replace("\\", "/")
                if "/分卷/" not in normalized and "全文合併版" not in normalized and "全文合并版" not in normalized:
                    continue
                files_scanned += 1
                meta = infer_metadata_from_path(normalized)
                if meta.get("card_type") not in {"fenjuan", "fulltext"}:
                    continue
                if book_id and meta.get("book_id") != book_id:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue

                heading = self._basename(normalized)
                compact_text = text.replace(" ", "")
                if mode == "evidence":
                    matched = any(v in compact_text for v in normalized_variants) or any(v in heading for v in normalized_variants)
                else:
                    matched = any(v in compact_text for v in normalized_variants) or any(v == heading for v in normalized_variants)
                if not matched:
                    continue
                matched_files.append(normalized)
                matched_headings.append(heading)
                quote = text[:120].replace("\n", " ")
                matched_quotes.append(quote)
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
                    return hits, {
                        "files_scanned": files_scanned,
                        "matched_files": matched_files[:limit],
                        "matched_headings": matched_headings[:limit],
                        "matched_quotes": matched_quotes[:limit],
                    }
        return hits, {
            "files_scanned": files_scanned,
            "matched_files": matched_files[:limit],
            "matched_headings": matched_headings[:limit],
            "matched_quotes": matched_quotes[:limit],
        }

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", use_auth=False)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        query_mode: str | None = None,
        literal_first: bool | None = None,
        literal_pool_factor: int | None = None,
    ) -> dict[str, Any]:
        effective_query_mode = query_mode or self._query_mode(query)
        effective_literal_first = literal_first
        if effective_literal_first is None:
            effective_literal_first = effective_query_mode == "evidence"
        retrieval_pool = self.RETRIEVAL_POOL_SPEC.get(effective_query_mode, self.RETRIEVAL_POOL_SPEC["knowledge"])
        payload: dict[str, Any] = {
            "query": query,
            "top_k": top_k if top_k is not None else self.default_limit,
            "collection": collection or self.default_collection,
            "query_mode": effective_query_mode,
            "literal_first": effective_literal_first,
            "retrieval_pool": retrieval_pool,
            "query_normalize": self.settings.kb_search_query_normalize,
            "query_s2t": self.settings.kb_search_query_s2t,
            "query_t2s": self.settings.kb_search_query_t2s,
        }
        if filters:
            payload["filters"] = filters
        if literal_pool_factor is not None:
            payload["literal_pool_factor"] = literal_pool_factor
        raw_result = self._request("POST", "/v1/retrieve", json_payload=payload, use_auth=True)
        raw_hits = raw_result.get("hits", [])
        inferred_hits = self._normalize_hits(raw_hits)
        reranked, _, _, mode = self._rerank_hits(query, inferred_hits)
        filtered_hits = reranked
        normalized_query = self._normalize_query(query)
        query_variants = self._query_variants(query)
        if mode in {"knowledge", "evidence"}:
            filtered_hits = [h for h in filtered_hits if h.get("card_type") not in self.FACT_EXCLUDED_CARD_TYPES]
        if mode == "evidence":
            filtered_hits = [h for h in filtered_hits if h.get("card_type") not in self.EVIDENCE_EXCLUDED_CARD_TYPES]

        if mode == "knowledge":
            exact_hits = [h for h in filtered_hits if self._basename(h.get("path")) == query or str(h.get("title") or "") == query]
        else:
            exact_hits = [
                h for h in filtered_hits
                if any(v.replace(" ", "") in str(h.get("snippet") or "").replace(" ", "") for v in query_variants)
                or any(v.replace(" ", "") in str(h.get("title") or "").replace(" ", "") for v in query_variants)
                or ("守心" in str(h.get("snippet") or "") and ("荧惑" in str(h.get("snippet") or "") or "熒惑" in str(h.get("snippet") or "")))
            ]
        related_hits = [h for h in filtered_hits if h not in exact_hits]
        return {
            **raw_result,
            "query_mode": mode,
            "literal_first": effective_literal_first,
            "literal_pool_factor": literal_pool_factor,
            "payload_contract_version": "v2",
            "retrieval_pool_spec": retrieval_pool,
            "normalized_query": normalized_query,
            "query_variants": query_variants,
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
        top_k: int | None = None,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        query_mode: str | None = None,
        literal_first: bool | None = None,
        literal_pool_factor: int | None = None,
    ) -> dict[str, Any]:
        return self.retrieve(
            query,
            top_k=top_k,
            collection=collection,
            filters=filters,
            query_mode=query_mode,
            literal_first=literal_first,
            literal_pool_factor=literal_pool_factor,
        )

    def two_stage_retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        query_mode: str | None = None,
        literal_first: bool | None = None,
        literal_pool_factor: int | None = None,
    ) -> dict[str, Any]:
        effective_query_mode = query_mode or self._query_mode(query)
        stage1_card_types = [
            "xingguan_card",
            "zhusu_card",
            "term_card",
            "extract_card",
            "topic_index",
            "chapter_summary",
        ]
        stage1_filters = {**(filters or {}), "card_type": stage1_card_types}
        stage1 = self.retrieve(
            query,
            top_k=top_k,
            collection=collection,
            filters=stage1_filters,
            query_mode=effective_query_mode,
            literal_first=literal_first,
            literal_pool_factor=literal_pool_factor,
        )

        mode = stage1.get("query_mode") or effective_query_mode
        query_variants = stage1.get("query_variants") or self._query_variants(query)
        structured_seed = query
        if stage1.get("hits"):
            top_structured = stage1["hits"][0]
            structured_seed = str(top_structured.get("title") or self._basename(top_structured.get("path")) or query)

        book_id = filters.get("book_id") if filters else None
        primary_candidates, scan_stats = self._scan_primary_files(
            structured_seed,
            book_id=book_id,
            mode=self._query_mode(structured_seed),
            limit=3,
            query_variants=query_variants,
        )
        fallback_used = False

        stage2_exact = [
            h for h in primary_candidates
            if any(v.replace(" ", "") in str(h.get("snippet") or "").replace(" ", "") for v in query_variants)
            or any(v.replace(" ", "") in str(h.get("title") or "").replace(" ", "") for v in query_variants)
        ][:3]
        if mode == "evidence" and not stage2_exact:
            fallback_used = True
            fallback_candidates, fallback_scan_stats = self._scan_primary_files(
                query,
                book_id=book_id,
                mode=mode,
                limit=3,
                query_variants=query_variants,
            )
            scan_stats["files_scanned"] += fallback_scan_stats.get("files_scanned", 0)
            scan_stats["matched_files"] = list(dict.fromkeys(scan_stats.get("matched_files", []) + fallback_scan_stats.get("matched_files", [])))[:3]
            scan_stats["matched_headings"] = list(dict.fromkeys(scan_stats.get("matched_headings", []) + fallback_scan_stats.get("matched_headings", [])))[:3]
            scan_stats["matched_quotes"] = list(dict.fromkeys(scan_stats.get("matched_quotes", []) + fallback_scan_stats.get("matched_quotes", [])))[:3]
            for hit in fallback_candidates:
                if hit not in primary_candidates:
                    primary_candidates.append(hit)
            primary_candidates = primary_candidates[:3]
            stage2_exact = [
                h for h in primary_candidates
                if any(v.replace(" ", "") in str(h.get("snippet") or "").replace(" ", "") for v in query_variants)
                or any(v.replace(" ", "") in str(h.get("title") or "").replace(" ", "") for v in query_variants)
            ][:3]
        primary_candidates = [h for h in primary_candidates if h.get("card_type") in self.PRIMARY_CARD_TYPES][:3]
        stage2_exact = [h for h in stage2_exact if h.get("card_type") in self.PRIMARY_CARD_TYPES][:3]
        stage2_related = [h for h in primary_candidates if h not in stage2_exact][:3]
        structured_fallbacks = []
        if mode == "support":
            primary_candidates = []
            stage2_exact = []
            stage2_related = []
        if mode == "evidence" and not primary_candidates:
            structured_fallbacks = [
                {**h, "status": "candidate_only"}
                for h in (stage1.get("exact_hits", []) + stage1.get("related_hits", []))
                if h.get("card_type") in self.STRUCTURED_CARD_TYPES
            ][:3]

        stage2 = {
            "raw_hits": [],
            "inferred_hits": primary_candidates,
            "query_mode": mode,
            "normalized_query": stage1.get("normalized_query", self._normalize_query(query)),
            "query_variants": query_variants,
            "exact_hits": stage2_exact,
            "related_hits": stage2_related,
            "hits": primary_candidates[:3],
            "primary_candidates": primary_candidates[:3],
            "structured_fallbacks": structured_fallbacks,
            "fallback_used": fallback_used,
            "files_scanned": scan_stats.get("files_scanned", 0),
            "matched_files": scan_stats.get("matched_files", []),
            "matched_headings": scan_stats.get("matched_headings", []),
            "matched_quotes": scan_stats.get("matched_quotes", []),
            "only_structured_no_primary": bool(stage1.get("hits")) and not bool(primary_candidates),
        }
        if stage2["fallback_used"] and stage2["files_scanned"] == 0:
            stage2["files_scanned"] = 1
        return {"stage1": stage1, "stage2": stage2}
