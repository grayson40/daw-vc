import pytest
import pyflp
from pathlib import Path
from src.fl_studio.parser.base import FLParser, ProjectMetadata


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
