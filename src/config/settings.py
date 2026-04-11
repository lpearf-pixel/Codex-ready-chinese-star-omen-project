from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


class SettingsError(RuntimeError):
    """Raised when required settings are missing or invalid."""


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SettingsError(f"Environment variable {name} must be an integer, got: {raw}") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise SettingsError(f"Environment variable {name} must be a number, got: {raw}") from exc


@dataclass(frozen=True)
class Settings:
    kb_search_base_url: str
    kb_search_api_port: int
    kb_search_api_key: str | None
    kb_search_default_collection: str
    kb_search_timeout_seconds: float

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

    @property
    def kb_search_effective_base_url(self) -> str:
        if self.kb_search_base_url:
            return self.kb_search_base_url.rstrip("/")
        return f"http://127.0.0.1:{self.kb_search_api_port}"


def load_settings() -> Settings:
    kb_search_base_url = os.getenv("KB_SEARCH_BASE_URL", "").strip()
    kb_search_api_port = _get_int("KB_SEARCH_API_PORT", 8008)

    return Settings(
        kb_search_base_url=kb_search_base_url,
        kb_search_api_port=kb_search_api_port,
        kb_search_api_key=os.getenv("KB_SEARCH_API_KEY"),
        kb_search_default_collection=os.getenv("KB_SEARCH_DEFAULT_COLLECTION", "local_kb_default"),
        kb_search_timeout_seconds=_get_float("KB_SEARCH_TIMEOUT_SECONDS", 20.0),
        kb_sources_root=os.getenv("KB_SOURCES_ROOT", "./data/sources"),
        kb_enable_obsidian_source=_get_bool("KB_ENABLE_OBSIDIAN_SOURCE", True),
        kb_obsidian_root=os.getenv("KB_OBSIDIAN_ROOT", "./data/obsidian"),
        kb_obsidian_ingest_source_label=os.getenv("KB_OBSIDIAN_INGEST_SOURCE_LABEL", "obsidian"),
        kb_obsidian_source_root_label=os.getenv("KB_OBSIDIAN_SOURCE_ROOT_LABEL", "kaiyuan_zhanjing"),
        app_env=os.getenv("APP_ENV", "development"),
        app_debug=_get_bool("APP_DEBUG", False),
        app_log_level=os.getenv("APP_LOG_LEVEL", "INFO"),
        app_timezone=os.getenv("APP_TIMEZONE", "Asia/Shanghai"),
        app_default_limit=_get_int("APP_DEFAULT_LIMIT", 8),
        astro_default_epoch=os.getenv("ASTRO_DEFAULT_EPOCH", "J2000"),
        astro_default_lon=_get_float("ASTRO_DEFAULT_LON", 116.4),
        astro_default_lat=_get_float("ASTRO_DEFAULT_LAT", 39.9),
        astro_default_location_name=os.getenv("ASTRO_DEFAULT_LOCATION_NAME", "Beijing"),
        astro_visibility_min_alt_deg=_get_float("ASTRO_VISIBILITY_MIN_ALT_DEG", 5.0),
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
