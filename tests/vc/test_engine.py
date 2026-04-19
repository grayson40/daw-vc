import pytest
import json
from pathlib import Path
from src.vc.engine import DawVC


def test_init_creates_daw_directory(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    assert (tmp_path / ".daw").is_dir()
    assert (tmp_path / ".daw" / "state.json").exists()
    assert (tmp_path / ".daw" / "commits.json").exists()
    assert (tmp_path / ".daw" / "staged.json").exists()
    assert (tmp_path / ".daw" / "branches.json").exists()
    assert (tmp_path / ".daw" / "objects").is_dir()


def test_init_state_has_main_branch(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    state = json.loads((tmp_path / ".daw" / "state.json").read_text())
    assert state["branch"] == "main"
    assert state["head"] is None
    assert state["last_pushed_hash"] is None


def test_init_branches_has_main(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    branches = json.loads((tmp_path / ".daw" / "branches.json").read_text())
    assert "main" in branches
    assert branches["main"] is None


def test_create_branch(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    vc.create_branch("feature-x")
    branches = json.loads((tmp_path / ".daw" / "branches.json").read_text())
    assert "feature-x" in branches
    assert branches["feature-x"] is None


def test_create_duplicate_branch_raises(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    vc.create_branch("feature-x")
    with pytest.raises(ValueError, match="already exists"):
        vc.create_branch("feature-x")


def _make_fake_flp(tmp_path, name="test.flp") -> Path:
    p = tmp_path / name
    p.write_bytes(b"FLP_FAKE")
    return p


def test_checkout_branch_switches_branch(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    flp = _make_fake_flp(tmp_path)
    vc.add(flp)
    vc.commit("initial")
    vc.create_branch("feature-x")
    vc.checkout("feature-x")
    assert vc.current_branch() == "feature-x"


def test_checkout_unknown_branch_raises(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    with pytest.raises(ValueError, match="not found"):
        vc.checkout("nonexistent")


def test_checkout_restores_flp(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    flp = _make_fake_flp(tmp_path)
    vc.add(flp)
    vc.commit("initial")
    vc.create_branch("feature-x")
    vc.checkout("feature-x")
    restored = tmp_path / "test.flp"
    assert restored.exists()


def test_merge_fast_forward(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    flp = _make_fake_flp(tmp_path)
    vc.add(flp)
    vc.commit("base")
    vc.create_branch("feature")
    vc.checkout("feature")
    vc.add(flp)
    feature_hash = vc.commit("feature work")
    vc.checkout("main")
    result = vc.merge("feature")
    assert result["status"] == "fast-forward"
    assert vc.head_hash() == feature_hash


def test_merge_already_up_to_date(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    flp = _make_fake_flp(tmp_path)
    vc.add(flp)
    vc.commit("base")
    vc.create_branch("feature")
    result = vc.merge("feature")
    assert result["status"] == "up-to-date"


from src.vc.blob import hash_file


def test_commit_stores_blob_by_sha(tmp_path: Path):
    (tmp_path / "song.flp").write_bytes(b"fake flp bytes")
    vc = DawVC(tmp_path)
    vc.init()
    vc.add(tmp_path / "song.flp")
    commit_hash = vc.commit("init")

    blob_sha = hash_file(tmp_path / "song.flp")
    assert (vc.objects_dir / blob_sha).exists()
    assert (vc.objects_dir / blob_sha).read_bytes() == b"fake flp bytes"

    commits = vc.get_commits()
    assert commits[-1]["hash"] == commit_hash
    assert commits[-1]["blob_sha"] == blob_sha


def test_commit_deduplicates_identical_bytes(tmp_path: Path):
    (tmp_path / "a.flp").write_bytes(b"same bytes")
    vc = DawVC(tmp_path)
    vc.init()
    vc.add(tmp_path / "a.flp")
    vc.commit("one")

    (tmp_path / "a.flp").write_bytes(b"same bytes")  # unchanged
    vc.add(tmp_path / "a.flp")
    vc.commit("two")

    blobs = [p for p in vc.objects_dir.iterdir() if not p.name.endswith(".diff.json")]
    assert len(blobs) == 1  # dedup


def test_checkout_restores_from_blob_sha(tmp_path: Path):
    (tmp_path / "song.flp").write_bytes(b"v1 bytes")
    vc = DawVC(tmp_path)
    vc.init()
    vc.add(tmp_path / "song.flp")
    c1 = vc.commit("v1")

    (tmp_path / "song.flp").write_bytes(b"v2 bytes")
    vc.add(tmp_path / "song.flp")
    vc.commit("v2")

    vc.checkout(c1)
    assert (tmp_path / "song.flp").read_bytes() == b"v1 bytes"
