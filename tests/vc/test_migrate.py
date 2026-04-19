import json
from pathlib import Path
from src.vc.engine import DawVC
from src.vc.blob import hash_file
from src.vc.migrate import migrate_objects


def test_migrate_renames_by_commit_hash_to_blob_sha(tmp_path: Path):
    vc = DawVC(tmp_path)
    vc.init()

    old_path = vc.objects_dir / "abc12345.flp"
    old_path.write_bytes(b"legacy bytes")
    commits = [{"hash": "abc12345", "message": "old", "timestamp": "t", "branch": "main",
                "parent_hash": None, "changes": []}]
    vc._write_commits(commits)

    migrated = migrate_objects(vc)

    expected_sha = hash_file(old_path) if old_path.exists() else None
    if not expected_sha:
        from src.vc.blob import hash_bytes
        expected_sha = hash_bytes(b"legacy bytes")

    assert migrated == 1
    assert not (vc.objects_dir / "abc12345.flp").exists()
    assert (vc.objects_dir / expected_sha).exists()

    new_commits = vc.get_commits()
    assert new_commits[0]["blob_sha"] == expected_sha


def test_migrate_idempotent(tmp_path: Path):
    vc = DawVC(tmp_path)
    vc.init()
    blob = vc.objects_dir / ("a" * 64)  # already a sha-shaped name
    blob.write_bytes(b"x")
    commits = [{"hash": "abc12345", "blob_sha": "a" * 64, "message": "x",
                "timestamp": "t", "branch": "main", "parent_hash": None, "changes": []}]
    vc._write_commits(commits)

    migrated = migrate_objects(vc)
    assert migrated == 0  # nothing to do
