import json
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".daw" / "config.json"


def load_config() -> Optional[dict]:
    if not CONFIG_PATH.exists():
        return None
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
