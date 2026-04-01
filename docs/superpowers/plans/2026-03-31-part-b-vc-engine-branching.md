# Part B: VC Engine + Branching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the VC engine with full branching support: `branch`, `checkout`, `merge`, and a fixed `log` command with rich output. Depends on Part A being complete.

**Architecture:** All state lives in `.daw/` (JSON files + raw `.flp` objects). `DawVC` class manages reads/writes. Branches are pointers (name → commit hash) in `branches.json`. Merge uses a three-way strategy keyed by entity `name` field — conflicts are reported, not auto-resolved.

**Tech Stack:** Python 3.9+, click, rich, shutil (stdlib)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/cli/cli.py` | Modify | Add `branch`, `checkout`, `merge` commands; fix `init` to create `branches.json`, fix `log` with rich |
| `src/vc/engine.py` | Create | `DawVC` class extracted from cli.py — pure data operations, no click |
| `src/vc/__init__.py` | Create | Empty init |
| `tests/vc/test_engine.py` | Create | Unit tests for DawVC engine operations |
| `tests/vc/__init__.py` | Create | Empty init |

---

## Task 1: Extract DawVC into its own module

**Files:**
- Create: `src/vc/__init__.py`
- Create: `src/vc/engine.py`
- Modify: `src/cli/cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/vc/__init__.py  (empty)
# tests/vc/test_engine.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/vc/test_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create src/vc/engine.py**

```python
# src/vc/__init__.py  (empty file)

# src/vc/engine.py
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
        staged = json.loads(self.staged_file.read_text())
        if not staged:
            raise ValueError("Nothing to commit")

        state = self._read_state()
        commits = self._read_commits()
        commit_hash = _generate_hash()

        for entry in staged:
            src_path = Path(entry["path"])
            if src_path.exists():
                shutil.copy2(src_path, self.objects_dir / f"{commit_hash}.flp")

        new_commit = Commit(
            hash=commit_hash,
            message=message,
            timestamp=datetime.now().isoformat(),
            branch=state["branch"],
            parent_hash=state["head"],
            changes=staged,
        )
        commits.append(asdict(new_commit))
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/vc/test_engine.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Update cli.py to use DawVC from src.vc.engine**

In `src/cli/cli.py`, replace `class DawVC` and the `generate_hash` import/definition with:

```python
from src.vc.engine import DawVC
```

Remove the inline `DawVC` class and `generate_hash` function from cli.py. All CLI commands already call `DawVC(Path.cwd())` — this import makes them use the new module.

- [ ] **Step 6: Run full test suite to confirm nothing broke**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/vc/__init__.py src/vc/engine.py src/cli/cli.py tests/vc/__init__.py tests/vc/test_engine.py
git commit -m "refactor: extract DawVC into src/vc/engine.py"
```

---

## Task 2: Branch command

**Files:**
- Modify: `src/vc/engine.py`
- Modify: `src/cli/cli.py`
- Modify: `tests/vc/test_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/vc/test_engine.py`:

```python
def test_create_branch(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    vc.create_branch("feature-x")
    branches = json.loads((tmp_path / ".daw" / "branches.json").read_text())
    assert "feature-x" in branches
    assert branches["feature-x"] is None  # points to current HEAD (None before first commit)


def test_create_duplicate_branch_raises(tmp_path):
    vc = DawVC(tmp_path)
    vc.init()
    vc.create_branch("feature-x")
    with pytest.raises(ValueError, match="already exists"):
        vc.create_branch("feature-x")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/vc/test_engine.py::test_create_branch tests/vc/test_engine.py::test_create_duplicate_branch_raises -v
```

Expected: FAIL with `AttributeError: 'DawVC' object has no attribute 'create_branch'`

- [ ] **Step 3: Add create_branch() to engine.py**

Add to `DawVC` class in `src/vc/engine.py`:

```python
def create_branch(self, name: str) -> None:
    branches = self._read_branches()
    if name in branches:
        raise ValueError(f"Branch '{name}' already exists")
    branches[name] = self.head_hash()
    self._write_branches(branches)
```

- [ ] **Step 4: Add branch CLI command to cli.py**

```python
@cli.command()
@click.argument('name')
def branch(name):
    """Create a new branch at current HEAD."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        vc.create_branch(name)
        console.print(f"[green]Created branch '{name}'[/green]")
    except ValueError as e:
        raise click.ClickException(str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/vc/test_engine.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/vc/engine.py src/cli/cli.py tests/vc/test_engine.py
git commit -m "feat: add branch creation command"
```

---

## Task 3: Checkout command

**Files:**
- Modify: `src/vc/engine.py`
- Modify: `src/cli/cli.py`
- Modify: `tests/vc/test_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/vc/test_engine.py`:

```python
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
    commit_hash = vc.commit("initial")
    vc.create_branch("feature-x")
    vc.checkout("feature-x")
    # The .flp should be restored from objects/
    restored = tmp_path / "test.flp"
    assert restored.exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/vc/test_engine.py::test_checkout_branch_switches_branch tests/vc/test_engine.py::test_checkout_unknown_branch_raises tests/vc/test_engine.py::test_checkout_restores_flp -v
```

Expected: FAIL with `AttributeError`

- [ ] **Step 3: Add checkout() to engine.py**

Add to `DawVC` class in `src/vc/engine.py`:

```python
def checkout(self, ref: str) -> None:
    """Switch to a branch or commit hash. Restores .flp from objects/."""
    branches = self._read_branches()
    commits = self._read_commits()

    # Resolve ref to a commit hash
    if ref in branches:
        target_hash = branches[ref]
        new_branch = ref
    else:
        # Check if ref is a commit hash
        commit_hashes = {c["hash"] for c in commits}
        if ref in commit_hashes:
            target_hash = ref
            new_branch = self.current_branch()  # stay on current branch (detached-ish)
        else:
            raise ValueError(f"Branch or commit '{ref}' not found")

    # Restore .flp from objects if a snapshot exists
    if target_hash:
        snapshot = self.objects_dir / f"{target_hash}.flp"
        if snapshot.exists():
            # Restore to the original path recorded in the commit
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
```

- [ ] **Step 4: Add checkout CLI command to cli.py**

```python
@cli.command()
@click.argument('ref')
def checkout(ref):
    """Switch to a branch or restore a commit snapshot."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        vc.checkout(ref)
        console.print(f"[green]Switched to '{ref}'[/green]")
    except ValueError as e:
        raise click.ClickException(str(e))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/vc/test_engine.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/vc/engine.py src/cli/cli.py tests/vc/test_engine.py
git commit -m "feat: add checkout command for branches and commit hashes"
```

---

## Task 4: Merge command

**Files:**
- Modify: `src/vc/engine.py`
- Modify: `src/cli/cli.py`
- Modify: `tests/vc/test_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/vc/test_engine.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/vc/test_engine.py::test_merge_fast_forward tests/vc/test_engine.py::test_merge_already_up_to_date -v
```

Expected: FAIL with `AttributeError`

- [ ] **Step 3: Add merge() to engine.py**

Add to `DawVC` class in `src/vc/engine.py`:

```python
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
    our_ancestors = self._ancestor_hashes(commits, our_hash)

    # Fast-forward: if our HEAD is an ancestor of theirs
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

    # Diverged: report conflict (manual resolution required)
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
```

- [ ] **Step 4: Add merge CLI command to cli.py**

```python
@cli.command()
@click.argument('branch_name')
def merge(branch_name):
    """Merge a branch into the current branch."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        result = vc.merge(branch_name)
    except ValueError as e:
        raise click.ClickException(str(e))

    if result["status"] == "up-to-date":
        console.print("Already up to date.")
    elif result["status"] == "fast-forward":
        console.print(f"[green]Fast-forward merge from '{branch_name}'[/green]")
    elif result["status"] == "conflict":
        for c in result["conflicts"]:
            console.print(f"[red]CONFLICT: {c}[/red]")
        raise click.ClickException("Merge failed due to conflicts.")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/vc/test_engine.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/vc/engine.py src/cli/cli.py tests/vc/test_engine.py
git commit -m "feat: add merge command with fast-forward and conflict detection"
```

---

## Task 5: Improve log command with rich output

**Files:**
- Modify: `src/cli/cli.py`

- [ ] **Step 1: Update the log command**

Replace the existing `log` command in `src/cli/cli.py`:

```python
@cli.command()
def log():
    """Show commit history."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    commits = vc.get_commits()
    if not commits:
        console.print("No commits yet.")
        return

    state = json.loads(vc.state_file.read_text())
    current_branch = state["branch"]

    for commit in reversed(commits):
        branch_tag = f" [bold green]({current_branch})[/bold green]" if commit["hash"] == state["head"] else ""
        console.print(f"[yellow]{commit['hash']}[/yellow]{branch_tag} {commit['message']}")
        console.print(f"  [dim]{commit['timestamp']} on {commit['branch']}[/dim]")
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/cli/cli.py
git commit -m "feat: improve log command with rich formatting"
```

---

## Verification

```bash
pytest -v --tb=short
```

Expected: all tests pass. To manually verify end-to-end:

```bash
mkdir /tmp/test-daw && cd /tmp/test-daw
daw init
cp /path/to/some.flp .
daw add some.flp
daw commit -m "initial"
daw branch feature-x
daw checkout feature-x
# edit some.flp externally
daw add some.flp
daw commit -m "feature work"
daw checkout main
daw merge feature-x
daw log
```
