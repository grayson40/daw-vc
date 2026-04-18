# FL Studio Diff System — Design

**Date:** 2026-04-18
**Scope:** FL Studio `.flp` files only
**Status:** Approved design, ready for implementation plan

## Goal

Produce trustworthy, human-readable diffs between two `.flp` versions with enough fidelity to see plugin-knob-level deltas and per-note position changes. Store diffs efficiently alongside content-addressed file blobs so commits stay small and push/pull is fast.

**Priorities (ranked):**
1. Human-readable changelog
2. Storage efficiency
3. Merge conflict detection
4. Foundation for collaboration features

## Non-goals

- VST plugin parameter introspection (opaque blobs — `state_hash` fallback only).
- Headless FL Studio / VM-based rendering comparison (FL has no scriptable diff mode).
- Delta compression between blobs (raw `.flp` bytes; dedup alone is the 80% win).
- Auto-generated adapters for all 80+ native FL plugins (grows as needed).
- Performance tuning for large files.

## Architecture

Four layers, each independently testable:

```
parser  →  canonical model  →  differ  →  renderer
 (pyflp)    (normalized dict)   (tree)     (rich TTY / JSON)
```

- **parser**: `src/fl_studio/parser/*` — already exists; wraps `pyflp`.
- **canonical model**: normalized dict produced by `FLParser.get_state()`, augmented by plugin adapters.
- **differ**: `src/fl_studio/diff/compare.py` — walks two canonical models, emits structured tree diff.
- **renderer**: `src/cli/cli.py::_render_diff` for TTY; same diff tree also serializable to JSON for the remote and `daw diff --json`.

## Canonical model & identity keys

Identity keys are how the differ pairs objects across two versions. Without stable keys, renaming a channel reads as `delete + add` instead of `modified`.

| Object       | Identity key                                     | Notes                                                          |
|--------------|--------------------------------------------------|----------------------------------------------------------------|
| metadata     | —                                                | single scalar bag; no keying needed                            |
| channel      | `internal_name` (falls back to `iid`)            | survives display-name renames                                  |
| pattern      | `iid`                                            | FL assigns stable internal id                                  |
| note         | `(rack_channel, key, position)` composite        | allows per-note detection; see "note moves" below              |
| mixer insert | `iid`                                            | FL insert index                                                |
| mixer slot   | `(insert_iid, slot_index)`                       | position within insert matters for signal chain                |
| plugin       | `channel_name` (for instrument plugins)          | adapter decides param-level keying internally                  |
| arrangement  | `iid`                                            |                                                                |
| track        | `(arrangement_iid, iid)`                         |                                                                |
| playlist item| `(track_id, position, ref_name)` composite       | items don't have stable ids; composite is "best effort"        |

**Note moves:** MVP renders as `delete + add`. A future pass can detect "same `(rack_channel, key)` appearing at different `position`" and collapse into a single `moved` op. Out of scope now.

**VST plugins:** `extract()` returns `{"state_hash": sha256(raw_state_bytes)}`. Diff shows "VST state changed" but not which param. Honest about the ceiling.

## Differ output format

Tree-structured diff (not flat jsonpatch). Example:

```json
{
  "metadata": {
    "tempo": {"old": 128.0, "new": 140.0}
  },
  "channels": {
    "added": [{"internal_name": "Kick", "name": "Kick", ...}],
    "removed": [],
    "modified": [
      {
        "internal_name": "Lead",
        "name": "Lead",
        "changes": {
          "volume": {"old": 0.8, "new": 0.65}
        }
      }
    ]
  },
  "patterns": {
    "added": [],
    "removed": [],
    "modified": [
      {
        "iid": 3,
        "name": "Melody",
        "notes": {
          "added":    [{"key": 64, "position": 384, ...}],
          "removed":  [{"key": 62, "position": 192, ...}],
          "modified": [
            {
              "key": {"rack_channel": 1, "key": 60, "position": 0},
              "changes": {"velocity": {"old": 100, "new": 115}}
            }
          ]
        }
      }
    ]
  },
  "mixer": {...},
  "plugins": {
    "modified": [
      {
        "channel_name": "Lead",
        "plugin_type": "FruityReverb2",
        "params": {
          "modified": [
            {"name": "mix", "unit": "%", "old": 35.0, "new": 50.0}
          ]
        }
      }
    ]
  },
  "playlist": {...}
}
```

Tree shape mirrors the canonical model so the renderer can walk it section-by-section.

**Both outputs:** `daw diff` prints rich-formatted TTY; `daw diff --json` emits the tree above. Remote stores the JSON tree in the existing `commits.diff` JSONB column.

**Current bug to fix:** `compare.py::_diff_scalar_fields` explicitly skips `dict` and `list` values (`if isinstance(ov, (dict, list)) or isinstance(nv, (dict, list)): continue`). Notes inside patterns, mixer slots, playlist items are parsed but never diffed today. New differ recurses into lists with identity keys and dicts with scalar comparisons.

## Plugin adapter system

Registry at `src/fl_studio/plugins/` — one file per adapter plus `base.py`:

```python
# src/fl_studio/plugins/base.py
from typing import Protocol

class Param(TypedDict):
    name: str
    unit: str        # "%", "Hz", "dB", "dB_norm", "raw"
    value: float

class Adapter(Protocol):
    plugin_class: type     # pyflp plugin class
    display_name: str
    def extract(self, plugin) -> dict[str, Param]: ...

REGISTRY: list[Adapter] = []  # populated by imports
```

Normalization flow in `src/fl_studio/parser/plugins.py`:
1. If `type(plugin)` matches a registered adapter → call `adapter.extract()` → structured `params` dict.
2. Else if plugin is a VST → `{"state_hash": sha256(plugin.raw_state_bytes)}`.
3. Else (unknown native) → `{"state_hash": sha256(json.dumps(plugin.__dict__, sort_keys=True, default=str))}`.

**MVP seed adapters** (exercise the `%`, `Hz`, `dB_norm`, `raw` unit types):
- `FruityReverb2` — mix, room_size, color, hp, low, high (`%`, `Hz`)
- `FruityBalance` — volume (`dB_norm`), pan (`raw`)
- `FruityFilter` — cutoff (`Hz`), resonance (`%`), type (`raw`)

Pattern proven with 3; rest grows as the user needs them.

## Content-addressed blob storage

**New `.daw/` layout:**

```
.daw/
  objects/
    <sha256>              # raw .flp bytes
    <sha256>.diff.json    # structured diff from parent (cached)
  commits.json            # each entry now includes blob_sha
  state.json
```

- `commit` hashes `.flp` bytes → `blob_sha`. If `objects/<blob_sha>` exists, reuse it (dedup across branches).
- `commit_hash` and `blob_sha` stay distinct (identity of commit vs. identity of content — mirrors git's commit/blob split).
- Diff JSON computed at commit time vs. parent blob and cached alongside. `daw log --diff` and remote push don't re-parse.

**Remote sync changes:**
- Supabase `commits` table gets a `blob_sha TEXT NOT NULL` column. Existing `diff JSONB` holds the structured tree.
- Push uploads blobs by `blob_sha` path in the `objects` bucket. HEAD check first — skip upload if present.

**Migration:**
- One-shot `daw migrate` command: hashes each existing `.daw/objects/<commit_hash>.flp`, moves to `<blob_sha>`, adds `blob_sha` to matching `commits.json` entries.
- Not automatic — user runs it once. Safe to re-run.

## Testing strategy

**Fixtures** (tiny hand-built `.flp` files, <50KB each), committed under `tests/fixtures/flp/`:

- `baseline.flp` — reference point
- `tempo_changed.flp` — metadata only
- `channel_added.flp` — new sampler
- `channel_renamed.flp` — `internal_name` stable, display name changed
- `note_added.flp` — pattern gained a note
- `note_moved.flp` — same note, new position
- `mixer_volume.flp` — single insert volume change
- `reverb_knob.flp` — `FruityReverb2` mix param changed
- `vst_opaque.flp` — VST with `state_hash` change

**Test layers:**

1. **Parser tests** (`tests/parser/`) — extend existing; assert new fields adapters need.
2. **Differ unit tests** (`tests/diff/test_compare.py`) — one test per section; assert tree shape against known fixture pairs.
3. **Adapter tests** (`tests/plugins/`) — one file per adapter; load fixture, call `extract()`, assert `Param` dict.
4. **Renderer snapshot tests** (`tests/cli/test_render.py`) — `Console(record=True)`, golden `.txt` files under `tests/fixtures/rendered/`. Catches formatting churn.
5. **End-to-end** (`tests/e2e/test_commit_diff.py`) — init repo, commit baseline, swap fixture, commit again, run `daw diff`, assert expected strings. One test proves the full pipeline.

**Not tested:** VST param introspection (impossible), every native plugin (only 3 MVP adapters), performance.

## Open decisions deferred

- Note-move detection (delete+add collapse) — post-MVP.
- Adapter coverage beyond the 3 seeds — add-on-demand.
- Delta compression between blobs — only if repo size becomes a problem.
- Merge conflict surfacing in the differ tree — priority 3, not in this spec's scope.
