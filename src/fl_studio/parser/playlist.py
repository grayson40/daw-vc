# src/fl_studio/parser/playlist.py
from typing import Any


class FLPlaylistParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_arrangement(a) for a in self.project.arrangements]

    def _parse_arrangement(self, arrangement: Any) -> dict:
        return {
            "iid": arrangement.iid,
            "name": arrangement.name,
            "tracks": [self._parse_track(t) for t in arrangement.tracks],
        }

    def _parse_track(self, track: Any) -> dict:
        return {
            "iid": track.iid,
            "name": track.name,
            "enabled": track.enabled,
            "locked": track.locked,
            "items": [self._parse_item(i) for i in track],  # pyflp Track is ModelCollection[PLItemBase], iterable
        }

    def _parse_item(self, item: Any) -> dict:
        ref = None
        if hasattr(item, "pattern") and item.pattern is not None:
            ref = {"type": "pattern", "name": item.pattern.name}
        elif hasattr(item, "channel") and item.channel is not None:
            ref = {"type": "channel", "name": item.channel.name}
        return {
            "position": item.position,
            "length": item.length,
            "muted": item.muted,
            "ref": ref,
        }
