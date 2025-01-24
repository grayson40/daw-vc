import pytest
from unittest.mock import MagicMock
from src.fl_studio.parser.channels import FLChannelParser


@pytest.fixture
def mock_project():
    project = MagicMock()
    project.channels.groups = []
    project.channels.samplers = []
    project.channels.instruments = []
    project.channels.layers = []
    project.channels.automations = []
    project.channels.height = 100
    project.channels.fit_to_steps = False
    project.channels.swing = 0.5
    return project


def test_channel_parser_initialization(mock_project):
    parser = FLChannelParser(mock_project)
    assert parser.project == mock_project
    assert parser.channels == mock_project.channels


def test_parse_rack_settings(mock_project):
    mock_project.channels.height = 150
    mock_project.channels.fit_to_steps = True
    mock_project.channels.swing = 0.8

    parser = FLChannelParser(mock_project)
    state = parser.get_state()
    rack_settings = state['rack_settings']

    assert rack_settings['height'] == 150
    assert rack_settings['fit_to_steps'] is True
    assert rack_settings['swing'] == 0.8


def test_parse_groups(mock_project):
    mock_group = MagicMock()
    mock_group.name = "Group 1"
    mock_project.channels.groups = [mock_group]

    parser = FLChannelParser(mock_project)
    state = parser.get_state()
    groups = state['groups']

    assert len(groups) == 1
    assert groups[0]['name'] == "Group 1"


def test_parse_samplers(mock_project):
    mock_sampler = MagicMock()
    mock_sampler.name = "Sampler 1"
    mock_sampler.sample_path = "path/to/sample.wav"
    mock_project.channels.samplers = [mock_sampler]

    parser = FLChannelParser(mock_project)
    state = parser.get_state()
    samplers = state['channels']['samplers']

    assert len(samplers) == 1
    assert samplers[0]['sample_path'] == "path/to/sample.wav"


def test_empty_sampler_content(mock_project):
    mock_sampler = MagicMock()
    mock_sampler.name = "Sampler 1"
    mock_sampler.sample_path = None
    mock_sampler.content = None
    mock_project.channels.samplers = [mock_sampler]

    parser = FLChannelParser(mock_project)
    state = parser.get_state()

    samplers = state['channels']['samplers']
    assert len(samplers) == 1
    assert samplers[0]['sample_path'] is None
    assert samplers[0]['content'] == {}

# Other tests can be added in similar fashion for instruments, layers, automations, etc.
