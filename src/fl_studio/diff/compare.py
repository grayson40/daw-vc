from typing import Any


def compare(old: dict, new: dict) -> dict:
    """Compare two project state dicts. Returns structured diff."""
    return {
        "metadata": _diff_metadata(old.get("metadata", {}), new.get("metadata", {})),
        "channels": _diff_named_list(
            _flatten_channels(old.get("channels", {})),
            _flatten_channels(new.get("channels", {})),
        ),
        "patterns": _diff_named_list(old.get("patterns", []), new.get("patterns", [])),
        "mixer": _diff_named_list(old.get("mixer", []), new.get("mixer", [])),
        "plugins": _diff_named_list(
            old.get("plugins", []), new.get("plugins", []), key="channel_name"
        ),
        "playlist": _diff_named_list(old.get("playlist", []), new.get("playlist", [])),
    }


def _diff_metadata(old: dict, new: dict) -> dict:
    changes = {}
    for k in set(list(old.keys()) + list(new.keys())):
        if old.get(k) != new.get(k):
            changes[k] = {"old": old.get(k), "new": new.get(k)}
    return changes


def _diff_named_list(old_items: list, new_items: list, key: str = "name") -> dict:
    old_by_name = {item[key]: item for item in old_items}
    new_by_name = {item[key]: item for item in new_items}

    added = [new_by_name[k] for k in new_by_name if k not in old_by_name]
    removed = [old_by_name[k] for k in old_by_name if k not in new_by_name]
    modified = []

    for name in old_by_name:
        if name in new_by_name:
            changes = _diff_scalar_fields(old_by_name[name], new_by_name[name])
            if changes:
                modified.append({"name": name, "changes": changes})

    return {"added": added, "removed": removed, "modified": modified}


def _diff_scalar_fields(old: dict, new: dict) -> dict:
    changes = {}
    for k in set(list(old.keys()) + list(new.keys())):
        ov, nv = old.get(k), new.get(k)
        if isinstance(ov, (dict, list)) or isinstance(nv, (dict, list)):
            continue  # skip nested — only scalar field changes
        if ov != nv:
            changes[k] = {"old": ov, "new": nv}
    return changes


def _flatten_channels(channels_state: dict) -> list:
    """Flatten nested channel types into a single list keyed by name for diffing."""
    result = []
    inner = channels_state.get("channels", {})
    for category in ("samplers", "instruments", "layers", "automations"):
        for ch in inner.get(category, []):
            base = ch.get("base", ch)
            result.append(base)
    return result
