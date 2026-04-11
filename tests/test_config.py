from src.config.settings import SettingsError, load_settings, require_api_key


def test_base_url_priority(monkeypatch):
    monkeypatch.setenv("KB_SEARCH_BASE_URL", "http://localhost:9999")
    monkeypatch.setenv("KB_SEARCH_API_PORT", "8008")
    s = load_settings()
    assert s.kb_search_effective_base_url == "http://localhost:9999"


def test_port_fallback_when_base_url_missing(monkeypatch):
    monkeypatch.delenv("KB_SEARCH_BASE_URL", raising=False)
    monkeypatch.setenv("KB_SEARCH_API_PORT", "8011")
    s = load_settings()
    assert s.kb_search_effective_base_url == "http://127.0.0.1:8011"


def test_require_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("KB_SEARCH_API_KEY", raising=False)
    s = load_settings()
    try:
        require_api_key(s)
        raise AssertionError("expected SettingsError")
    except SettingsError as exc:
        assert "KB_SEARCH_API_KEY" in str(exc)


def test_monkeypatch_env_injection(monkeypatch):
    monkeypatch.setenv("APP_DEFAULT_LIMIT", "13")
    monkeypatch.setenv("KB_SEARCH_TIMEOUT_SECONDS", "9")
    s = load_settings()
    assert s.app_default_limit == 13
    assert s.kb_search_timeout_seconds == 9.0
