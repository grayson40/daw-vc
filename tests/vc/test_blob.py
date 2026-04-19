import hashlib
from pathlib import Path
from src.vc.blob import hash_bytes, hash_file, blob_path, diff_cache_path


def test_hash_bytes_matches_sha256():
    assert hash_bytes(b"hello") == hashlib.sha256(b"hello").hexdigest()


def test_hash_file_reads_content(tmp_path: Path):
    f = tmp_path / "a.flp"
    f.write_bytes(b"flp content")
    assert hash_file(f) == hashlib.sha256(b"flp content").hexdigest()


def test_blob_path_is_objects_dir_plus_sha(tmp_path: Path):
    assert blob_path(tmp_path, "abc123") == tmp_path / "abc123"


def test_diff_cache_path_appends_diff_json(tmp_path: Path):
    assert diff_cache_path(tmp_path, "abc123") == tmp_path / "abc123.diff.json"
