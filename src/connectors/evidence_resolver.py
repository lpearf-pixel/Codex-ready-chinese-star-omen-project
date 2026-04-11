from __future__ import annotations

from pathlib import Path
from typing import Any

from src.connectors.kb_contract import can_be_final_fact, resolve_evidence_level


def resolve_evidence(evidence: dict[str, Any], kb_root: str | Path | None = None) -> dict[str, Any]:
    card_type = evidence.get("card_type")
    inferred_level = resolve_evidence_level(card_type) if card_type else None

    resolved: dict[str, Any] = {
        "kb_book_id": evidence.get("kb_book_id"),
        "note_id": evidence.get("note_id"),
        "relative_path": evidence.get("relative_path"),
        "card_type": card_type,
        "locator": evidence.get("locator"),
        "anchor_heading": evidence.get("anchor_heading"),
        "quote": evidence.get("quote"),
        "ingest_source": evidence.get("ingest_source", "obsidian"),
        "source_type": evidence.get("source_type", "docs"),
        "evidence_level": evidence.get("evidence_level") or inferred_level,
        "final_citable": can_be_final_fact(card_type) if card_type else False,
        "candidate_reason": None,
    }

    relative_path = evidence.get("relative_path")
    if kb_root and relative_path:
        full_path = (Path(kb_root) / relative_path).resolve()
        resolved["resolved_path"] = str(full_path)
        resolved["path_exists"] = full_path.exists()
    else:
        resolved["resolved_path"] = relative_path
        resolved["path_exists"] = None

    has_minimum_primary_fields = bool(resolved.get("relative_path") and resolved.get("locator") and resolved.get("quote"))
    if not resolved["final_citable"] or not has_minimum_primary_fields:
        resolved["status"] = "candidate_only"
        if not resolved["final_citable"]:
            resolved["candidate_reason"] = "card_type_not_primary"
        else:
            resolved["candidate_reason"] = "insufficient_primary_fields"
    else:
        resolved["status"] = "citable"

    resolved["trace"] = {
        "resolver_version": "m0",
        "requires_primary_card_types": ["fenjuan", "fulltext"],
        "primary_projection_ready": has_minimum_primary_fields,
    }
    return resolved
