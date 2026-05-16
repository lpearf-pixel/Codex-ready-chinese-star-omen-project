from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.connectors.kb_contract import infer_metadata_from_path, is_final_citable

STANDARD_FIELDS = [
    "kb_book_id",
    "book_title",
    "card_type",
    "evidence_level",
    "final_citable",
    "query_mode_hint",
    "aliases",
    "variant_terms",
    "normalized_terms",
    "source_locator",
]

DEPRECATED_FIELDS = ["book_id"]
QUERY_MODE_HINTS = {"knowledge", "evidence", "support"}


@dataclass(frozen=True)
class AdaptedKBPayload:
    kb_book_id: str | None = None
    book_title: str | None = None
    card_type: str | None = None
    evidence_level: str | None = None
    final_citable: bool | None = None
    query_mode_hint: str | None = None
    aliases: list[str] = field(default_factory=list)
    variant_terms: list[str] = field(default_factory=list)
    normalized_terms: list[str] = field(default_factory=list)
    source_locator: str | None = None
    deprecated_fields_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _frontmatter(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("frontmatter", "metadata"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _first(payload: dict[str, Any], frontmatter: dict[str, Any], field_name: str, inferred: dict[str, Any]) -> Any:
    if payload.get(field_name) is not None:
        return payload.get(field_name)
    if frontmatter.get(field_name) is not None:
        return frontmatter.get(field_name)
    return inferred.get(field_name)


def _infer_query_mode(card_type: str | None, evidence_level: str | None) -> str | None:
    if card_type in {"fenjuan", "fulltext"} or evidence_level == "primary":
        return "evidence"
    if card_type in {"topic_index", "chapter_summary"}:
        return "support"
    if card_type:
        return "knowledge"
    return None


def adapt_kb_payload(payload: dict[str, Any]) -> AdaptedKBPayload:
    """Normalize a kb-search payload/frontmatter/path into the downstream v1 contract.

    Consumption priority is top-level payload, then payload.frontmatter/metadata, then path inference.
    `book_id` is accepted only as a deprecated fallback and is normalized to `kb_book_id`.
    """

    frontmatter = _frontmatter(payload)
    inferred = infer_metadata_from_path(payload.get("path") or frontmatter.get("path") or payload.get("source_file"))
    deprecated_used: list[str] = []

    kb_book_id = payload.get("kb_book_id")
    if kb_book_id is None:
        kb_book_id = frontmatter.get("kb_book_id")
    if kb_book_id is None:
        if payload.get("book_id") is not None:
            kb_book_id = payload.get("book_id")
            deprecated_used.append("book_id")
        elif frontmatter.get("book_id") is not None:
            kb_book_id = frontmatter.get("book_id")
            deprecated_used.append("book_id")
    if kb_book_id is None:
        kb_book_id = inferred.get("book_id")

    book_title = _first(payload, frontmatter, "book_title", inferred)
    card_type = _first(payload, frontmatter, "card_type", inferred)
    evidence_level = _first(payload, frontmatter, "evidence_level", inferred)
    final_citable = _first(payload, frontmatter, "final_citable", {})
    if final_citable is None and card_type:
        final_citable = is_final_citable(str(card_type))
    query_mode_hint = _first(payload, frontmatter, "query_mode_hint", {})
    if query_mode_hint not in QUERY_MODE_HINTS:
        query_mode_hint = _infer_query_mode(str(card_type) if card_type else None, str(evidence_level) if evidence_level else None)

    return AdaptedKBPayload(
        kb_book_id=str(kb_book_id) if kb_book_id is not None else None,
        book_title=str(book_title) if book_title is not None else None,
        card_type=str(card_type) if card_type is not None else None,
        evidence_level=str(evidence_level) if evidence_level is not None else None,
        final_citable=bool(final_citable) if final_citable is not None else None,
        query_mode_hint=str(query_mode_hint) if query_mode_hint is not None else None,
        aliases=_coerce_list(_first(payload, frontmatter, "aliases", {})),
        variant_terms=_coerce_list(_first(payload, frontmatter, "variant_terms", {})),
        normalized_terms=_coerce_list(_first(payload, frontmatter, "normalized_terms", {})),
        source_locator=str(_first(payload, frontmatter, "source_locator", {})) if _first(payload, frontmatter, "source_locator", {}) is not None else None,
        deprecated_fields_used=deprecated_used,
    )


def adapt_hit(hit: dict[str, Any]) -> dict[str, Any]:
    adapted = adapt_kb_payload(hit).to_dict()
    return {**hit, **{k: v for k, v in adapted.items() if k in STANDARD_FIELDS or k == "deprecated_fields_used"}}
