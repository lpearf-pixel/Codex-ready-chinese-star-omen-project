from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_THRESHOLDS_PATH = Path("config/event_thresholds.yaml")


def _parse_scalar(raw: str) -> Any:
    v = raw.strip().strip('"')
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def _load_yaml_fallback(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {"event_thresholds": {}}
    current_section: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if raw.startswith("event_thresholds:"):
            continue
        if raw.startswith("  ") and not raw.startswith("    ") and raw.strip().endswith(":"):
            current_section = raw.strip().rstrip(":")
            root["event_thresholds"][current_section] = {}
            continue
        if raw.startswith("    ") and current_section and ":" in raw:
            k, v = raw.strip().split(":", 1)
            root["event_thresholds"][current_section][k] = _parse_scalar(v)
    return root


def load_event_thresholds(path: Path = DEFAULT_THRESHOLDS_PATH) -> dict[str, dict[str, Any]]:
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        parsed = _load_yaml_fallback(path)
    return parsed.get("event_thresholds", {})
