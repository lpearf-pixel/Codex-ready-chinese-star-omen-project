from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

from src.config.settings import Settings, SettingsError, get_settings, mask_secret, require_api_key
from src.connectors.kb_contract import infer_metadata_from_path
from src.connectors.kb_contract_adapter import adapt_kb_payload

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
    INVALID_API_KEY_PLACEHOLDERS = {"change_me", "please_change_me", "replace_me", "your_api_key_here"}
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
            path = str(hit.get("path") or "")
            title = str(hit.get("title") or "")
            adapted = adapt_kb_payload(hit)
            adapted_dict = adapted.to_dict()
            heading_path = hit.get("heading_path") or upstream_meta.get("heading_path") or ([title] if title else [])
            volume = hit.get("volume") or upstream_meta.get("volume")
            if not volume and "卷" in title:
                volume = title
            section = hit.get("section") or upstream_meta.get("section") or (heading_path[-1] if heading_path else title or None)
            source_locator = adapted.source_locator or hit.get("source_locator") or upstream_meta.get("source_locator")
            if not source_locator:
                source_locator = f"{volume}/{section}" if volume and section else section or volume or None
            anchor_text = hit.get("anchor_text") or upstream_meta.get("anchor_text")
            if not anchor_text:
                anchor_text = str(hit.get("snippet") or "")[:120]
            kb_book_id = adapted.kb_book_id
            inferred_hits.append(
                {
                    **hit,
                    **{k: v for k, v in adapted_dict.items() if k != "source_locator"},
                    "book_title": adapted.book_title,
                    "kb_book_id": kb_book_id,
                    "book_id": kb_book_id,
                    "card_type": adapted.card_type,
                    "evidence_level": adapted.evidence_level,
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
            out = [h for h in out if (h.get("kb_book_id") or h.get("book_id")) == book_id]
        if card_types:
            allowed = set(card_types)
            out = [h for h in out if h.get("card_type") in allowed]
        if evidence_level:
            out = [h for h in out if h.get("evidence_level") == evidence_level]
        return out

    @staticmethod
    def _compact_with_index_map(text: str) -> tuple[str, list[int]]:
        compact_chars: list[str] = []
        index_map: list[int] = []
        for idx, ch in enumerate(text):
            if ch.isspace():
                continue
            compact_chars.append(ch)
            index_map.append(idx)
        return "".join(compact_chars), index_map

    @classmethod
    def _compact_text(cls, text: str) -> str:
        return "".join(ch for ch in text if not ch.isspace())

    @classmethod
    def _expanded_query_variants(cls, query_variants: list[str]) -> list[str]:
        expanded: list[str] = []
        for variant in query_variants:
            compact = cls._compact_text(str(variant))
            if not compact:
                continue
            simp = compact.translate(cls.SIMPLIFIED_MAP)
            trad = compact.translate(cls.TRADITIONAL_MAP)
            candidates = [compact, simp, trad]
            for candidate in (compact, simp, trad):
                if len(candidate) > 2:
                    candidates.append(f"{candidate[:2]} {candidate[2:]}")
            for candidate in candidates:
                if candidate and candidate not in expanded:
                    expanded.append(candidate)
        return expanded

    @classmethod
    def _loose_term_groups(cls, query_variants: list[str]) -> list[list[str]]:
        groups: list[list[str]] = []
        for variant in cls._expanded_query_variants(query_variants):
            compact = cls._compact_text(variant)
            if not compact:
                continue
            fire_terms = [term for term in ("荧惑", "熒惑") if term in compact]
            if fire_terms and "心" in compact:
                for fire_term in fire_terms:
                    candidates = [[fire_term, "心"]]
                    if "守" in compact:
                        candidates.append([fire_term, "守", "心"])
                    for group in candidates:
                        if group not in groups:
                            groups.append(group)
                continue
            if len(compact) >= 3:
                chars = list(dict.fromkeys(compact))
                if 1 < len(chars) <= 6 and chars not in groups:
                    groups.append(chars)
        return groups

    @classmethod
    def _excerpt_around_offset(cls, text: str, offset: int | None, window: int) -> str:
        if offset is None:
            return ""
        start = max(0, offset - window)
        end = min(len(text), offset + window)
        return text[start:end].strip()

    @classmethod
    def _find_query_context(
        cls,
        text: str,
        query_variants: list[str],
        *,
        window: int = 160,
        loose_window: int = 500,
        heading: str | None = None,
    ) -> dict[str, Any]:
        compact_text, index_map = cls._compact_with_index_map(text)
        variants = cls._expanded_query_variants(query_variants)
        compact_variants = [cls._compact_text(v) for v in variants if cls._compact_text(v)]

        matched_variants: list[str] = []
        best_compact_offset: int | None = None
        for variant in compact_variants:
            pos = compact_text.find(variant)
            if pos < 0:
                continue
            if variant not in matched_variants:
                matched_variants.append(variant)
            if best_compact_offset is None or pos < best_compact_offset:
                best_compact_offset = pos

        if best_compact_offset is not None:
            original_offset = index_map[best_compact_offset] if best_compact_offset < len(index_map) else None
            excerpt = cls._excerpt_around_offset(text, original_offset, window)
            return {
                "matched": True,
                "excerpt": excerpt,
                "matched_variants": matched_variants,
                "match_offset": original_offset,
                "match_type": "exact_phrase",
            }

        compact_heading = cls._compact_text(heading or "")
        heading_matches = [variant for variant in compact_variants if variant and variant in compact_heading]
        if heading_matches:
            return {
                "matched": True,
                "excerpt": text[: min(len(text), window * 2)].strip(),
                "matched_variants": heading_matches,
                "match_offset": None,
                "match_type": "heading",
            }

        for group in cls._loose_term_groups(query_variants):
            positions: list[tuple[int, str]] = []
            for term in group:
                compact_term = cls._compact_text(term)
                pos = compact_text.find(compact_term)
                if pos < 0:
                    positions = []
                    break
                positions.append((pos, compact_term))
            if not positions:
                continue
            min_pos = min(pos for pos, _ in positions)
            max_pos = max(pos + len(term) for pos, term in positions)
            if max_pos - min_pos > loose_window:
                continue
            original_offset = index_map[min_pos] if min_pos < len(index_map) else None
            excerpt = cls._excerpt_around_offset(text, original_offset, window)
            return {
                "matched": True,
                "excerpt": excerpt,
                "matched_variants": group,
                "match_offset": original_offset,
                "match_type": "loose_terms",
            }

        return {
            "matched": False,
            "excerpt": "",
            "matched_variants": [],
            "match_offset": None,
            "match_type": "none",
        }

    @staticmethod
    def _fallback_score(card_type: str | None, match_type: str | None) -> float:
        if match_type == "exact_phrase":
            return 1.0 if card_type == "fenjuan" else 0.85
        if match_type == "heading":
            return 0.65 if card_type == "fenjuan" else 0.50
        if match_type == "loose_terms":
            return 0.55 if card_type == "fenjuan" else 0.40
        return 0.0

    @staticmethod
    def _fallback_sort_key(hit: dict[str, Any]) -> tuple[int, int, float, int, str]:
        match_priority = {"exact_phrase": 0, "heading": 1, "loose_terms": 2}.get(str(hit.get("match_type") or ""), 9)
        card_priority = {"fenjuan": 0, "fulltext": 1}.get(str(hit.get("card_type") or ""), 9)
        score = float(hit.get("score") or 0)
        offset = hit.get("match_offset")
        offset_priority = int(offset) if isinstance(offset, int) else 10**12
        return (match_priority, card_priority, -score, offset_priority, str(hit.get("path") or ""))

    @classmethod
    def _dedupe_fallback_hits(cls, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(hits, key=cls._fallback_sort_key)
        deduped: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        seen_match_keys: set[tuple[str, str, str]] = set()
        for hit in ordered:
            path = str(hit.get("path") or "")
            if path in seen_paths:
                continue
            matched_variants = hit.get("matched_variants") or []
            variant_key = str(matched_variants[0]) if matched_variants else ""
            excerpt_key = cls._compact_text(str(hit.get("excerpt") or ""))[:120]
            match_key = (str(hit.get("kb_book_id") or hit.get("book_id") or ""), variant_key, excerpt_key)
            if hit.get("card_type") == "fulltext" and match_key in seen_match_keys:
                continue
            seen_paths.add(path)
            seen_match_keys.add(match_key)
            deduped.append(hit)
        return deduped

    @staticmethod
    def _parse_candidate_card(path: Path) -> tuple[dict[str, Any], str] | None:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return None
        if not text.startswith("---\n"):
            return None
        end = text.find("\n---", 4)
        if end < 0:
            return None
        raw_frontmatter = text[4:end]
        body = text[end + 4 :].lstrip("\n")
        meta: dict[str, Any] = {}
        for raw_line in raw_frontmatter.splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#") or ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value in {"", "null", "None"}:
                meta[key] = None
                continue
            try:
                meta[key] = json.loads(value)
            except json.JSONDecodeError:
                meta[key] = value.strip('"\'')
        return meta, body

    @staticmethod
    def _candidate_manifest_statuses(root: Path) -> dict[str, dict[str, Any]]:
        statuses: dict[str, dict[str, Any]] = {}
        for manifest_path in root.rglob("candidate_manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(manifest, dict):
                items = manifest.get("items") or manifest.get("candidates") or []
            elif isinstance(manifest, list):
                items = manifest
            else:
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_path = str(item.get("path") or "")
                item_id = str(item.get("id") or "")
                if item_path:
                    statuses[item_path] = item
                    statuses[str((manifest_path.parent / item_path).resolve())] = item
                if item_id:
                    statuses[item_id] = item
        return statuses

    def _scan_candidate_overlay(
        self,
        query: str,
        *,
        book_id: str | None,
        limit: int,
        query_variants: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        root = Path(self.settings.kb_candidate_overlay_root)
        if not root.exists():
            return []
        variants = self._expanded_query_variants(query_variants or [query])
        manifest_statuses = self._candidate_manifest_statuses(root)
        hits: list[dict[str, Any]] = []
        for path in root.rglob("*.md"):
            parsed = self._parse_candidate_card(path)
            if not parsed:
                continue
            meta, body = parsed
            manifest_item = (
                manifest_statuses.get(str(path))
                or manifest_statuses.get(str(path.resolve()))
                or manifest_statuses.get(str(meta.get("id") or ""))
                or {}
            )
            sync_status = str(manifest_item.get("sync_status") or meta.get("sync_status") or "pending")
            review_status = str(manifest_item.get("review_status") or meta.get("review_status") or "pending")
            if sync_status in {"merged", "stale"}:
                continue
            if meta.get("source_namespace") != "downstream_generated":
                continue
            if meta.get("card_type") != "extract_card":
                continue
            if book_id and meta.get("kb_book_id") != book_id:
                continue
            searchable = "\n".join(str(meta.get(key) or "") for key in ("term", "anchor_text", "source_locator"))
            aliases = meta.get("aliases") if isinstance(meta.get("aliases"), list) else []
            searchable = "\n".join([searchable, "\n".join(str(a) for a in aliases), body])
            context = self._find_query_context(searchable, variants, heading=str(meta.get("source_locator") or path.stem))
            if not context["matched"]:
                continue
            source_file = str(meta.get("source_file") or manifest_item.get("source_file") or "")
            title = str(meta.get("source_volume") or meta.get("source_locator") or path.stem)
            excerpt = str(meta.get("anchor_text") or context.get("excerpt") or "")
            match_type = str(meta.get("match_type") or context.get("match_type") or "exact_phrase")
            score = self._fallback_score("fenjuan", match_type) * (0.75 if review_status == "pending" else 1.0)
            hits.append(
                {
                    "chunk_id": f"candidate:{meta.get('id') or path.stem}",
                    "score": score,
                    "path": str(path).replace("\\", "/"),
                    "source_file": source_file,
                    "snippet": excerpt[:300],
                    "excerpt": excerpt,
                    "matched_variants": context.get("matched_variants") or meta.get("aliases") or [],
                    "match_offset": meta.get("match_offset"),
                    "match_type": match_type,
                    "source_type": "candidate_overlay",
                    "source_namespace": "downstream_generated",
                    "generated_status": meta.get("generated_status"),
                    "review_status": review_status,
                    "sync_status": sync_status,
                    "title": title,
                    "book_title": meta.get("book_title"),
                    "kb_book_id": meta.get("kb_book_id"),
                    "book_id": meta.get("kb_book_id"),
                    "card_type": "extract_card",
                    "evidence_level": meta.get("evidence_level") or "candidate",
                    "source_locator": meta.get("source_locator"),
                    "volume": meta.get("source_volume"),
                    "heading_path": meta.get("heading_path") if isinstance(meta.get("heading_path"), list) else [title],
                    "anchor_text": meta.get("anchor_text"),
                    "paragraph_index": meta.get("paragraph_index"),
                    "content_hash": meta.get("content_hash"),
                }
            )
        return sorted(hits, key=self._fallback_sort_key)[:limit]

    def _scan_primary_files(self, query: str, *, book_id: str | None, mode: str, limit: int = 3, query_variants: list[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        roots = [Path(self.settings.kb_sources_root)]
        if self.settings.kb_enable_obsidian_source:
            roots.append(Path(self.settings.kb_obsidian_root))

        debug_enabled = os.environ.get("KB_DEBUG_SCAN") == "1"
        debug_scan: dict[str, Any] = {
            "roots": [str(root) for root in roots],
            "root_exists": {str(root): root.exists() for root in roots},
            "md_files_seen": 0,
            "path_candidates": 0,
            "files_scanned": 0,
            "skipped_by_path_rule": 0,
            "skipped_by_card_type": [],
            "skipped_by_book_id": [],
            "read_errors": [],
            "text_checked": 0,
            "matched_files": [],
            "unmatched_files_sample": [],
        }

        hits: list[dict[str, Any]] = []
        files_scanned = 0
        variants = self._expanded_query_variants(query_variants or [query])
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                debug_scan["md_files_seen"] += 1
                normalized = str(path).replace("\\", "/")
                if "/分卷/" not in normalized and "全文合併版" not in normalized and "全文合并版" not in normalized:
                    debug_scan["skipped_by_path_rule"] += 1
                    continue
                debug_scan["path_candidates"] += 1
                meta = infer_metadata_from_path(normalized)
                card_type = meta.get("card_type")
                if card_type not in self.PRIMARY_CARD_TYPES:
                    if debug_enabled:
                        debug_scan["skipped_by_card_type"].append({"path": normalized, "card_type": card_type})
                    continue
                if book_id and (meta.get("kb_book_id") or meta.get("book_id")) != book_id:
                    if debug_enabled:
                        debug_scan["skipped_by_book_id"].append({"path": normalized, "kb_book_id": meta.get("kb_book_id") or meta.get("book_id")})
                    continue
                files_scanned += 1
                debug_scan["files_scanned"] = files_scanned
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception as exc:
                    if debug_enabled:
                        debug_scan["read_errors"].append({"path": normalized, "error": str(exc)})
                    continue

                debug_scan["text_checked"] += 1
                heading = self._basename(normalized)
                context = self._find_query_context(text, variants, heading=heading)
                if not context["matched"]:
                    if debug_enabled and len(debug_scan["unmatched_files_sample"]) < 10:
                        debug_scan["unmatched_files_sample"].append(normalized)
                    continue

                match_type = context["match_type"]
                excerpt = context["excerpt"]
                score = self._fallback_score(card_type, match_type)
                matched_file_debug = {
                    "path": normalized,
                    "heading": heading,
                    "matched_variants": context["matched_variants"],
                    "match_type": match_type,
                    "match_offset": context["match_offset"],
                    "excerpt": excerpt,
                }
                if debug_enabled:
                    debug_scan["matched_files"].append(matched_file_debug)
                hits.append(
                    {
                        "chunk_id": f"fallback:{path.name}:{context['match_offset']}",
                        "score": score,
                        "path": normalized,
                        "snippet": excerpt[:300],
                        "excerpt": excerpt,
                        "matched_variants": context["matched_variants"],
                        "match_offset": context["match_offset"],
                        "match_type": match_type,
                        "source_type": "docs",
                        "title": heading,
                        "book_title": meta.get("book_title"),
                        "kb_book_id": meta.get("kb_book_id") or meta.get("book_id"),
                        "book_id": meta.get("kb_book_id") or meta.get("book_id"),
                        "card_type": card_type,
                        "evidence_level": meta.get("evidence_level"),
                    }
                )

        sorted_hits = sorted(hits, key=self._fallback_sort_key)
        final_hits = self._dedupe_fallback_hits(sorted_hits)[:limit]
        meta_out = {
            "files_scanned": files_scanned,
            "matched_files": [str(h.get("path") or "") for h in final_hits],
            "matched_headings": [str(h.get("title") or "") for h in final_hits],
            "matched_quotes": [str(h.get("excerpt") or h.get("snippet") or "") for h in final_hits],
        }
        if debug_enabled:
            debug_scan["final_sorted_headings"] = [str(h.get("title") or "") for h in final_hits]
            debug_scan["final_sorted_files"] = [str(h.get("path") or "") for h in final_hits]
            debug_scan["final_sorted_match_types"] = [str(h.get("match_type") or "") for h in final_hits]
            debug_scan["final_sorted_scores"] = [float(h.get("score") or 0) for h in final_hits]
            meta_out["debug_scan"] = debug_scan
        return final_hits, meta_out

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", use_auth=False)

    def upstream_meta(self) -> dict[str, Any]:
        try:
            return self._request("GET", "/v1/meta", use_auth=False)
        except KBSearchError:
            return self.health()

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
        limit: int | None = None,
    ) -> dict[str, Any]:
        effective_top_k = top_k if top_k is not None else limit
        effective_query_mode = query_mode or self._query_mode(query)
        effective_literal_first = literal_first
        if effective_literal_first is None:
            effective_literal_first = effective_query_mode == "evidence"
        retrieval_pool = self.RETRIEVAL_POOL_SPEC.get(effective_query_mode, self.RETRIEVAL_POOL_SPEC["knowledge"])
        payload: dict[str, Any] = {
            "query": query,
            "top_k": effective_top_k if effective_top_k is not None else self.default_limit,
            "limit": effective_top_k if effective_top_k is not None else self.default_limit,
            "collection": collection or self.default_collection,
            "query_mode": effective_query_mode,
            "literal_first": effective_literal_first,
            "retrieval_pool": retrieval_pool,
            "query_normalize": self.settings.kb_search_query_normalize,
            "query_s2t": self.settings.kb_search_query_s2t,
            "query_t2s": self.settings.kb_search_query_t2s,
        }
        if filters:
            if "book_id" in filters and "kb_book_id" not in filters:
                filters = {**filters, "kb_book_id": filters.get("book_id")}
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
            payload["kb_book_id"] = book_id
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
        limit: int | None = None,
    ) -> dict[str, Any]:
        effective_top_k = top_k if top_k is not None else limit
        return self.retrieve(
            query,
            top_k=effective_top_k,
            limit=effective_top_k,
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
        limit: int | None = None,
    ) -> dict[str, Any]:
        effective_top_k = top_k if top_k is not None else limit
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
            top_k=effective_top_k,
            limit=effective_top_k,
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

        book_id = (filters.get("kb_book_id") or filters.get("book_id")) if filters else None
        scan_limit = effective_top_k if effective_top_k is not None else 3
        overlay_candidates = (
            self._scan_candidate_overlay(query, book_id=book_id, limit=scan_limit, query_variants=query_variants)
            if self.settings.kb_enable_candidate_overlay
            else []
        )
        primary_candidates, scan_stats = self._scan_primary_files(
            structured_seed,
            book_id=book_id,
            mode=self._query_mode(structured_seed),
            limit=scan_limit,
            query_variants=query_variants,
        )
        for hit in overlay_candidates:
            if hit not in primary_candidates:
                primary_candidates.append(hit)
        primary_candidates = self._dedupe_fallback_hits(primary_candidates)[:scan_limit]
        fallback_used = False

        def _eligible_exact(hit: dict[str, Any]) -> bool:
            return hit.get("match_type") == "exact_phrase" and not (
                hit.get("source_namespace") == "downstream_generated" and hit.get("review_status") == "pending"
            )

        stage2_exact = [h for h in primary_candidates if _eligible_exact(h)][:scan_limit]
        if mode == "evidence" and not stage2_exact:
            fallback_used = True
            fallback_candidates, fallback_scan_stats = self._scan_primary_files(
                query,
                book_id=book_id,
                mode=mode,
                limit=scan_limit,
                query_variants=query_variants,
            )
            scan_stats["files_scanned"] += fallback_scan_stats.get("files_scanned", 0)
            scan_stats["matched_files"] = list(dict.fromkeys(scan_stats.get("matched_files", []) + fallback_scan_stats.get("matched_files", [])))[:scan_limit]
            scan_stats["matched_headings"] = list(dict.fromkeys(scan_stats.get("matched_headings", []) + fallback_scan_stats.get("matched_headings", [])))[:scan_limit]
            scan_stats["matched_quotes"] = list(dict.fromkeys(scan_stats.get("matched_quotes", []) + fallback_scan_stats.get("matched_quotes", [])))[:scan_limit]
            if "debug_scan" in fallback_scan_stats:
                scan_stats["debug_scan"] = fallback_scan_stats["debug_scan"]
            for hit in fallback_candidates:
                if hit not in primary_candidates:
                    primary_candidates.append(hit)
            primary_candidates = self._dedupe_fallback_hits(primary_candidates)[:scan_limit]
            for hit in overlay_candidates:
                if hit not in primary_candidates:
                    primary_candidates.append(hit)
            primary_candidates = self._dedupe_fallback_hits(primary_candidates)[:scan_limit]
            stage2_exact = [h for h in primary_candidates if _eligible_exact(h)][:scan_limit]
        primary_candidates = self._dedupe_fallback_hits([
            h for h in primary_candidates
            if h.get("card_type") in self.PRIMARY_CARD_TYPES or h.get("source_namespace") == "downstream_generated"
        ])[:scan_limit]
        stage2_exact = [
            h for h in stage2_exact
            if (h.get("card_type") in self.PRIMARY_CARD_TYPES or h.get("source_namespace") == "downstream_generated") and _eligible_exact(h)
        ][:scan_limit]
        stage2_related = [h for h in primary_candidates if h not in stage2_exact][:scan_limit]
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
            "hits": primary_candidates[:scan_limit],
            "primary_candidates": primary_candidates[:scan_limit],
            "structured_fallbacks": structured_fallbacks,
            "fallback_used": fallback_used,
            "files_scanned": scan_stats.get("files_scanned", 0),
            "matched_files": scan_stats.get("matched_files", []),
            "matched_headings": scan_stats.get("matched_headings", []),
            "matched_quotes": scan_stats.get("matched_quotes", []),
            "only_structured_no_primary": bool(stage1.get("hits")) and not bool(primary_candidates),
        }
        if "debug_scan" in scan_stats:
            stage2["debug_scan"] = scan_stats["debug_scan"]
        if stage2["fallback_used"] and stage2["files_scanned"] == 0:
            stage2["files_scanned"] = 1
        return {"stage1": stage1, "stage2": stage2}
