import pyflp
from pathlib import Path
from typing import Dict, Any
from .channels import FLChannelParser
from .patterns import FLPatternParser
from .mixer import FLMixerParser
from .plugins import FLPluginParser
from .playlist import FLPlaylistParser


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
        """Get complete project state as a JSON-serializable dict."""
        return {
            'metadata': self._extract_metadata(),
            'channels': FLChannelParser(self.project).get_state(),
            'patterns': FLPatternParser(self.project).get_state(),
            'mixer': FLMixerParser(self.project).get_state(),
            'plugins': FLPluginParser(self.project).get_state(),
            'playlist': FLPlaylistParser(self.project).get_state(),
        }

    def _extract_metadata(self) -> Dict[str, Any]:
        return {
            'title': self.project.title,
            'artists': self.project.artists,
            'genre': self.project.genre,
            'version': str(self.project.version),
            'tempo': float(self.project.tempo),
            'ppq': self.project.ppq,
        }
