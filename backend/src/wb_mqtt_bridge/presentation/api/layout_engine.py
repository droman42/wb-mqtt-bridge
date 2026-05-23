"""Layer-3 placement engine — build a LayoutManifest from a device's capabilities.

Reconstructs, server-side and keyed off capability **domains** (not config-group name-matching),
the zone/control structure the UI used to generate at build time. The frozen oracle
(`docs/scenarios/layer3_oracle/`) is the fidelity target.

STATUS (Step 1, incremental): the framework + the **power** and **playback** zone builders are in
(covers reel_to_reel + vhs_player). The remaining domain builders — input/tracks (media-stack),
volume, menu, apps, screen, pointer — are TODO (their zones render empty until added). Icons/uiHints
are placeholders for now (oracle-exact material icons = a follow-on; see `ui_backend_contract.md`
"Icons" open decision).
"""
from typing import Any, Dict, List, Optional, Tuple

from wb_mqtt_bridge.infrastructure.capabilities.models import Capability, CapabilityMap
from wb_mqtt_bridge.presentation.api.layout_manifest import (
    ActionIcon,
    LayoutManifest,
    PlaybackConfig,
    PowerButtonConfig,
    ProcessedAction,
    ProcessedParameter,
    RemoteZone,
    UIHints,
    ZoneContent,
    ZoneLayoutConfig,
)

# The 7-zone skeleton (zoneName / showHide / layout), reproduced from the oracle. Every manifest
# emits all 7 zones in this order; absent domains render empty.
_ZONE_META: Dict[str, Tuple[str, bool, Dict[str, Any]]] = {
    "power": ("Power Control", True, {"columns": 3, "spacing": "normal", "alignment": "center"}),
    "media-stack": ("Media Stack", True, {"spacing": "normal", "orientation": "vertical"}),
    "screen": ("Screen Controls", False, {"orientation": "vertical", "alignment": "left", "spacing": "compact"}),
    "volume": ("Volume Control", False, {"priority": 2, "orientation": "vertical", "alignment": "right", "spacing": "compact"}),
    "apps": ("Applications", True, {"spacing": "normal"}),
    "menu": ("Navigation", False, {"alignment": "center", "spacing": "normal"}),
    "pointer": ("Pointer Control", True, {"spacing": "normal"}),
}

_PARAM_TYPES = {"range", "string", "integer", "boolean"}


def _humanize(name: str) -> str:
    return name.replace("_", " ").title()


def _parameters(cmd: Any) -> List[ProcessedParameter]:
    out: List[ProcessedParameter] = []
    for p in (getattr(cmd, "params", None) or []):
        ptype = getattr(p, "type", "string")
        out.append(ProcessedParameter(
            name=p.name,
            type=ptype if ptype in _PARAM_TYPES else "string",
            required=bool(getattr(p, "required", False)),
            default=getattr(p, "default", None),
            min=getattr(p, "min", None),
            max=getattr(p, "max", None),
            description=getattr(p, "description", "") or "",
        ))
    return out


def _action(device: Any, command: str) -> Optional[ProcessedAction]:
    """Build a ProcessedAction for a native command (None if the device lacks it)."""
    cmd = device.get_available_commands().get(command)
    if cmd is None:
        return None
    return ProcessedAction(
        action_name=command,
        display_name=_humanize(getattr(cmd, "action", None) or command),
        description=getattr(cmd, "description", "") or "",
        parameters=_parameters(cmd),
        group="default",
        # placeholder icon/uiHints — oracle-exact material icons are a follow-on
        icon=ActionIcon(icon_library="fallback", icon_name=command, fallback_icon=command, confidence=0.0),
        ui_hints=UIHints(button_size="medium", button_style="secondary"),
    )


# --- zone content builders (domain -> content) ------------------------------------------------
def _power_content(device: Any, cap: Capability) -> ZoneContent:
    """power domain -> powerButtons. on->right, off->left, toggle->left, zone2->zone2-power."""
    by_key = {
        "off": ("power-off", "left"),
        "on": ("power-on", "right"),
        "toggle": ("power-toggle", "left"),
    }
    buttons: List[PowerButtonConfig] = []
    for key, cap_action in cap.actions.items():
        if not cap_action.command:
            continue
        action = _action(device, cap_action.command)
        if action is None:
            continue
        button_type, position = by_key.get(key, ("power-toggle", "left"))
        buttons.append(PowerButtonConfig(position=position, action=action, button_type=button_type))
    return ZoneContent(power_buttons=buttons)


def _playback_content(device: Any, cap: Capability) -> PlaybackConfig:
    """playback domain -> playbackSection (actions in capability declaration order)."""
    actions = [_action(device, a.command) for a in cap.actions.values() if a.command]
    return PlaybackConfig(actions=[a for a in actions if a is not None], layout="horizontal")


def build_device_manifest(device: Any) -> LayoutManifest:
    """Build a device's LayoutManifest from its capability map (Layer-3 placement)."""
    cap_map: Optional[CapabilityMap] = getattr(device, "capabilities", None)
    caps: Dict[str, Capability] = dict(cap_map.root) if cap_map is not None else {}

    # collect content per zoneId (media-stack aggregates input/playback/tracks)
    content: Dict[str, ZoneContent] = {zid: ZoneContent() for zid in _ZONE_META}

    if "power" in caps:
        content["power"] = _power_content(device, caps["power"])
    if "playback" in caps:
        content["media-stack"].playback_section = _playback_content(device, caps["playback"])
    # TODO: input/tracks (media-stack), volume, menu, apps, screen, pointer

    def _is_empty(zone_id: str, c: ZoneContent) -> bool:
        return c.model_dump(exclude_none=True, by_alias=True) == {}

    zones: List[RemoteZone] = []
    for zone_id, (zone_name, show_hide, layout) in _ZONE_META.items():
        c = content[zone_id]
        zones.append(RemoteZone(
            zone_id=zone_id, zone_name=zone_name, zone_type=zone_id,
            show_hide=show_hide, is_empty=_is_empty(zone_id, c),
            content=c, layout=ZoneLayoutConfig(**layout),
        ))

    cfg = device.config
    state_schema = type(getattr(device, "state", None)).__name__ if getattr(device, "state", None) else None
    return LayoutManifest(
        device_id=cfg.device_id,
        device_name=cfg.device_name,
        device_class=cfg.device_class,
        remote_zones=zones,
        entity_kind="device",
        device_category=getattr(cfg, "device_category", "device") or "device",
        state_schema=state_schema,
    )
