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


from src.remote.supabase_client import SupabaseRemote


def test_upload_blob_calls_storage(tmp_path):
    mock_client = MagicMock()
    mock_client.storage.from_.return_value.upload.return_value = {"Key": "objects/proj1/abc12345.flp"}

    remote = SupabaseRemote(client=mock_client)
    flp_path = tmp_path / "abc12345.flp"
    flp_path.write_bytes(b"FLP_DATA")

    remote.upload_blob("proj1", "abc12345", flp_path)

    mock_client.storage.from_.assert_called_with("objects")
    mock_client.storage.from_.return_value.upload.assert_called_once()


def test_insert_commit_calls_table(tmp_path):
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()

    remote = SupabaseRemote(client=mock_client)
    commit = {
        "hash": "abc12345",
        "message": "test",
        "branch": "main",
        "timestamp": "2026-03-31T00:00:00",
        "parent_hash": None,
        "diff": {},
    }
    remote.insert_commit("proj-uuid", commit)

    mock_client.table.assert_called_with("commits")


def test_fetch_commits_since(tmp_path):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"hash": "abc12345", "message": "test", "branch": "main", "timestamp": "2026-03-31T00:00:00", "parent_hash": None}
    ]

    remote = SupabaseRemote(client=mock_client)
    result = remote.fetch_commits("proj-uuid", "main")
    assert len(result) == 1
    assert result[0]["hash"] == "abc12345"
