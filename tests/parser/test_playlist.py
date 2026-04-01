# tests/parser/test_playlist.py
import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.playlist import FLPlaylistParser


def _make_pattern_item(position=0, length=384, muted=False, pattern_name="Verse"):
    item = MagicMock(spec=["position", "length", "muted", "pattern"])
    item.position = position
    item.length = length
    item.muted = muted
    item.pattern = MagicMock()
    item.pattern.name = pattern_name
    return item


def _make_channel_item(position=0, length=384, muted=False, channel_name="Kick"):
    item = MagicMock(spec=["position", "length", "muted", "channel"])
    item.position = position
    item.length = length
    item.muted = muted
    item.channel = MagicMock()
    item.channel.name = channel_name
    return item


def _make_track(iid=0, name="Track 1", enabled=True, locked=False, items=None):
    track = MagicMock()
    track.iid = iid
    track.name = name
    track.enabled = enabled
    track.locked = locked
    track.__iter__ = MagicMock(return_value=iter(items or []))
    return track


def _make_arrangement(iid=0, name="Song", tracks=None):
    arr = MagicMock()
    arr.iid = iid
    arr.name = name
    arr.tracks = tracks or []
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
    item = _make_pattern_item(position=0, length=384, muted=False, pattern_name="Verse")
    track = _make_track(iid=0, name="Piano Roll", items=[item])
    arr = _make_arrangement(iid=0, name="Song", tracks=[track])
    project = _make_project(arrangements=[arr])
    parser = FLPlaylistParser(project)
    result = parser.get_state()
    assert len(result) == 1
    a = result[0]
    assert a["iid"] == 0
    assert a["name"] == "Song"
    assert len(a["tracks"]) == 1
    t = a["tracks"][0]
    assert t["iid"] == 0
    assert t["name"] == "Piano Roll"
    assert t["enabled"] is True
    assert t["locked"] is False
    assert len(t["items"]) == 1
    i = t["items"][0]
    assert i["position"] == 0
    assert i["length"] == 384
    assert i["muted"] is False
    assert i["ref"] == {"type": "pattern", "name": "Verse"}


def test_parse_channel_item():
    item = _make_channel_item(position=96, length=192, channel_name="Kick")
    track = _make_track(iid=1, name="Audio", items=[item])
    arr = _make_arrangement(iid=0, name="Song", tracks=[track])
    project = _make_project(arrangements=[arr])
    parser = FLPlaylistParser(project)
    result = parser.get_state()
    i = result[0]["tracks"][0]["items"][0]
    assert i["ref"] == {"type": "channel", "name": "Kick"}


def test_parse_multiple_arrangements():
    arr1 = _make_arrangement(iid=0, name="Intro")
    arr2 = _make_arrangement(iid=1, name="Verse")
    project = _make_project(arrangements=[arr1, arr2])
    parser = FLPlaylistParser(project)
    result = parser.get_state()
    assert len(result) == 2
    assert result[0]["name"] == "Intro"
    assert result[1]["name"] == "Verse"
