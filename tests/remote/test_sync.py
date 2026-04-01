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


from src.remote.sync import push


def test_push_uploads_unpushed_commits(tmp_path):
    from src.vc.engine import DawVC

    vc = DawVC(tmp_path)
    vc.init()
    flp = tmp_path / "test.flp"
    flp.write_bytes(b"FLP_DATA")
    vc.add(flp)
    commit_hash = vc.commit("initial")

    mock_remote = MagicMock()
    mock_remote.ensure_project.return_value = "proj-uuid-123"

    push(vc, mock_remote, project_name="my-project", owner="user1")

    mock_remote.ensure_project.assert_called_once_with("my-project", "user1")
    mock_remote.upload_blob.assert_called_once()
    mock_remote.insert_commit.assert_called_once()

    import json
    state = json.loads((tmp_path / ".daw" / "state.json").read_text())
    assert state["last_pushed_hash"] == commit_hash


def test_push_skips_already_pushed(tmp_path):
    from src.vc.engine import DawVC

    vc = DawVC(tmp_path)
    vc.init()
    flp = tmp_path / "test.flp"
    flp.write_bytes(b"FLP_DATA")
    vc.add(flp)
    commit_hash = vc.commit("initial")

    import json
    state = json.loads((tmp_path / ".daw" / "state.json").read_text())
    state["last_pushed_hash"] = commit_hash
    (tmp_path / ".daw" / "state.json").write_text(json.dumps(state))

    mock_remote = MagicMock()
    mock_remote.ensure_project.return_value = "proj-uuid-123"

    push(vc, mock_remote, project_name="my-project", owner="user1")

    mock_remote.upload_blob.assert_not_called()
    mock_remote.insert_commit.assert_not_called()


from src.remote.sync import pull


def test_pull_downloads_new_commits(tmp_path):
    from src.vc.engine import DawVC

    vc = DawVC(tmp_path)
    vc.init()

    remote_commits = [
        {
            "hash": "aabb1122",
            "message": "remote work",
            "branch": "main",
            "timestamp": "2026-03-31T10:00:00",
            "parent_hash": None,
        }
    ]

    mock_remote = MagicMock()
    mock_remote.ensure_project.return_value = "proj-uuid-123"
    mock_remote.fetch_commits.return_value = remote_commits
    mock_remote.download_blob.return_value = None

    result = pull(vc, mock_remote, project_name="my-project", owner="user1")

    assert result["status"] in ("fast-forward", "up-to-date", "conflict")
    mock_remote.fetch_commits.assert_called_once()


def test_pull_up_to_date(tmp_path):
    from src.vc.engine import DawVC

    vc = DawVC(tmp_path)
    vc.init()
    flp = tmp_path / "test.flp"
    flp.write_bytes(b"FLP")
    vc.add(flp)
    commit_hash = vc.commit("local")

    import json
    state = json.loads((tmp_path / ".daw" / "state.json").read_text())
    state["last_pushed_hash"] = commit_hash
    (tmp_path / ".daw" / "state.json").write_text(json.dumps(state))

    mock_remote = MagicMock()
    mock_remote.ensure_project.return_value = "proj-uuid-123"
    mock_remote.fetch_commits.return_value = []

    result = pull(vc, mock_remote, project_name="my-project", owner="user1")
    assert result["status"] == "up-to-date"


from src.remote.sync import clone


def test_clone_initializes_and_pulls(tmp_path):
    remote_commits = [
        {
            "hash": "aabb1122",
            "message": "initial",
            "branch": "main",
            "timestamp": "2026-03-31T10:00:00",
            "parent_hash": None,
        }
    ]

    mock_remote = MagicMock()
    mock_remote.fetch_commits.return_value = remote_commits
    mock_remote.download_blob.return_value = None

    clone_dir = tmp_path / "cloned"
    clone_dir.mkdir()

    clone(clone_dir, mock_remote, project_id="proj-uuid-123", branch="main")

    assert (clone_dir / ".daw").is_dir()
    import json
    commits = json.loads((clone_dir / ".daw" / "commits.json").read_text())
    assert len(commits) == 1
    assert commits[0]["hash"] == "aabb1122"
