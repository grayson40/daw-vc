import hashlib
from pathlib import Path


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def blob_path(objects_dir: Path, blob_sha: str) -> Path:
    return objects_dir / blob_sha


def diff_cache_path(objects_dir: Path, blob_sha: str) -> Path:
    return objects_dir / f"{blob_sha}.diff.json"
