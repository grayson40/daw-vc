import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from src.cli.cli import cli


def test_status_requires_daw_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    flp = tmp_path / "test.flp"
    flp.write_bytes(b"")
    result = runner.invoke(cli, ["status", str(flp)])
    assert result.exit_code != 0


def test_init_creates_daw_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".daw").is_dir()
    assert (tmp_path / ".daw" / "commits.json").exists()
    assert (tmp_path / ".daw" / "staged.json").exists()


def test_commit_requires_staged_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    result = runner.invoke(cli, ["commit", "my message"])
    assert result.exit_code != 0


def test_log_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init"])
    result = runner.invoke(cli, ["log"])
    assert result.exit_code == 0
    assert "no commits" in result.output.lower()
