from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


DEFAULT_CONFIG_PATH = Path("config/config.yaml")
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class SettingsError(RuntimeError):
    """Raised when required settings are missing or invalid."""


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _minimal_yaml_parse(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    section_stack: list[tuple[int, dict[str, Any]]] = [(0, root)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        while len(section_stack) > 1 and indent < section_stack[-1][0]:
            section_stack.pop()

        current = section_stack[-1][1]
        if value == "":
            current[key] = {}
            section_stack.append((indent + 2, current[key]))
        else:
            current[key] = _parse_scalar(value.strip("\"'"))

    return root


@dataclass(frozen=True)
class Settings:
    kb_search_base_url: str
    kb_search_api_port: int
    kb_search_api_key: str | None
    kb_search_default_collection: str
    kb_search_timeout_seconds: float
    kb_search_query_normalize: bool
    kb_search_query_s2t: bool
    kb_search_query_t2s: bool

    kb_sources_root: str
    kb_enable_obsidian_source: bool
    kb_obsidian_root: str
    kb_obsidian_ingest_source_label: str
    kb_obsidian_source_root_label: str

    app_env: str
    app_debug: bool
    app_log_level: str
    app_timezone: str
    app_default_limit: int

    astro_default_epoch: str
    astro_default_lon: float
    astro_default_lat: float
    astro_default_location_name: str
    astro_visibility_min_alt_deg: float

    config_path: str
    raw_config: dict[str, Any]

    @property
    def kb_search_effective_base_url(self) -> str:
        if self.kb_search_base_url:
            return self.kb_search_base_url.rstrip("/")
        return f"http://127.0.0.1:{self.kb_search_api_port}"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"Setting {name} must be an integer, got: {value}") from exc


def _as_float(name: str, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SettingsError(f"Setting {name} must be a number, got: {value}") from exc


def _env_or(env_name: str, yaml_value: Any) -> Any:
    val = os.getenv(env_name)
    return val if val is not None else yaml_value


def interpolate_env(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.getenv(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        raise SettingsError(f"Missing environment variable for interpolation: {var_name}")

    return ENV_PATTERN.sub(_replace, text)


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or Path(os.getenv("APP_CONFIG_PATH", str(DEFAULT_CONFIG_PATH)))
    if not path.exists():
        raise SettingsError(f"Config file not found: {path}")
    raw_text = interpolate_env(path.read_text(encoding="utf-8"))
    if yaml is not None:
        parsed = yaml.safe_load(raw_text) or {}
    else:  # pragma: no cover - fallback for restricted environments
        parsed = _minimal_yaml_parse(raw_text)
    if not isinstance(parsed, dict):
        raise SettingsError("Config file root must be a mapping/object")
    return parsed


def load_settings(config_path: Path | None = None) -> Settings:
    cfg = load_config(config_path)

    app = cfg.get("app", {})
    kb_search = cfg.get("kb_search", {})
    kb_cfg = cfg.get("knowledge_base", {})
    astro = cfg.get("astro", {})

    base_url = _env_or("KB_SEARCH_BASE_URL", kb_search.get("base_url", ""))
    api_port = _as_int("KB_SEARCH_API_PORT", _env_or("KB_SEARCH_API_PORT", kb_search.get("api_port")))

    return Settings(
        kb_search_base_url=str(base_url or ""),
        kb_search_api_port=api_port,
        kb_search_api_key=_env_or("KB_SEARCH_API_KEY", kb_search.get("api_key")),
        kb_search_default_collection=str(_env_or("KB_SEARCH_DEFAULT_COLLECTION", kb_search.get("default_collection"))),
        kb_search_timeout_seconds=_as_float("KB_SEARCH_TIMEOUT_SECONDS", _env_or("KB_SEARCH_TIMEOUT_SECONDS", kb_search.get("timeout_seconds"))),
        kb_search_query_normalize=_as_bool(_env_or("KB_SEARCH_QUERY_NORMALIZE", kb_search.get("query_normalize", True))),
        kb_search_query_s2t=_as_bool(_env_or("KB_SEARCH_QUERY_S2T", kb_search.get("query_s2t", True))),
        kb_search_query_t2s=_as_bool(_env_or("KB_SEARCH_QUERY_T2S", kb_search.get("query_t2s", True))),
        kb_sources_root=str(_env_or("KB_SOURCES_ROOT", kb_cfg.get("sources_root"))),
        kb_enable_obsidian_source=_as_bool(_env_or("KB_ENABLE_OBSIDIAN_SOURCE", kb_cfg.get("enable_obsidian_source"))),
        kb_obsidian_root=str(_env_or("KB_OBSIDIAN_ROOT", kb_cfg.get("obsidian_root"))),
        kb_obsidian_ingest_source_label=str(_env_or("KB_OBSIDIAN_INGEST_SOURCE_LABEL", kb_cfg.get("obsidian_ingest_source_label"))),
        kb_obsidian_source_root_label=str(_env_or("KB_OBSIDIAN_SOURCE_ROOT_LABEL", kb_cfg.get("obsidian_source_root_label"))),
        app_env=str(_env_or("APP_ENV", app.get("env"))),
        app_debug=_as_bool(_env_or("APP_DEBUG", app.get("debug"))),
        app_log_level=str(_env_or("APP_LOG_LEVEL", app.get("log_level"))),
        app_timezone=str(_env_or("APP_TIMEZONE", app.get("timezone"))),
        app_default_limit=_as_int("APP_DEFAULT_LIMIT", _env_or("APP_DEFAULT_LIMIT", app.get("default_limit"))),
        astro_default_epoch=str(_env_or("ASTRO_DEFAULT_EPOCH", astro.get("default_epoch"))),
        astro_default_lon=_as_float("ASTRO_DEFAULT_LON", _env_or("ASTRO_DEFAULT_LON", astro.get("default_lon"))),
        astro_default_lat=_as_float("ASTRO_DEFAULT_LAT", _env_or("ASTRO_DEFAULT_LAT", astro.get("default_lat"))),
        astro_default_location_name=str(_env_or("ASTRO_DEFAULT_LOCATION_NAME", astro.get("default_location_name"))),
        astro_visibility_min_alt_deg=_as_float(
            "ASTRO_VISIBILITY_MIN_ALT_DEG",
            _env_or("ASTRO_VISIBILITY_MIN_ALT_DEG", astro.get("visibility_min_alt_deg")),
        ),
        config_path=str(config_path or Path(os.getenv("APP_CONFIG_PATH", str(DEFAULT_CONFIG_PATH)))),
        raw_config=cfg,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def require_api_key(settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    key = (cfg.kb_search_api_key or "").strip()
    if not key:
        raise SettingsError("Missing required environment variable: KB_SEARCH_API_KEY")
    return key


def mask_secret(secret: str | None) -> str:
    if not secret:
        return "<empty>"
    if len(secret) <= 4:
        return "****"
    return f"{secret[:2]}***{secret[-2:]}"
