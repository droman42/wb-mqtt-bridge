"""Pydantic schema for device capability maps.

The capability map translates canonical ``domain.action`` calls into a device's
native commands/params, and declares how each stateful capability is reconciled
(state field, feedback, timing). The *data* lives in JSON (``config/capabilities/``)
so it can be hot-fixed without a rebuild; these models only validate it.

See ``docs/design/scenarios/scenario_system_redesign.md`` §5 (shape) and §16 (worked maps).
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from wb_mqtt_bridge.domain.devices.config import LocalizedName, ValueLabel, _normalise_value_labels

CapabilityFieldType = Literal["str", "int", "float", "bool", "rgb", "enum"]


class CapabilityAction(BaseModel):
    """How to invoke one canonical action: a native ``command`` (or a ``sequence``
    of native steps) plus optional param renaming and fixed params."""

    model_config = ConfigDict(extra="forbid")

    command: Optional[str] = None
    sequence: Optional[List["CapabilityAction"]] = None
    param_map: Dict[str, str] = Field(
        default_factory=dict, description="canonical_param -> native_param (renames only)"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="fixed native params, e.g. {'zone': 2}"
    )
    delay_after_ms: int = Field(
        default=0, ge=0,
        description="Pause after this step before the next one runs (sequence steps; IR "
                    "macros need inter-press gaps). Ignored on the last/only step. VWB-17.",
    )

    @model_validator(mode="after")
    def _exactly_one_invocation(self) -> "CapabilityAction":
        if (self.command is None) == (self.sequence is None):
            raise ValueError("capability action needs exactly one of `command` or `sequence`")
        return self

    def expand(self, incoming_params: Optional[Dict[str, Any]] = None) -> List["NativeStep"]:
        """Flatten this action into the ordered native steps to execute (VWB-17).

        The single place canonical -> native translation happens, shared by the
        canonical endpoint, the Scenario Manager proxy, and any future dispatcher:

        - command form -> one step: incoming params renamed via ``param_map``
          (names absent from the map pass through unchanged), then the fixed
          ``params`` overlaid;
        - sequence form -> each step expanded recursively, each applying ITS OWN
          ``param_map``/``params`` to the same incoming params.
        """
        incoming = incoming_params or {}
        if self.command is not None:
            native = {self.param_map.get(k, k): v for k, v in incoming.items()}
            native.update(self.params)
            return [NativeStep(command=self.command, params=native,
                               delay_after_ms=self.delay_after_ms)]
        steps: List["NativeStep"] = []
        for sub in (self.sequence or []):
            steps.extend(sub.expand(incoming))
        return steps


class NativeStep(BaseModel):
    """One executable native step produced by :meth:`CapabilityAction.expand`."""

    model_config = ConfigDict(extra="forbid")

    command: str
    params: Dict[str, Any] = Field(default_factory=dict)
    delay_after_ms: int = 0


class CapabilitySelect(BaseModel):
    """Input selection: either parametric (``command`` + ``param_map``, e.g. LG
    ``set_input_source(source=…)``) or value-mapped (``by_value``: one command per
    input value, e.g. the IR amp's ``input_cd`` / ``input_aux2``)."""

    model_config = ConfigDict(extra="forbid")

    command: Optional[str] = None
    param_map: Dict[str, str] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    by_value: Optional[Dict[str, CapabilityAction]] = None

    @model_validator(mode="after")
    def _exactly_one_form(self) -> "CapabilitySelect":
        if (self.command is None) == (self.by_value is None):
            raise ValueError("capability select needs exactly one of `command` or `by_value`")
        return self


class CapabilityGate(BaseModel):
    """Timing for a stateful action. Feedback devices poll ``state_field`` to the
    target (``poll_timeout_ms``); no-feedback devices wait ``delay_ms``."""

    model_config = ConfigDict(extra="forbid")

    poll_timeout_ms: Optional[int] = Field(default=None, ge=0)
    delay_ms: int = Field(default=0, ge=0)


class ZonePower(BaseModel):
    """One zone of a multi-zone power capability (e.g. eMotiva zone 1 / zone 2)."""

    model_config = ConfigDict(extra="forbid")

    state_field: str
    on_value: str | bool | int = "on"
    actions: Dict[str, CapabilityAction]


class CapabilityField(BaseModel):
    """A read-only field on a stateful capability (e.g. `sensor.temperature`,
    `climate.room_temperature`). Drives type-coercion on the device's mirrored state
    and the catalog's per-field metadata so voice/UI consumers can render and parse
    correctly without out-of-band knowledge. Added §P3.7 #19."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Field name (matches the device's state_topics key).")
    type: CapabilityFieldType = Field(..., description="Wire-to-typed coercion kind.")
    encoding: Optional[str] = Field(
        None,
        description="Template-with-placeholders for composite values, e.g. `\"{r};{g};{b}\"` "
                    "for `type=\"rgb\"`. The driver parses incoming echoes back into typed dicts.",
    )
    values: Optional[List[ValueLabel]] = Field(
        None,
        description="Value table for `type=\"enum\"` (§P3.7 #26): each entry carries `wire` "
                    "(MQTT payload), `canonical` (action/state identifier), and optional "
                    "localized `labels`. Bare `[\"a\", \"b\"]` form is back-compat — normalised "
                    "to `[{wire: \"a\", canonical: \"a\"}, ...]` with `labels=None`.",
    )
    unit: Optional[str] = Field(None, description="Display unit (`°C`, `%`, `ppm`, `lux`, `dB`).")
    labels: Optional[LocalizedName] = Field(
        None, description="Localised display label (catalog surface; UI labels)."
    )

    @field_validator("values", mode="before")
    @classmethod
    def _normalise_values(cls, v: Any) -> Any:
        return _normalise_value_labels(v)


class Capability(BaseModel):
    """A canonical capability domain (``power``, ``input``, ``volume``, …)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["stateful", "momentary"]
    feedback: bool = False
    reconcile: bool = Field(
        default=True,
        description="Whether the scenario reconciler drives this capability. False = exposed on the "
                    "page/WB/HTTP but skipped by the reconciler (e.g. a device that auto-powers with "
                    "its source, like the upscaler).",
    )
    state_field: Optional[str] = None
    on_value: str | bool | int = "on"
    gate: CapabilityGate = Field(default_factory=CapabilityGate)
    actions: Dict[str, CapabilityAction] = Field(default_factory=dict)
    select: Optional[CapabilitySelect] = None
    list: Optional[CapabilityAction] = Field(
        default=None, description="query that enumerates options (e.g. get_available_inputs)"
    )
    zones: Optional[Dict[str, ZonePower]] = None
    source_modes: Optional[List[str]] = Field(
        default=None,
        description=(
            "Topology src_port values this device responds to via its `select` action when it "
            "is the SOURCE end of a link in an active scenario path (symmetric to dst_port → "
            "input). Opt-in per device — leave None for sources whose output engages passively. "
            "Example: LG TV `input.source_modes = ['arc']` makes the reconciler emit "
            "`set_input_source(arc)` when the topology routes audio via `living_room_tv:arc`; "
            "the driver translates that to `handle_home` (= 'be on internal mode')."
        ),
    )
    fields: List[CapabilityField] = Field(
        # NOTE: `default_factory=list` would resolve to the FieldInfo of the `list` field
        # above (class-body name shadow), not the builtin. The lambda dodges that.
        default_factory=lambda: [],
        description=(
            "Read-only state surfaces for this capability (e.g. `sensor.temperature/humidity/co2`, "
            "`climate.room_temperature`, `brightness.level`). Drives type coercion in the "
            "WB-passthrough driver and the per-field metadata in the catalog. Empty for momentary "
            "capabilities like `power` whose state lives in `state_field`. Added §P3.7 #19."
        ),
    )

    @model_validator(mode="after")
    def _shape(self) -> "Capability":
        if self.kind == "stateful" and not (self.actions or self.select or self.zones or self.fields):
            raise ValueError(
                "stateful capability needs one of `actions`, `select`, `zones`, or `fields`"
            )
        return self


class CapabilityMap(RootModel[Dict[str, Capability]]):
    """A device's capability map: canonical domain -> :class:`Capability`."""

    def domains(self) -> List[str]:
        return list(self.root.keys())

    def get(self, domain: str) -> Optional[Capability]:
        return self.root.get(domain)
