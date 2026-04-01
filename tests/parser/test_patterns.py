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
    pattern.notes = notes or []
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
    assert n["fine_pitch"] == 120
    assert n["rack_channel"] == 0
    assert n["slide"] is False


def test_parse_multiple_patterns():
    p1 = _make_pattern(iid=1, name="Verse")
    p2 = _make_pattern(iid=2, name="Chorus")
    project = _make_project(patterns=[p1, p2])
    parser = FLPatternParser(project)
    result = parser.get_state()
    assert len(result) == 2
    assert result[0]["name"] == "Verse"
    assert result[1]["name"] == "Chorus"


def test_parse_pattern_color():
    color = MagicMock()
    color.__str__ = MagicMock(return_value="#FF0000")
    pattern = _make_pattern(iid=1, name="Colored", color=color, notes=[])
    project = _make_project(patterns=[pattern])
    parser = FLPatternParser(project)
    result = parser.get_state()
    assert result[0]["color"] == "#FF0000"


def test_parse_pattern_no_color():
    pattern = _make_pattern(iid=1, name="No Color", color=None, notes=[])
    project = _make_project(patterns=[pattern])
    parser = FLPatternParser(project)
    result = parser.get_state()
    assert result[0]["color"] is None
