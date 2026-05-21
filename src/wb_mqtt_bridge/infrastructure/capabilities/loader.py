"""Load and merge device capability maps from ``config/capabilities/``.

Resolution for a device: the class default (``classes/<device_class>.json``, shared by
all instances of specific drivers) deep-merged with a per-device file
(``devices/<device_id>.json``, the home for generic IR devices and per-instance
overrides), with the device file winning. Either may be absent.
"""

import json
from pathlib import Path
from typing import Any, Dict

from wb_mqtt_bridge.infrastructure.capabilities.models import CapabilityMap


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` onto ``base`` (override wins at the leaves)."""
    out = dict(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _read(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_capability_map(
    device_class: str, device_id: str, capabilities_dir: Path
) -> CapabilityMap:
    """Resolve and validate a device's capability map.

    Returns an empty map if neither the class nor the device file exists.
    Raises ``pydantic.ValidationError`` if a present file is malformed.
    """
    merged: Dict[str, Any] = {}

    class_file = capabilities_dir / "classes" / f"{device_class}.json"
    if class_file.exists():
        merged = _read(class_file)

    device_file = capabilities_dir / "devices" / f"{device_id}.json"
    if device_file.exists():
        merged = _deep_merge(merged, _read(device_file))

    return CapabilityMap.model_validate(merged)


def attach_capability_maps(devices: Dict[str, Any], capabilities_dir: Path) -> None:
    """Resolve and attach a ``CapabilityMap`` to each device in ``devices``.

    ``devices`` maps device_id -> device (each having ``.config.device_class`` and a
    settable ``.capabilities``). Called from bootstrap after device construction.
    """
    for device_id, device in devices.items():
        device.capabilities = load_capability_map(
            device.config.device_class, device_id, capabilities_dir
        )
