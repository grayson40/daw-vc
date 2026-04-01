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
    insert.routes = routes or []
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
    assert ins["locked"] is False
    assert ins["is_solo"] is False
    assert len(ins["slots"]) == 1
    assert ins["slots"][0]["name"] == "Fruity Reeverb 2"
    assert ins["slots"][0]["internal_name"] == "Fruity Reeverb 2"
    assert ins["slots"][0]["color"] is None


def test_parse_insert_routes():
    insert = _make_insert(iid=2, name="Bass", routes=[0, 1])
    project = _make_project(inserts=[insert])
    parser = FLMixerParser(project)
    result = parser.get_state()
    assert result[0]["routes"] == [0, 1]


def test_parse_slot_with_color():
    color = MagicMock()
    color.__str__ = MagicMock(return_value="#AABBCC")
    slot = _make_slot(name="EQ", color=color)
    insert = _make_insert(iid=1, name="Lead", slots=[slot])
    project = _make_project(inserts=[insert])
    parser = FLMixerParser(project)
    result = parser.get_state()
    assert result[0]["slots"][0]["color"] == "#AABBCC"


def test_parse_multiple_inserts():
    ins1 = _make_insert(iid=1, name="Kick")
    ins2 = _make_insert(iid=2, name="Snare")
    project = _make_project(inserts=[ins1, ins2])
    parser = FLMixerParser(project)
    result = parser.get_state()
    assert len(result) == 2
    assert result[0]["name"] == "Kick"
    assert result[1]["name"] == "Snare"
