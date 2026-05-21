"""Pydantic schema for the signal topology (``config/topology.json``).

See ``docs/scenarios/scenario_system_redesign.md`` §4. The data is hot-fixable JSON;
this is only the validator. A link's destination port is the input value to select
on the sink device; ordering edges are unambiguous ``first -> then``.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SignalKind = Literal["video", "audio", "arc"]


class ManualNode(BaseModel):
    """A signal-routing element switched by hand (no driver), e.g. an RCA hub."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["manual"] = "manual"
    name: str
    positions: Dict[str, str] = Field(
        default_factory=dict,
        description="position-id -> human instruction surfaced when that position is needed",
    )


class TopologyLink(BaseModel):
    """A physical connection. ``from``/``to`` are ``<node>:<port>``; the *destination*
    port is the input value to select on the sink device."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str = Field(..., alias="from", description="<node>:<port> source/output end")
    to: str = Field(..., description="<node>:<port> sink end (dst port = input value)")
    carries: List[SignalKind] = Field(..., min_length=1)

    @staticmethod
    def _node(endpoint: str) -> str:
        return endpoint.split(":", 1)[0]

    @staticmethod
    def _port(endpoint: str) -> str:
        return endpoint.split(":", 1)[1] if ":" in endpoint else ""

    @property
    def src_node(self) -> str:
        return self._node(self.from_)

    @property
    def dst_node(self) -> str:
        return self._node(self.to)

    @property
    def dst_port(self) -> str:
        """The input value to select on the sink device for this link."""
        return self._port(self.to)


class OrderingEdge(BaseModel):
    """``first`` must complete before ``then`` runs; ``delay_ms`` is an extra wait
    used where ``first`` is a no-feedback device (otherwise gating is by polling)."""

    model_config = ConfigDict(extra="forbid")

    first: str = Field(..., description="<device>.<capability> that must complete first")
    then: str = Field(..., description="<device>.<capability> that runs after `first`")
    delay_ms: int = Field(default=0, ge=0)
    reason: str = ""


class Topology(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    comment_: Optional[str] = Field(default=None, alias="_comment")
    nodes: Dict[str, ManualNode] = Field(default_factory=dict)
    links: List[TopologyLink] = Field(default_factory=list)
    ordering: List[OrderingEdge] = Field(default_factory=list)
