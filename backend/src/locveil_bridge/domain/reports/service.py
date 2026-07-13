"""Report service (problem_reports_bridge.md): the evidence collector behind BOTH
``POST /reports`` (file a ticket) and ``GET /reports/evidence`` (the B-11 read seam
the voice collector folds into voice bundles).

Cross-layer inputs arrive as injected callables (system config, persisted state,
catalog version) so the domain stays import-pure; managers and rings are domain
types. Filing goes through ``ReportSinkPort``.
"""

import gzip
import io
import json
import logging
import tarfile
import time
import uuid
from base64 import b64encode
from collections import deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from locveil_bridge.domain.devices.service import DeviceManager
from locveil_bridge.domain.ports import ReportSinkPort
from locveil_bridge.domain.reports.models import (
    EvidenceEnvelope,
    ReportFiling,
    ReportFilingResult,
    ReportsSettings,
)
from locveil_bridge.domain.reports.redaction import redact_mapping, redact_text
from locveil_bridge.domain.reports.rings import DispatchRing, MqttWindow
from locveil_bridge.domain.scenarios.service import ScenarioManager

logger = logging.getLogger(__name__)

# The wire-visible filing surface — locked to the pinned Locveil report-protocol
# core (``contracts/pins/report-protocol/``, tag ``report-protocol-v1``) by the
# conformance test in ``tests/unit/test_report_protocol_pin.py``. Change the pin
# first; the test keeps these from drifting silently (VWB-37 / PROD-6).
REPORT_SOURCE = "bridge-ui"
REPORT_TITLE_PREFIX = f"[{REPORT_SOURCE}]"
REPORT_FILED_LABELS = ("problem-report", "lens:bridge", "new")
REPORT_BUNDLE_NAME = "bundle.tar.gz"


class RateLimited(Exception):
    """Raised when the B-6 client-side rate limit blocks a filing."""


class ReportService:
    def __init__(
        self,
        *,
        settings: ReportsSettings,
        device_manager: DeviceManager,
        scenario_manager: ScenarioManager,
        sink: Optional[ReportSinkPort],
        dispatch_ring: DispatchRing,
        mqtt_window: MqttWindow,
        persisted_state: Callable[[str], Awaitable[Optional[Dict[str, Any]]]],
        system_config: Callable[[], Dict[str, Any]],
        catalog_version: Callable[[], str],
        bridge_version: str,
        platform: str,
    ):
        self.settings = settings
        self._devices = device_manager
        self._scenarios = scenario_manager
        self._sink = sink
        self._dispatch_ring = dispatch_ring
        self._mqtt_window = mqtt_window
        self._persisted_state = persisted_state
        self._system_config = system_config
        self._catalog_version = catalog_version
        self._bridge_version = bridge_version
        self._platform = platform
        self._filing_times: deque[float] = deque()

    # --- scoping (B-1) --------------------------------------------------------

    def _scoped_devices(self, entity_id: Optional[str]) -> List[str]:
        """The report anchor + its topology neighbors (the page-context set)."""
        if not entity_id:
            return []
        scoped = {entity_id}
        for link in self._scenarios.topology.links:
            if link.src_node == entity_id:
                scoped.add(link.dst_node)
            elif link.dst_node == entity_id:
                scoped.add(link.src_node)
        # only real devices (manual topology nodes have no driver to report on)
        return sorted(d for d in scoped if d in self._devices.devices)

    # --- evidence (B-11: also served without filing) ---------------------------

    async def collect_evidence(self, entity_id: Optional[str] = None) -> EvidenceEnvelope:
        devices = self._devices.devices
        scoped = self._scoped_devices(entity_id)

        states: Dict[str, Any] = {}
        for did, device in devices.items():
            try:
                state = device.get_current_state()
                states[did] = state.model_dump() if hasattr(state, "model_dump") else dict(state)
            except Exception as e:  # noqa: BLE001 - one bad device must not sink the bundle
                states[did] = {"_error": str(e)}

        state_diffs: Dict[str, Any] = {}
        for did in scoped:
            try:
                persisted = await self._persisted_state(did)
            except Exception as e:  # noqa: BLE001
                state_diffs[did] = {"_error": str(e)}
                continue
            if not persisted:
                continue
            live = states.get(did, {})
            diff = {
                k: {"persisted": v, "live": live.get(k)}
                for k, v in persisted.items()
                if k in live and live.get(k) != v
            }
            if diff:
                state_diffs[did] = diff

        scenarios: Dict[str, Any] = {}
        for room, sc in self._scenarios.active.items():
            st = self._scenarios.get_scenario_state(sc.scenario_id)
            scenarios[room] = {
                "active": sc.scenario_id,
                "manual_steps": [m.model_dump() for m in st.manual_steps],
            }

        configs: Dict[str, Any] = {}
        for did in scoped:
            cfg = getattr(devices[did], "config", None)
            if cfg is not None and hasattr(cfg, "model_dump"):
                configs[did] = redact_mapping(cfg.model_dump(mode="json"))

        return EvidenceEnvelope(
            generated_at=datetime.now(timezone.utc).isoformat(),
            bridge={
                "version": self._bridge_version,
                "platform": self._platform,
                "catalog_version": self._safe_catalog_version(),
            },
            context={"entity_id": entity_id, "scoped_devices": scoped},
            states=states,
            state_diffs=state_diffs,
            scenarios=scenarios,
            configs=configs,
            system_config=redact_mapping(self._system_config()),
            dispatch_ring=self._dispatch_ring.snapshot(),
            mqtt_window=self._mqtt_window.snapshot(),
            logs=self._collect_logs(),
        )

    def _safe_catalog_version(self) -> str:
        try:
            return self._catalog_version()
        except Exception as e:  # noqa: BLE001
            return f"unavailable: {e}"

    def _collect_logs(self) -> Dict[str, str]:
        """Today's log + the newest rotated sibling, gzipped + base64 (redacted)."""
        out: Dict[str, str] = {}
        log_file = self.settings.log_file
        if log_file is None or not log_file.exists():
            return out
        candidates = [log_file]
        rotated = sorted(log_file.parent.glob(log_file.name + ".*"), reverse=True)
        if rotated:
            candidates.append(rotated[0])
        for p in candidates:
            try:
                text = redact_text(p.read_text(encoding="utf-8", errors="replace"))
                out[p.name + ".gz"] = b64encode(gzip.compress(text.encode("utf-8"))).decode("ascii")
            except Exception as e:  # noqa: BLE001
                out[p.name] = f"unreadable: {e}"
        return out

    # --- filing (B-6/B-8) -------------------------------------------------------

    def _check_rate_limit(self) -> None:
        now = time.time()
        while self._filing_times and self._filing_times[0] < now - 86400:
            self._filing_times.popleft()
        last_hour = sum(1 for t in self._filing_times if t > now - 3600)
        if last_hour >= self.settings.max_reports_per_hour or \
                len(self._filing_times) >= self.settings.max_reports_per_day:
            raise RateLimited(
                f"rate limit reached ({self.settings.max_reports_per_hour}/hour, "
                f"{self.settings.max_reports_per_day}/day)"
            )

    async def file_report(
        self,
        free_text: str,
        context: Optional[Dict[str, Any]] = None,
        ui_evidence: Optional[Dict[str, Any]] = None,
    ) -> ReportFilingResult:
        if self._sink is None or not self.settings.enabled:
            raise RuntimeError("report filing is not enabled (system.json `reports.enabled`)")
        self._check_rate_limit()

        context = context or {}
        entity_id = context.get("entity_id")
        evidence = await self.collect_evidence(entity_id)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        room = self._room_of(entity_id) or "house"
        # VWB-30 (#15): the timestamp is second-granular, so two reports filed in the
        # same second + room collided — the report_id doubles as the spool filename, so a
        # collision silently overwrote one bundle / left it permanently undeliverable. A
        # short random suffix makes the id (and the spool file) unique.
        report_id = f"{ts}-{REPORT_SOURCE}-{room}-{uuid.uuid4().hex[:8]}"

        bundle = self._build_bundle(evidence, context, ui_evidence)
        title = f"{REPORT_TITLE_PREFIX} {redact_text(free_text.strip())[:60]}"
        body = self._issue_body(report_id, free_text, context, evidence)
        filing = ReportFiling(
            report_id=report_id,
            title=title,
            body=body,
            labels=list(REPORT_FILED_LABELS),
            bundle_name=REPORT_BUNDLE_NAME,
            bundle_bytes=bundle,
        )
        result = await self._sink.file_report(filing)
        self._filing_times.append(time.time())
        logger.info("problem report %s: filed=%s spooled=%s", report_id, result.filed, result.spooled)
        return result

    def _room_of(self, entity_id: Optional[str]) -> Optional[str]:
        if not entity_id:
            return None
        device = self._devices.devices.get(entity_id)
        room = getattr(device, "get_room", None)
        try:
            value = room() if callable(room) else None
        except Exception:  # noqa: BLE001
            return None
        return str(value) if value is not None else None

    def _build_bundle(
        self,
        evidence: EvidenceEnvelope,
        context: Dict[str, Any],
        ui_evidence: Optional[Dict[str, Any]],
    ) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            def add(name: str, data: bytes) -> None:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            add("evidence.json", evidence.model_dump_json(indent=2).encode("utf-8"))
            add("context.json", json.dumps(context, indent=2, ensure_ascii=False).encode("utf-8"))
            if ui_evidence is not None:
                add("ui_evidence.json",
                    json.dumps(redact_mapping(ui_evidence), indent=2, ensure_ascii=False).encode("utf-8"))
        return buf.getvalue()

    def _issue_body(
        self,
        report_id: str,
        free_text: str,
        context: Dict[str, Any],
        evidence: EvidenceEnvelope,
    ) -> str:
        """The distilled §5 summary — triage should rarely need the tarball."""
        diffs = ", ".join(
            f"{d}: {', '.join(sorted(fields))}" for d, fields in evidence.state_diffs.items()
        ) or "none"
        recent = "\n".join(
            f"- `{e['source']}` {e['device_id']}.{e['action']}({e['params']}) → "
            f"{'ok' if e['success'] else 'FAILED: ' + str(e.get('error'))}"
            for e in evidence.dispatch_ring[-5:]
        ) or "- (empty)"
        return "\n".join([
            "## Report (verbatim)",
            "",
            redact_text(free_text.strip()),
            "",
            "## Context",
            f"- page/route: `{context.get('route', '?')}` · entity: `{context.get('entity_id')}`",
            f"- bridge {evidence.bridge['version']} · catalog `{evidence.bridge['catalog_version']}`"
            f" · {evidence.bridge['platform']}",
            f"- persisted-vs-live diffs: {diffs}",
            "",
            "## Last dispatches",
            recent,
            "",
            f"Bundle: `reports/{report_id}/bundle.tar.gz` · report-id: `{report_id}`",
        ])
