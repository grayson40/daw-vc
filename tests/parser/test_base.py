import pytest
import pyflp
from pathlib import Path
from src.fl_studio.parser.base import FLParser


@pytest.fixture
def test_project_path(tmp_path):
    return Path("../fixtures/flp/try-it-out.flp")


def test_load_project(test_project_path):
    parser = FLParser(test_project_path)
    assert parser.project is not None


def test_metadata(test_project_path):
    parser = FLParser(test_project_path)
    metadata = parser._parse_metadata()

    assert isinstance(metadata, ProjectMetadata)
    assert metadata.tempo > 0
    assert metadata.ppq > 0
    assert metadata.version is not None
    assert metadata.title is not None
    assert metadata.artists is not None
    assert metadata.genre is not None


def test_invalid_project():
    with pytest.raises(RuntimeError):
        FLParser(Path("nonexistent.flp"))


def test_empty_or_invalid_flp(tmp_path):
    empty_flp = tmp_path / "empty.flp"
    empty_flp.write_text("")
    with pytest.raises(RuntimeError):
        FLParser(empty_flp)


def test_non_flp_files():
    non_flp_file = Path("tests/fixtures/test.txt")
    with pytest.raises(RuntimeError):
        FLParser(non_flp_file)


def test_pyflp_parse_exception_handling(test_project_path, monkeypatch):
    def mock_parse(*args, **kwargs):
        raise Exception("Parsing failed")

    monkeypatch.setattr(pyflp, "parse", mock_parse)
    with pytest.raises(RuntimeError):
        FLParser(test_project_path)


def test_get_state_keys():
    """Test that get_state() returns all expected top-level keys."""
    from unittest.mock import MagicMock, patch

    mock_project = MagicMock()
    mock_project.title = "Test"
    mock_project.artists = ""
    mock_project.genre = ""
    mock_project.version = "21"
    mock_project.tempo = 140.0
    mock_project.ppq = 96
    mock_project.channels = MagicMock()
    mock_project.channels.groups = []
    mock_project.channels.height = 0
    mock_project.channels.fit_to_steps = False
    mock_project.channels.swing = 0
    mock_project.channels.samplers = []
    mock_project.channels.instruments = []
    mock_project.channels.layers = []
    mock_project.channels.automations = []
    mock_project.patterns = MagicMock()
    mock_project.patterns.__iter__ = MagicMock(return_value=iter([]))
    mock_project.mixer = MagicMock()
    mock_project.mixer.__iter__ = MagicMock(return_value=iter([]))
    mock_project.arrangements = MagicMock()
    mock_project.arrangements.__iter__ = MagicMock(return_value=iter([]))

    fake_path = MagicMock(spec=Path)
    fake_path.is_file.return_value = True
    fake_path.suffix = ".flp"

    with patch("src.fl_studio.parser.base.pyflp.parse", return_value=mock_project):
        parser = FLParser(fake_path)

    state = parser.get_state()
    assert "metadata" in state
    assert "channels" in state
    assert "patterns" in state
    assert "mixer" in state
    assert "plugins" in state
    assert "playlist" in state
