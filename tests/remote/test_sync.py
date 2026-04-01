import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.remote.config import load_config, save_config, CONFIG_PATH


def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("src.remote.config.CONFIG_PATH", config_path):
        save_config({"url": "https://abc.supabase.co", "key": "anon-key-123"})
        result = load_config()
    assert result["url"] == "https://abc.supabase.co"
    assert result["key"] == "anon-key-123"


def test_load_config_missing_returns_none(tmp_path):
    config_path = tmp_path / "config.json"
    with patch("src.remote.config.CONFIG_PATH", config_path):
        result = load_config()
    assert result is None
