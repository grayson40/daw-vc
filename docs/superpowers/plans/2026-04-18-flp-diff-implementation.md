# FLP Diff System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trustworthy, high-fidelity diff system for FL Studio `.flp` files with content-addressed blob storage, plugin-parameter-level deltas, per-note change detection, and rich TTY + JSON output.

**Architecture:** Four-layer pipeline — `pyflp` parsers produce a canonical state dict, normalized via a plugin adapter registry, walked by a tree-differ with stable identity keys, and rendered either to the terminal via `rich` or as JSON. Blobs are stored under `.daw/objects/<sha256>` (deduped by content) and synced to Supabase with HEAD-check skips.

**Tech Stack:** Python 3.10+, `pyflp`, `click`, `rich`, `pytest`, Supabase (existing).

**Reference spec:** [docs/superpowers/specs/2026-04-18-flp-diff-design.md](docs/superpowers/specs/2026-04-18-flp-diff-design.md)

---

## Phase 0: Prerequisite fixtures (human step)

Before TDD work begins, the user (or engineer with FL Studio access) must produce these small `.flp` files under `tests/fixtures/flp/diff/`. Each built from the same project — change one thing per file:

- `baseline.flp` — one sampler "Kick", one pattern "Verse" with one C5 note at position 0, one mixer insert "Main" with volume at default. No plugins on inserts.
- `tempo_changed.flp` — baseline with tempo changed 140 → 150 bpm.
- `channel_added.flp` — baseline + new sampler named "Snare".
- `channel_renamed.flp` — baseline with "Kick" renamed to "Kick 808" (display name only; internal_name stays).
- `note_added.flp` — baseline with an extra note (key D5, position 96) in "Verse".
- `note_moved.flp` — baseline with the C5 note moved from position 0 to position 96.
- `mixer_volume.flp` — baseline with "Main" insert volume nudged (e.g., 12800 → 10000).
- `reverb_knob.flp` — baseline with a Fruity Reverb 2 on the "Main" insert, and a second variant with its `mix` knob moved (commit both as `reverb_base.flp` and `reverb_knob.flp`).
- `vst_opaque.flp` — baseline with any VST loaded on an insert; second variant with one knob on the VST moved (commit both as `vst_base.flp` and `vst_opaque.flp`).

Each file should be under 100KB. These are one-time generated, committed to the repo, and never regenerated automatically.

**This phase blocks Task 25 onward (E2E tests).** Tasks 1–24 use hand-built state dicts and mocked pyflp — no real `.flp` needed.

---

## File structure

**Create:**
- `src/fl_studio/diff/model.py` — TypedDicts for the diff tree shape
- `src/fl_studio/diff/metadata.py` — metadata differ
- `src/fl_studio/diff/channels.py` — channel differ with `internal_name` identity
- `src/fl_studio/diff/patterns.py` — pattern + note differ
- `src/fl_studio/diff/mixer.py` — mixer insert + slot differ
- `src/fl_studio/diff/plugins.py` — plugin (param-level) differ
- `src/fl_studio/diff/playlist.py` — arrangement/track/item differ
- `src/fl_studio/plugins/__init__.py` — adapter registry exports
- `src/fl_studio/plugins/base.py` — `Adapter` Protocol, `Param` TypedDict, `REGISTRY`
- `src/fl_studio/plugins/fruity_balance.py` — adapter
- `src/fl_studio/plugins/fruity_filter.py` — adapter
- `src/fl_studio/plugins/fruity_reverb2.py` — adapter
- `src/vc/blob.py` — content-addressed hashing + object path helpers
- `src/vc/migrate.py` — one-shot migration from `<commit_hash>.flp` → `<blob_sha>`
- `src/cli/render.py` — rich renderer for the new diff tree
- `tests/diff/test_metadata.py`
- `tests/diff/test_channels.py`
- `tests/diff/test_patterns.py`
- `tests/diff/test_mixer.py`
- `tests/diff/test_plugins.py`
- `tests/diff/test_playlist.py`
- `tests/plugins/__init__.py`
- `tests/plugins/test_fruity_balance.py`
- `tests/plugins/test_fruity_filter.py`
- `tests/plugins/test_fruity_reverb2.py`
- `tests/plugins/test_vst_fallback.py`
- `tests/vc/test_blob.py`
- `tests/vc/test_migrate.py`
- `tests/cli/test_render.py`
- `tests/e2e/__init__.py`
- `tests/e2e/test_commit_diff.py`
- `tests/fixtures/rendered/` (directory for golden-text snapshot files, populated during Task 27)

**Modify:**
- `src/fl_studio/diff/compare.py` — rewrite as thin orchestrator calling per-section differs
- `src/fl_studio/parser/plugins.py` — invoke adapter registry; add `params` / `state_hash` fields
- `src/vc/engine.py` — commit writes blobs to `<blob_sha>` paths; caches diff JSON; checkout/merge read by blob_sha
- `src/remote/sync.py` — push/pull use `blob_sha` for blob paths; HEAD check before upload
- `src/remote/supabase_client.py` — `upload_blob` / `download_blob` signatures accept blob_sha, `head_blob` helper
- `src/cli/cli.py` — replace inline `_render_diff` with import from `src/cli/render.py`; add `--json` flag on `daw diff`; add `daw migrate` command
- `README.md` — document `daw migrate`, `daw diff --json`, and the new SQL column (`blob_sha TEXT NOT NULL`)
- `tests/diff/test_compare.py` — update existing tests to new tree shape (keep as integration over the full orchestrator)

---

## Phase 1: Content-addressed blob storage

### Task 1: Blob hashing helpers

**Files:**
- Create: `src/vc/blob.py`
- Test: `tests/vc/test_blob.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/vc/test_blob.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/vc/test_blob.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.vc.blob'`

- [ ] **Step 3: Implement blob helpers**

```python
# src/vc/blob.py
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/vc/test_blob.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/vc/blob.py tests/vc/test_blob.py
git commit -m "feat: add content-addressed blob hashing helpers"
```

---

### Task 2: Commit writes content-addressed blobs

**Files:**
- Modify: `src/vc/engine.py:71-104` (`DawVC.commit`)
- Modify: `tests/vc/test_engine.py` (existing; if absent, create)

- [ ] **Step 1: Add test for blob_sha in commit entry and object path**

Append to `tests/vc/test_engine.py` (or create it):

```python
from pathlib import Path
from src.vc.engine import DawVC
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/vc/test_engine.py -v -k "blob"`
Expected: FAIL — commit still uses `<commit_hash>.flp`

- [ ] **Step 3: Rewrite commit to use blob_sha**

Replace lines 71–104 of `src/vc/engine.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/vc/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vc/engine.py tests/vc/test_engine.py
git commit -m "feat: commit stores .flp bytes under content-addressed blob_sha"
```

---

### Task 3: Checkout and merge read by blob_sha

**Files:**
- Modify: `src/vc/engine.py:122-196` (`checkout` + `merge`)

- [ ] **Step 1: Add failing test**

Append to `tests/vc/test_engine.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/vc/test_engine.py -v -k "checkout_restores"`
Expected: FAIL — looks up `<commit_hash>.flp` which no longer exists.

- [ ] **Step 3: Update checkout + merge to look up blob_sha via commit record**

In `src/vc/engine.py`, replace the snapshot lookups in `checkout` (around line 138) and `merge` (around line 175):

```python
# In checkout, replace the "if target_hash: snapshot = ..." block:
if target_hash:
    commit = next((c for c in commits if c["hash"] == target_hash), None)
    if commit and commit.get("blob_sha") and commit.get("changes"):
        from src.vc.blob import blob_path
        snapshot = blob_path(self.objects_dir, commit["blob_sha"])
        if snapshot.exists():
            for entry in commit["changes"]:
                dest = Path(entry["path"])
                if dest.parent.exists():
                    shutil.copy2(snapshot, dest)
```

```python
# In merge, replace the fast-forward snapshot lookup:
if their_hash:
    commit = next((c for c in commits if c["hash"] == their_hash), None)
    if commit and commit.get("blob_sha") and commit.get("changes"):
        from src.vc.blob import blob_path
        snapshot = blob_path(self.objects_dir, commit["blob_sha"])
        if snapshot.exists():
            for entry in commit["changes"]:
                dest = Path(entry["path"])
                if dest.parent.exists():
                    shutil.copy2(snapshot, dest)
```

- [ ] **Step 4: Run all engine tests**

Run: `pytest tests/vc/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vc/engine.py tests/vc/test_engine.py
git commit -m "feat: checkout and merge restore files via blob_sha"
```

---

### Task 4: Migration command

**Files:**
- Create: `src/vc/migrate.py`
- Create: `tests/vc/test_migrate.py`
- Modify: `src/cli/cli.py` (add `daw migrate` command)

- [ ] **Step 1: Write failing test**

```python
# tests/vc/test_migrate.py
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
    blob = vc.objects_dir / "a" * 64  # already a sha-shaped name
    blob.write_bytes(b"x")
    commits = [{"hash": "abc12345", "blob_sha": "a" * 64, "message": "x",
                "timestamp": "t", "branch": "main", "parent_hash": None, "changes": []}]
    vc._write_commits(commits)

    migrated = migrate_objects(vc)
    assert migrated == 0  # nothing to do
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/vc/test_migrate.py -v`
Expected: FAIL — `src.vc.migrate` doesn't exist.

- [ ] **Step 3: Implement migrate**

```python
# src/vc/migrate.py
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
```

- [ ] **Step 4: Wire CLI**

In `src/cli/cli.py`, add after the existing `clone` command:

```python
@cli.command()
def migrate():
    """One-shot: migrate legacy <commit_hash>.flp objects to content-addressed <blob_sha>."""
    from src.vc.migrate import migrate_objects
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository.")
    count = migrate_objects(vc)
    if count == 0:
        console.print("Nothing to migrate.")
    else:
        console.print(f"[green]Migrated {count} object(s) to content-addressed storage.[/green]")
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/vc/test_migrate.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/vc/migrate.py tests/vc/test_migrate.py src/cli/cli.py
git commit -m "feat: add daw migrate for legacy commit-hash object paths"
```

---

### Task 5: Remote sync uses blob_sha paths

**Files:**
- Modify: `src/remote/sync.py:18-38` (`push`) and `src/remote/sync.py:41-85` (`pull`)
- Modify: `src/remote/supabase_client.py` (add `head_blob`, accept `blob_sha` in upload/download)

- [ ] **Step 1: Inspect existing client**

Read `src/remote/supabase_client.py` to locate `upload_blob` and `download_blob` signatures.

- [ ] **Step 2: Add failing test for HEAD-check skip**

Read `tests/remote/test_sync.py` first to match existing patterns. If it doesn't exist, create it. Append:

```python
from unittest.mock import MagicMock
from pathlib import Path
from src.vc.engine import DawVC
from src.remote.sync import push


def test_push_skips_upload_when_blob_already_present(tmp_path: Path):
    (tmp_path / "song.flp").write_bytes(b"x")
    vc = DawVC(tmp_path)
    vc.init()
    vc.add(tmp_path / "song.flp")
    vc.commit("c1")

    remote = MagicMock()
    remote.ensure_project.return_value = "proj-id"
    remote.head_blob.return_value = True  # already uploaded

    push(vc, remote, project_name="p", owner="me")

    remote.upload_blob.assert_not_called()
    remote.insert_commit.assert_called_once()
```

- [ ] **Step 3: Run test**

Run: `pytest tests/remote/test_sync.py::test_push_skips_upload_when_blob_already_present -v`
Expected: FAIL

- [ ] **Step 4: Update supabase_client**

In `src/remote/supabase_client.py`, change blob methods to take `blob_sha` and add `head_blob`:

```python
def head_blob(self, project_id: str, blob_sha: str) -> bool:
    """Return True if the blob already exists in storage."""
    storage_path = f"{project_id}/{blob_sha}"
    try:
        self.client.storage.from_("objects").info(storage_path)
        return True
    except Exception:
        return False

def upload_blob(self, project_id: str, blob_sha: str, local_path: Path) -> None:
    storage_path = f"{project_id}/{blob_sha}"
    with local_path.open("rb") as f:
        self.client.storage.from_("objects").upload(storage_path, f, {"upsert": "true"})

def download_blob(self, project_id: str, blob_sha: str, dest: Path) -> None:
    storage_path = f"{project_id}/{blob_sha}"
    data = self.client.storage.from_("objects").download(storage_path)
    dest.write_bytes(data)
```

(If existing methods take a different name like `commit_hash`, rename parameter and audit call sites.)

- [ ] **Step 5: Update push/pull**

In `src/remote/sync.py`, replace `push`:

```python
def push(vc: DawVC, remote: SupabaseRemote, project_name: str, owner: str) -> int:
    from src.vc.blob import blob_path

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
            local_blob = blob_path(vc.objects_dir, blob_sha)
            if local_blob.exists() and not remote.head_blob(project_id, blob_sha):
                remote.upload_blob(project_id, blob_sha, local_blob)
        remote.insert_commit(project_id, commit)

    state["last_pushed_hash"] = to_push[-1]["hash"]
    vc.state_file.write_text(json.dumps(state))
    return len(to_push)
```

Replace the blob-download line in `pull` (around line 67–71) and `clone` (around line 96–100):

```python
# pull:
blob_sha = commit.get("blob_sha")
if blob_sha:
    from src.vc.blob import blob_path
    snapshot_dest = blob_path(vc.objects_dir, blob_sha)
    try:
        remote.download_blob(project_id, blob_sha, snapshot_dest)
    except Exception:
        pass
```

Do the same substitution in `clone`.

- [ ] **Step 6: Run tests**

Run: `pytest tests/remote/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/remote/sync.py src/remote/supabase_client.py tests/remote/test_sync.py
git commit -m "feat: remote sync uses blob_sha paths with HEAD-check dedup"
```

---

## Phase 2: Diff tree model & metadata differ

### Task 6: Diff tree TypedDicts

**Files:**
- Create: `src/fl_studio/diff/model.py`

- [ ] **Step 1: Define types**

```python
# src/fl_studio/diff/model.py
from typing import TypedDict, Any


class Change(TypedDict):
    old: Any
    new: Any


class SectionDiff(TypedDict):
    added: list
    removed: list
    modified: list


class DiffTree(TypedDict):
    metadata: dict
    channels: SectionDiff
    patterns: SectionDiff
    mixer: SectionDiff
    plugins: SectionDiff
    playlist: SectionDiff


def empty_section() -> SectionDiff:
    return {"added": [], "removed": [], "modified": []}


def empty_tree() -> DiffTree:
    return {
        "metadata": {},
        "channels": empty_section(),
        "patterns": empty_section(),
        "mixer": empty_section(),
        "plugins": empty_section(),
        "playlist": empty_section(),
    }
```

- [ ] **Step 2: Commit (no test — pure type definitions)**

```bash
git add src/fl_studio/diff/model.py
git commit -m "feat: add diff tree type definitions"
```

---

### Task 7: Metadata differ

**Files:**
- Create: `src/fl_studio/diff/metadata.py`
- Create: `tests/diff/test_metadata.py`

- [ ] **Step 1: Failing tests**

```python
# tests/diff/test_metadata.py
from src.fl_studio.diff.metadata import diff_metadata


def test_identical_metadata_returns_empty():
    m = {"tempo": 140.0, "title": "T", "artists": "", "genre": "", "version": "21", "ppq": 96}
    assert diff_metadata(m, m) == {}


def test_tempo_change_reported():
    old = {"tempo": 140.0}
    new = {"tempo": 150.0}
    assert diff_metadata(old, new) == {"tempo": {"old": 140.0, "new": 150.0}}


def test_added_field_reported_with_old_none():
    assert diff_metadata({}, {"title": "New"}) == {"title": {"old": None, "new": "New"}}


def test_removed_field_reported_with_new_none():
    assert diff_metadata({"title": "Old"}, {}) == {"title": {"old": "Old", "new": None}}
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/diff/test_metadata.py -v`
Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# src/fl_studio/diff/metadata.py
def diff_metadata(old: dict, new: dict) -> dict:
    changes = {}
    for k in set(list(old.keys()) + list(new.keys())):
        if old.get(k) != new.get(k):
            changes[k] = {"old": old.get(k), "new": new.get(k)}
    return changes
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/diff/test_metadata.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/metadata.py tests/diff/test_metadata.py
git commit -m "feat: add metadata differ"
```

---

## Phase 3: Section differs

### Task 8: Channel differ with internal_name identity

**Files:**
- Create: `src/fl_studio/diff/channels.py`
- Create: `tests/diff/test_channels.py`

- [ ] **Step 1: Failing tests**

```python
# tests/diff/test_channels.py
from src.fl_studio.diff.channels import diff_channels


def _ch(name, internal_name=None, **kw):
    base = {"name": name, "internal_name": internal_name or name, "display_name": name,
            "enabled": True, "locked": False, "volume": 12800, "pan": 0,
            "color": None, "icon": 0, "zipped": False}
    base.update(kw)
    return {"base": base}


BASE = {
    "rack_settings": {}, "groups": [],
    "channels": {"samplers": [_ch("Kick")], "instruments": [], "layers": [], "automations": []},
}


def test_identical_channels_empty():
    d = diff_channels(BASE, BASE)
    assert d == {"added": [], "removed": [], "modified": []}


def test_channel_added():
    new = {**BASE, "channels": {"samplers": [_ch("Kick"), _ch("Snare")],
                                "instruments": [], "layers": [], "automations": []}}
    d = diff_channels(BASE, new)
    assert len(d["added"]) == 1
    assert d["added"][0]["base"]["internal_name"] == "Snare"


def test_channel_rename_detected_via_internal_name():
    renamed = {"channels": {"samplers": [_ch("Kick 808", internal_name="Kick")],
                             "instruments": [], "layers": [], "automations": []},
               "rack_settings": {}, "groups": []}
    d = diff_channels(BASE, renamed)
    assert d["added"] == []
    assert d["removed"] == []
    assert len(d["modified"]) == 1
    assert d["modified"][0]["internal_name"] == "Kick"
    assert d["modified"][0]["changes"]["name"] == {"old": "Kick", "new": "Kick 808"}


def test_channel_volume_changed():
    louder = {"channels": {"samplers": [_ch("Kick", volume=10000)],
                           "instruments": [], "layers": [], "automations": []},
              "rack_settings": {}, "groups": []}
    d = diff_channels(BASE, louder)
    assert d["modified"][0]["changes"]["volume"] == {"old": 12800, "new": 10000}
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/diff/test_channels.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/diff/channels.py
from src.fl_studio.diff.model import SectionDiff, empty_section


SCALAR_FIELDS = ("name", "display_name", "enabled", "locked", "volume", "pan",
                 "color", "icon", "zipped")


def _flatten(channels_state: dict) -> list:
    result = []
    inner = channels_state.get("channels", {})
    for cat in ("samplers", "instruments", "layers", "automations"):
        for ch in inner.get(cat, []):
            result.append(ch)
    return result


def _identity(ch: dict) -> str:
    base = ch.get("base", {})
    return base.get("internal_name") or base.get("name") or ""


def _scalar_changes(old_base: dict, new_base: dict) -> dict:
    changes = {}
    for field in SCALAR_FIELDS:
        ov, nv = old_base.get(field), new_base.get(field)
        if ov != nv:
            changes[field] = {"old": ov, "new": nv}
    return changes


def diff_channels(old: dict, new: dict) -> SectionDiff:
    old_list = _flatten(old)
    new_list = _flatten(new)
    old_by_id = {_identity(c): c for c in old_list}
    new_by_id = {_identity(c): c for c in new_list}

    result = empty_section()
    for ident, ch in new_by_id.items():
        if ident not in old_by_id:
            result["added"].append(ch)
    for ident, ch in old_by_id.items():
        if ident not in new_by_id:
            result["removed"].append(ch)
        else:
            changes = _scalar_changes(old_by_id[ident].get("base", {}),
                                       new_by_id[ident].get("base", {}))
            if changes:
                result["modified"].append({
                    "internal_name": ident,
                    "name": new_by_id[ident].get("base", {}).get("name"),
                    "changes": changes,
                })
    return result
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/diff/test_channels.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/channels.py tests/diff/test_channels.py
git commit -m "feat: add channel differ with internal_name identity key"
```

---

### Task 9: Pattern differ with per-note detection

**Files:**
- Create: `src/fl_studio/diff/patterns.py`
- Create: `tests/diff/test_patterns.py`

- [ ] **Step 1: Failing tests**

```python
# tests/diff/test_patterns.py
from src.fl_studio.diff.patterns import diff_patterns


def _note(key, pos, **kw):
    n = {"key": key, "position": pos, "length": 96, "velocity": 100,
         "pan": 0, "fine_pitch": 0, "rack_channel": 1, "slide": False}
    n.update(kw)
    return n


def _pat(iid, name="P", notes=None):
    return {"iid": iid, "name": name, "color": None, "length": 384,
            "looped": False, "notes": notes or []}


def test_identical_patterns_empty():
    p = [_pat(1, notes=[_note(60, 0)])]
    d = diff_patterns(p, p)
    assert d == {"added": [], "removed": [], "modified": []}


def test_pattern_added():
    old = [_pat(1)]
    new = [_pat(1), _pat(2, name="Chorus")]
    d = diff_patterns(old, new)
    assert len(d["added"]) == 1 and d["added"][0]["iid"] == 2


def test_note_added_inside_pattern():
    old = [_pat(1, notes=[_note(60, 0)])]
    new = [_pat(1, notes=[_note(60, 0), _note(64, 96)])]
    d = diff_patterns(old, new)
    assert len(d["modified"]) == 1
    mod = d["modified"][0]
    assert mod["iid"] == 1
    assert len(mod["notes"]["added"]) == 1
    assert mod["notes"]["added"][0]["key"] == 64


def test_note_velocity_modified():
    old = [_pat(1, notes=[_note(60, 0, velocity=100)])]
    new = [_pat(1, notes=[_note(60, 0, velocity=115)])]
    d = diff_patterns(old, new)
    mod = d["modified"][0]
    assert mod["notes"]["modified"][0]["changes"]["velocity"] == {"old": 100, "new": 115}


def test_note_moved_shows_as_delete_plus_add():
    old = [_pat(1, notes=[_note(60, 0)])]
    new = [_pat(1, notes=[_note(60, 96)])]
    d = diff_patterns(old, new)
    mod = d["modified"][0]
    assert len(mod["notes"]["removed"]) == 1
    assert len(mod["notes"]["added"]) == 1
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/diff/test_patterns.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/diff/patterns.py
from src.fl_studio.diff.model import SectionDiff, empty_section


NOTE_SCALAR_FIELDS = ("length", "velocity", "pan", "fine_pitch", "slide")
PATTERN_SCALAR_FIELDS = ("name", "color", "length", "looped")


def _note_key(n: dict) -> tuple:
    return (n["rack_channel"], n["key"], n["position"])


def _diff_notes(old_notes: list, new_notes: list) -> dict:
    old_by_k = {_note_key(n): n for n in old_notes}
    new_by_k = {_note_key(n): n for n in new_notes}

    out = empty_section()
    for k, n in new_by_k.items():
        if k not in old_by_k:
            out["added"].append(n)
    for k, n in old_by_k.items():
        if k not in new_by_k:
            out["removed"].append(n)
        else:
            changes = {}
            for f in NOTE_SCALAR_FIELDS:
                if old_by_k[k].get(f) != new_by_k[k].get(f):
                    changes[f] = {"old": old_by_k[k].get(f), "new": new_by_k[k].get(f)}
            if changes:
                out["modified"].append({
                    "key": {"rack_channel": k[0], "key": k[1], "position": k[2]},
                    "changes": changes,
                })
    return out


def diff_patterns(old: list, new: list) -> SectionDiff:
    old_by_iid = {p["iid"]: p for p in old}
    new_by_iid = {p["iid"]: p for p in new}

    result = empty_section()
    for iid, p in new_by_iid.items():
        if iid not in old_by_iid:
            result["added"].append(p)
    for iid, p in old_by_iid.items():
        if iid not in new_by_iid:
            result["removed"].append(p)
            continue

        pattern_changes = {}
        for f in PATTERN_SCALAR_FIELDS:
            if old_by_iid[iid].get(f) != new_by_iid[iid].get(f):
                pattern_changes[f] = {"old": old_by_iid[iid].get(f),
                                      "new": new_by_iid[iid].get(f)}

        note_diff = _diff_notes(old_by_iid[iid].get("notes", []),
                                new_by_iid[iid].get("notes", []))
        has_note_changes = any(note_diff[k] for k in ("added", "removed", "modified"))

        if pattern_changes or has_note_changes:
            entry = {"iid": iid, "name": new_by_iid[iid].get("name")}
            if pattern_changes:
                entry["changes"] = pattern_changes
            if has_note_changes:
                entry["notes"] = note_diff
            result["modified"].append(entry)

    return result
```

- [ ] **Step 4: Run**

Run: `pytest tests/diff/test_patterns.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/patterns.py tests/diff/test_patterns.py
git commit -m "feat: add pattern differ with per-note detection"
```

---

### Task 10: Mixer differ with insert + slot diffs

**Files:**
- Create: `src/fl_studio/diff/mixer.py`
- Create: `tests/diff/test_mixer.py`

- [ ] **Step 1: Failing tests**

```python
# tests/diff/test_mixer.py
from src.fl_studio.diff.mixer import diff_mixer


def _ins(iid, name="Insert", volume=12800, slots=None):
    return {"iid": iid, "name": name, "enabled": True, "volume": volume, "pan": 0,
            "bypassed": False, "locked": False, "is_solo": False, "routes": [],
            "slots": slots or []}


def _slot(name, internal_name=None, color=None):
    return {"name": name, "internal_name": internal_name or name, "color": color}


def test_identical_mixer_empty():
    m = [_ins(1)]
    assert diff_mixer(m, m) == {"added": [], "removed": [], "modified": []}


def test_insert_volume_change():
    d = diff_mixer([_ins(1, volume=12800)], [_ins(1, volume=10000)])
    assert d["modified"][0]["iid"] == 1
    assert d["modified"][0]["changes"]["volume"] == {"old": 12800, "new": 10000}


def test_slot_added_to_insert():
    old = [_ins(1, slots=[])]
    new = [_ins(1, slots=[_slot("Reverb")])]
    d = diff_mixer(old, new)
    mod = d["modified"][0]
    assert len(mod["slots"]["added"]) == 1
    assert mod["slots"]["added"][0]["name"] == "Reverb"


def test_slot_renamed_at_same_index():
    old = [_ins(1, slots=[_slot("Rev A")])]
    new = [_ins(1, slots=[_slot("Rev B")])]
    d = diff_mixer(old, new)
    mod = d["modified"][0]
    assert mod["slots"]["modified"][0]["changes"]["name"] == {"old": "Rev A", "new": "Rev B"}
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/diff/test_mixer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/diff/mixer.py
from src.fl_studio.diff.model import SectionDiff, empty_section


INSERT_SCALAR_FIELDS = ("name", "enabled", "volume", "pan", "bypassed", "locked",
                        "is_solo", "routes")
SLOT_SCALAR_FIELDS = ("name", "internal_name", "color")


def _diff_slots(old_slots: list, new_slots: list) -> dict:
    out = empty_section()
    for idx in range(max(len(old_slots), len(new_slots))):
        old_slot = old_slots[idx] if idx < len(old_slots) else None
        new_slot = new_slots[idx] if idx < len(new_slots) else None
        if old_slot is None and new_slot is not None:
            out["added"].append({**new_slot, "slot_index": idx})
        elif new_slot is None and old_slot is not None:
            out["removed"].append({**old_slot, "slot_index": idx})
        else:
            changes = {}
            for f in SLOT_SCALAR_FIELDS:
                if old_slot.get(f) != new_slot.get(f):
                    changes[f] = {"old": old_slot.get(f), "new": new_slot.get(f)}
            if changes:
                out["modified"].append({"slot_index": idx, "changes": changes})
    return out


def diff_mixer(old: list, new: list) -> SectionDiff:
    old_by_iid = {i["iid"]: i for i in old}
    new_by_iid = {i["iid"]: i for i in new}

    result = empty_section()
    for iid, ins in new_by_iid.items():
        if iid not in old_by_iid:
            result["added"].append(ins)
    for iid, ins in old_by_iid.items():
        if iid not in new_by_iid:
            result["removed"].append(ins)
            continue

        insert_changes = {}
        for f in INSERT_SCALAR_FIELDS:
            if old_by_iid[iid].get(f) != new_by_iid[iid].get(f):
                insert_changes[f] = {"old": old_by_iid[iid].get(f),
                                     "new": new_by_iid[iid].get(f)}

        slot_diff = _diff_slots(old_by_iid[iid].get("slots", []),
                                new_by_iid[iid].get("slots", []))
        has_slot_changes = any(slot_diff[k] for k in ("added", "removed", "modified"))

        if insert_changes or has_slot_changes:
            entry = {"iid": iid, "name": new_by_iid[iid].get("name")}
            if insert_changes:
                entry["changes"] = insert_changes
            if has_slot_changes:
                entry["slots"] = slot_diff
            result["modified"].append(entry)

    return result
```

- [ ] **Step 4: Run**

Run: `pytest tests/diff/test_mixer.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/mixer.py tests/diff/test_mixer.py
git commit -m "feat: add mixer differ with insert and slot diffs"
```

---

### Task 11: Playlist differ

**Files:**
- Create: `src/fl_studio/diff/playlist.py`
- Create: `tests/diff/test_playlist.py`

- [ ] **Step 1: Failing tests**

```python
# tests/diff/test_playlist.py
from src.fl_studio.diff.playlist import diff_playlist


def _item(position, length=96, ref_name="Verse", ref_type="pattern", muted=False):
    return {"position": position, "length": length, "muted": muted,
            "ref": {"type": ref_type, "name": ref_name}}


def _track(iid, name="T", items=None):
    return {"iid": iid, "name": name, "enabled": True, "locked": False,
            "items": items or []}


def _arr(iid, name="Main", tracks=None):
    return {"iid": iid, "name": name, "tracks": tracks or []}


def test_identical_empty():
    p = [_arr(0)]
    assert diff_playlist(p, p) == {"added": [], "removed": [], "modified": []}


def test_track_added():
    old = [_arr(0, tracks=[])]
    new = [_arr(0, tracks=[_track(1, name="Drums")])]
    d = diff_playlist(old, new)
    mod = d["modified"][0]
    assert len(mod["tracks"]["added"]) == 1
    assert mod["tracks"]["added"][0]["name"] == "Drums"


def test_item_added_to_track():
    old = [_arr(0, tracks=[_track(1, items=[])])]
    new = [_arr(0, tracks=[_track(1, items=[_item(0)])])]
    d = diff_playlist(old, new)
    mod = d["modified"][0]
    track_mod = mod["tracks"]["modified"][0]
    assert len(track_mod["items"]["added"]) == 1
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/diff/test_playlist.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/diff/playlist.py
from src.fl_studio.diff.model import SectionDiff, empty_section


TRACK_SCALAR_FIELDS = ("name", "enabled", "locked")
ITEM_SCALAR_FIELDS = ("length", "muted")


def _item_key(item: dict) -> tuple:
    ref = item.get("ref") or {}
    return (item["position"], ref.get("type"), ref.get("name"))


def _diff_items(old_items: list, new_items: list) -> dict:
    old_by = {_item_key(i): i for i in old_items}
    new_by = {_item_key(i): i for i in new_items}
    out = empty_section()
    for k, it in new_by.items():
        if k not in old_by:
            out["added"].append(it)
    for k, it in old_by.items():
        if k not in new_by:
            out["removed"].append(it)
        else:
            changes = {}
            for f in ITEM_SCALAR_FIELDS:
                if old_by[k].get(f) != new_by[k].get(f):
                    changes[f] = {"old": old_by[k].get(f), "new": new_by[k].get(f)}
            if changes:
                out["modified"].append({
                    "key": {"position": k[0], "ref_type": k[1], "ref_name": k[2]},
                    "changes": changes,
                })
    return out


def _diff_tracks(old_tracks: list, new_tracks: list) -> dict:
    old_by_iid = {t["iid"]: t for t in old_tracks}
    new_by_iid = {t["iid"]: t for t in new_tracks}
    out = empty_section()

    for iid, t in new_by_iid.items():
        if iid not in old_by_iid:
            out["added"].append(t)
    for iid, t in old_by_iid.items():
        if iid not in new_by_iid:
            out["removed"].append(t)
            continue

        track_changes = {}
        for f in TRACK_SCALAR_FIELDS:
            if old_by_iid[iid].get(f) != new_by_iid[iid].get(f):
                track_changes[f] = {"old": old_by_iid[iid].get(f),
                                    "new": new_by_iid[iid].get(f)}

        item_diff = _diff_items(old_by_iid[iid].get("items", []),
                                new_by_iid[iid].get("items", []))
        has_item_changes = any(item_diff[k] for k in ("added", "removed", "modified"))

        if track_changes or has_item_changes:
            entry = {"iid": iid, "name": new_by_iid[iid].get("name")}
            if track_changes:
                entry["changes"] = track_changes
            if has_item_changes:
                entry["items"] = item_diff
            out["modified"].append(entry)

    return out


def diff_playlist(old: list, new: list) -> SectionDiff:
    old_by_iid = {a["iid"]: a for a in old}
    new_by_iid = {a["iid"]: a for a in new}

    result = empty_section()
    for iid, a in new_by_iid.items():
        if iid not in old_by_iid:
            result["added"].append(a)
    for iid, a in old_by_iid.items():
        if iid not in new_by_iid:
            result["removed"].append(a)
            continue

        track_diff = _diff_tracks(old_by_iid[iid].get("tracks", []),
                                  new_by_iid[iid].get("tracks", []))
        has_track_changes = any(track_diff[k] for k in ("added", "removed", "modified"))
        if has_track_changes:
            result["modified"].append({
                "iid": iid,
                "name": new_by_iid[iid].get("name"),
                "tracks": track_diff,
            })
    return result
```

- [ ] **Step 4: Run**

Run: `pytest tests/diff/test_playlist.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/playlist.py tests/diff/test_playlist.py
git commit -m "feat: add playlist differ with track and item diffs"
```

---

## Phase 4: Plugin adapter system

### Task 12: Adapter protocol, Param type, registry

**Files:**
- Create: `src/fl_studio/plugins/__init__.py`
- Create: `src/fl_studio/plugins/base.py`

- [ ] **Step 1: Implement the base module**

```python
# src/fl_studio/plugins/base.py
from typing import Protocol, TypedDict, runtime_checkable


class Param(TypedDict):
    name: str
    unit: str   # "%", "Hz", "dB", "dB_norm", "raw"
    value: float


@runtime_checkable
class Adapter(Protocol):
    plugin_class: type
    display_name: str

    def extract(self, plugin) -> dict[str, Param]: ...


REGISTRY: list[Adapter] = []


def register(adapter: Adapter) -> Adapter:
    REGISTRY.append(adapter)
    return adapter


def find_adapter(plugin) -> Adapter | None:
    for a in REGISTRY:
        if isinstance(plugin, a.plugin_class):
            return a
    return None
```

```python
# src/fl_studio/plugins/__init__.py
from src.fl_studio.plugins.base import Adapter, Param, REGISTRY, register, find_adapter

# Import adapter modules so their `register()` calls run.
from src.fl_studio.plugins import fruity_balance  # noqa: F401
from src.fl_studio.plugins import fruity_filter   # noqa: F401
from src.fl_studio.plugins import fruity_reverb2  # noqa: F401

__all__ = ["Adapter", "Param", "REGISTRY", "register", "find_adapter"]
```

*(Note: the adapter modules are created in Tasks 13–15; the package `__init__.py` import will raise until they exist. That's fine — don't run tests yet. Alternatively comment the three imports and uncomment as each adapter lands.)*

- [ ] **Step 2: Commit base only first**

Comment out the three `from src.fl_studio.plugins import ...` lines in `__init__.py`, then:

```bash
git add src/fl_studio/plugins/
git commit -m "feat: add plugin adapter protocol and registry"
```

---

### Task 13: FruityBalance adapter

**Files:**
- Create: `src/fl_studio/plugins/fruity_balance.py`
- Create: `tests/plugins/__init__.py` (empty)
- Create: `tests/plugins/test_fruity_balance.py`

- [ ] **Step 1: Failing test**

```python
# tests/plugins/test_fruity_balance.py
from types import SimpleNamespace
from src.fl_studio.plugins.fruity_balance import FruityBalanceAdapter


def test_extracts_volume_and_pan():
    fake_plugin = SimpleNamespace(volume=128, pan=0)
    adapter = FruityBalanceAdapter()
    params = adapter.extract(fake_plugin)
    assert params["volume"] == {"name": "volume", "unit": "dB_norm", "value": 128.0}
    assert params["pan"] == {"name": "pan", "unit": "raw", "value": 0.0}
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/plugins/test_fruity_balance.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/plugins/fruity_balance.py
from src.fl_studio.plugins.base import register

try:
    from pyflp.plugin import FruityBalance
except Exception:
    FruityBalance = type("FruityBalance", (), {})  # placeholder when pyflp version differs


class FruityBalanceAdapter:
    plugin_class = FruityBalance
    display_name = "Fruity Balance"

    def extract(self, plugin) -> dict:
        return {
            "volume": {"name": "volume", "unit": "dB_norm", "value": float(plugin.volume)},
            "pan":    {"name": "pan",    "unit": "raw",     "value": float(plugin.pan)},
        }


register(FruityBalanceAdapter())
```

- [ ] **Step 4: Uncomment import in `src/fl_studio/plugins/__init__.py`**

Re-enable:
```python
from src.fl_studio.plugins import fruity_balance  # noqa: F401
```

- [ ] **Step 5: Run**

Run: `pytest tests/plugins/test_fruity_balance.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/fl_studio/plugins/fruity_balance.py src/fl_studio/plugins/__init__.py tests/plugins/
git commit -m "feat: add FruityBalance plugin adapter"
```

---

### Task 14: FruityFilter adapter

**Files:**
- Create: `src/fl_studio/plugins/fruity_filter.py`
- Create: `tests/plugins/test_fruity_filter.py`

- [ ] **Step 1: Failing test**

```python
# tests/plugins/test_fruity_filter.py
from types import SimpleNamespace
from src.fl_studio.plugins.fruity_filter import FruityFilterAdapter


def test_extracts_cutoff_resonance_type():
    fake = SimpleNamespace(cutoff=8000.0, resonance=50.0, type=1)
    adapter = FruityFilterAdapter()
    params = adapter.extract(fake)
    assert params["cutoff"]["unit"] == "Hz"
    assert params["cutoff"]["value"] == 8000.0
    assert params["resonance"]["unit"] == "%"
    assert params["type"]["unit"] == "raw"
    assert params["type"]["value"] == 1.0
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/plugins/test_fruity_filter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/plugins/fruity_filter.py
from src.fl_studio.plugins.base import register

try:
    from pyflp.plugin import FruityFilter
except Exception:
    FruityFilter = type("FruityFilter", (), {})


class FruityFilterAdapter:
    plugin_class = FruityFilter
    display_name = "Fruity Filter"

    def extract(self, plugin) -> dict:
        return {
            "cutoff":    {"name": "cutoff",    "unit": "Hz",  "value": float(plugin.cutoff)},
            "resonance": {"name": "resonance", "unit": "%",   "value": float(plugin.resonance)},
            "type":      {"name": "type",      "unit": "raw", "value": float(plugin.type)},
        }


register(FruityFilterAdapter())
```

- [ ] **Step 4: Uncomment import in `src/fl_studio/plugins/__init__.py`**

```python
from src.fl_studio.plugins import fruity_filter  # noqa: F401
```

- [ ] **Step 5: Run**

Run: `pytest tests/plugins/test_fruity_filter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/fl_studio/plugins/fruity_filter.py src/fl_studio/plugins/__init__.py tests/plugins/test_fruity_filter.py
git commit -m "feat: add FruityFilter plugin adapter"
```

---

### Task 15: FruityReverb2 adapter

**Files:**
- Create: `src/fl_studio/plugins/fruity_reverb2.py`
- Create: `tests/plugins/test_fruity_reverb2.py`

- [ ] **Step 1: Failing test**

```python
# tests/plugins/test_fruity_reverb2.py
from types import SimpleNamespace
from src.fl_studio.plugins.fruity_reverb2 import FruityReverb2Adapter


def test_extracts_six_params():
    fake = SimpleNamespace(mix=35.0, room_size=50.0, color=0.5,
                           hp=80.0, low=0.0, high=0.0)
    adapter = FruityReverb2Adapter()
    params = adapter.extract(fake)
    assert set(params.keys()) == {"mix", "room_size", "color", "hp", "low", "high"}
    assert params["mix"]["unit"] == "%"
    assert params["mix"]["value"] == 35.0
    assert params["hp"]["unit"] == "Hz"
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/plugins/test_fruity_reverb2.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/plugins/fruity_reverb2.py
from src.fl_studio.plugins.base import register

try:
    from pyflp.plugin import FruityReverb2
except Exception:
    FruityReverb2 = type("FruityReverb2", (), {})


class FruityReverb2Adapter:
    plugin_class = FruityReverb2
    display_name = "Fruity Reverb 2"

    def extract(self, plugin) -> dict:
        return {
            "mix":       {"name": "mix",       "unit": "%",  "value": float(plugin.mix)},
            "room_size": {"name": "room_size", "unit": "%",  "value": float(plugin.room_size)},
            "color":     {"name": "color",     "unit": "%",  "value": float(plugin.color)},
            "hp":        {"name": "hp",        "unit": "Hz", "value": float(plugin.hp)},
            "low":       {"name": "low",       "unit": "%",  "value": float(plugin.low)},
            "high":      {"name": "high",      "unit": "%",  "value": float(plugin.high)},
        }


register(FruityReverb2Adapter())
```

- [ ] **Step 4: Uncomment import in `src/fl_studio/plugins/__init__.py`**

```python
from src.fl_studio.plugins import fruity_reverb2  # noqa: F401
```

- [ ] **Step 5: Run**

Run: `pytest tests/plugins/test_fruity_reverb2.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/fl_studio/plugins/fruity_reverb2.py src/fl_studio/plugins/__init__.py tests/plugins/test_fruity_reverb2.py
git commit -m "feat: add FruityReverb2 plugin adapter"
```

---

### Task 16: VST / unknown-plugin state_hash fallback

**Files:**
- Modify: `src/fl_studio/parser/plugins.py`
- Create: `tests/plugins/test_vst_fallback.py`

- [ ] **Step 1: Failing test**

```python
# tests/plugins/test_vst_fallback.py
import hashlib
import json
from types import SimpleNamespace
from src.fl_studio.parser.plugins import FLPluginParser


def _mk_instrument(name, plugin):
    return SimpleNamespace(name=name, insert=1, plugin=plugin)


def test_known_plugin_gets_params(monkeypatch):
    from src.fl_studio.plugins.fruity_balance import FruityBalanceAdapter
    # Make the adapter class match our fake
    class FakeFB: ...
    FruityBalanceAdapter.plugin_class = FakeFB
    fake = FakeFB()
    fake.volume = 128
    fake.pan = 0

    project = SimpleNamespace(channels=SimpleNamespace(instruments=[
        _mk_instrument("Lead", fake)
    ]))
    state = FLPluginParser(project).get_state()
    assert state[0]["plugin_type"] == "FakeFB"
    assert state[0]["params"]["volume"]["value"] == 128.0


def test_vst_plugin_gets_state_hash():
    # Mimic a pyflp VST plugin: has `raw_state_bytes` attribute
    vst = SimpleNamespace(raw_state_bytes=b"vst binary state")
    project = SimpleNamespace(channels=SimpleNamespace(instruments=[
        _mk_instrument("Serum", vst)
    ]))
    state = FLPluginParser(project).get_state()
    expected = hashlib.sha256(b"vst binary state").hexdigest()
    assert state[0]["state_hash"] == expected
    assert "params" not in state[0]


def test_unknown_plugin_gets_state_hash_of_public_fields():
    unknown = SimpleNamespace(foo=1, bar="x")
    project = SimpleNamespace(channels=SimpleNamespace(instruments=[
        _mk_instrument("Mystery", unknown)
    ]))
    state = FLPluginParser(project).get_state()
    blob = json.dumps(unknown.__dict__, sort_keys=True, default=str).encode()
    assert state[0]["state_hash"] == hashlib.sha256(blob).hexdigest()


def test_no_plugin_returns_none_type():
    project = SimpleNamespace(channels=SimpleNamespace(instruments=[
        _mk_instrument("Empty", None)
    ]))
    state = FLPluginParser(project).get_state()
    assert state[0]["plugin_type"] is None
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/plugins/test_vst_fallback.py -v`
Expected: FAIL

- [ ] **Step 3: Rewrite parser/plugins.py**

```python
# src/fl_studio/parser/plugins.py
import hashlib
import json
from typing import Any
from src.fl_studio.plugins import find_adapter


class FLPluginParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_instrument(ch) for ch in self.project.channels.instruments]

    def _parse_instrument(self, instrument: Any) -> dict:
        plugin = instrument.plugin
        out = {
            "channel_name": instrument.name,
            "plugin_type": type(plugin).__name__ if plugin is not None else None,
            "insert": instrument.insert,
        }
        if plugin is None:
            return out

        adapter = find_adapter(plugin)
        if adapter is not None:
            out["params"] = adapter.extract(plugin)
            return out

        if hasattr(plugin, "raw_state_bytes"):
            out["state_hash"] = hashlib.sha256(plugin.raw_state_bytes).hexdigest()
            return out

        blob = json.dumps(plugin.__dict__, sort_keys=True, default=str).encode()
        out["state_hash"] = hashlib.sha256(blob).hexdigest()
        return out
```

- [ ] **Step 4: Run**

Run: `pytest tests/plugins/ -v`
Expected: PASS (all plugin tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/parser/plugins.py tests/plugins/test_vst_fallback.py
git commit -m "feat: plugin parser dispatches to adapters or state_hash fallback"
```

---

### Task 17: Plugin param-level differ

**Files:**
- Create: `src/fl_studio/diff/plugins.py`
- Create: `tests/diff/test_plugins.py`

- [ ] **Step 1: Failing test**

```python
# tests/diff/test_plugins.py
from src.fl_studio.diff.plugins import diff_plugins


def _plugin(channel_name, plugin_type="FruityReverb2", params=None, state_hash=None):
    p = {"channel_name": channel_name, "plugin_type": plugin_type, "insert": 1}
    if params is not None:
        p["params"] = params
    if state_hash is not None:
        p["state_hash"] = state_hash
    return p


def _param(name, unit, value):
    return {"name": name, "unit": unit, "value": value}


def test_identical_empty():
    p = [_plugin("Lead", params={"mix": _param("mix", "%", 35.0)})]
    assert diff_plugins(p, p) == {"added": [], "removed": [], "modified": []}


def test_param_changed():
    old = [_plugin("Lead", params={"mix": _param("mix", "%", 35.0)})]
    new = [_plugin("Lead", params={"mix": _param("mix", "%", 50.0)})]
    d = diff_plugins(old, new)
    mod = d["modified"][0]
    assert mod["channel_name"] == "Lead"
    assert mod["params"]["modified"][0]["name"] == "mix"
    assert mod["params"]["modified"][0]["old"] == 35.0
    assert mod["params"]["modified"][0]["new"] == 50.0
    assert mod["params"]["modified"][0]["unit"] == "%"


def test_plugin_swapped_shows_type_change():
    old = [_plugin("Lead", plugin_type="FruityReverb2", params={})]
    new = [_plugin("Lead", plugin_type="Harmor", params={})]
    d = diff_plugins(old, new)
    mod = d["modified"][0]
    assert mod["changes"]["plugin_type"] == {"old": "FruityReverb2", "new": "Harmor"}


def test_state_hash_change():
    old = [_plugin("Lead", plugin_type="Serum", state_hash="aaa")]
    new = [_plugin("Lead", plugin_type="Serum", state_hash="bbb")]
    d = diff_plugins(old, new)
    assert d["modified"][0]["state_hash_changed"] is True
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/diff/test_plugins.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/fl_studio/diff/plugins.py
from src.fl_studio.diff.model import SectionDiff, empty_section


def _diff_params(old_params: dict, new_params: dict) -> dict:
    out = empty_section()
    for k, p in new_params.items():
        if k not in old_params:
            out["added"].append(p)
    for k, p in old_params.items():
        if k not in new_params:
            out["removed"].append(p)
        elif old_params[k].get("value") != new_params[k].get("value"):
            out["modified"].append({
                "name": k,
                "unit": new_params[k].get("unit"),
                "old": old_params[k].get("value"),
                "new": new_params[k].get("value"),
            })
    return out


def diff_plugins(old: list, new: list) -> SectionDiff:
    old_by = {p["channel_name"]: p for p in old}
    new_by = {p["channel_name"]: p for p in new}

    result = empty_section()
    for name, p in new_by.items():
        if name not in old_by:
            result["added"].append(p)
    for name, p in old_by.items():
        if name not in new_by:
            result["removed"].append(p)
            continue

        op, np = old_by[name], new_by[name]
        changes = {}
        if op.get("plugin_type") != np.get("plugin_type"):
            changes["plugin_type"] = {"old": op.get("plugin_type"), "new": np.get("plugin_type")}
        if op.get("insert") != np.get("insert"):
            changes["insert"] = {"old": op.get("insert"), "new": np.get("insert")}

        params_diff = _diff_params(op.get("params", {}), np.get("params", {}))
        has_param_changes = any(params_diff[k] for k in ("added", "removed", "modified"))

        state_hash_changed = (
            op.get("state_hash") is not None
            and np.get("state_hash") is not None
            and op["state_hash"] != np["state_hash"]
        )

        if changes or has_param_changes or state_hash_changed:
            entry = {
                "channel_name": name,
                "plugin_type": np.get("plugin_type"),
            }
            if changes:
                entry["changes"] = changes
            if has_param_changes:
                entry["params"] = params_diff
            if state_hash_changed:
                entry["state_hash_changed"] = True
            result["modified"].append(entry)

    return result
```

- [ ] **Step 4: Run**

Run: `pytest tests/diff/test_plugins.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/plugins.py tests/diff/test_plugins.py
git commit -m "feat: add plugin differ with param-level and state_hash deltas"
```

---

## Phase 5: Orchestration & integration

### Task 18: Rewrite compare.py as orchestrator

**Files:**
- Modify: `src/fl_studio/diff/compare.py`
- Modify: `tests/diff/test_compare.py` (update for new tree shape)

- [ ] **Step 1: Replace compare.py**

```python
# src/fl_studio/diff/compare.py
from src.fl_studio.diff.model import DiffTree, empty_tree
from src.fl_studio.diff.metadata import diff_metadata
from src.fl_studio.diff.channels import diff_channels
from src.fl_studio.diff.patterns import diff_patterns
from src.fl_studio.diff.mixer import diff_mixer
from src.fl_studio.diff.plugins import diff_plugins
from src.fl_studio.diff.playlist import diff_playlist


def compare(old: dict, new: dict) -> DiffTree:
    return {
        "metadata": diff_metadata(old.get("metadata", {}), new.get("metadata", {})),
        "channels": diff_channels(old.get("channels", {}), new.get("channels", {})),
        "patterns": diff_patterns(old.get("patterns", []), new.get("patterns", [])),
        "mixer":    diff_mixer(old.get("mixer", []), new.get("mixer", [])),
        "plugins":  diff_plugins(old.get("plugins", []), new.get("plugins", [])),
        "playlist": diff_playlist(old.get("playlist", []), new.get("playlist", [])),
    }


def has_changes(diff: DiffTree) -> bool:
    if diff["metadata"]:
        return True
    for section in ("channels", "patterns", "mixer", "plugins", "playlist"):
        s = diff[section]
        if s["added"] or s["removed"] or s["modified"]:
            return True
    return False
```

- [ ] **Step 2: Update existing test_compare.py**

Replace the file with integration tests over the full orchestrator:

```python
# tests/diff/test_compare.py
from src.fl_studio.diff.compare import compare, has_changes


BASE_STATE = {
    "metadata": {"tempo": 140.0, "title": "T", "artists": "", "genre": "",
                 "version": "21", "ppq": 96},
    "channels": {"rack_settings": {}, "groups": [],
                 "channels": {"samplers": [], "instruments": [], "layers": [],
                              "automations": []}},
    "patterns": [],
    "mixer": [],
    "plugins": [],
    "playlist": [],
}


def test_identical_has_no_changes():
    d = compare(BASE_STATE, BASE_STATE)
    assert has_changes(d) is False


def test_tempo_change_flagged():
    new = {**BASE_STATE, "metadata": {**BASE_STATE["metadata"], "tempo": 150.0}}
    d = compare(BASE_STATE, new)
    assert has_changes(d) is True
    assert d["metadata"]["tempo"]["new"] == 150.0


def test_tree_shape_always_present():
    d = compare(BASE_STATE, BASE_STATE)
    for section in ("channels", "patterns", "mixer", "plugins", "playlist"):
        assert set(d[section].keys()) == {"added", "removed", "modified"}
```

- [ ] **Step 3: Run all diff tests**

Run: `pytest tests/diff/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/fl_studio/diff/compare.py tests/diff/test_compare.py
git commit -m "feat: rewrite compare.py as orchestrator over per-section differs"
```

---

### Task 19: Rich renderer for new tree shape

**Files:**
- Create: `src/cli/render.py`
- Create: `tests/cli/test_render.py`
- Modify: `src/cli/cli.py:11-37` (remove old `_render_diff`; import from render module)

- [ ] **Step 1: Failing test**

```python
# tests/cli/test_render.py
from rich.console import Console
from src.cli.render import render_diff
from src.fl_studio.diff.model import empty_tree


def _capture(diff):
    console = Console(record=True, width=100, force_terminal=False)
    render_diff(diff, console)
    return console.export_text()


def test_empty_diff_prints_nothing_changed():
    out = _capture(empty_tree())
    assert "Nothing changed" in out


def test_metadata_change_rendered():
    d = empty_tree()
    d["metadata"] = {"tempo": {"old": 140.0, "new": 150.0}}
    out = _capture(d)
    assert "tempo" in out
    assert "140" in out and "150" in out


def test_channel_modified_with_volume_change():
    d = empty_tree()
    d["channels"]["modified"].append({
        "internal_name": "Kick",
        "name": "Kick",
        "changes": {"volume": {"old": 12800, "new": 10000}},
    })
    out = _capture(d)
    assert "Kick" in out
    assert "volume" in out


def test_note_added_rendered():
    d = empty_tree()
    d["patterns"]["modified"].append({
        "iid": 1,
        "name": "Verse",
        "notes": {
            "added": [{"key": 64, "position": 96, "length": 96, "velocity": 100,
                       "pan": 0, "fine_pitch": 0, "rack_channel": 1, "slide": False}],
            "removed": [], "modified": [],
        },
    })
    out = _capture(d)
    assert "Verse" in out
    assert "+" in out  # indicates addition


def test_plugin_param_change_shows_unit():
    d = empty_tree()
    d["plugins"]["modified"].append({
        "channel_name": "Lead",
        "plugin_type": "FruityReverb2",
        "params": {
            "added": [], "removed": [],
            "modified": [{"name": "mix", "unit": "%", "old": 35.0, "new": 50.0}],
        },
    })
    out = _capture(d)
    assert "mix" in out
    assert "%" in out
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/cli/test_render.py -v`
Expected: FAIL

- [ ] **Step 3: Implement renderer**

```python
# src/cli/render.py
from rich.console import Console
from src.fl_studio.diff.model import DiffTree
from src.fl_studio.diff.compare import has_changes


def render_diff(diff: DiffTree, console: Console) -> None:
    if not has_changes(diff):
        console.print("Nothing changed since last commit.")
        return

    if diff["metadata"]:
        console.print("[bold yellow]Metadata:[/bold yellow]")
        for field, chg in diff["metadata"].items():
            console.print(f"  {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")

    _render_channels(diff["channels"], console)
    _render_patterns(diff["patterns"], console)
    _render_mixer(diff["mixer"], console)
    _render_plugins(diff["plugins"], console)
    _render_playlist(diff["playlist"], console)


def _render_channels(section, console):
    if not _any(section):
        return
    console.print("\n[bold cyan]Channels:[/bold cyan]")
    for ch in section["added"]:
        console.print(f"  [green]+ {ch.get('base', {}).get('name', '?')}[/green]")
    for ch in section["removed"]:
        console.print(f"  [red]- {ch.get('base', {}).get('name', '?')}[/red]")
    for mod in section["modified"]:
        console.print(f"  [yellow]~ {mod['name']}[/yellow]")
        for field, chg in mod["changes"].items():
            console.print(f"    {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")


def _render_patterns(section, console):
    if not _any(section):
        return
    console.print("\n[bold cyan]Patterns:[/bold cyan]")
    for p in section["added"]:
        console.print(f"  [green]+ {p.get('name', '?')}[/green]")
    for p in section["removed"]:
        console.print(f"  [red]- {p.get('name', '?')}[/red]")
    for mod in section["modified"]:
        console.print(f"  [yellow]~ {mod['name']}[/yellow]")
        for field, chg in (mod.get("changes") or {}).items():
            console.print(f"    {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")
        notes = mod.get("notes")
        if notes:
            for n in notes["added"]:
                console.print(f"    [green]+ note key={n['key']} pos={n['position']}[/green]")
            for n in notes["removed"]:
                console.print(f"    [red]- note key={n['key']} pos={n['position']}[/red]")
            for nm in notes["modified"]:
                k = nm["key"]
                console.print(f"    [yellow]~ note key={k['key']} pos={k['position']}[/yellow]")
                for field, chg in nm["changes"].items():
                    console.print(f"      {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")


def _render_mixer(section, console):
    if not _any(section):
        return
    console.print("\n[bold cyan]Mixer:[/bold cyan]")
    for ins in section["added"]:
        console.print(f"  [green]+ {ins.get('name', '?')}[/green]")
    for ins in section["removed"]:
        console.print(f"  [red]- {ins.get('name', '?')}[/red]")
    for mod in section["modified"]:
        console.print(f"  [yellow]~ {mod['name']}[/yellow]")
        for field, chg in (mod.get("changes") or {}).items():
            console.print(f"    {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")
        slots = mod.get("slots")
        if slots:
            for s in slots["added"]:
                console.print(f"    [green]+ slot[{s['slot_index']}] {s.get('name')}[/green]")
            for s in slots["removed"]:
                console.print(f"    [red]- slot[{s['slot_index']}] {s.get('name')}[/red]")
            for sm in slots["modified"]:
                console.print(f"    [yellow]~ slot[{sm['slot_index']}][/yellow]")
                for field, chg in sm["changes"].items():
                    console.print(f"      {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")


def _render_plugins(section, console):
    if not _any(section):
        return
    console.print("\n[bold cyan]Plugins:[/bold cyan]")
    for p in section["added"]:
        console.print(f"  [green]+ {p['channel_name']} ({p['plugin_type']})[/green]")
    for p in section["removed"]:
        console.print(f"  [red]- {p['channel_name']}[/red]")
    for mod in section["modified"]:
        console.print(f"  [yellow]~ {mod['channel_name']} ({mod['plugin_type']})[/yellow]")
        for field, chg in (mod.get("changes") or {}).items():
            console.print(f"    {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")
        params = mod.get("params")
        if params:
            for pm in params["modified"]:
                console.print(f"    {pm['name']} ({pm['unit']}): "
                              f"[red]{pm['old']}[/red] -> [green]{pm['new']}[/green]")
            for pm in params["added"]:
                console.print(f"    [green]+ param {pm['name']} = {pm['value']} {pm['unit']}[/green]")
            for pm in params["removed"]:
                console.print(f"    [red]- param {pm['name']}[/red]")
        if mod.get("state_hash_changed"):
            console.print("    [yellow]VST state changed (opaque)[/yellow]")


def _render_playlist(section, console):
    if not _any(section):
        return
    console.print("\n[bold cyan]Playlist:[/bold cyan]")
    for a in section["added"]:
        console.print(f"  [green]+ arrangement {a.get('name')}[/green]")
    for a in section["removed"]:
        console.print(f"  [red]- arrangement {a.get('name')}[/red]")
    for mod in section["modified"]:
        console.print(f"  [yellow]~ arrangement {mod['name']}[/yellow]")
        tracks = mod.get("tracks", {})
        for t in tracks.get("added", []):
            console.print(f"    [green]+ track {t.get('name')}[/green]")
        for t in tracks.get("removed", []):
            console.print(f"    [red]- track {t.get('name')}[/red]")
        for tm in tracks.get("modified", []):
            console.print(f"    [yellow]~ track {tm['name']}[/yellow]")
            items = tm.get("items", {})
            for i in items.get("added", []):
                ref = i.get("ref") or {}
                console.print(f"      [green]+ item pos={i['position']} -> {ref.get('name')}[/green]")
            for i in items.get("removed", []):
                ref = i.get("ref") or {}
                console.print(f"      [red]- item pos={i['position']} -> {ref.get('name')}[/red]")
            for im in items.get("modified", []):
                k = im["key"]
                console.print(f"      [yellow]~ item pos={k['position']}[/yellow]")
                for field, chg in im["changes"].items():
                    console.print(f"        {field}: [red]{chg['old']}[/red] -> [green]{chg['new']}[/green]")


def _any(section) -> bool:
    return bool(section["added"] or section["removed"] or section["modified"])
```

- [ ] **Step 4: Remove old `_render_diff` from cli.py**

In `src/cli/cli.py`, delete lines 11–37 (the `_render_diff` function) and the two call sites replace with:

```python
from src.cli.render import render_diff
# ...
# In status():
render_diff(diff_result, console)
# In diff():
render_diff(diff_result, console)
```

Also remove the `has_changes` manual check in `status`; use `render_diff` directly (it prints "Nothing changed" itself). Or keep `console.print("Nothing changed...")` guarded by `has_changes(diff_result)` — pick one. Simplest: drop the check, rely on renderer.

Exact `status` body becomes:

```python
from src.fl_studio.parser.base import FLParser
old_state = FLParser(head_flp).get_state()
new_state = FLParser(Path(project)).get_state()
diff_result = compare(old_state, new_state)
render_diff(diff_result, console)
```

- [ ] **Step 5: Run**

Run: `pytest tests/cli/test_render.py tests/diff/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/cli/render.py tests/cli/test_render.py src/cli/cli.py
git commit -m "feat: rich renderer for new tree-shaped diff; cli uses it"
```

---

### Task 20: `daw diff --json` output mode

**Files:**
- Modify: `src/cli/cli.py` — `diff` command

- [ ] **Step 1: Add failing test**

First read `tests/test_cli.py` to see its runner setup. Then append:

```python
# tests/test_cli.py — append
import json as _json
from click.testing import CliRunner
from src.cli.cli import cli


def test_diff_json_flag_emits_json_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Stub FLParser so we don't need real .flp bytes
    states = iter([
        {"metadata": {"tempo": 140.0}, "channels": {"channels": {"samplers": [],
         "instruments": [], "layers": [], "automations": []}}, "patterns": [],
         "mixer": [], "plugins": [], "playlist": []},
        {"metadata": {"tempo": 150.0}, "channels": {"channels": {"samplers": [],
         "instruments": [], "layers": [], "automations": []}}, "patterns": [],
         "mixer": [], "plugins": [], "playlist": []},
    ])

    class FakeParser:
        def __init__(self, p): pass
        def get_state(self): return next(states)

    monkeypatch.setattr("src.fl_studio.parser.base.FLParser", FakeParser)

    runner = CliRunner()
    (tmp_path / "song.flp").write_bytes(b"v1")
    runner.invoke(cli, ["init"], catch_exceptions=False)
    runner.invoke(cli, ["add", "song.flp"], catch_exceptions=False)
    runner.invoke(cli, ["commit", "c1"], catch_exceptions=False)

    (tmp_path / "song.flp").write_bytes(b"v2")
    runner.invoke(cli, ["add", "song.flp"], catch_exceptions=False)
    runner.invoke(cli, ["commit", "c2"], catch_exceptions=False)

    result = runner.invoke(cli, ["diff", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    data = _json.loads(result.output)
    assert set(data.keys()) == {"metadata", "channels", "patterns", "mixer",
                                "plugins", "playlist"}
    assert data["metadata"]["tempo"]["new"] == 150.0
```

- [ ] **Step 2: Add --json flag to diff command**

In `src/cli/cli.py`, modify `diff`:

```python
@cli.command()
@click.argument('hash1', required=False)
@click.argument('hash2', required=False)
@click.option('--json', 'json_out', is_flag=True, default=False, help='Emit diff as JSON instead of rendering')
def diff(hash1, hash2, json_out):
    """Show diff between two commits (default: HEAD~1 vs HEAD)."""
    import json as _json
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    commits = json.loads(vc.commits_file.read_text())
    if len(commits) < 2:
        console.print("Need at least 2 commits to diff.")
        return

    if hash1 is None and hash2 is None:
        h1, h2 = commits[-2]["hash"], commits[-1]["hash"]
    elif hash2 is None:
        raise click.ClickException("Provide both hash1 and hash2, or neither.")
    else:
        h1, h2 = hash1, hash2

    from src.vc.blob import blob_path
    c1 = next((c for c in commits if c["hash"] == h1), None)
    c2 = next((c for c in commits if c["hash"] == h2), None)
    if not c1 or not c2 or not c1.get("blob_sha") or not c2.get("blob_sha"):
        raise click.ClickException("Commit or blob not found (run 'daw migrate'?)")

    flp1 = blob_path(vc.objects_dir, c1["blob_sha"])
    flp2 = blob_path(vc.objects_dir, c2["blob_sha"])
    for p in (flp1, flp2):
        if not p.exists():
            raise click.ClickException(f"Snapshot not found: {p}")

    from src.fl_studio.parser.base import FLParser
    old_state = FLParser(flp1).get_state()
    new_state = FLParser(flp2).get_state()
    diff_result = compare(old_state, new_state)

    if json_out:
        click.echo(_json.dumps(diff_result, indent=2, default=str))
    else:
        render_diff(diff_result, console)
```

Do the same `blob_path` substitution in `status` (replaces `head_flp = vc.objects_dir / f"{head_hash}.flp"`).

- [ ] **Step 3: Run all tests**

Run: `pytest -v`
Expected: PASS (or existing test_cli.py tests may need small updates for blob_sha paths)

- [ ] **Step 4: Commit**

```bash
git add src/cli/cli.py tests/test_cli.py
git commit -m "feat: add daw diff --json and route status/diff through blob_sha paths"
```

---

### Task 21: Cache diff JSON at commit time

**Files:**
- Modify: `src/vc/engine.py` — `commit()`

- [ ] **Step 1: Failing test**

Append to `tests/vc/test_engine.py`:

```python
import json as _json

def test_commit_writes_diff_cache_against_parent(tmp_path: Path, monkeypatch):
    """After the second commit, a .diff.json should exist for the new blob."""
    # Skip if pyflp can't read our fake .flp — the engineer should use a real
    # fixture here. For now, stub FLParser to return a synthetic state.
    import src.vc.engine as eng
    from src.fl_studio.diff.compare import compare

    states = iter([
        {"metadata": {"tempo": 140.0}, "channels": {}, "patterns": [], "mixer": [],
         "plugins": [], "playlist": []},
        {"metadata": {"tempo": 150.0}, "channels": {}, "patterns": [], "mixer": [],
         "plugins": [], "playlist": []},
    ])

    class FakeParser:
        def __init__(self, p): self.p = p
        def get_state(self): return next(states)

    monkeypatch.setattr("src.fl_studio.parser.base.FLParser", FakeParser)

    (tmp_path / "song.flp").write_bytes(b"v1")
    vc = DawVC(tmp_path)
    vc.init()
    vc.add(tmp_path / "song.flp")
    vc.commit("c1")

    (tmp_path / "song.flp").write_bytes(b"v2")
    vc.add(tmp_path / "song.flp")
    vc.commit("c2")

    commits = vc.get_commits()
    blob_sha = commits[-1]["blob_sha"]
    cache = vc.objects_dir / f"{blob_sha}.diff.json"
    assert cache.exists()
    data = _json.loads(cache.read_text())
    assert data["metadata"]["tempo"]["new"] == 150.0
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/vc/test_engine.py -v -k "diff_cache"`
Expected: FAIL

- [ ] **Step 3: Add diff caching to commit**

In `src/vc/engine.py::commit`, after the blob is written but before `commits.append(...)`, compute and cache the diff:

```python
# After: dest = blob_path(self.objects_dir, blob_sha); copy/ reuse
# Before: appending commit to commits list

parent_hash = state["head"]
parent = next((c for c in commits if c["hash"] == parent_hash), None)
if parent and parent.get("blob_sha") and blob_sha:
    parent_blob = blob_path(self.objects_dir, parent["blob_sha"])
    if parent_blob.exists() and blob_sha != parent["blob_sha"]:
        from src.fl_studio.parser.base import FLParser
        from src.fl_studio.diff.compare import compare
        old_state = FLParser(parent_blob).get_state()
        new_state = FLParser(blob_path(self.objects_dir, blob_sha)).get_state()
        diff_data = compare(old_state, new_state)
        cache_path = self.objects_dir / f"{blob_sha}.diff.json"
        cache_path.write_text(json.dumps(diff_data, default=str))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/vc/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vc/engine.py tests/vc/test_engine.py
git commit -m "feat: cache structured diff JSON alongside blob at commit time"
```

---

### Task 22: Push includes diff JSON in Supabase commits row

**Files:**
- Modify: `src/remote/sync.py::push`
- Modify: `src/remote/supabase_client.py::insert_commit` (accept/pass `diff` field)

- [ ] **Step 1: Failing test**

Append to `tests/remote/test_sync.py`:

```python
def test_push_passes_diff_json_to_supabase(tmp_path: Path):
    (tmp_path / "song.flp").write_bytes(b"v1")
    vc = DawVC(tmp_path)
    vc.init()
    vc.add(tmp_path / "song.flp")
    vc.commit("c1")

    # Simulate a second commit + cached diff file
    from src.vc.blob import hash_file
    (tmp_path / "song.flp").write_bytes(b"v2")
    vc.add(tmp_path / "song.flp")
    vc.commit("c2")
    blob_sha = hash_file(tmp_path / "song.flp")
    diff_path = vc.objects_dir / f"{blob_sha}.diff.json"
    diff_path.write_text('{"metadata": {"tempo": {"old": 140, "new": 150}}}')

    remote = MagicMock()
    remote.ensure_project.return_value = "proj"
    remote.head_blob.return_value = False

    push(vc, remote, project_name="p", owner="me")

    # Inspect call args: second insert_commit should have diff dict attached
    last_call = remote.insert_commit.call_args_list[-1]
    commit_arg = last_call.args[1] if len(last_call.args) > 1 else last_call.kwargs.get("commit")
    assert "diff" in commit_arg
    assert commit_arg["diff"]["metadata"]["tempo"]["new"] == 150
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/remote/test_sync.py -v -k "diff_json"`
Expected: FAIL

- [ ] **Step 3: Augment push**

In `src/remote/sync.py::push`, load the cached diff before inserting the commit:

```python
for commit in to_push:
    blob_sha = commit.get("blob_sha")
    if blob_sha:
        from src.vc.blob import blob_path
        local_blob = blob_path(vc.objects_dir, blob_sha)
        if local_blob.exists() and not remote.head_blob(project_id, blob_sha):
            remote.upload_blob(project_id, blob_sha, local_blob)

        cache = vc.objects_dir / f"{blob_sha}.diff.json"
        if cache.exists():
            commit = {**commit, "diff": json.loads(cache.read_text())}

    remote.insert_commit(project_id, commit)
```

- [ ] **Step 4: Update supabase_client.insert_commit**

If `insert_commit` currently only inserts `hash/message/branch/timestamp/parent_hash`, add `blob_sha` and `diff` to the inserted row:

```python
def insert_commit(self, project_id: str, commit: dict) -> None:
    row = {
        "hash": commit["hash"],
        "message": commit["message"],
        "branch": commit["branch"],
        "timestamp": commit["timestamp"],
        "parent_hash": commit.get("parent_hash"),
        "project_id": project_id,
        "blob_sha": commit.get("blob_sha"),
        "diff": commit.get("diff"),
    }
    self.client.table("commits").insert(row).execute()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/remote/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/remote/sync.py src/remote/supabase_client.py tests/remote/test_sync.py
git commit -m "feat: push includes structured diff and blob_sha in Supabase commits"
```

---

## Phase 6: Fixtures, E2E, and docs

### Task 23: README updates for new features

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Supabase SQL block**

In `README.md`, update the `CREATE TABLE IF NOT EXISTS commits` block to add `blob_sha TEXT NOT NULL`:

```sql
CREATE TABLE IF NOT EXISTS commits (
    hash TEXT PRIMARY KEY,
    message TEXT NOT NULL,
    branch TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    project_id UUID REFERENCES projects(id),
    parent_hash TEXT,
    blob_sha TEXT NOT NULL,
    diff JSONB
);
```

Add a "Migration" subsection with:
```
### Migration from pre-0.2 repos

If your repo was created before content-addressed storage, run:

`daw migrate`

This renames `.daw/objects/<commit_hash>.flp` files to `<blob_sha>` and
annotates `commits.json` with the new field. Safe to re-run.
```

- [ ] **Step 2: Document `daw diff --json`**

Under the existing `daw diff` section, add:
```
daw diff --json             # machine-readable JSON
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document content-addressed blobs, migrate, and diff --json"
```

---

### Task 24: End-to-end test — commit two .flp files and diff

*Requires fixtures from Phase 0.*

**Files:**
- Create: `tests/e2e/__init__.py` (empty)
- Create: `tests/e2e/test_commit_diff.py`

- [ ] **Step 1: Write the E2E test**

```python
# tests/e2e/test_commit_diff.py
import shutil
from pathlib import Path
from click.testing import CliRunner
from src.cli.cli import cli


FIXTURES = Path(__file__).parent.parent / "fixtures" / "flp" / "diff"


def _require_fixture(name: str) -> Path:
    p = FIXTURES / name
    if not p.exists():
        import pytest
        pytest.skip(f"Fixture {name} not generated yet — see Phase 0 of plan")
    return p


def test_commit_tempo_change_surfaces_in_diff(tmp_path: Path):
    baseline = _require_fixture("baseline.flp")
    changed = _require_fixture("tempo_changed.flp")

    work = tmp_path / "proj"
    work.mkdir()
    shutil.copy(baseline, work / "song.flp")

    runner = CliRunner()
    result = runner.invoke(cli, ["init"], catch_exceptions=False)
    # Run commands inside work dir
    import os
    os.chdir(work)

    runner.invoke(cli, ["init"], catch_exceptions=False)
    runner.invoke(cli, ["add", "song.flp"], catch_exceptions=False)
    runner.invoke(cli, ["commit", "baseline"], catch_exceptions=False)

    shutil.copy(changed, work / "song.flp")
    runner.invoke(cli, ["add", "song.flp"], catch_exceptions=False)
    runner.invoke(cli, ["commit", "tempo"], catch_exceptions=False)

    result = runner.invoke(cli, ["diff"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "tempo" in result.output.lower()


def test_commit_note_added_shows_in_diff(tmp_path: Path):
    baseline = _require_fixture("baseline.flp")
    changed = _require_fixture("note_added.flp")

    work = tmp_path / "proj"
    work.mkdir()
    shutil.copy(baseline, work / "song.flp")

    runner = CliRunner()
    import os
    os.chdir(work)

    runner.invoke(cli, ["init"], catch_exceptions=False)
    runner.invoke(cli, ["add", "song.flp"], catch_exceptions=False)
    runner.invoke(cli, ["commit", "baseline"], catch_exceptions=False)

    shutil.copy(changed, work / "song.flp")
    runner.invoke(cli, ["add", "song.flp"], catch_exceptions=False)
    runner.invoke(cli, ["commit", "note"], catch_exceptions=False)

    result = runner.invoke(cli, ["diff"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "note" in result.output.lower() or "+" in result.output
```

- [ ] **Step 2: Run**

Run: `pytest tests/e2e/ -v`
Expected: PASS if fixtures present; SKIP otherwise.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/
git commit -m "test: add end-to-end commit+diff tests (fixture-gated)"
```

---

### Task 25: Golden-text snapshot tests for renderer

**Files:**
- Create: `tests/fixtures/rendered/tempo_change.txt`
- Create: `tests/fixtures/rendered/note_added.txt`
- Create: `tests/fixtures/rendered/reverb_knob.txt`
- Modify: `tests/cli/test_render.py`

- [ ] **Step 1: Generate golden outputs**

Run a small script inside the repo that feeds known diff trees into the renderer and captures output. For the first time, run it once, pipe output to the fixture file, then use that as the golden. Example helper added to the test file:

```python
# tests/cli/test_render.py (append)
from pathlib import Path

GOLDEN = Path(__file__).parent.parent / "fixtures" / "rendered"


def _read_golden(name: str) -> str:
    return (GOLDEN / name).read_text()


def test_snapshot_tempo_change():
    d = empty_tree()
    d["metadata"] = {"tempo": {"old": 140.0, "new": 150.0}}
    assert _capture(d).strip() == _read_golden("tempo_change.txt").strip()


def test_snapshot_note_added():
    d = empty_tree()
    d["patterns"]["modified"].append({
        "iid": 1, "name": "Verse",
        "notes": {
            "added": [{"key": 64, "position": 96, "length": 96, "velocity": 100,
                       "pan": 0, "fine_pitch": 0, "rack_channel": 1, "slide": False}],
            "removed": [], "modified": [],
        },
    })
    assert _capture(d).strip() == _read_golden("note_added.txt").strip()


def test_snapshot_reverb_knob():
    d = empty_tree()
    d["plugins"]["modified"].append({
        "channel_name": "Lead",
        "plugin_type": "FruityReverb2",
        "params": {
            "added": [], "removed": [],
            "modified": [{"name": "mix", "unit": "%", "old": 35.0, "new": 50.0}],
        },
    })
    assert _capture(d).strip() == _read_golden("reverb_knob.txt").strip()
```

- [ ] **Step 2: Bootstrap golden files**

Run once with `_capture(d)` printed to stdout for each of the three cases, save as `.txt` under `tests/fixtures/rendered/`. A small inline `python -c` in the terminal is fine:

```bash
python -c "
from rich.console import Console
from src.fl_studio.diff.model import empty_tree
from src.cli.render import render_diff
c = Console(record=True, width=100, force_terminal=False)
d = empty_tree(); d['metadata'] = {'tempo': {'old': 140.0, 'new': 150.0}}
render_diff(d, c)
print(c.export_text())" > tests/fixtures/rendered/tempo_change.txt
```

Repeat for the other two.

- [ ] **Step 3: Run snapshot tests**

Run: `pytest tests/cli/test_render.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/rendered/ tests/cli/test_render.py
git commit -m "test: golden-text snapshot tests for rendered diffs"
```

---

### Task 26: Final regression run

- [ ] **Step 1: Run full suite**

Run: `pytest -v`
Expected: ALL tests pass (E2E may skip if fixtures absent — that's acceptable).

- [ ] **Step 2: Spot-check a real .flp if available**

If the user has a real `.flp`, have them:
```bash
cd ~/Music/SomeProject
daw init
daw add Song.flp
daw commit "before"
# edit in FL Studio, save
daw add Song.flp
daw commit "after"
daw diff
daw diff --json | jq .
```

Confirm output is sensible (metadata/channels/patterns appear).

- [ ] **Step 3: Commit anything that fell out (likely nothing)**

```bash
git status
# If clean, nothing to do.
```

---

## Summary of commits

1. feat: add content-addressed blob hashing helpers
2. feat: commit stores .flp bytes under content-addressed blob_sha
3. feat: checkout and merge restore files via blob_sha
4. feat: add daw migrate for legacy commit-hash object paths
5. feat: remote sync uses blob_sha paths with HEAD-check dedup
6. feat: add diff tree type definitions
7. feat: add metadata differ
8. feat: add channel differ with internal_name identity key
9. feat: add pattern differ with per-note detection
10. feat: add mixer differ with insert and slot diffs
11. feat: add playlist differ with track and item diffs
12. feat: add plugin adapter protocol and registry
13. feat: add FruityBalance plugin adapter
14. feat: add FruityFilter plugin adapter
15. feat: add FruityReverb2 plugin adapter
16. feat: plugin parser dispatches to adapters or state_hash fallback
17. feat: add plugin differ with param-level and state_hash deltas
18. feat: rewrite compare.py as orchestrator over per-section differs
19. feat: rich renderer for new tree-shaped diff; cli uses it
20. feat: add daw diff --json and route status/diff through blob_sha paths
21. feat: cache structured diff JSON alongside blob at commit time
22. feat: push includes structured diff and blob_sha in Supabase commits
23. docs: document content-addressed blobs, migrate, and diff --json
24. test: add end-to-end commit+diff tests (fixture-gated)
25. test: golden-text snapshot tests for rendered diffs

26 tasks, 26 commits (Task 26 is verification only and may not generate a commit).
