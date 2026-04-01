from typing import Any


class FLMixerParser:
    def __init__(self, project: Any):
        self.project = project

    def get_state(self) -> list:
        return [self._parse_insert(ins) for ins in self.project.mixer]

    def _parse_insert(self, insert: Any) -> dict:
        return {
            "iid": insert.iid,
            "name": insert.name,
            "enabled": insert.enabled,
            "volume": insert.volume,
            "pan": insert.pan,
            "bypassed": insert.bypassed,
            "locked": insert.locked,
            "is_solo": insert.is_solo,
            "routes": list(insert.routes),
            "slots": [self._parse_slot(s) for s in insert],
        }

    def _parse_slot(self, slot: Any) -> dict:
        return {
            "name": slot.name,
            "internal_name": slot.internal_name,
            "color": str(slot.color) if slot.color else None,
        }
