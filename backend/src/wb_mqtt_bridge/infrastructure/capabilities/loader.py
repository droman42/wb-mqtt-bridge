"""Load and merge device capability maps from ``config/capabilities/``.

Resolution for a device: the class default (``classes/<device_class>.json``, shared by
all instances of specific drivers) deep-merged with a per-device file
(``devices/<device_id>.json``, the home for generic IR devices and per-instance
overrides), with the device file winning. Either may be absent.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Set

from wb_mqtt_bridge.domain.capabilities.models import CapabilityAction, CapabilityMap


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


def referenced_commands(cap_map: CapabilityMap) -> Set[str]:
    """All native command names a capability map references (across every
    action / select / list / zone). Used to decide whether a config command is
    "capability-backed"."""
    cmds: Set[str] = set()

    def _walk(action: CapabilityAction) -> None:
        if action is None:
            return
        if action.command:
            cmds.add(action.command)
        for step in (action.sequence or []):
            _walk(step)

    for cap in cap_map.root.values():
        for action in cap.actions.values():
            _walk(action)
        if cap.select is not None:
            if cap.select.command:
                cmds.add(cap.select.command)
            for action in (cap.select.by_value or {}).values():
                _walk(action)
        _walk(cap.list)
        for zone in (cap.zones or {}).values():
            for action in zone.actions.values():
                _walk(action)
    return cmds


def validate_command_exposure(devices: Dict[str, Any]) -> List[str]:
    """Layer-3 readiness / drift check. Returns the list of violations: for each
    ``device_category == "device"`` device, any command that is ``exposed`` but **not**
    backed by a capability (so it would be invisible in a Layer-3 manifest). Appliances
    are exempt — they render from explicit ``wb_controls`` / bespoke pages, not capabilities.
    A command is acceptable iff it is ``exposed: false`` OR capability-backed."""
    violations: List[str] = []
    for device_id, device in devices.items():
        config = getattr(device, "config", None)
        if getattr(config, "device_category", "device") == "appliance":
            continue
        cap_map = getattr(device, "capabilities", None)
        backed = referenced_commands(cap_map) if cap_map is not None else set()
        for name, cmd in device.get_available_commands().items():
            if getattr(cmd, "exposed", True) and name not in backed:
                violations.append(f"{device_id}.{name}")
    return violations
