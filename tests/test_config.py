import json
import os
import stat

import pytest
import config as cfg


def test_load_creates_default_when_missing(tmp_config):
    result = cfg.load()
    assert set(result.keys()) == set(cfg.DEFAULT_CONFIG.keys())
    assert result["session_active"] is False
    assert result["deck"] == ""


def test_load_reads_existing_config(tmp_config):
    cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = cfg._deep_copy(cfg.DEFAULT_CONFIG)
    data["deck"] = "TestDeck"
    with open(cfg.CONFIG_FILE, "w") as f:
        json.dump(data, f)
    result = cfg.load()
    assert result["deck"] == "TestDeck"


def test_load_forward_fills_missing_keys(tmp_config):
    cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    partial = {
        "session_active": False,
        "deck": "",
        "model": cfg.DEFAULT_CONFIG["model"],
        "api_keys": cfg.DEFAULT_CONFIG["api_keys"],
        "deck_prompts": {},
        # "custom_prompt" intentionally omitted
    }
    with open(cfg.CONFIG_FILE, "w") as f:
        json.dump(partial, f)
    result = cfg.load()
    assert "custom_prompt" in result


def test_load_forward_fills_nested_api_keys(tmp_config):
    cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    partial = cfg._deep_copy(cfg.DEFAULT_CONFIG)
    del partial["api_keys"]["groq"]
    with open(cfg.CONFIG_FILE, "w") as f:
        json.dump(partial, f)
    result = cfg.load()
    assert "groq" in result["api_keys"]


def test_save_writes_json(tmp_config):
    config = cfg._deep_copy(cfg.DEFAULT_CONFIG)
    config["deck"] = "SavedDeck"
    cfg.save(config)
    with open(cfg.CONFIG_FILE) as f:
        saved = json.load(f)
    assert saved["deck"] == "SavedDeck"


def test_save_sets_permissions(tmp_config):
    config = cfg._deep_copy(cfg.DEFAULT_CONFIG)
    cfg.save(config)
    mode = stat.S_IMODE(os.stat(cfg.CONFIG_FILE).st_mode)
    assert mode == 0o600


def test_deep_copy_independent():
    copy1 = cfg._deep_copy(cfg.DEFAULT_CONFIG)
    copy2 = cfg._deep_copy(cfg.DEFAULT_CONFIG)
    copy1["api_keys"]["anthropic"] = "changed"
    assert copy2["api_keys"]["anthropic"] == ""
    assert cfg.DEFAULT_CONFIG["api_keys"]["anthropic"] == ""
