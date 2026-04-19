from src.vc.engine import DawVC
from src.vc.blob import hash_file, blob_path


def migrate_objects(vc: DawVC) -> int:
    """Rename legacy <commit_hash>.flp objects to <blob_sha> and annotate commits.

    Returns the number of objects migrated. Safe to re-run (idempotent).
    """
    commits = vc.get_commits()
    migrated = 0

    for commit in commits:
        if commit.get("blob_sha"):
            continue
        legacy = vc.objects_dir / f"{commit['hash']}.flp"
        if not legacy.exists():
            continue
        blob_sha = hash_file(legacy)
        dest = blob_path(vc.objects_dir, blob_sha)
        if not dest.exists():
            legacy.rename(dest)
        else:
            legacy.unlink()
        commit["blob_sha"] = blob_sha
        migrated += 1

    if migrated:
        vc._write_commits(commits)
    return migrated
