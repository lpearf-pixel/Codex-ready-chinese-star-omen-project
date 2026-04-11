from pathlib import Path

from src.config.settings import SettingsError, load_settings, require_api_key


def _write_config(path: Path) -> None:
    path.write_text(
        """
app:
  env: development
  debug: false
  log_level: INFO
  timezone: UTC
  default_limit: 8
kb_search:
  base_url: ""
  api_port: 8008
  api_key: ""
  default_collection: local_kb_default
  timeout_seconds: 20
knowledge_base:
  sources_root: ./data/sources
  enable_obsidian_source: true
  obsidian_root: ./data/obsidian
  obsidian_ingest_source_label: obsidian
  obsidian_source_root_label: kaiyuan_zhanjing
astro:
  default_epoch: J2000
  default_lon: 116.4
  default_lat: 39.9
  default_location_name: Beijing
  visibility_min_alt_deg: 5
contract: {}
evidence: {}
cli: {}
logging: {}
paths: {}
postgres: {}
git_internal: {}
""",
        encoding="utf-8",
    )


def test_base_url_priority(monkeypatch, tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg)
    monkeypatch.setenv("KB_SEARCH_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("KB_SEARCH_API_PORT", "8008")
    s = load_settings(cfg)
    assert s.kb_search_effective_base_url == "http://localhost:9999"


def test_port_fallback_when_base_url_missing(monkeypatch, tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg)
    monkeypatch.delenv("KB_SEARCH_BASE_URL", raising=False)
    monkeypatch.setenv("KB_SEARCH_API_PORT", "8011")
    s = load_settings(cfg)
    assert s.kb_search_effective_base_url == "http://127.0.0.1:8011"


def test_require_api_key_raises_when_missing(monkeypatch, tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg)
    monkeypatch.delenv("KB_SEARCH_API_KEY", raising=False)
    s = load_settings(cfg)
    try:
        require_api_key(s)
        raise AssertionError("expected SettingsError")
    except SettingsError as exc:
        assert "KB_SEARCH_API_KEY" in str(exc)


def test_env_overrides_yaml(monkeypatch, tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    _write_config(cfg)
    monkeypatch.setenv("APP_DEFAULT_LIMIT", "13")
    monkeypatch.setenv("KB_SEARCH_TIMEOUT_SECONDS", "9")
    s = load_settings(cfg)
    assert s.app_default_limit == 13
    assert s.kb_search_timeout_seconds == 9.0
