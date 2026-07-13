"""Report models (problem_reports_bridge.md). ``EvidenceEnvelope`` is the B-11
contract surface: the bridge owns its shape; the voice side pins its expectation
via the OpenAPI schema in ``contracts/``."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceEnvelope(BaseModel):
    """The bundle-shaped evidence — returned by ``GET /reports/evidence`` (redacted,
    no filing) and embedded in every filed bundle. Top-level keys are the contract."""

    generated_at: str = Field(description="UTC ISO-8601 timestamp of collection")
    bridge: Dict[str, Any] = Field(description="version, platform, catalog_version")
    context: Dict[str, Any] = Field(default_factory=dict,
                                    description="entity_id/room the report is anchored to + the scoped device set")
    states: Dict[str, Any] = Field(default_factory=dict, description="live state of EVERY device (B-1)")
    state_diffs: Dict[str, Any] = Field(default_factory=dict,
                                        description="persisted-vs-live field diffs for the scoped devices")
    scenarios: Dict[str, Any] = Field(default_factory=dict, description="active scenario + manual steps per room")
    configs: Dict[str, Any] = Field(default_factory=dict, description="scoped device configs, redacted")
    system_config: Dict[str, Any] = Field(default_factory=dict, description="system.json, redacted")
    dispatch_ring: List[Dict[str, Any]] = Field(default_factory=list, description="last executed actions (B-2)")
    mqtt_window: List[Dict[str, Any]] = Field(default_factory=list, description="recent broker traffic (B-2)")
    logs: Dict[str, str] = Field(default_factory=dict, description="log filename -> base64(gzip(content))")


@dataclass
class ReportsSettings:
    """Plain settings handed to the domain service (built from the infra config in bootstrap).
    The target repo is the sink's concern (see ``GitHubReportSink``), not the domain's."""
    enabled: bool = False
    max_reports_per_hour: int = 3
    max_reports_per_day: int = 10
    log_file: Optional[Path] = None


@dataclass
class ReportFiling:
    """One filing, ready for the sink: the §5 envelope (issue + bundle commit)."""
    report_id: str
    title: str
    body: str
    labels: List[str]
    bundle_name: str
    bundle_bytes: bytes = field(repr=False)


@dataclass
class ReportFilingResult:
    report_id: str
    filed: bool
    spooled: bool
    url: Optional[str] = None
