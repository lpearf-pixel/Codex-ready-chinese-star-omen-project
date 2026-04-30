from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("data/calibration/profile_registry.json")
GOVERNANCE_LOG_PATH = Path("data/calibration/profile_governance_log.jsonl")
VALID_STATUSES = {"draft", "candidate", "baseline", "deprecated"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"profiles": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(registry: dict[str, Any], path: Path = REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def append_governance_log(row: dict[str, Any], path: Path = GOVERNANCE_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def propose_profile(*, profile_name: str, source_file: str, parent_profile: str | None, change_summary: str, registry_path: Path = REGISTRY_PATH, log_path: Path = GOVERNANCE_LOG_PATH) -> dict[str, Any]:
    reg = load_registry(registry_path)
    now = _now()
    row = {
        "profile_name": profile_name,
        "source_file": source_file,
        "status": "candidate",
        "parent_profile": parent_profile,
        "change_summary": change_summary,
        "created_at": now,
        "updated_at": now,
    }
    reg["profiles"] = [p for p in reg.get("profiles", []) if p.get("profile_name") != profile_name] + [row]
    save_registry(reg, registry_path)
    append_governance_log({"action": "propose", "profile_name": profile_name, "at": now}, log_path)
    return row


def promote_profile(*, profile_name: str, experiment_exists: bool, compare_exists: bool, registry_path: Path = REGISTRY_PATH, log_path: Path = GOVERNANCE_LOG_PATH) -> dict[str, Any]:
    if not experiment_exists or not compare_exists:
        raise ValueError("promotion requires experiment result and compare report")
    reg = load_registry(registry_path)
    now = _now()
    found = False
    for p in reg.get("profiles", []):
        if p.get("status") == "baseline":
            p["status"] = "deprecated"
            p["updated_at"] = now
        if p.get("profile_name") == profile_name:
            p["status"] = "baseline"
            p["updated_at"] = now
            found = True
    if not found:
        raise ValueError(f"profile not found: {profile_name}")
    save_registry(reg, registry_path)
    append_governance_log({"action": "promote", "profile_name": profile_name, "at": now}, log_path)
    return {"ok": True, "profile_name": profile_name, "status": "baseline"}


def rollback_profile(*, to_profile: str, registry_path: Path = REGISTRY_PATH, log_path: Path = GOVERNANCE_LOG_PATH) -> dict[str, Any]:
    reg = load_registry(registry_path)
    now = _now()
    found = False
    for p in reg.get("profiles", []):
        if p.get("status") == "baseline":
            p["status"] = "deprecated"
            p["updated_at"] = now
        if p.get("profile_name") == to_profile:
            p["status"] = "baseline"
            p["updated_at"] = now
            found = True
    if not found:
        raise ValueError(f"rollback target profile not found: {to_profile}")
    save_registry(reg, registry_path)
    append_governance_log({"action": "rollback", "profile_name": to_profile, "at": now}, log_path)
    return {"ok": True, "baseline": to_profile}
