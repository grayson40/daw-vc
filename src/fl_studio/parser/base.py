import pyflp
from pathlib import Path
from typing import Dict, Any
from .channels import FLChannelParser


class ProjectMetadata:
    def __init__(self, title: str, artists: str, genre: str, version: str, tempo: float, ppq: int):
        self.title = title
        self.artists = artists
        self.genre = genre
        self.version = version
        self.tempo = tempo
        self.ppq = ppq


class FLParser:
    """Base parser for FL Studio projects"""

    def __init__(self, project_path: Path):
        self.project_path = project_path

        # Check if the file exists and is a valid FLP file
        if not project_path.is_file() or project_path.suffix != '.flp':
            raise RuntimeError(f"Invalid FL Studio project file: {project_path}")

        try:
            self.project = pyflp.parse(project_path)
        except Exception as e:
            raise RuntimeError(f"Failed to parse the FLP file: {project_path}") from e

    def get_state(self) -> Dict[str, Any]:
        """Get complete project state"""
        return {
            'metadata': self._parse_metadata(),
            'modules': {
                'channels': self._parse_channels(),
                # 'patterns': self._parse_patterns(),
                # 'mixer': self._parse_mixer(),
                # 'playlist': self._parse_playlist(),
                # 'arrangements': self._parse_arrangements()
            }
        }

    def _parse_metadata(self) -> ProjectMetadata:
        metadata = self._extract_metadata()
        return ProjectMetadata(**metadata)

    def _extract_metadata(self) -> Dict[str, Any]:
        return {
            'title': self.project.title,
            'artists': self.project.artists,
            'genre': self.project.genre,
            'version': self.project.version,
            'tempo': self.project.tempo,
            'ppq': self.project.ppq
        }

    def _parse_channels(self) -> Dict[str, Any]:
        return FLChannelParser(self.project).get_state()

    def _parse_patterns(self) -> Dict[str, Any]:
        raise NotImplementedError

    def _parse_mixer(self) -> Dict[str, Any]:
        raise NotImplementedError

    def _parse_playlist(self) -> Dict[str, Any]:
        raise NotImplementedError

    def _parse_arrangements(self) -> Dict[str, Any]:
        raise NotImplementedError
