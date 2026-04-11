from pathlib import Path

from src.config import load_kb_search_config


def test_load_kb_search_config_from_file(tmp_path: Path):
    cfg_file = tmp_path / "app_config.yaml"
    cfg_file.write_text(
        "kb_search:\n  base_url: 'http://localhost:9001'\n  timeout_seconds: 3\n",
        encoding="utf-8",
    )

    cfg = load_kb_search_config(cfg_file)
    assert cfg.base_url == "http://localhost:9001"
    assert cfg.timeout_seconds == 3.0


def test_load_kb_search_config_defaults_when_missing(tmp_path: Path):
    cfg = load_kb_search_config(tmp_path / "missing.yaml")
    assert cfg.base_url == "http://localhost:8008"
    assert cfg.timeout_seconds == 10.0
