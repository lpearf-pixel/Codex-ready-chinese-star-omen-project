from __future__ import annotations

from pathlib import Path
from typing import Any

from src.connectors.kb_contract import is_final_citable, resolve_evidence_level


def resolve_evidence(evidence: dict[str, Any], kb_root: str | Path | None = None) -> dict[str, Any]:
    card_type = evidence.get("card_type")
    inferred_level = resolve_evidence_level(card_type) if card_type else None

    resolved: dict[str, Any] = {
        "kb_book_id": evidence.get("kb_book_id"),
        "note_id": evidence.get("note_id"),
        "locator": evidence.get("locator"),
        "anchor_heading": evidence.get("anchor_heading"),
        "quote": evidence.get("quote"),
        "card_type": card_type,
        "evidence_level": evidence.get("evidence_level") or inferred_level,
        "final_citable": is_final_citable(card_type) if card_type else False,
    }

    relative_path = evidence.get("relative_path")
    if kb_root and relative_path:
        full_path = (Path(kb_root) / relative_path).resolve()
        resolved["resolved_path"] = str(full_path)
        resolved["path_exists"] = full_path.exists()
    else:
        resolved["resolved_path"] = relative_path
        resolved["path_exists"] = None

    if not resolved["final_citable"]:
        resolved["status"] = "candidate_only"
    else:
        resolved["status"] = "citable"

    return resolved
