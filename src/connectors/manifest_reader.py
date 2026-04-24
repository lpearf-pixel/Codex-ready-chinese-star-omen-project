from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.settings import get_settings


class ManifestReader:
    def __init__(self, root: str | Path | None = None) -> None:
        cfg = get_settings()
        self.root = Path(root) if root else Path(cfg.kb_sources_root)

    def load_manifest(self, manifest_ref: str) -> dict[str, Any]:
        if not manifest_ref.startswith("manifest:"):
            raise ValueError("manifest_ref must start with 'manifest:'")
        manifest_name = manifest_ref.split(":", 1)[1]
        path = self.root / "manifests" / f"{manifest_name}.json"
        if not path.exists():
            return {"manifest_found": False, "manifest_name": manifest_name, "path": str(path)}
        return json.loads(path.read_text(encoding="utf-8"))

    def inspect(self) -> dict[str, list[str]]:
        manifests_dir = self.root / "manifests"
        if not manifests_dir.exists():
            return {"manifests": []}
        return {"manifests": sorted(p.name for p in manifests_dir.glob("*.json"))}

    def inspect_root(self) -> dict[str, Any]:
        exists = self.root.exists()
        manifests = self.inspect()["manifests"] if exists else []
        return {"root_exists": exists, "root": str(self.root), "manifests": manifests}
