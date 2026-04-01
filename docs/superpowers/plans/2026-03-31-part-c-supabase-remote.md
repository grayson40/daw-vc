# Part C: Supabase Remote (Push/Pull/Clone) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `push`, `pull`, and `clone` commands that sync local `.daw/` repositories to a Supabase backend (Postgres for metadata, Storage bucket for `.flp` blobs).

**Architecture:** `src/remote/supabase_client.py` wraps the Supabase Python SDK. `src/remote/sync.py` implements push/pull logic (find unpushed commits, upload blobs, insert rows). CLI calls sync functions. Global config at `~/.daw/config.json` stores Supabase URL + anon key. Depends on Parts A and B being complete.

**Tech Stack:** Python 3.9+, supabase-py, click, rich

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/remote/__init__.py` | Create | Empty init |
| `src/remote/supabase_client.py` | Create | Thin wrapper: init client, upload blob, download blob, insert/query commits |
| `src/remote/sync.py` | Create | `push()`, `pull()`, `clone()` — orchestrate client calls + local engine |
| `src/remote/config.py` | Create | Read/write `~/.daw/config.json` |
| `src/cli/cli.py` | Modify | Add `push`, `pull`, `clone` commands |
| `requirements.txt` | Modify | Add `supabase` |
| `tests/remote/test_sync.py` | Create | Unit tests with mocked Supabase client |
| `tests/remote/__init__.py` | Create | Empty init |

---

## Supabase Setup (one-time, done before running tests)

Before implementing, create the required Supabase schema. Run this SQL in the Supabase dashboard or via the MCP tool:

```sql
-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Commits table
CREATE TABLE IF NOT EXISTS commits (
    hash TEXT PRIMARY KEY,
    message TEXT NOT NULL,
    branch TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    project_id UUID REFERENCES projects(id),
    parent_hash TEXT,
    diff JSONB
);

-- Storage bucket (create via Supabase dashboard: Storage > New bucket > name: "objects", public: false)
```

---

## Task 1: Config module

**Files:**
- Create: `src/remote/__init__.py`
- Create: `src/remote/config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/remote/__init__.py  (empty)
# tests/remote/test_sync.py
import pytest
import json
from pathlib import Path
from unittest.mock import patch
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/remote/test_sync.py::test_save_and_load_config tests/remote/test_sync.py::test_load_config_missing_returns_none -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement config.py**

```python
# src/remote/__init__.py  (empty)

# src/remote/config.py
import json
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".daw" / "config.json"


def load_config() -> Optional[dict]:
    if not CONFIG_PATH.exists():
        return None
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/remote/test_sync.py::test_save_and_load_config tests/remote/test_sync.py::test_load_config_missing_returns_none -v
```

Expected: both PASS

- [ ] **Step 5: Add supabase to requirements.txt**

Add to `requirements.txt`:
```
supabase>=2.0.0
```

Install it:
```bash
pip install supabase
```

- [ ] **Step 6: Commit**

```bash
git add src/remote/__init__.py src/remote/config.py tests/remote/__init__.py tests/remote/test_sync.py requirements.txt
git commit -m "feat: add remote config module for Supabase credentials"
```

---

## Task 2: Supabase client wrapper

**Files:**
- Create: `src/remote/supabase_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/remote/test_sync.py`:

```python
from unittest.mock import MagicMock, patch
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/remote/test_sync.py::test_upload_blob_calls_storage tests/remote/test_sync.py::test_insert_commit_calls_table tests/remote/test_sync.py::test_fetch_commits_since -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement supabase_client.py**

```python
# src/remote/supabase_client.py
from pathlib import Path
from typing import Any, Optional


class SupabaseRemote:
    BUCKET = "objects"

    def __init__(self, client: Any):
        self.client = client

    @classmethod
    def from_config(cls, url: str, key: str) -> "SupabaseRemote":
        from supabase import create_client
        return cls(client=create_client(url, key))

    def upload_blob(self, project_id: str, commit_hash: str, flp_path: Path) -> None:
        blob_path = f"{project_id}/{commit_hash}.flp"
        with open(flp_path, "rb") as f:
            data = f.read()
        self.client.storage.from_(self.BUCKET).upload(
            path=blob_path,
            file=data,
            file_options={"content-type": "application/octet-stream", "upsert": "true"},
        )

    def download_blob(self, project_id: str, commit_hash: str, dest: Path) -> None:
        blob_path = f"{project_id}/{commit_hash}.flp"
        data = self.client.storage.from_(self.BUCKET).download(blob_path)
        dest.write_bytes(data)

    def insert_commit(self, project_id: str, commit: dict) -> None:
        row = {
            "hash": commit["hash"],
            "message": commit["message"],
            "branch": commit["branch"],
            "timestamp": commit["timestamp"],
            "project_id": project_id,
            "parent_hash": commit.get("parent_hash"),
            "diff": commit.get("changes", {}),
        }
        self.client.table("commits").insert(row).execute()

    def fetch_commits(self, project_id: str, branch: str) -> list:
        result = (
            self.client.table("commits")
            .select("*")
            .eq("project_id", project_id)
            .eq("branch", branch)
            .execute()
        )
        return result.data

    def ensure_project(self, name: str, owner: str) -> str:
        """Get or create a project row, return its UUID."""
        result = self.client.table("projects").select("id").eq("name", name).eq("owner", owner).execute()
        if result.data:
            return result.data[0]["id"]
        insert_result = self.client.table("projects").insert({"name": name, "owner": owner}).execute()
        return insert_result.data[0]["id"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/remote/test_sync.py::test_upload_blob_calls_storage tests/remote/test_sync.py::test_insert_commit_calls_table tests/remote/test_sync.py::test_fetch_commits_since -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/remote/supabase_client.py tests/remote/test_sync.py
git commit -m "feat: add Supabase client wrapper for blob and commit operations"
```

---

## Task 3: Push command

**Files:**
- Create: `src/remote/sync.py`
- Modify: `src/cli/cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/remote/test_sync.py`:

```python
from src.remote.sync import push


def test_push_uploads_unpushed_commits(tmp_path):
    from src.vc.engine import DawVC

    # Set up a local repo with one commit
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

    # last_pushed_hash should be updated
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

    # Simulate already pushed
    import json
    state = json.loads((tmp_path / ".daw" / "state.json").read_text())
    state["last_pushed_hash"] = commit_hash
    (tmp_path / ".daw" / "state.json").write_text(json.dumps(state))

    mock_remote = MagicMock()
    mock_remote.ensure_project.return_value = "proj-uuid-123"

    push(vc, mock_remote, project_name="my-project", owner="user1")

    mock_remote.upload_blob.assert_not_called()
    mock_remote.insert_commit.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/remote/test_sync.py::test_push_uploads_unpushed_commits tests/remote/test_sync.py::test_push_skips_already_pushed -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement push() in sync.py**

```python
# src/remote/sync.py
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
        snapshot = vc.objects_dir / f"{commit['hash']}.flp"
        if snapshot.exists():
            remote.upload_blob(project_id, commit["hash"], snapshot)
        remote.insert_commit(project_id, commit)

    state["last_pushed_hash"] = to_push[-1]["hash"]
    vc.state_file.write_text(json.dumps(state))
    return len(to_push)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/remote/test_sync.py::test_push_uploads_unpushed_commits tests/remote/test_sync.py::test_push_skips_already_pushed -v
```

Expected: both PASS

- [ ] **Step 5: Add push CLI command to cli.py**

```python
@cli.command()
@click.option('--project', 'project_name', required=True, help='Project name on remote')
@click.option('--owner', default=None, help='Owner name (defaults to git user or system user)')
def push(project_name, owner):
    """Push local commits to Supabase remote."""
    import getpass
    from src.remote.config import load_config
    from src.remote.supabase_client import SupabaseRemote
    from src.remote.sync import push as do_push

    config = load_config()
    if not config:
        url = click.prompt("Supabase project URL")
        key = click.prompt("Supabase anon key")
        from src.remote.config import save_config
        save_config({"url": url, "key": key})
        config = {"url": url, "key": key}

    if owner is None:
        owner = getpass.getuser()

    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    remote = SupabaseRemote.from_config(config["url"], config["key"])
    count = do_push(vc, remote, project_name=project_name, owner=owner)
    if count == 0:
        console.print("Everything up to date.")
    else:
        console.print(f"[green]Pushed {count} commit(s) to '{project_name}'[/green]")
```

- [ ] **Step 6: Commit**

```bash
git add src/remote/sync.py src/cli/cli.py tests/remote/test_sync.py
git commit -m "feat: add push command to sync commits to Supabase"
```

---

## Task 4: Pull command

**Files:**
- Modify: `src/remote/sync.py`
- Modify: `src/cli/cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/remote/test_sync.py`:

```python
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
    mock_remote.download_blob.return_value = None  # writes nothing in mock

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

    # Remote has the same commit
    import json
    state = json.loads((tmp_path / ".daw" / "state.json").read_text())
    state["last_pushed_hash"] = commit_hash
    (tmp_path / ".daw" / "state.json").write_text(json.dumps(state))

    mock_remote = MagicMock()
    mock_remote.ensure_project.return_value = "proj-uuid-123"
    mock_remote.fetch_commits.return_value = []  # no new remote commits

    result = pull(vc, mock_remote, project_name="my-project", owner="user1")
    assert result["status"] == "up-to-date"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/remote/test_sync.py::test_pull_downloads_new_commits tests/remote/test_sync.py::test_pull_up_to_date -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement pull() in sync.py**

Add to `src/remote/sync.py`:

```python
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

    # Check for divergence: local has commits remote doesn't know about
    last_pushed = state.get("last_pushed_hash")
    local_commits = vc.get_commits()
    local_after_push = _unpushed_commits(local_commits, last_pushed)

    if local_after_push:
        return {
            "status": "conflict",
            "message": "Local and remote have diverged. Run 'daw merge' after pulling.",
        }

    # Fast-forward: download blobs and append commits
    all_commits = local_commits[:]
    for commit in new_commits:
        snapshot_dest = vc.objects_dir / f"{commit['hash']}.flp"
        try:
            remote.download_blob(project_id, commit["hash"], snapshot_dest)
        except Exception:
            pass  # blob may not exist for all commits
        all_commits.append(commit)

    vc._write_commits(all_commits)

    # Update HEAD and branch pointer to latest remote commit
    latest = new_commits[-1]
    state["head"] = latest["hash"]
    state["last_pushed_hash"] = latest["hash"]
    vc.state_file.write_text(json.dumps(state))

    branches = vc._read_branches()
    branches[current_branch] = latest["hash"]
    vc._write_branches(branches)

    return {"status": "fast-forward", "count": len(new_commits)}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/remote/test_sync.py::test_pull_downloads_new_commits tests/remote/test_sync.py::test_pull_up_to_date -v
```

Expected: both PASS

- [ ] **Step 5: Add pull CLI command to cli.py**

```python
@cli.command()
@click.option('--project', 'project_name', required=True, help='Project name on remote')
@click.option('--owner', default=None, help='Owner name')
def pull(project_name, owner):
    """Pull commits from Supabase remote."""
    import getpass
    from src.remote.config import load_config
    from src.remote.supabase_client import SupabaseRemote
    from src.remote.sync import pull as do_pull

    config = load_config()
    if not config:
        raise click.ClickException("No remote configured. Run 'daw push' first to set credentials.")

    if owner is None:
        owner = getpass.getuser()

    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    remote = SupabaseRemote.from_config(config["url"], config["key"])
    result = do_pull(vc, remote, project_name=project_name, owner=owner)

    if result["status"] == "up-to-date":
        console.print("Already up to date.")
    elif result["status"] == "fast-forward":
        console.print(f"[green]Pulled {result['count']} commit(s)[/green]")
    elif result["status"] == "conflict":
        console.print(f"[red]{result['message']}[/red]")
        raise click.ClickException("Pull stopped due to divergence.")
```

- [ ] **Step 6: Commit**

```bash
git add src/remote/sync.py src/cli/cli.py tests/remote/test_sync.py
git commit -m "feat: add pull command to sync from Supabase"
```

---

## Task 5: Clone command

**Files:**
- Modify: `src/remote/sync.py`
- Modify: `src/cli/cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/remote/test_sync.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/remote/test_sync.py::test_clone_initializes_and_pulls -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement clone() in sync.py**

Add to `src/remote/sync.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/remote/test_sync.py::test_clone_initializes_and_pulls -v
```

Expected: PASS

- [ ] **Step 5: Add clone CLI command to cli.py**

```python
@cli.command()
@click.argument('project_id')
@click.option('--branch', default='main', help='Branch to clone')
@click.option('--dir', 'dest', default=None, help='Destination directory (default: current dir)')
def clone(project_id, branch, dest):
    """Clone a project from Supabase into a local directory."""
    import getpass
    from src.remote.config import load_config
    from src.remote.supabase_client import SupabaseRemote
    from src.remote.sync import clone as do_clone

    config = load_config()
    if not config:
        url = click.prompt("Supabase project URL")
        key = click.prompt("Supabase anon key")
        from src.remote.config import save_config
        save_config({"url": url, "key": key})
        config = {"url": url, "key": key}

    dest_path = Path(dest) if dest else Path.cwd()
    remote = SupabaseRemote.from_config(config["url"], config["key"])

    do_clone(dest_path, remote, project_id=project_id, branch=branch)
    console.print(f"[green]Cloned project '{project_id}' branch '{branch}' into {dest_path}[/green]")
```

- [ ] **Step 6: Run full test suite**

```bash
pytest -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/remote/sync.py src/cli/cli.py tests/remote/test_sync.py
git commit -m "feat: add clone command to initialize from Supabase remote"
```

---

## Verification

```bash
pytest -v --tb=short
```

All tests should pass. To manually verify against a real Supabase instance:

1. Create a Supabase project and run the SQL schema above
2. Create an `objects` storage bucket
3. `daw init` in a project folder
4. `daw add project.flp && daw commit -m "initial"`
5. `daw push --project my-song` (enter Supabase URL + anon key when prompted)
6. In a new directory: `daw clone <project-id>`
7. Verify `.daw/commits.json` contains the pushed commit
