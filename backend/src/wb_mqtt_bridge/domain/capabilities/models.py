"""Pydantic schema for device capability maps.

The capability map translates canonical ``domain.action`` calls into a device's
native commands/params, and declares how each stateful capability is reconciled
(state field, feedback, timing). The *data* lives in JSON (``config/capabilities/``)
so it can be hot-fixed without a rebuild; these models only validate it.

See ``docs/scenarios/scenario_system_redesign.md`` §5 (shape) and §16 (worked maps).
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


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

    @model_validator(mode="after")
    def _exactly_one_invocation(self) -> "CapabilityAction":
        if (self.command is None) == (self.sequence is None):
            raise ValueError("capability action needs exactly one of `command` or `sequence`")
        return self


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

    @model_validator(mode="after")
    def _shape(self) -> "Capability":
        if self.kind == "stateful" and not (self.actions or self.select or self.zones):
            raise ValueError("stateful capability needs one of `actions`, `select`, or `zones`")
        return self


class CapabilityMap(RootModel[Dict[str, Capability]]):
    """A device's capability map: canonical domain -> :class:`Capability`."""

    def domains(self) -> List[str]:
        return list(self.root.keys())

    def get(self, domain: str) -> Optional[Capability]:
        return self.root.get(domain)
