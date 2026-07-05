"""Layer-3 placement engine — build a LayoutManifest from a device's capabilities.

Reconstructs, server-side and keyed off capability **domains** (not config-group name-matching),
the zone/control structure the UI used to generate at build time. Validation surface since the
2026-05-24 Layer-3 cutover is the live ``/devices/{id}/layout`` endpoint consumed by the UI's
``RuntimeDevicePage`` — the frozen structural oracle that bootstrapped the engine was retired
2026-06-09 (archived at ``docs/archive/layer3_oracle/``).

Domain coverage: all 9 domains (power [single- and multi-zone], playback, volume, input, tracks,
menu, screen, apps, pointer). The 12 standard devices have shipped on the runtime renderer since
the cutover, plus eMotiva multi-zone power (zone 1 off/on + zone 2 native toggle — pinned by
`test_engine_emotiva_multizone_power` since the capability-driven shape intentionally diverges
from the old codegen). **Icons are resolved UI-side** (decided 2026-05-23 — keeps the manifest
skin-agnostic; see `ui_backend_contract.md` "Icons"): this engine emits placeholder icons that
the renderer overrides via its `IconResolver`; the manifest `icon` field is only an optional
override.
"""
from types import SimpleNamespace
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from wb_mqtt_bridge.domain.scenarios.proxy import SCENARIO_ROLE_DOMAIN
from wb_mqtt_bridge.domain.capabilities.models import Capability, CapabilityMap
from wb_mqtt_bridge.presentation.api.param_projection import project_params
from wb_mqtt_bridge.presentation.api.layout_manifest import (
    ActionIcon,
    DropdownConfig,
    DropdownOption,
    LayoutManifest,
    ManualInstructions,
    NavigationClusterConfig,
    PlaybackConfig,
    PointerPadConfig,
    PowerButtonConfig,
    ProcessedAction,
    ProcessedParameter,
    RemoteZone,
    TracksConfig,
    ZoneType,
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


def _parameters(cmd: Any, fixed_params: Optional[Dict[str, Any]] = None) -> List[ProcessedParameter]:
    """Native-name view of the shared §6 param projection (`param_projection.py`) — the
    SAME code path that feeds the catalog's canonical view (VWB-15), so UI and voice
    metadata cannot drift. Params fixed by the capability action are excluded: they are
    values the UI *sends* (`ProcessedAction.params`), not knobs the user sets."""
    fixed_holder = SimpleNamespace(params=fixed_params or {}, param_map={})
    out: List[ProcessedParameter] = []
    for d in project_params(cmd, fixed_holder, canonical_names=False):
        normalized_type = d["type"] if d["type"] in _PARAM_TYPES else "string"
        out.append(ProcessedParameter(
            name=d["name"],
            # _PARAM_TYPES is the Literal-aligned set; pyright doesn't narrow
            # `ptype if ptype in <set> else <literal>` to the Literal union.
            type=cast(Literal["range", "string", "integer", "boolean"], normalized_type),
            required=d["required"],
            default=d["default"],
            min=d["min"],
            max=d["max"],
            description=d["description"],
        ))
    return out


def _action(device: Any, command: str, fixed_params: Optional[Dict[str, Any]] = None) -> Optional[ProcessedAction]:
    """Build a ProcessedAction for a native command (None if the device lacks it). `fixed_params` are
    the capability action's fixed native params (e.g. {zone: 2}) the UI must always send."""
    cmd = device.get_available_commands().get(command)
    if cmd is None:
        return None
    return ProcessedAction(
        action_name=command,
        display_name=_humanize(getattr(cmd, "action", None) or command),
        description=getattr(cmd, "description", "") or "",
        parameters=_parameters(cmd, fixed_params),
        group="default",
        # placeholder icon/uiHints — oracle-exact material icons are a follow-on
        icon=ActionIcon(icon_library="fallback", icon_name=command, fallback_icon=command, confidence=0.0),
        ui_hints=UIHints(button_size="medium", button_style="secondary"),
        params=dict(fixed_params or {}),
    )


# --- zone content builders (domain -> content) ------------------------------------------------
def _power_content(device: Any, cap: Capability) -> ZoneContent:
    """power domain -> powerButtons (off->left, on->right). Handles single-zone (cap.actions) and
    multi-zone (cap.zones): a zone that has a `toggle` action renders one toggle button (zone 2 ->
    `zone2-power`, middle), otherwise discrete off/on. Buttons are position-sorted (slot zone)."""
    by_key = {"off": ("power-off", "left"), "on": ("power-on", "right"), "toggle": ("power-toggle", "left")}
    buttons: List[PowerButtonConfig] = []

    def _add(key: str, command: str, *, button_type: Optional[str] = None, position: Optional[str] = None,
             params: Optional[Dict[str, Any]] = None) -> None:
        action = _action(device, command, params)
        if action is None:
            return
        bt, pos = by_key.get(key, ("power-toggle", "left"))
        buttons.append(PowerButtonConfig(
            position=cast(Literal["left", "middle", "right"], position or pos),
            action=action,
            button_type=cast(Literal["power-off", "power-on", "power-toggle", "zone2-power"], button_type or bt),
        ))

    for key, cap_action in cap.actions.items():
        if cap_action.command:
            _add(key, cap_action.command, params=cap_action.params)

    for zone_key, zone in (cap.zones or {}).items():
        toggle = zone.actions.get("toggle")
        if toggle and toggle.command:  # native zone toggle (e.g. eMotiva zone2_power) -> one button
            _add("toggle", toggle.command,
                 button_type=("zone2-power" if str(zone_key) == "2" else "power-toggle"),
                 position="middle", params=toggle.params)
        else:  # discrete per-zone on/off
            for key in ("off", "on"):
                ca = zone.actions.get(key)
                if ca and ca.command:
                    _add(key, ca.command, params=ca.params)

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
    mute = _action(device, acts["mute_toggle"].command, acts["mute_toggle"].params) if "mute_toggle" in acts and acts["mute_toggle"].command else None
    if "set" in acts and acts["set"].command:
        set_action = _action(device, acts["set"].command, acts["set"].params)
        if set_action is None:
            return ZoneContent()
        return ZoneContent(volume_slider=VolumeSliderConfig(
            action=set_action, mute_action=mute,
            orientation="vertical", show_value=True,
            value_field=cap.state_field,  # serialized state field for the current level (UI value binding)
            value_param=(acts["set"].param_map or {}).get("level") or "level",  # native param the level is sent under
        ))
    up = _action(device, acts["up"].command, acts["up"].params) if "up" in acts and acts["up"].command else None
    down = _action(device, acts["down"].command, acts["down"].params) if "down" in acts and acts["down"].command else None
    return ZoneContent(volume_buttons=[VolumeButtonConfig(up_action=up, down_action=down, mute_action=mute)])


def _inputs_dropdown(device: Any, cap: Capability) -> DropdownConfig:
    """input domain -> inputsDropdown. Parametric select -> api-populated (runtime); by_value ->
    one command per option (populated from the map)."""
    sel = cap.select
    if sel is not None and sel.command:
        # native param the selected value is sent under: the param_map's native name for the
        # canonical "input" key (e.g. LG {input: source} -> "source"), else "input" (e.g. eMotiva).
        set_param = (sel.param_map or {}).get("input") or "input"
        return DropdownConfig(
            type="inputs", population_method="api",
            api_action=cap.list.command if cap.list else None,
            set_action=sel.command, set_param=set_param, options=[], loading=False, empty=True,
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
    # native param the selected app is sent under: param_map's native name for the canonical "app"
    # key (LG {app: app_name} -> "app_name"), else "app" (AppleTV launch_app takes "app").
    set_param = ((launch.param_map or {}).get("app") or "app") if launch else None
    return DropdownConfig(
        type="apps", population_method="api",
        api_action=cap.list.command if cap.list else None,
        set_action=launch.command if launch and launch.command else None,
        set_param=set_param,
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

    # SCN-7: every action-backed control carries its canonical (capability, action)
    # tuple so the UI dispatches POST /devices/{id}/canonical. The dropdowns still
    # dispatch natively: select became canonically routable in VWB-19 (`input.set
    # {value}`), but flipping the manifest/UI dropdown seam is UI-9.
    if "power" in caps:
        content["power"] = _power_content(device, caps["power"])
        _tag_source(content["power"], None, "power", _canonical_reverse_map(caps["power"]))
    media = content["media-stack"]
    if "input" in caps:
        media.inputs_dropdown = _inputs_dropdown(device, caps["input"])
    if "playback" in caps:
        media.playback_section = _playback_content(device, caps["playback"])
        for a in media.playback_section.actions:
            _tag_action(a, None, "playback", _canonical_reverse_map(caps["playback"]))
    if "tracks" in caps:
        media.tracks_section = _tracks_content(device, caps["tracks"])
        for a in media.tracks_section.actions:
            _tag_action(a, None, "tracks", _canonical_reverse_map(caps["tracks"]))
    if "volume" in caps:
        content["volume"] = _volume_content(device, caps["volume"])
        _tag_source(content["volume"], None, "volume", _canonical_reverse_map(caps["volume"]))
    if "menu" in caps:
        content["menu"] = _menu_content(device, caps["menu"])
        _tag_source(content["menu"], None, "menu", _canonical_reverse_map(caps["menu"]))
    if "screen" in caps:
        content["screen"] = _screen_content(device, caps["screen"])
        _tag_source(content["screen"], None, "screen", _canonical_reverse_map(caps["screen"]))
    if "apps" in caps:
        content["apps"] = ZoneContent(apps_dropdown=_apps_dropdown(device, caps["apps"]))
    if "pointer" in caps:
        content["pointer"] = _pointer_content(device, caps["pointer"])
        _tag_source(content["pointer"], None, "pointer", _canonical_reverse_map(caps["pointer"]))
    # TODO: multi-zone power (emotiva — cap.zones, not cap.actions)

    def _is_empty(c: ZoneContent) -> bool:
        # empty iff no content field holds a truthy value (covers None and empty lists)
        return not any(c.model_dump(exclude_none=True, by_alias=True).values())

    zones: List[RemoteZone] = []
    for zone_id, (zone_name, show_hide, layout) in _ZONE_META.items():
        c = content[zone_id]
        zones.append(RemoteZone(
            zone_id=cast("ZoneType", zone_id),
            zone_name=zone_name,
            zone_type=cast("ZoneType", zone_id),
            show_hide=show_hide, is_empty=_is_empty(c),
            content=c, layout=ZoneLayoutConfig(**layout),
        ))

    cfg = device.config
    state_schema = type(getattr(device, "state", None)).__name__ if getattr(device, "state", None) else None
    return LayoutManifest(
        device_id=cfg.device_id,
        # LayoutManifest.device_name stays a flat string (UI surface unchanged); the bilingual
        # source of truth is cfg.names. UI consumes the russian rendering by default.
        device_name=cfg.names.ru,
        device_class=cfg.device_class,
        remote_zones=zones,
        entity_kind="device",
        device_category=getattr(cfg, "device_category", "device") or "device",
        state_schema=state_schema,
    )


# === scenario manifest ========================================================================
# Role -> capability domain (rendered). "inputs" is intentionally omitted: target inputs are
# reconciler-derived from topology at activation, not a UI control (scenario_system_redesign.md §6).
# Role -> capability domain: single source of truth in the domain layer (SCN-6);
# consumed here for manifest assembly and by the Scenario Manager proxy for fire-time
# resolution.
_SCENARIO_ROLE_DOMAIN: Dict[str, str] = SCENARIO_ROLE_DOMAIN


def _canonical_reverse_map(cap: Optional[Capability]) -> Dict[str, str]:
    """native command name -> canonical action name for a capability (SCN-6 dispatch
    annotation). Only single-command actions map (sequence-form is skipped by the zone
    builders anyway)."""
    if cap is None:
        return {}
    return {ca.command: name for name, ca in cap.actions.items() if ca.command}


def _tag_action(a: Optional[ProcessedAction], dev_id: Optional[str],
                domain: Optional[str] = None,
                cmd_to_action: Optional[Dict[str, str]] = None) -> None:
    if a is None:
        return
    if dev_id is not None:
        a.source_device_id = dev_id
    if domain and cmd_to_action:
        canonical = cmd_to_action.get(a.action_name)
        if canonical is not None:
            a.canonical_capability = domain
            a.canonical_action = canonical


def _tag_source(content: ZoneContent, dev_id: Optional[str],
                domain: Optional[str] = None,
                cmd_to_action: Optional[Dict[str, str]] = None) -> None:
    """Tag every control in a zone's content with its role device (scenario sourceDeviceId
    routing; None on device manifests, where the target is the device itself) and, when
    the capability is known, its canonical (capability, action) tuple (SCN-6/SCN-7
    canonical dispatch)."""
    for b in (content.power_buttons or []):
        _tag_action(b.action, dev_id, domain, cmd_to_action)
    for dd in (content.inputs_dropdown, content.apps_dropdown):
        if dd is not None and dev_id is not None:
            dd.source_device_id = dev_id
    for sec in (content.playback_section, content.tracks_section):
        if sec is not None:
            for a in sec.actions:
                _tag_action(a, dev_id, domain, cmd_to_action)
    for a in (content.screen_actions or []):
        _tag_action(a, dev_id, domain, cmd_to_action)
    if content.volume_slider is not None:
        _tag_action(content.volume_slider.action, dev_id, domain, cmd_to_action)
        _tag_action(content.volume_slider.mute_action, dev_id, domain, cmd_to_action)
    for b in (content.volume_buttons or []):
        _tag_action(b.up_action, dev_id, domain, cmd_to_action)
        _tag_action(b.down_action, dev_id, domain, cmd_to_action)
        _tag_action(b.mute_action, dev_id, domain, cmd_to_action)
    for grp in (content.navigation_cluster, content.pointer_pad):
        if grp is not None:
            for name in type(grp).model_fields:
                v = getattr(grp, name)
                if isinstance(v, ProcessedAction):
                    _tag_action(v, dev_id, domain, cmd_to_action)


def _scenario_power_zone() -> ZoneContent:
    """The scenario lifecycle zone: power_off=Stop (left), power_on=Start (right). No sourceDeviceId —
    the UI routes these to /scenario/shutdown + /scenario/start (not a device action)."""
    def _btn(position: str, button_type: str, action_name: str, label: str) -> PowerButtonConfig:
        return PowerButtonConfig(
            position=cast(Literal["left", "middle", "right"], position),
            button_type=cast(Literal["power-off", "power-on", "power-toggle", "zone2-power"], button_type),
            action=ProcessedAction(
                action_name=action_name, display_name=label, description=label,
                icon=ActionIcon(icon_library="fallback", icon_name="power", fallback_icon="power", confidence=0.0),
                ui_hints=UIHints(button_size="medium", button_style="secondary"),
            ),
        )
    return ZoneContent(power_buttons=[
        _btn("left", "power-off", "power_off", "Stop scenario"),
        _btn("right", "power-on", "power_on", "Start scenario"),
    ])


def build_scenario_manifest(scenario_def: Any, device_manager: Any) -> LayoutManifest:
    """Build a scenario's LayoutManifest: a composite remote assembled per role from the role-bound
    devices' capabilities. Controls carry sourceDeviceId (routed to the role device); the power zone is
    the scenario lifecycle. Spec: scenario_system_redesign.md §6 (NOT the old scenario .gen.tsx)."""
    roles: Dict[str, str] = dict(getattr(scenario_def, "roles", {}) or {})
    content: Dict[str, ZoneContent] = {zid: ZoneContent() for zid in _ZONE_META}
    content["power"] = _scenario_power_zone()
    media = content["media-stack"]

    def _role(role: str) -> Tuple[Optional[str], Optional[Any], Optional[Capability]]:
        dev_id = roles.get(role)
        if not dev_id:
            return None, None, None
        device = device_manager.devices.get(dev_id)
        cap_map: Optional[CapabilityMap] = getattr(device, "capabilities", None) if device else None
        cap = (dict(cap_map.root) if cap_map is not None else {}).get(_SCENARIO_ROLE_DOMAIN[role])
        return dev_id, device, cap

    # _role's contract: if cap is non-None, dev_id is non-None too (the early
    # `if not dev_id: return None, None, None` short-circuits before lookup).
    # asserts encode that invariant for pyright.
    dev_id, device, cap = _role("volume")
    if cap:
        assert dev_id is not None
        content["volume"] = _volume_content(device, cap)
        _tag_source(content["volume"], dev_id, "volume", _canonical_reverse_map(cap))
    dev_id, device, cap = _role("playback")
    if cap:
        assert dev_id is not None
        media.playback_section = _playback_content(device, cap)
        for a in media.playback_section.actions:
            _tag_action(a, dev_id, "playback", _canonical_reverse_map(cap))
    dev_id, device, cap = _role("tracks")
    if cap:
        assert dev_id is not None
        media.tracks_section = _tracks_content(device, cap)
        for a in media.tracks_section.actions:
            _tag_action(a, dev_id, "tracks", _canonical_reverse_map(cap))
    dev_id, device, cap = _role("screen")
    if cap:
        assert dev_id is not None
        content["screen"] = _screen_content(device, cap)
        _tag_source(content["screen"], dev_id, "screen", _canonical_reverse_map(cap))
    dev_id, device, cap = _role("menu")
    if cap:
        assert dev_id is not None
        content["menu"] = _menu_content(device, cap)
        _tag_source(content["menu"], dev_id, "menu", _canonical_reverse_map(cap))
    dev_id, device, cap = _role("pointer")
    if cap:
        assert dev_id is not None
        content["pointer"] = _pointer_content(device, cap)
        _tag_source(content["pointer"], dev_id, "pointer", _canonical_reverse_map(cap))
    dev_id, device, cap = _role("apps")
    if cap:
        assert dev_id is not None
        content["apps"] = ZoneContent(apps_dropdown=_apps_dropdown(device, cap))
        _tag_source(content["apps"], dev_id, "apps", _canonical_reverse_map(cap))

    def _is_empty(c: ZoneContent) -> bool:
        return not any(c.model_dump(exclude_none=True, by_alias=True).values())

    zones: List[RemoteZone] = []
    for zone_id, (zone_name, show_hide, layout) in _ZONE_META.items():
        c = content[zone_id]
        zones.append(RemoteZone(
            zone_id=cast("ZoneType", zone_id),
            zone_name=zone_name,
            zone_type=cast("ZoneType", zone_id),
            show_hide=show_hide, is_empty=_is_empty(c),
            content=c, layout=ZoneLayoutConfig(**layout),
        ))

    mi = getattr(scenario_def, "manual_instructions", None)
    manual = ManualInstructions(
        startup=list(getattr(mi, "startup", []) or []),
        shutdown=list(getattr(mi, "shutdown", []) or []),
    ) if mi is not None else None

    room_id = getattr(scenario_def, "room_id", None)
    return LayoutManifest(
        device_id=scenario_def.scenario_id,
        # Russian rendering, matching device manifests (cfg.names.ru) — SCN-8.
        device_name=scenario_def.names.ru,
        device_class="ScenarioDevice",
        remote_zones=zones,
        entity_kind="scenario",
        manual_instructions=manual,
        # SCN-6: the room's Scenario Manager entity — the UI's canonical dispatch target
        # (power zone -> scenario.set/off; annotated controls -> their canonical tuple).
        canonical_entity_id=f"scenario_manager_{room_id}" if room_id else None,
    )
