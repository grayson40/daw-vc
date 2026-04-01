# Part A: Parser + Diff Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all FL Studio parsers (patterns, mixer, plugins, playlist) and implement the diff engine that compares two project state dicts.

**Architecture:** `FLParser.get_state()` calls all sub-parsers and returns a single JSON-serializable dict (the "snapshot"). `diff/compare.py` is a pure function that takes two snapshots and returns a structured diff dict. The CLI renders that diff via `rich`.

**Tech Stack:** Python 3.9+, pyflp 2.2.1, pytest, rich

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/fl_studio/parser/base.py` | Modify | Orchestrate all sub-parsers in `get_state()` |
| `src/fl_studio/parser/patterns.py` | Implement | Parse patterns and notes from `project.patterns` |
| `src/fl_studio/parser/mixer.py` | Implement | Parse mixer inserts, slots, routing from `project.mixer` |
| `src/fl_studio/parser/plugins.py` | Implement | Parse plugin name/type from channel instruments and mixer slots |
| `src/fl_studio/parser/playlist.py` | Create | Parse arrangements/tracks/playlist items from `project.arrangements` |
| `src/fl_studio/diff/compare.py` | Implement | Pure `compare(old, new) -> dict` function |
| `src/cli/cli.py` | Modify | Wire `status` and `diff` commands to use compare + rich output |
| `tests/parser/test_patterns.py` | Implement | Tests for FLPatternParser |
| `tests/parser/test_mixer.py` | Implement | Tests for FLMixerParser |
| `tests/parser/test_plugins.py` | Implement | Tests for FLPluginParser |
| `tests/parser/test_playlist.py` | Create | Tests for FLPlaylistParser |
| `tests/diff/test_compare.py` | Create | Tests for compare() |

---

## Task 1: Pattern Parser

**Files:**
- Implement: `src/fl_studio/parser/patterns.py`
- Implement: `tests/parser/test_patterns.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/parser/test_patterns.py
import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.patterns import FLPatternParser


def _make_note(key="C5", position=0, length=96, velocity=100, pan=64, fine_pitch=120, rack_channel=0, slide=False):
    note = MagicMock()
    note.key = key
    note.position = position
    note.length = length
    note.velocity = velocity
    note.pan = pan
    note.fine_pitch = fine_pitch
    note.rack_channel = rack_channel
    note.slide = slide
    return note


def _make_pattern(iid=1, name="Pattern 1", color=None, length=384, looped=False, notes=None):
    pattern = MagicMock()
    pattern.iid = iid
    pattern.name = name
    pattern.color = color
    pattern.length = length
    pattern.looped = looped
    pattern.notes = iter(notes or [])
    pattern.controllers = iter([])
    return pattern


def _make_project(patterns=None):
    project = MagicMock()
    project.patterns = MagicMock()
    project.patterns.__iter__ = MagicMock(return_value=iter(patterns or []))
    return project


def test_parse_empty_patterns():
    project = _make_project(patterns=[])
    parser = FLPatternParser(project)
    result = parser.get_state()
    assert result == []


def test_parse_pattern_fields():
    note = _make_note(key="A#3", position=48, length=96, velocity=80, pan=32)
    pattern = _make_pattern(iid=1, name="Verse", notes=[note])
    project = _make_project(patterns=[pattern])
    parser = FLPatternParser(project)
    result = parser.get_state()
    assert len(result) == 1
    p = result[0]
    assert p["iid"] == 1
    assert p["name"] == "Verse"
    assert p["length"] == 384
    assert p["looped"] is False
    assert len(p["notes"]) == 1
    n = p["notes"][0]
    assert n["key"] == "A#3"
    assert n["position"] == 48
    assert n["length"] == 96
    assert n["velocity"] == 80
    assert n["pan"] == 32


def test_parse_multiple_patterns():
    p1 = _make_pattern(iid=1, name="Verse")
    p2 = _make_pattern(iid=2, name="Chorus")
    project = _make_project(patterns=[p1, p2])
    parser = FLPatternParser(project)
    result = parser.get_state()
    assert len(result) == 2
    assert result[0]["name"] == "Verse"
    assert result[1]["name"] == "Chorus"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /path/to/daw-vc && source venv/bin/activate
pytest tests/parser/test_patterns.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement FLPatternParser**

```python
# src/fl_studio/parser/patterns.py
from typing import Any


class FLPatternParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_pattern(p) for p in self.project.patterns]

    def _parse_pattern(self, pattern: Any) -> dict:
        return {
            "iid": pattern.iid,
            "name": pattern.name,
            "color": str(pattern.color) if pattern.color else None,
            "length": pattern.length,
            "looped": pattern.looped,
            "notes": [self._parse_note(n) for n in pattern.notes],
        }

    def _parse_note(self, note: Any) -> dict:
        return {
            "key": note.key,
            "position": note.position,
            "length": note.length,
            "velocity": note.velocity,
            "pan": note.pan,
            "fine_pitch": note.fine_pitch,
            "rack_channel": note.rack_channel,
            "slide": note.slide,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/parser/test_patterns.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/parser/patterns.py tests/parser/test_patterns.py
git commit -m "feat: implement FLPatternParser with note parsing"
```

---

## Task 2: Mixer Parser

**Files:**
- Implement: `src/fl_studio/parser/mixer.py`
- Implement: `tests/parser/test_mixer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/parser/test_mixer.py
import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.mixer import FLMixerParser


def _make_slot(name="Fruity Reeverb 2", internal_name="Fruity Reeverb 2", color=None):
    slot = MagicMock()
    slot.name = name
    slot.internal_name = internal_name
    slot.color = color
    return slot


def _make_insert(iid=1, name="Master", enabled=True, volume=12800, pan=0,
                 bypassed=False, locked=False, is_solo=False, routes=None, slots=None):
    insert = MagicMock()
    insert.iid = iid
    insert.name = name
    insert.enabled = enabled
    insert.volume = volume
    insert.pan = pan
    insert.bypassed = bypassed
    insert.locked = locked
    insert.is_solo = is_solo
    insert.routes = iter(routes or [])
    insert.__iter__ = MagicMock(return_value=iter(slots or []))
    return insert


def _make_project(inserts=None):
    project = MagicMock()
    project.mixer = MagicMock()
    project.mixer.__iter__ = MagicMock(return_value=iter(inserts or []))
    return project


def test_parse_empty_mixer():
    project = _make_project(inserts=[])
    parser = FLMixerParser(project)
    result = parser.get_state()
    assert result == []


def test_parse_insert_fields():
    slot = _make_slot(name="Fruity Reeverb 2")
    insert = _make_insert(iid=1, name="Kick", volume=10000, pan=64, slots=[slot])
    project = _make_project(inserts=[insert])
    parser = FLMixerParser(project)
    result = parser.get_state()
    assert len(result) == 1
    ins = result[0]
    assert ins["iid"] == 1
    assert ins["name"] == "Kick"
    assert ins["volume"] == 10000
    assert ins["pan"] == 64
    assert ins["enabled"] is True
    assert ins["bypassed"] is False
    assert len(ins["slots"]) == 1
    assert ins["slots"][0]["name"] == "Fruity Reeverb 2"


def test_parse_insert_routes():
    insert = _make_insert(iid=2, name="Bass", routes=[0, 1])
    project = _make_project(inserts=[insert])
    parser = FLMixerParser(project)
    result = parser.get_state()
    assert result[0]["routes"] == [0, 1]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/parser/test_mixer.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement FLMixerParser**

```python
# src/fl_studio/parser/mixer.py
from typing import Any


class FLMixerParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_insert(ins) for ins in self.project.mixer]

    def _parse_insert(self, insert: Any) -> dict:
        return {
            "iid": insert.iid,
            "name": insert.name,
            "enabled": insert.enabled,
            "volume": insert.volume,
            "pan": insert.pan,
            "bypassed": insert.bypassed,
            "locked": insert.locked,
            "is_solo": insert.is_solo,
            "routes": list(insert.routes),
            "slots": [self._parse_slot(s) for s in insert],
        }

    def _parse_slot(self, slot: Any) -> dict:
        return {
            "name": slot.name,
            "internal_name": slot.internal_name,
            "color": str(slot.color) if slot.color else None,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/parser/test_mixer.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/parser/mixer.py tests/parser/test_mixer.py
git commit -m "feat: implement FLMixerParser with insert and slot parsing"
```

---

## Task 3: Plugin Parser

**Files:**
- Implement: `src/fl_studio/parser/plugins.py`
- Implement: `tests/parser/test_plugins.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/parser/test_plugins.py
import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.plugins import FLPluginParser


def _make_instrument(name="Kick", plugin=None, insert=0):
    ch = MagicMock()
    ch.name = name
    ch.plugin = plugin
    ch.insert = insert
    return ch


def _make_plugin(internal_name="Sytrus"):
    plugin = MagicMock()
    plugin.INTERNAL_NAME = internal_name
    plugin.__class__.__name__ = internal_name
    return plugin


def _make_project(instruments=None):
    project = MagicMock()
    project.channels = MagicMock()
    project.channels.instruments = instruments or []
    return project


def test_parse_empty_plugins():
    project = _make_project(instruments=[])
    parser = FLPluginParser(project)
    result = parser.get_state()
    assert result == []


def test_parse_plugin_with_plugin_object():
    plugin = _make_plugin(internal_name="Sytrus")
    instrument = _make_instrument(name="Lead", plugin=plugin, insert=1)
    project = _make_project(instruments=[instrument])
    parser = FLPluginParser(project)
    result = parser.get_state()
    assert len(result) == 1
    assert result[0]["channel_name"] == "Lead"
    assert result[0]["plugin_type"] == "Sytrus"
    assert result[0]["insert"] == 1


def test_parse_instrument_no_plugin():
    instrument = _make_instrument(name="Sampler", plugin=None, insert=0)
    project = _make_project(instruments=[instrument])
    parser = FLPluginParser(project)
    result = parser.get_state()
    assert result[0]["plugin_type"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/parser/test_plugins.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement FLPluginParser**

```python
# src/fl_studio/parser/plugins.py
from typing import Any


class FLPluginParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_instrument(ch) for ch in self.project.channels.instruments]

    def _parse_instrument(self, instrument: Any) -> dict:
        plugin = instrument.plugin
        plugin_type = type(plugin).__name__ if plugin is not None else None
        return {
            "channel_name": instrument.name,
            "plugin_type": plugin_type,
            "insert": instrument.insert,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/parser/test_plugins.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/parser/plugins.py tests/parser/test_plugins.py
git commit -m "feat: implement FLPluginParser for instrument channels"
```

---

## Task 4: Playlist Parser

**Files:**
- Create: `src/fl_studio/parser/playlist.py`
- Create: `tests/parser/test_playlist.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/parser/test_playlist.py
import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.playlist import FLPlaylistParser


def _make_pl_item(position=0, length=384, muted=False, kind="pattern", ref_name="Pattern 1"):
    item = MagicMock()
    item.position = position
    item.length = length
    item.muted = muted
    if kind == "pattern":
        item.pattern = MagicMock()
        item.pattern.name = ref_name
        del item.channel
    else:
        item.channel = MagicMock()
        item.channel.name = ref_name
        del item.pattern
    return item


def _make_track(iid=0, name="Track 1", enabled=True, locked=False, items=None):
    track = MagicMock()
    track.iid = iid
    track.name = name
    track.enabled = enabled
    track.locked = locked
    track.__iter__ = MagicMock(return_value=iter(items or []))
    return track


def _make_arrangement(iid=0, name="Arrangement", tracks=None):
    arr = MagicMock()
    arr.iid = iid
    arr.name = name
    arr.tracks = iter(tracks or [])
    return arr


def _make_project(arrangements=None):
    project = MagicMock()
    project.arrangements = MagicMock()
    project.arrangements.__iter__ = MagicMock(return_value=iter(arrangements or []))
    return project


def test_parse_empty_playlist():
    project = _make_project(arrangements=[])
    parser = FLPlaylistParser(project)
    result = parser.get_state()
    assert result == []


def test_parse_arrangement_fields():
    item = _make_pl_item(position=0, length=384, muted=False, kind="pattern", ref_name="Verse")
    track = _make_track(iid=0, name="Piano Roll", items=[item])
    arr = _make_arrangement(iid=0, name="Song", tracks=[track])
    project = _make_project(arrangements=[arr])
    parser = FLPlaylistParser(project)
    result = parser.get_state()
    assert len(result) == 1
    a = result[0]
    assert a["name"] == "Song"
    assert len(a["tracks"]) == 1
    t = a["tracks"][0]
    assert t["name"] == "Piano Roll"
    assert len(t["items"]) == 1
    i = t["items"][0]
    assert i["position"] == 0
    assert i["length"] == 384
    assert i["muted"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/parser/test_playlist.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement FLPlaylistParser**

```python
# src/fl_studio/parser/playlist.py
from typing import Any


class FLPlaylistParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_arrangement(a) for a in self.project.arrangements]

    def _parse_arrangement(self, arrangement: Any) -> dict:
        return {
            "iid": arrangement.iid,
            "name": arrangement.name,
            "tracks": [self._parse_track(t) for t in arrangement.tracks],
        }

    def _parse_track(self, track: Any) -> dict:
        return {
            "iid": track.iid,
            "name": track.name,
            "enabled": track.enabled,
            "locked": track.locked,
            "items": [self._parse_item(i) for i in track],
        }

    def _parse_item(self, item: Any) -> dict:
        ref = None
        if hasattr(item, "pattern") and item.pattern is not None:
            ref = {"type": "pattern", "name": item.pattern.name}
        elif hasattr(item, "channel") and item.channel is not None:
            ref = {"type": "channel", "name": item.channel.name}
        return {
            "position": item.position,
            "length": item.length,
            "muted": item.muted,
            "ref": ref,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/parser/test_playlist.py -v
```

Expected: all 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/parser/playlist.py tests/parser/test_playlist.py
git commit -m "feat: implement FLPlaylistParser for arrangements and tracks"
```

---

## Task 5: Wire Sub-Parsers into FLParser.get_state()

**Files:**
- Modify: `src/fl_studio/parser/base.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/parser/test_base.py` (the file already exists from the initial commit — check it out from git history since it was lost):

```python
# tests/parser/test_base.py — add this test
def test_get_state_keys(test_project_path):
    parser = FLParser(test_project_path)
    state = parser.get_state()
    assert "metadata" in state
    assert "channels" in state
    assert "patterns" in state
    assert "mixer" in state
    assert "plugins" in state
    assert "playlist" in state
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/parser/test_base.py::test_get_state_keys -v
```

Expected: FAIL — `get_state()` doesn't include `patterns`, `mixer`, `plugins`, `playlist` keys yet

- [ ] **Step 3: Update base.py to orchestrate all parsers**

Replace `get_state()` in `src/fl_studio/parser/base.py`:

```python
# At top of file, add imports:
from .patterns import FLPatternParser
from .mixer import FLMixerParser
from .plugins import FLPluginParser
from .playlist import FLPlaylistParser

# Replace get_state():
def get_state(self) -> Dict[str, Any]:
    """Get complete project state"""
    return {
        'metadata': self._extract_metadata(),
        'channels': FLChannelParser(self.project).get_state(),
        'patterns': FLPatternParser(self.project).get_state(),
        'mixer': FLMixerParser(self.project).get_state(),
        'plugins': FLPluginParser(self.project).get_state(),
        'playlist': FLPlaylistParser(self.project).get_state(),
    }
```

Also update `_parse_metadata()` to return a dict (not a `ProjectMetadata` object) so `get_state()` is fully JSON-serializable:

```python
def _extract_metadata(self) -> Dict[str, Any]:
    return {
        'title': self.project.title,
        'artists': self.project.artists,
        'genre': self.project.genre,
        'version': str(self.project.version),
        'tempo': float(self.project.tempo),
        'ppq': self.project.ppq,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/parser/ -v
```

Expected: all tests PASS (note: `test_metadata` in `test_base.py` may need updating since `_parse_metadata()` now returns dict — update assertion to `isinstance(metadata, dict)`)

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/parser/base.py tests/parser/test_base.py
git commit -m "feat: wire all sub-parsers into FLParser.get_state()"
```

---

## Task 6: Diff Engine

**Files:**
- Implement: `src/fl_studio/diff/compare.py`
- Create: `tests/diff/__init__.py`
- Create: `tests/diff/test_compare.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/diff/test_compare.py
import pytest
from src.fl_studio.diff.compare import compare


BASE_STATE = {
    "metadata": {"tempo": 140.0, "title": "My Track", "artists": "", "genre": "", "version": "21", "ppq": 96},
    "channels": {"rack_settings": {}, "groups": [], "channels": {"samplers": [], "instruments": [], "layers": [], "automations": []}},
    "patterns": [{"iid": 1, "name": "Verse", "color": None, "length": 384, "looped": False, "notes": []}],
    "mixer": [{"iid": 1, "name": "Kick", "enabled": True, "volume": 12800, "pan": 0, "bypassed": False, "locked": False, "is_solo": False, "routes": [], "slots": []}],
    "plugins": [{"channel_name": "Lead", "plugin_type": "Sytrus", "insert": 1}],
    "playlist": [],
}


def test_identical_states_produce_empty_diff():
    result = compare(BASE_STATE, BASE_STATE)
    assert result["metadata"] == {}
    assert result["patterns"]["added"] == []
    assert result["patterns"]["removed"] == []
    assert result["patterns"]["modified"] == []
    assert result["mixer"]["added"] == []
    assert result["mixer"]["removed"] == []
    assert result["mixer"]["modified"] == []


def test_metadata_change():
    new_state = {**BASE_STATE, "metadata": {**BASE_STATE["metadata"], "tempo": 150.0}}
    result = compare(BASE_STATE, new_state)
    assert result["metadata"]["tempo"] == {"old": 140.0, "new": 150.0}


def test_pattern_added():
    new_pattern = {"iid": 2, "name": "Chorus", "color": None, "length": 384, "looped": False, "notes": []}
    new_state = {**BASE_STATE, "patterns": BASE_STATE["patterns"] + [new_pattern]}
    result = compare(BASE_STATE, new_state)
    assert len(result["patterns"]["added"]) == 1
    assert result["patterns"]["added"][0]["name"] == "Chorus"


def test_pattern_removed():
    new_state = {**BASE_STATE, "patterns": []}
    result = compare(BASE_STATE, new_state)
    assert len(result["patterns"]["removed"]) == 1
    assert result["patterns"]["removed"][0]["name"] == "Verse"


def test_mixer_insert_modified():
    new_mixer = [{"iid": 1, "name": "Kick", "enabled": True, "volume": 10000, "pan": 0, "bypassed": False, "locked": False, "is_solo": False, "routes": [], "slots": []}]
    new_state = {**BASE_STATE, "mixer": new_mixer}
    result = compare(BASE_STATE, new_state)
    assert len(result["mixer"]["modified"]) == 1
    mod = result["mixer"]["modified"][0]
    assert mod["name"] == "Kick"
    assert mod["changes"]["volume"] == {"old": 12800, "new": 10000}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
mkdir -p tests/diff && touch tests/diff/__init__.py
pytest tests/diff/test_compare.py -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement compare()**

```python
# src/fl_studio/diff/compare.py
from typing import Any


def compare(old: dict, new: dict) -> dict:
    """Compare two project state dicts. Returns structured diff."""
    return {
        "metadata": _diff_metadata(old.get("metadata", {}), new.get("metadata", {})),
        "channels": _diff_named_list(
            _flatten_channels(old.get("channels", {})),
            _flatten_channels(new.get("channels", {})),
        ),
        "patterns": _diff_named_list(old.get("patterns", []), new.get("patterns", [])),
        "mixer": _diff_named_list(old.get("mixer", []), new.get("mixer", [])),
        "plugins": _diff_named_list(
            old.get("plugins", []), new.get("plugins", []), key="channel_name"
        ),
        "playlist": _diff_named_list(old.get("playlist", []), new.get("playlist", [])),
    }


def _diff_metadata(old: dict, new: dict) -> dict:
    changes = {}
    for k in set(list(old.keys()) + list(new.keys())):
        if old.get(k) != new.get(k):
            changes[k] = {"old": old.get(k), "new": new.get(k)}
    return changes


def _diff_named_list(old_items: list, new_items: list, key: str = "name") -> dict:
    old_by_name = {item[key]: item for item in old_items}
    new_by_name = {item[key]: item for item in new_items}

    added = [new_by_name[k] for k in new_by_name if k not in old_by_name]
    removed = [old_by_name[k] for k in old_by_name if k not in new_by_name]
    modified = []

    for name in old_by_name:
        if name in new_by_name:
            changes = _diff_scalar_fields(old_by_name[name], new_by_name[name])
            if changes:
                modified.append({"name": name, "changes": changes})

    return {"added": added, "removed": removed, "modified": modified}


def _diff_scalar_fields(old: dict, new: dict) -> dict:
    changes = {}
    for k in set(list(old.keys()) + list(new.keys())):
        ov, nv = old.get(k), new.get(k)
        if isinstance(ov, (dict, list)) or isinstance(nv, (dict, list)):
            continue  # skip nested — only scalar field changes
        if ov != nv:
            changes[k] = {"old": ov, "new": nv}
    return changes


def _flatten_channels(channels_state: dict) -> list:
    """Flatten nested channel types into a single list for diffing."""
    result = []
    inner = channels_state.get("channels", {})
    for category in ("samplers", "instruments", "layers", "automations"):
        for ch in inner.get(category, []):
            base = ch.get("base", ch)
            result.append(base)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/diff/test_compare.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/fl_studio/diff/compare.py tests/diff/__init__.py tests/diff/test_compare.py
git commit -m "feat: implement diff engine compare() function"
```

---

## Task 7: Wire diff into CLI status and diff commands

**Files:**
- Modify: `src/cli/cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py (create this file)
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from src.cli.cli import cli


def test_status_requires_daw_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    # Create a dummy .flp file
    flp = tmp_path / "test.flp"
    flp.write_bytes(b"")
    result = runner.invoke(cli, ["status", str(flp)])
    assert result.exit_code != 0 or "not initialized" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL with `ImportError` or assertion error

- [ ] **Step 3: Implement status and diff commands in cli.py**

Open `src/cli/cli.py` and replace the stub `status` and `diff` commands with:

```python
# Add at top of file:
import shutil
from rich.console import Console
from rich.table import Table
from src.fl_studio.diff.compare import compare

console = Console()


def _render_diff(diff: dict) -> None:
    """Render a structured diff dict to the terminal using rich."""
    if diff.get("metadata"):
        console.print("[bold yellow]Metadata changes:[/bold yellow]")
        for field, change in diff["metadata"].items():
            console.print(f"  {field}: [red]{change['old']}[/red] → [green]{change['new']}[/green]")

    for section in ("channels", "patterns", "mixer", "plugins", "playlist"):
        section_diff = diff.get(section, {})
        if not isinstance(section_diff, dict):
            continue
        added = section_diff.get("added", [])
        removed = section_diff.get("removed", [])
        modified = section_diff.get("modified", [])
        if not (added or removed or modified):
            continue
        console.print(f"\n[bold cyan]{section.capitalize()}:[/bold cyan]")
        for item in added:
            name = item.get("name") or item.get("channel_name", "?")
            console.print(f"  [green]+ {name}[/green]")
        for item in removed:
            name = item.get("name") or item.get("channel_name", "?")
            console.print(f"  [red]- {name}[/red]")
        for item in modified:
            console.print(f"  [yellow]~ {item['name']}[/yellow]")
            for field, change in item["changes"].items():
                console.print(f"    {field}: [red]{change['old']}[/red] → [green]{change['new']}[/green]")


@cli.command()
@click.argument('project', type=click.Path(exists=True))
def status(project):
    """Show changes between working file and HEAD commit."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    commits = json.loads(vc.commits_file.read_text())
    if not commits:
        console.print("No commits yet. Run 'daw add' and 'daw commit' first.")
        return

    last_commit = commits[-1]
    head_hash = last_commit["hash"]
    head_flp = vc.daw_dir / "objects" / f"{head_hash}.flp"

    if not head_flp.exists():
        raise click.ClickException(f"HEAD snapshot not found: {head_flp}")

    from src.fl_studio.parser.base import FLParser
    old_state = FLParser(head_flp).get_state()
    new_state = FLParser(Path(project)).get_state()
    diff = compare(old_state, new_state)

    has_changes = (
        diff["metadata"]
        or any(diff[s].get("added") or diff[s].get("removed") or diff[s].get("modified")
               for s in ("channels", "patterns", "mixer", "plugins", "playlist"))
    )
    if not has_changes:
        console.print("Nothing changed since last commit.")
    else:
        _render_diff(diff)


@cli.command()
@click.argument('hash1', required=False)
@click.argument('hash2', required=False)
def diff(hash1, hash2):
    """Show diff between two commits (default: HEAD~1 vs HEAD)."""
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

    flp1 = vc.daw_dir / "objects" / f"{h1}.flp"
    flp2 = vc.daw_dir / "objects" / f"{h2}.flp"

    for p in (flp1, flp2):
        if not p.exists():
            raise click.ClickException(f"Snapshot not found: {p}")

    from src.fl_studio.parser.base import FLParser
    old_state = FLParser(flp1).get_state()
    new_state = FLParser(flp2).get_state()
    diff_result = compare(old_state, new_state)
    _render_diff(diff_result)
```

Also update the `commit` command to save the `.flp` file to `objects/`:

```python
@cli.command()
@click.argument('message')
def commit(message):
    """Commit staged changes"""
    vc = DawVC(Path.cwd())
    staged = json.loads(vc.staged_file.read_text())
    if not staged:
        raise click.ClickException("Nothing to commit")

    objects_dir = vc.daw_dir / "objects"
    objects_dir.mkdir(exist_ok=True)

    commits = json.loads(vc.commits_file.read_text())
    commit_hash = generate_hash()

    # Copy each staged .flp to objects/
    for entry in staged:
        src_path = Path(entry["path"])
        if src_path.exists():
            shutil.copy2(src_path, objects_dir / f"{commit_hash}.flp")

    new_commit = {
        "hash": commit_hash,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "branch": "main",
        "parent_hash": commits[-1]["hash"] if commits else None,
        "changes": staged,
    }
    commits.append(new_commit)
    vc.commits_file.write_text(json.dumps(commits, default=str))
    vc.staged_file.write_text(json.dumps([]))
    console.print(f"[green]Committed {commit_hash}: {message}[/green]")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli.py -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/cli/cli.py tests/test_cli.py
git commit -m "feat: wire diff engine into CLI status and diff commands"
```

---

## Verification

After all tasks are complete, run the full test suite:

```bash
pytest -v --tb=short
```

Expected: all tests pass with no errors.
