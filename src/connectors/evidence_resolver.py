from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.settings import get_settings
from src.connectors.kb_contract import can_be_final_fact, is_citable_evidence, resolve_evidence_level


def resolve_evidence(evidence: dict[str, Any], kb_root: str | Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    card_type = evidence.get("card_type")
    inferred_level = resolve_evidence_level(card_type) if card_type else None

    locator = evidence.get("locator")
    anchor_heading = evidence.get("anchor_heading")
    volume = evidence.get("volume")
    section = evidence.get("section")
    heading_path = evidence.get("heading_path")
    if not isinstance(heading_path, list):
        heading_path = [anchor_heading] if anchor_heading else []
    if not volume and isinstance(locator, str) and "/" in locator:
        volume = locator.split("/", 1)[0]
    if not volume and isinstance(locator, str):
        volume = locator
    if not section and isinstance(locator, str):
        section = locator.split("/")[-1]
    source_locator = evidence.get("source_locator") or locator or (f"{volume}/{section}" if volume and section else None)
    anchor_text = evidence.get("anchor_text") or evidence.get("quote")

    resolved: dict[str, Any] = {
        "kb_book_id": evidence.get("kb_book_id"),
        "note_id": evidence.get("note_id"),
        "relative_path": evidence.get("relative_path"),
        "card_type": card_type,
        "locator": locator,
        "anchor_heading": anchor_heading,
        "quote": evidence.get("quote"),
        "volume": volume,
        "section": section,
        "source_locator": source_locator,
        "heading_path": heading_path,
        "anchor_text": anchor_text,
        "paragraph_index": evidence.get("paragraph_index"),
        "ingest_source": evidence.get("ingest_source", settings.kb_obsidian_ingest_source_label),
        "source_type": evidence.get("source_type", "docs"),
        "evidence_level": evidence.get("evidence_level") or inferred_level,
        "final_citable": can_be_final_fact(card_type) if card_type else False,
        "candidate_reason": None,
    }

    relative_path = evidence.get("relative_path")
    effective_kb_root = Path(kb_root) if kb_root else Path(settings.kb_sources_root)
    if relative_path:
        full_path = (effective_kb_root / relative_path).resolve()
        resolved["resolved_path"] = str(full_path)
        resolved["path_exists"] = full_path.exists()
    else:
        resolved["resolved_path"] = None
        resolved["path_exists"] = None

    citable = is_citable_evidence(resolved)
    if citable:
        resolved["status"] = "citable"
    else:
        resolved["status"] = "candidate_only"
        if not resolved.get("relative_path"):
            resolved["candidate_reason"] = "missing_relative_path"
        elif not resolved["final_citable"]:
            resolved["candidate_reason"] = "card_type_not_primary"
        else:
            resolved["candidate_reason"] = "insufficient_primary_fields"

    resolved["trace"] = {
        "resolver_version": "m0",
        "requires_primary_card_types": ["fenjuan", "fulltext"],
        "primary_projection_ready": citable,
        "source_root_label": settings.kb_obsidian_source_root_label,
    }
    return resolved
