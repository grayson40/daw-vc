import json
from pathlib import Path
from typing import Optional
from src.vc.engine import DawVC
from src.remote.supabase_client import SupabaseRemote


def _unpushed_commits(commits: list, last_pushed_hash: Optional[str]) -> list:
    """Return commits after last_pushed_hash in chronological order."""
    if last_pushed_hash is None:
        return commits
    for i, c in enumerate(commits):
        if c["hash"] == last_pushed_hash:
            return commits[i + 1:]
    return commits


def push(vc: DawVC, remote: SupabaseRemote, project_name: str, owner: str) -> int:
    """Push unpushed commits to Supabase. Returns number of commits pushed."""
    state = json.loads(vc.state_file.read_text())
    commits = vc.get_commits()
    last_pushed = state.get("last_pushed_hash")
    to_push = _unpushed_commits(commits, last_pushed)

    if not to_push:
        return 0

    project_id = remote.ensure_project(project_name, owner)

    for commit in to_push:
        blob_sha = commit.get("blob_sha")
        if blob_sha:
            snapshot = vc.objects_dir / blob_sha
        else:
            snapshot = vc.objects_dir / f"{commit['hash']}.flp"
        if snapshot.exists():
            remote.upload_blob(project_id, commit["hash"], snapshot)
        remote.insert_commit(project_id, commit)

    state["last_pushed_hash"] = to_push[-1]["hash"]
    vc.state_file.write_text(json.dumps(state))
    return len(to_push)


def pull(vc: DawVC, remote: SupabaseRemote, project_name: str, owner: str) -> dict:
    """Pull remote commits not in local history. Returns status dict."""
    state = json.loads(vc.state_file.read_text())
    current_branch = state["branch"]
    project_id = remote.ensure_project(project_name, owner)

    remote_commits = remote.fetch_commits(project_id, current_branch)
    local_hashes = {c["hash"] for c in vc.get_commits()}

    new_commits = [c for c in remote_commits if c["hash"] not in local_hashes]

    if not new_commits:
        return {"status": "up-to-date"}

    last_pushed = state.get("last_pushed_hash")
    local_commits = vc.get_commits()
    local_after_push = _unpushed_commits(local_commits, last_pushed)

    if local_after_push:
        return {
            "status": "conflict",
            "message": "Local and remote have diverged. Run 'daw merge' after pulling.",
        }

    all_commits = local_commits[:]
    for commit in new_commits:
        snapshot_dest = vc.objects_dir / f"{commit['hash']}.flp"
        try:
            remote.download_blob(project_id, commit["hash"], snapshot_dest)
        except Exception:
            pass
        all_commits.append(commit)

    vc._write_commits(all_commits)

    latest = new_commits[-1]
    state["head"] = latest["hash"]
    state["last_pushed_hash"] = latest["hash"]
    vc.state_file.write_text(json.dumps(state))

    branches = vc._read_branches()
    branches[current_branch] = latest["hash"]
    vc._write_branches(branches)

    return {"status": "fast-forward", "count": len(new_commits)}


def clone(dest_dir: Path, remote: SupabaseRemote, project_id: str, branch: str = "main") -> None:
    """Clone a remote project into dest_dir."""
    vc = DawVC(dest_dir)
    vc.init()

    remote_commits = remote.fetch_commits(project_id, branch)

    for commit in remote_commits:
        snapshot_dest = vc.objects_dir / f"{commit['hash']}.flp"
        try:
            remote.download_blob(project_id, commit["hash"], snapshot_dest)
        except Exception:
            pass

    if remote_commits:
        vc._write_commits(remote_commits)
        latest = remote_commits[-1]
        state = json.loads(vc.state_file.read_text())
        state["head"] = latest["hash"]
        state["last_pushed_hash"] = latest["hash"]
        vc.state_file.write_text(json.dumps(state))
        branches = vc._read_branches()
        branches[branch] = latest["hash"]
        vc._write_branches(branches)
