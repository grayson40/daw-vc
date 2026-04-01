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
