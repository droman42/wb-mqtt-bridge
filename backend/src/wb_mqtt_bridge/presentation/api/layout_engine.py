"""Layer-3 placement engine — build a LayoutManifest from a device's capabilities.

Reconstructs, server-side and keyed off capability **domains** (not config-group name-matching),
the zone/control structure the UI used to generate at build time. The frozen oracle
(`docs/scenarios/layer3_oracle/`) is the fidelity target.

STATUS (Step 1, incremental): the framework + the **power**, **playback**, **volume**, and **input**
(media-stack) zone builders are in (covers reel_to_reel, vhs_player, mf_amplifier). TODO: tracks
(media-stack), menu, apps, screen, pointer builders; and **multi-zone power** (the emotiva special
case — the cap has `zones`, not `actions`). Icons/uiHints are placeholders for now (oracle-exact
material icons = a follow-on; see `ui_backend_contract.md` "Icons" open decision).
"""
from typing import Any, Dict, List, Optional, Tuple

from wb_mqtt_bridge.infrastructure.capabilities.models import Capability, CapabilityMap
from wb_mqtt_bridge.presentation.api.layout_manifest import (
    ActionIcon,
    DropdownConfig,
    DropdownOption,
    LayoutManifest,
    NavigationClusterConfig,
    PlaybackConfig,
    PointerPadConfig,
    PowerButtonConfig,
    ProcessedAction,
    ProcessedParameter,
    RemoteZone,
    TracksConfig,
    UIHints,
    VolumeButtonConfig,
    VolumeSliderConfig,
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
    """power domain -> powerButtons (off->left, on->right). Handles single-zone (cap.actions) and
    multi-zone (cap.zones): a zone that has a `toggle` action renders one toggle button (zone 2 ->
    `zone2-power`, middle), otherwise discrete off/on. Buttons are position-sorted (slot zone)."""
    by_key = {"off": ("power-off", "left"), "on": ("power-on", "right"), "toggle": ("power-toggle", "left")}
    buttons: List[PowerButtonConfig] = []

    def _add(key: str, command: str, *, button_type: Optional[str] = None, position: Optional[str] = None) -> None:
        action = _action(device, command)
        if action is None:
            return
        bt, pos = by_key.get(key, ("power-toggle", "left"))
        buttons.append(PowerButtonConfig(position=position or pos, action=action, button_type=button_type or bt))

    for key, cap_action in cap.actions.items():
        if cap_action.command:
            _add(key, cap_action.command)

    for zone_key, zone in (cap.zones or {}).items():
        toggle = zone.actions.get("toggle")
        if toggle and toggle.command:  # native zone toggle (e.g. eMotiva zone2_power) -> one button
            _add("toggle", toggle.command,
                 button_type=("zone2-power" if str(zone_key) == "2" else "power-toggle"),
                 position="middle")
        else:  # discrete per-zone on/off
            for key in ("off", "on"):
                ca = zone.actions.get(key)
                if ca and ca.command:
                    _add(key, ca.command)

    buttons.sort(key=lambda b: {"left": 0, "middle": 1, "right": 2}.get(b.position, 9))
    return ZoneContent(power_buttons=buttons)


def _playback_content(device: Any, cap: Capability) -> PlaybackConfig:
    """playback domain -> playbackSection (actions in capability declaration order)."""
    actions = [_action(device, a.command) for a in cap.actions.values() if a.command]
    return PlaybackConfig(actions=[a for a in actions if a is not None], layout="horizontal")


def _volume_content(device: Any, cap: Capability) -> ZoneContent:
    """volume domain -> volumeSlider (if a `set` action) else volumeButtons (up/down). `mute_toggle`
    becomes the mute action of whichever is used."""
    acts = cap.actions
    mute = _action(device, acts["mute_toggle"].command) if "mute_toggle" in acts and acts["mute_toggle"].command else None
    if "set" in acts and acts["set"].command:
        return ZoneContent(volume_slider=VolumeSliderConfig(
            action=_action(device, acts["set"].command), mute_action=mute,
            orientation="vertical", show_value=True,
        ))
    up = _action(device, acts["up"].command) if "up" in acts and acts["up"].command else None
    down = _action(device, acts["down"].command) if "down" in acts and acts["down"].command else None
    return ZoneContent(volume_buttons=[VolumeButtonConfig(up_action=up, down_action=down, mute_action=mute)])


def _inputs_dropdown(device: Any, cap: Capability) -> DropdownConfig:
    """input domain -> inputsDropdown. Parametric select -> api-populated (runtime); by_value ->
    one command per option (populated from the map)."""
    sel = cap.select
    if sel is not None and sel.command:
        return DropdownConfig(
            type="inputs", population_method="api",
            api_action=cap.list.command if cap.list else None,
            set_action=sel.command, options=[], loading=False, empty=True,
        )
    options: List[DropdownOption] = []
    for value, cap_action in ((sel.by_value if sel else None) or {}).items():
        if not cap_action.command:
            continue
        cmd = device.get_available_commands().get(cap_action.command)
        options.append(DropdownOption(
            id=cap_action.command, display_name=_humanize(value),
            description=(getattr(cmd, "description", "") or "") if cmd else "",
        ))
    return DropdownConfig(type="inputs", population_method="commands",
                         options=options, loading=False, empty=not options)


def _tracks_content(device: Any, cap: Capability) -> TracksConfig:
    """tracks domain -> tracksSection (actions in capability declaration order)."""
    actions = [_action(device, a.command) for a in cap.actions.values() if a.command]
    return TracksConfig(actions=[a for a in actions if a is not None], layout="horizontal")


_DPAD = {"up": "up_action", "down": "down_action", "left": "left_action",
         "right": "right_action", "ok": "ok_action"}


def _menu_content(device: Any, cap: Capability) -> ZoneContent:
    """menu domain -> navigationCluster. Canonical up/down/left/right/ok fill the D-pad; any other
    menu actions (home/back/exit/menu/settings…) fill aux1..aux4 in capability-declaration order
    (an explicit `placement` hint will override this once hints land)."""
    kwargs: Dict[str, ProcessedAction] = {}
    aux = 1
    for key, cap_action in cap.actions.items():
        if not cap_action.command:
            continue
        action = _action(device, cap_action.command)
        if action is None:
            continue
        if key in _DPAD:
            kwargs[_DPAD[key]] = action
        elif aux <= 4:
            kwargs[f"aux{aux}_action"] = action
            aux += 1
    return ZoneContent(navigation_cluster=NavigationClusterConfig(**kwargs))


def _screen_content(device: Any, cap: Capability) -> ZoneContent:
    """screen domain -> screenActions (flat list, capability-declaration order)."""
    actions = [_action(device, a.command) for a in cap.actions.values() if a.command]
    return ZoneContent(screen_actions=[a for a in actions if a is not None])


def _apps_dropdown(device: Any, cap: Capability) -> DropdownConfig:
    """apps domain -> appsDropdown (api-populated: launch action + list query)."""
    launch = cap.actions.get("launch")
    return DropdownConfig(
        type="apps", population_method="api",
        api_action=cap.list.command if cap.list else None,
        set_action=launch.command if launch and launch.command else None,
        options=[], loading=False, empty=True,
    )


_POINTER = {"move": "move_action", "click": "click_action", "tap": "click_action",
            "drag": "drag_action", "scroll": "scroll_action"}


def _pointer_content(device: Any, cap: Capability) -> ZoneContent:
    """pointer domain -> pointerPad (move/click/tap/drag/scroll -> the pad's slots)."""
    kwargs: Dict[str, ProcessedAction] = {}
    for key, cap_action in cap.actions.items():
        field = _POINTER.get(key)
        if field and cap_action.command:
            action = _action(device, cap_action.command)
            if action is not None:
                kwargs[field] = action
    if "move_action" not in kwargs:  # PointerPadConfig requires a move action
        return ZoneContent()
    return ZoneContent(pointer_pad=PointerPadConfig(**kwargs))


def build_device_manifest(device: Any) -> LayoutManifest:
    """Build a device's LayoutManifest from its capability map (Layer-3 placement)."""
    cap_map: Optional[CapabilityMap] = getattr(device, "capabilities", None)
    caps: Dict[str, Capability] = dict(cap_map.root) if cap_map is not None else {}

    # collect content per zoneId (media-stack aggregates input/playback/tracks)
    content: Dict[str, ZoneContent] = {zid: ZoneContent() for zid in _ZONE_META}

    if "power" in caps:
        content["power"] = _power_content(device, caps["power"])
    media = content["media-stack"]
    if "input" in caps:
        media.inputs_dropdown = _inputs_dropdown(device, caps["input"])
    if "playback" in caps:
        media.playback_section = _playback_content(device, caps["playback"])
    if "tracks" in caps:
        media.tracks_section = _tracks_content(device, caps["tracks"])
    if "volume" in caps:
        content["volume"] = _volume_content(device, caps["volume"])
    if "menu" in caps:
        content["menu"] = _menu_content(device, caps["menu"])
    if "screen" in caps:
        content["screen"] = _screen_content(device, caps["screen"])
    if "apps" in caps:
        content["apps"] = ZoneContent(apps_dropdown=_apps_dropdown(device, caps["apps"]))
    if "pointer" in caps:
        content["pointer"] = _pointer_content(device, caps["pointer"])
    # TODO: multi-zone power (emotiva — cap.zones, not cap.actions)

    def _is_empty(c: ZoneContent) -> bool:
        # empty iff no content field holds a truthy value (covers None and empty lists)
        return not any(c.model_dump(exclude_none=True, by_alias=True).values())

    zones: List[RemoteZone] = []
    for zone_id, (zone_name, show_hide, layout) in _ZONE_META.items():
        c = content[zone_id]
        zones.append(RemoteZone(
            zone_id=zone_id, zone_name=zone_name, zone_type=zone_id,
            show_hide=show_hide, is_empty=_is_empty(c),
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
