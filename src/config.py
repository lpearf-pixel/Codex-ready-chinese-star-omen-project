from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback for restricted env
    yaml = None


@dataclass
class KBSearchConfig:
    base_url: str = "http://localhost:8008"
    timeout_seconds: float = 10.0


DEFAULT_CONFIG_PATH = Path("config/app_config.yaml")


def load_app_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw_text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(raw_text) or {}

    # Minimal fallback parser for simple key/value YAML used in this project.
    data: dict[str, Any] = {}
    current_section: dict[str, Any] | None = None
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            key = stripped.rstrip(":")
            data[key] = {}
            current_section = data[key]
            continue
        if current_section is not None and ":" in stripped:
            k, v = stripped.split(":", 1)
            current_section[k.strip()] = v.strip().strip("\"'")
    return data


def load_kb_search_config(path: Path = DEFAULT_CONFIG_PATH) -> KBSearchConfig:
    raw = load_app_config(path)
    section = raw.get("kb_search", {})
    return KBSearchConfig(
        base_url=section.get("base_url", "http://localhost:8008"),
        timeout_seconds=float(section.get("timeout_seconds", 10.0)),
    )
