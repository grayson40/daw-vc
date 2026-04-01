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


def test_plugin_modified():
    new_plugins = [{"channel_name": "Lead", "plugin_type": "Harmor", "insert": 1}]
    new_state = {**BASE_STATE, "plugins": new_plugins}
    result = compare(BASE_STATE, new_state)
    assert len(result["plugins"]["modified"]) == 1
    assert result["plugins"]["modified"][0]["name"] == "Lead"
    assert result["plugins"]["modified"][0]["changes"]["plugin_type"] == {"old": "Sytrus", "new": "Harmor"}
