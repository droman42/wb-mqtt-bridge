"""LayoutManifest — the backend-computed remote layout for a device or scenario (Layer 3).

A faithful, camelCase mirror of ``ui/src/types/RemoteControlLayout.ts`` (``RemoteDeviceStructure``)
so the existing ``RemoteControlLayout`` renderer consumes it **unchanged**, plus manifest metadata
(``entityKind``, ``deviceCategory``, ``stateSchema``). Served at runtime by
``GET /devices/{id}/layout`` and ``GET /scenario/{id}/layout`` and published in ``openapi.json``.

The build-time codegen fields (``stateInterface``, ``actionHandlers``) are kept **optional** —
the runtime engine omits them (live-state types come from ``openapi.json`` via ``stateSchema``;
action dispatch is generic). Were retained for parity with the now-retired frozen oracle
(archived 2026-06-09 at ``docs/archive/layer3_oracle/``); validation is render-level diff via
the live ``/devices/{id}/layout`` endpoint + the UI's ``RuntimeDevicePage`` consumer.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    """Base: snake_case fields, camelCase JSON (to match the UI types). Rejects unknown keys so a
    drift between this model and the UI structure fails loudly."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


ZoneType = Literal["power", "media-stack", "screen", "volume", "apps", "menu", "pointer"]


# --- the atom: a renderable action -------------------------------------------------------------
class ProcessedParameter(_Camel):
    name: str
    type: Literal["range", "string", "integer", "boolean"]
    required: bool
    default: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    description: str = ""


class ActionIcon(_Camel):
    icon_library: Literal["material", "custom", "fallback"]
    icon_name: str
    icon_variant: Optional[Literal["filled", "outlined", "rounded", "sharp", "two-tone"]] = None
    fallback_icon: str
    confidence: float


class UIHints(_Camel):
    button_size: Optional[Literal["small", "medium", "large"]] = None
    button_style: Optional[Literal["primary", "secondary", "destructive"]] = None
    is_pointer_action: Optional[bool] = None
    has_parameters: Optional[bool] = None
    zone_number: Optional[int] = None


class ProcessedAction(_Camel):
    action_name: str
    display_name: str
    description: str = ""
    parameters: List[ProcessedParameter] = Field(default_factory=list)
    group: str = "default"
    icon: ActionIcon
    ui_hints: UIHints = Field(default_factory=UIHints)
    source_device_id: Optional[str] = None  # scenario-inherited: which device to actually call
    # SCN-6 canonical dispatch (scenario manifests): the canonical (capability, action)
    # tuple this control maps to. When set (and the manifest carries canonicalEntityId),
    # the UI dispatches POST /devices/<entity>/canonical instead of the native /action.
    canonical_capability: Optional[str] = None
    canonical_action: Optional[str] = None
    # fixed native params the UI must always send with this action (from the capability action's
    # `params`, e.g. eMotiva power_off -> {zone: 1}, set_volume -> {zone: 2}). `parameters` above is
    # the *spec* (for the slider range etc.); `params` is the *values* to send.
    params: Dict[str, Any] = Field(default_factory=dict)


# --- zone content (one optional field per zone kind) -------------------------------------------
class ZoneLayoutConfig(_Camel):
    priority: Optional[int] = None
    columns: Optional[int] = None
    spacing: Optional[Literal["compact", "normal", "spacious"]] = None
    alignment: Optional[Literal["left", "center", "right"]] = None
    orientation: Optional[Literal["horizontal", "vertical"]] = None


class PowerButtonConfig(_Camel):
    position: Literal["left", "middle", "right"]
    action: ProcessedAction
    button_type: Literal["power-off", "power-on", "power-toggle", "zone2-power"]


class DropdownOption(_Camel):
    id: str
    display_name: str
    description: Optional[str] = None


class DropdownConfig(_Camel):
    type: Literal["inputs", "apps"]
    population_method: Literal["api", "commands"]
    api_action: Optional[str] = None
    set_action: Optional[str] = None
    # native param name the selected value is sent under for api selection (e.g. set_input -> "input",
    # LG set_input_source -> "source"). Only set for populationMethod="api".
    set_param: Optional[str] = None
    # scenario-inherited: which device to send select/launch to (the role device). None for device pages.
    source_device_id: Optional[str] = None
    options: List[DropdownOption] = Field(default_factory=list)
    loading: bool = False
    empty: bool = False


class PlaybackConfig(_Camel):
    actions: List[ProcessedAction] = Field(default_factory=list)
    layout: Literal["horizontal", "cluster"] = "horizontal"


class TracksConfig(_Camel):
    actions: List[ProcessedAction] = Field(default_factory=list)
    layout: Literal["horizontal", "vertical"] = "horizontal"


class VolumeSliderConfig(_Camel):
    action: ProcessedAction
    mute_action: Optional[ProcessedAction] = None
    orientation: Literal["vertical"] = "vertical"
    show_value: bool = True
    zone: Optional[int] = None
    # serialized device-state field holding the current level (e.g. "zone2_volume"); the UI reads
    # deviceState[valueField] instead of branching on deviceClass (Step-2 hardening).
    value_field: Optional[str] = None
    # native param the level value is sent under (from the set action's param_map: Auralic
    # {level: volume} -> "volume"), else "level". The analogue of DropdownConfig.set_param.
    value_param: Optional[str] = None


class VolumeButtonConfig(_Camel):
    up_action: Optional[ProcessedAction] = None
    down_action: Optional[ProcessedAction] = None
    mute_action: Optional[ProcessedAction] = None
    zone: Optional[int] = None


class NavigationClusterConfig(_Camel):
    up_action: Optional[ProcessedAction] = None
    down_action: Optional[ProcessedAction] = None
    left_action: Optional[ProcessedAction] = None
    right_action: Optional[ProcessedAction] = None
    ok_action: Optional[ProcessedAction] = None
    aux1_action: Optional[ProcessedAction] = None
    aux2_action: Optional[ProcessedAction] = None
    aux3_action: Optional[ProcessedAction] = None
    aux4_action: Optional[ProcessedAction] = None


class PointerPadConfig(_Camel):
    move_action: ProcessedAction
    click_action: Optional[ProcessedAction] = None
    drag_action: Optional[ProcessedAction] = None
    scroll_action: Optional[ProcessedAction] = None


class ZoneContent(_Camel):
    power_buttons: Optional[List[PowerButtonConfig]] = None
    inputs_dropdown: Optional[DropdownConfig] = None
    playback_section: Optional[PlaybackConfig] = None
    tracks_section: Optional[TracksConfig] = None
    screen_actions: Optional[List[ProcessedAction]] = None
    volume_slider: Optional[VolumeSliderConfig] = None
    volume_buttons: Optional[List[VolumeButtonConfig]] = None
    apps_dropdown: Optional[DropdownConfig] = None
    navigation_cluster: Optional[NavigationClusterConfig] = None
    pointer_pad: Optional[PointerPadConfig] = None


class RemoteZone(_Camel):
    zone_id: ZoneType
    zone_name: str
    zone_type: ZoneType
    show_hide: bool
    is_empty: bool
    enabled: Optional[bool] = None
    content: ZoneContent
    layout: ZoneLayoutConfig = Field(default_factory=ZoneLayoutConfig)


# --- build-time carryover (optional; dropped at the Step-4 cutover) ----------------------------
class StateField(_Camel):
    name: str
    type: str
    optional: bool
    description: str = ""


class StateDefinition(_Camel):
    interface_name: str
    fields: List[StateField] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    extends: List[str] = Field(default_factory=list)


class ActionHandler(_Camel):
    action_name: str
    handler_code: str
    dependencies: List[str] = Field(default_factory=list)


class ManualInstructions(_Camel):
    """Static human-in-the-loop notes for a scenario (rendered as a bottom section in the remote)."""
    startup: List[str] = Field(default_factory=list)
    shutdown: List[str] = Field(default_factory=list)


# --- the manifest -----------------------------------------------------------------------------
class LayoutManifest(_Camel):
    """The remote layout for one entity (device or scenario), served at runtime. A superset of the
    UI's ``RemoteDeviceStructure`` (renderer-compatible) plus manifest metadata."""

    device_id: str
    device_name: str
    device_class: str
    remote_zones: List[RemoteZone] = Field(default_factory=list)

    # manifest metadata (new; not in the legacy build-time structure)
    entity_kind: Literal["device", "scenario"] = "device"
    # SCN-6: scenario manifests carry the room's Scenario Manager entity id
    # (`scenario_manager_<room_id>`) — the UI dispatches canonical commands there
    # (power zone -> scenario.set/off; inherited controls -> their canonical tuple).
    canonical_entity_id: Optional[str] = None
    device_category: Literal["device", "appliance"] = "device"
    state_schema: Optional[str] = None  # openapi components.schemas name for live-state binding

    # scenario-only: static manual notes, rendered as a bottom section in the remote (omitted for devices)
    manual_instructions: Optional[ManualInstructions] = None

    # build-time carryover — present in the frozen oracle, omittable at runtime
    state_interface: Optional[StateDefinition] = None
    action_handlers: List[ActionHandler] = Field(default_factory=list)
