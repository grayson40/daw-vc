import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.plugins import FLPluginParser


def _make_instrument(name="Kick", plugin=None, insert=0):
    ch = MagicMock()
    ch.name = name
    ch.plugin = plugin
    ch.insert = insert
    return ch


def _make_plugin(class_name="Sytrus"):
    # Create a dynamic class with the given name
    plugin_class = type(class_name, (), {})
    # Create an instance of that class
    plugin = plugin_class()
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


def test_parse_instrument_with_plugin():
    plugin = _make_plugin("Sytrus")
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
    assert len(result) == 1
    assert result[0]["channel_name"] == "Sampler"
    assert result[0]["plugin_type"] is None
    assert result[0]["insert"] == 0


def test_parse_multiple_instruments():
    p1 = _make_plugin("FruitKick")
    p2 = _make_plugin("VSTPlugin")
    ins1 = _make_instrument(name="Kick", plugin=p1, insert=1)
    ins2 = _make_instrument(name="VST Synth", plugin=p2, insert=2)
    project = _make_project(instruments=[ins1, ins2])
    parser = FLPluginParser(project)
    result = parser.get_state()
    assert len(result) == 2
    assert result[0]["plugin_type"] == "FruitKick"
    assert result[1]["plugin_type"] == "VSTPlugin"
