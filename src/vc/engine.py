import json
import shutil
import hashlib
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


def _generate_hash() -> str:
    timestamp = str(time.time()).encode()
    return hashlib.sha1(timestamp).hexdigest()[:8]


@dataclass
class Commit:
    hash: str
    message: str
    timestamp: str
    branch: str
    parent_hash: Optional[str]
    changes: list


class DawVC:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.daw_dir = root_dir / ".daw"
        self.state_file = self.daw_dir / "state.json"
        self.commits_file = self.daw_dir / "commits.json"
        self.staged_file = self.daw_dir / "staged.json"
        self.branches_file = self.daw_dir / "branches.json"
        self.objects_dir = self.daw_dir / "objects"

    def init(self) -> None:
        self.daw_dir.mkdir(exist_ok=True)
        self.objects_dir.mkdir(exist_ok=True)
        self.state_file.write_text(json.dumps({
            "branch": "main",
            "head": None,
            "last_pushed_hash": None,
        }))
        self.commits_file.write_text(json.dumps([]))
        self.staged_file.write_text(json.dumps([]))
        self.branches_file.write_text(json.dumps({"main": None}))

    def _read_state(self) -> dict:
        return json.loads(self.state_file.read_text())

    def _write_state(self, state: dict) -> None:
        self.state_file.write_text(json.dumps(state))

    def _read_commits(self) -> list:
        return json.loads(self.commits_file.read_text())

    def _write_commits(self, commits: list) -> None:
        self.commits_file.write_text(json.dumps(commits, default=str))

    def _read_branches(self) -> dict:
        return json.loads(self.branches_file.read_text())

    def _write_branches(self, branches: dict) -> None:
        self.branches_file.write_text(json.dumps(branches))

    def add(self, project_path: Path) -> None:
        staged = json.loads(self.staged_file.read_text())
        staged.append({"path": str(project_path)})
        self.staged_file.write_text(json.dumps(staged))

    def commit(self, message: str) -> str:
        from src.vc.blob import hash_file, blob_path

        staged = json.loads(self.staged_file.read_text())
        if not staged:
            raise ValueError("Nothing to commit")

        state = self._read_state()
        commits = self._read_commits()
        commit_hash = _generate_hash()

        blob_sha: Optional[str] = None
        for entry in staged:
            src_path = Path(entry["path"])
            if src_path.exists():
                blob_sha = hash_file(src_path)
                dest = blob_path(self.objects_dir, blob_sha)
                if not dest.exists():
                    shutil.copy2(src_path, dest)

        new_commit = Commit(
            hash=commit_hash,
            message=message,
            timestamp=datetime.now().isoformat(),
            branch=state["branch"],
            parent_hash=state["head"],
            changes=staged,
        )
        commit_dict = asdict(new_commit)
        commit_dict["blob_sha"] = blob_sha
        commits.append(commit_dict)
        self._write_commits(commits)

        state["head"] = commit_hash
        self._write_state(state)

        branches = self._read_branches()
        branches[state["branch"]] = commit_hash
        self._write_branches(branches)

        self.staged_file.write_text(json.dumps([]))
        return commit_hash

    def get_commits(self) -> list:
        return self._read_commits()

    def current_branch(self) -> str:
        return self._read_state()["branch"]

    def head_hash(self) -> Optional[str]:
        return self._read_state()["head"]

    def create_branch(self, name: str) -> None:
        branches = self._read_branches()
        if name in branches:
            raise ValueError(f"Branch '{name}' already exists")
        branches[name] = self.head_hash()
        self._write_branches(branches)

    def checkout(self, ref: str) -> None:
        """Switch to a branch or commit hash. Restores .flp from objects/."""
        branches = self._read_branches()
        commits = self._read_commits()

        if ref in branches:
            target_hash = branches[ref]
            new_branch = ref
        else:
            commit_hashes = {c["hash"] for c in commits}
            if ref in commit_hashes:
                target_hash = ref
                new_branch = self.current_branch()
            else:
                raise ValueError(f"Branch or commit '{ref}' not found")

        if target_hash:
            snapshot = self.objects_dir / f"{target_hash}.flp"
            if snapshot.exists():
                commit = next((c for c in commits if c["hash"] == target_hash), None)
                if commit and commit.get("changes"):
                    for entry in commit["changes"]:
                        dest = Path(entry["path"])
                        if dest.parent.exists():
                            shutil.copy2(snapshot, dest)

        state = self._read_state()
        state["branch"] = new_branch
        state["head"] = target_hash
        self._write_state(state)

    def merge(self, source_branch: str) -> dict:
        """Merge source_branch into current branch.

        Returns dict with keys:
          status: 'fast-forward' | 'up-to-date' | 'merged' | 'conflict'
          conflicts: list of conflict descriptions (if status == 'conflict')
        """
        branches = self._read_branches()
        if source_branch not in branches:
            raise ValueError(f"Branch '{source_branch}' not found")

        state = self._read_state()
        current_branch = state["branch"]
        our_hash = branches[current_branch]
        their_hash = branches[source_branch]

        if our_hash == their_hash:
            return {"status": "up-to-date", "conflicts": []}

        commits = self._read_commits()

        if our_hash is None or our_hash in self._ancestor_hashes(commits, their_hash):
            if their_hash:
                snapshot = self.objects_dir / f"{their_hash}.flp"
                commit = next((c for c in commits if c["hash"] == their_hash), None)
                if commit and commit.get("changes") and snapshot.exists():
                    for entry in commit["changes"]:
                        dest = Path(entry["path"])
                        if dest.parent.exists():
                            shutil.copy2(snapshot, dest)

            state["head"] = their_hash
            self._write_state(state)
            branches[current_branch] = their_hash
            self._write_branches(branches)
            return {"status": "fast-forward", "conflicts": []}

        return {
            "status": "conflict",
            "conflicts": [
                f"Branches '{current_branch}' and '{source_branch}' have diverged. "
                "Resolve manually and commit."
            ],
        }

    def _ancestor_hashes(self, commits: list, start_hash: Optional[str]) -> set:
        """Return all ancestor hashes of start_hash (inclusive)."""
        by_hash = {c["hash"]: c for c in commits}
        ancestors = set()
        current = start_hash
        while current and current in by_hash:
            ancestors.add(current)
            current = by_hash[current].get("parent_hash")
        return ancestors
