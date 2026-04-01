from typing import Any


class FLPluginParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_instrument(ch) for ch in self.project.channels.instruments]

    def _parse_instrument(self, instrument: Any) -> dict:
        plugin = instrument.plugin
        plugin_type = type(plugin).__name__ if plugin is not None else None
        return {
            "channel_name": instrument.name,
            "plugin_type": plugin_type,
            "insert": instrument.insert,
        }
