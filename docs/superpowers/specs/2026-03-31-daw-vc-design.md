# DAW Version Control — Design Spec
Date: 2026-03-31

## Overview

A Git-like version control system for FL Studio `.flp` project files. Tracks musical changes (channels, patterns, mixer, playlist), supports branching and merging, and syncs to a Supabase cloud backend. Designed to eventually integrate into FL Studio as a plugin (Part D, separate spec).

## Architecture

Four layers, each built on the previous:

```
┌─────────────────────────────────────┐
│           CLI  (click)              │
├─────────────────────────────────────┤
│         VC Engine  (.daw/)          │
├──────────────────┬──────────────────┤
│   Parser         │   Diff Engine    │
│ (pyflp wrapper)  │  (compare.py)    │
├──────────────────┴──────────────────┤
│        Supabase Remote              │
└─────────────────────────────────────┘
```

## Part A: Parser + Diff Engine

### Parser

All sub-parsers return plain JSON-serializable dicts. `FLParser.get_state()` orchestrates all modules into one unified snapshot dict.

| Module | Status | Covers |
|---|---|---|
| `parser/base.py` | exists, partial | metadata, orchestrates sub-parsers |
| `parser/channels.py` | exists, complete | samplers, instruments, layers, automations |
| `parser/patterns.py` | stub → implement | note patterns, pitch, length, velocity, pan |
| `parser/mixer.py` | stub → implement | mixer tracks, FX slots, routing, EQ, sends |
| `parser/plugins.py` | stub → implement | plugin name, preset, per-parameter values |
| `parser/playlist.py` | new | playlist clips, arrangement, track order |

**Constraint:** only expose what `pyflp` provides — no custom binary parsing.

### Diff Engine

`diff/compare.py` — pure function, no I/O.

```python
def compare(old: dict, new: dict) -> dict
```

Output structure:
```json
{
  "metadata": { "tempo": {"old": 140, "new": 150} },
  "channels": {
    "added": [...],
    "removed": [...],
    "modified": [{ "name": "Kick", "changes": { "volume": {"old": 0.8, "new": 1.0} } }]
  },
  "patterns": { "added": [...], "removed": [...], "modified": [...] },
  "mixer": { "added": [...], "removed": [...], "modified": [...] },
  "playlist": { "added": [...], "removed": [...], "modified": [...] }
}
```

CLI renders this JSON diff as human-readable output via `rich`. JSON diff is also stored as a sidecar in Supabase per commit.

## Part B: VC Engine + Branching

### Local Storage (`.daw/` per project)

```
.daw/
  state.json        # HEAD commit hash, current branch name, last_pushed_hash
  commits.json      # list of all commits: hash, message, branch, timestamp, parent_hash
  staged.json       # staged .flp paths awaiting commit
  branches.json     # branch name → commit hash
  objects/          # raw .flp snapshots keyed by {hash}.flp
```

### Data Model

```python
@dataclass
class Commit:
    hash: str           # 8-char SHA1 of timestamp
    message: str
    timestamp: str      # ISO 8601
    branch: str
    parent_hash: str    # None for initial commit
    changes: dict       # diff JSON sidecar
```

### CLI Commands

| Command | Behavior |
|---|---|
| `daw init` | Create `.daw/` structure, initialize `main` branch |
| `daw add <project.flp>` | Parse + stage the .flp snapshot |
| `daw commit -m "msg"` | Copy `.flp` to `objects/{hash}.flp`, record commit |
| `daw status <project.flp>` | Compare working file vs HEAD, show diff summary |
| `daw diff [hash1] [hash2]` | Compare two commits (default: HEAD vs working) |
| `daw log` | Pretty-print commit history via `rich` |
| `daw branch <name>` | Create branch pointing to current HEAD |
| `daw checkout <branch/hash>` | Restore `.flp` from `objects/` to working directory |
| `daw merge <branch>` | Three-way merge; report conflicts for manual resolution |

### Merge Strategy

Entities (channels, patterns) identified by `name` field. If both branches modify the same named entity differently → conflict reported, user resolves manually. Non-conflicting changes are auto-merged into a new commit.

## Part C: Supabase Remote

### Supabase Schema

**Tables:**
- `projects` — `id`, `name`, `owner`, `created_at`
- `commits` — `hash`, `message`, `branch`, `timestamp`, `project_id`, `parent_hash`, `diff` (jsonb)

**Storage bucket:** `objects`
- Path: `{project_id}/{commit_hash}.flp`

### Global Config

`~/.daw/config.json` — stores Supabase project URL + anon key. Populated on first `daw push` via interactive prompt.

### CLI Commands

| Command | Behavior |
|---|---|
| `daw push` | Upload unpushed commits (blobs + metadata) to Supabase |
| `daw pull` | Fetch remote commits not in local history, update branch pointer |
| `daw clone <project-id>` | Pull full remote project into new local `.daw/` repo |

### Push Flow
1. Find commits since `last_pushed_hash` (from `state.json`)
2. Upload each `.flp` blob to Supabase storage
3. Insert commit rows into `commits` table
4. Update `last_pushed_hash` in `state.json`

### Pull Flow
1. Fetch commits from Supabase newer than `last_pushed_hash` on current branch
2. Download `.flp` blobs into local `objects/`
3. Fast-forward branch pointer if no local divergence
4. If diverged: require `daw merge` before allowing push (same as git non-fast-forward)

## Part D: FL Studio Plugin

Deferred — separate spec. Options under consideration: MIDI Remote Script (Python), native VST (C++), or external companion app (Tauri/Electron). Decision pending after Parts A–C are complete.

## Dependencies

- `pyflp==2.2.1` — FL Studio project parser
- `click` — CLI framework
- `rich` — terminal output formatting
- `supabase-py` — Supabase client (add to requirements.txt for Part C)
- `PyYAML` — already in requirements, available for config files

## Out of Scope

- Binary diffing of audio samples referenced by the project
- Real-time sync (file watcher) — future enhancement
- Multi-user conflict resolution UI — manual resolution only for now
