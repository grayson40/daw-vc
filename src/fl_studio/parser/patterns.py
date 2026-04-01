from typing import Any


class FLPatternParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_pattern(p) for p in self.project.patterns]

    def _parse_pattern(self, pattern: Any) -> dict:
        return {
            "iid": pattern.iid,
            "name": pattern.name,
            "color": str(pattern.color) if pattern.color else None,
            "length": pattern.length,
            "looped": pattern.looped,
            "notes": [self._parse_note(n) for n in pattern.notes],
        }

    def _parse_note(self, note: Any) -> dict:
        return {
            "key": note.key,
            "position": note.position,
            "length": note.length,
            "velocity": note.velocity,
            "pan": note.pan,
            "fine_pitch": note.fine_pitch,
            "rack_channel": note.rack_channel,
            "slide": note.slide,
        }
