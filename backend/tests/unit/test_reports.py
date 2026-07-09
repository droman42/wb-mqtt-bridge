"""Problem-reporting machinery (problem_reports_bridge.md, VWB-28).

Covers the evidence rings (B-2/B-9), the redaction pass (B-5), the collector +
filing service (B-1/B-6/B-8), the spool round-trip (B-7, temp-dir e2e), and the
two endpoints (B-8 filing gates + the B-11 evidence read seam)."""

import gzip
import json
import tarfile
import io
from base64 import b64decode
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wb_mqtt_bridge.domain.ports import ReportSinkPort
from wb_mqtt_bridge.domain.reports.models import ReportFiling, ReportFilingResult, ReportsSettings
from wb_mqtt_bridge.domain.reports.redaction import redact_mapping, redact_text
from wb_mqtt_bridge.domain.reports.rings import DispatchRing, MqttWindow
from wb_mqtt_bridge.domain.reports.service import RateLimited, ReportService
from wb_mqtt_bridge.infrastructure.reports.github_sink import GitHubReportSink
from wb_mqtt_bridge.presentation.api.routers import reports as reports_router


# --- rings -------------------------------------------------------------------


def test_dispatch_ring_bounded_and_ordered():
    ring = DispatchRing(depth=3)
    for i in range(5):
        ring.record(source="ui", device_id="amp", action=f"a{i}", params={}, success=True)
    snap = ring.snapshot()
    assert [e["action"] for e in snap] == ["a2", "a3", "a4"]
    assert all(e["source"] == "ui" and e["device_id"] == "amp" for e in snap)


def test_mqtt_window_filters_dedups_and_caps():
    w = MqttWindow(max_age_s=60, max_entries=3)
    w.record("in", "unrelated/topic", "x")           # filtered: not /devices/#
    w.record("in", "/devices/amp/controls/volume", "1")
    w.record("in", "/devices/amp/controls/volume", "2")  # dedup: replaces the "1"
    w.record("out", "/devices/amp/controls/volume", "3")  # different direction: kept separately
    snap = w.snapshot()
    assert len(snap) == 2
    in_entry = next(e for e in snap if e["direction"] == "in")
    assert in_entry["payload"] == "2"
    for i in range(5):
        w.record("in", f"/devices/d{i}/controls/x", "v")
    assert len(w.snapshot()) == 3  # max_entries cap


# --- redaction (B-5) -----------------------------------------------------------


def test_redact_mapping_masks_credential_shaped_keys():
    cfg = {
        "mqtt_broker": {"host": "192.168.1.1", "auth": {"username": "admin", "password": "hunter2"}},
        "token_env": "WB_REPORTS_TOKEN",  # the env var NAME is not a secret
        "api_key": "abc", "secret_thing": "x", "device_id": "amp",
    }
    red = redact_mapping(cfg)
    assert red["mqtt_broker"]["auth"]["password"] == "***"
    assert red["api_key"] == "***" and red["secret_thing"] == "***"
    assert red["mqtt_broker"]["host"] == "192.168.1.1"
    assert red["device_id"] == "amp"
    # "token_env" contains "token" -> masked; over-redaction is the safe direction
    assert red["token_env"] == "***"


def test_redact_text_masks_assignments():
    text = "Authorization: Bearer xyz\npassword=hunter2\nnormal line stays"
    red = redact_text(text)
    assert "xyz" not in red and "hunter2" not in red
    assert "normal line stays" in red


def test_redact_mapping_masks_secret_container_leaves():
    """VWB-30 #13: a credential-shaped key holding a container used to recurse and leak
    any leaf that lacked its own secret-shaped key."""
    obj = {
        "credentials": {"primary": "SECRET1", "secondary": ["SECRET2", {"deep": "SECRET3"}]},
        "auth": {"username": "admin", "password": "x"},
        "device_id": "amp",
    }
    red = redact_mapping(obj)
    # every leaf under a credential-shaped key is masked, structure preserved
    assert red["credentials"] == {"primary": "***", "secondary": ["***", {"deep": "***"}]}
    assert red["auth"] == {"username": "***", "password": "***"}
    assert red["device_id"] == "amp"  # non-secret key still passes through


def test_redact_text_masks_url_embedded_credentials():
    """VWB-30 #14: a broker URL carries no keyword before the password."""
    red = redact_text("connecting to mqtt://admin:t6uxESDN@192.168.110.250:1883")
    assert "t6uxESDN" not in red
    assert "admin" in red and "192.168.110.250" in red  # user + host stay diagnostic


@pytest.mark.asyncio
async def test_file_report_ids_are_unique(tmp_path):
    """VWB-30 #15: report_id doubles as the spool filename — two reports in the same
    second + room must not collide (silent overwrite / undeliverable)."""
    sink = _RecordingSink()
    svc = _service(tmp_path, sink=sink)
    await svc.file_report("first", context={"entity_id": "amp"})
    await svc.file_report("second", context={"entity_id": "amp"})
    ids = [f.report_id for f in sink.filings]
    assert len(ids) == 2 and ids[0] != ids[1]


# --- service fakes --------------------------------------------------------------


class _FakeState:
    def __init__(self, **kw):
        self._d = kw
    def model_dump(self):
        return dict(self._d)


def _fake_device(device_id: str, room: str = "living_room", **state):
    cfg = SimpleNamespace(model_dump=lambda mode="json": {"device_id": device_id, "password": "s3cret"})
    return SimpleNamespace(
        device_id=device_id,
        config=cfg,
        get_current_state=lambda: _FakeState(device_id=device_id, **state),
        get_room=lambda: room,
    )


class _RecordingSink(ReportSinkPort):
    def __init__(self):
        self.filings: list[ReportFiling] = []
    async def file_report(self, filing: ReportFiling) -> ReportFilingResult:
        self.filings.append(filing)
        return ReportFilingResult(report_id=filing.report_id, filed=True, spooled=False, url="http://t/1")
    async def retry_spooled(self) -> int:
        return 0


def _service(tmp_path: Optional[Path] = None, enabled: bool = True, sink: Optional[ReportSinkPort] = None,
             persisted: Optional[Dict[str, Dict[str, Any]]] = None) -> ReportService:
    devices = {
        "amp": _fake_device("amp", power="on", input="cd"),
        "tv": _fake_device("tv", power="off"),
        "streamer": _fake_device("streamer", power="on"),
    }
    dm = SimpleNamespace(devices=devices)
    topology = SimpleNamespace(links=[SimpleNamespace(src_node="streamer", dst_node="amp")])
    sm = SimpleNamespace(topology=topology, active={}, get_scenario_state=lambda sid: None)
    persisted = persisted or {}

    async def _persisted_state(did: str):
        return persisted.get(did)

    log_file = None
    if tmp_path is not None:
        log_file = tmp_path / "service.log"
        log_file.write_text("boot ok\npassword=hunter2\n", encoding="utf-8")

    ring = DispatchRing()
    ring.record(source="ui", device_id="amp", action="input_cd", params={}, success=False, error="boom")
    return ReportService(
        settings=ReportsSettings(enabled=enabled, log_file=log_file),
        device_manager=dm,  # type: ignore[arg-type] - duck-typed fake
        scenario_manager=sm,  # type: ignore[arg-type]
        sink=sink if sink is not None else _RecordingSink(),
        dispatch_ring=ring,
        mqtt_window=MqttWindow(),
        persisted_state=_persisted_state,
        system_config=lambda: {"mqtt_broker": {"auth": {"password": "t0psecret"}}, "log_level": "INFO"},
        catalog_version=lambda: "cafebabe",
        bridge_version="0.5.0-test",
        platform="test-arch",
    )


# --- collector (B-1/B-11) --------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_scopes_to_entity_and_topology_neighbors(tmp_path):
    svc = _service(tmp_path, persisted={"amp": {"power": "off", "input": "cd"}})
    env = await svc.collect_evidence("amp")
    # all live states, always (B-1)
    assert set(env.states) == {"amp", "tv", "streamer"}
    # scoped set = anchor + topology neighbor, not the unrelated tv
    assert env.context["scoped_devices"] == ["amp", "streamer"]
    assert set(env.configs) == {"amp", "streamer"}
    # persisted-vs-live diff caught the desync on power (cd == cd is not a diff)
    assert env.state_diffs["amp"] == {"power": {"persisted": "off", "live": "on"}}
    # redaction applied to configs and system config
    assert env.configs["amp"]["password"] == "***"
    assert env.system_config["mqtt_broker"]["auth"]["password"] == "***"
    # logs present, gzipped+b64, redacted
    (name, blob), = [(k, v) for k, v in env.logs.items() if k.endswith(".gz")]
    text = gzip.decompress(b64decode(blob)).decode()
    assert "boot ok" in text and "hunter2" not in text
    assert env.bridge == {"version": "0.5.0-test", "platform": "test-arch", "catalog_version": "cafebabe"}


@pytest.mark.asyncio
async def test_evidence_without_entity_has_no_scoped_set(tmp_path):
    env = await _service(tmp_path).collect_evidence(None)
    assert env.context["scoped_devices"] == []
    assert env.configs == {} and env.state_diffs == {}
    assert set(env.states) == {"amp", "tv", "streamer"}
    assert env.dispatch_ring[-1]["action"] == "input_cd"


# --- filing (B-6/B-8) -------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_report_builds_envelope_and_respects_rate_limit(tmp_path):
    sink = _RecordingSink()
    svc = _service(tmp_path, sink=sink)
    result = await svc.file_report("свет в спальне не включается",
                                   context={"route": "/devices/amp", "entity_id": "amp"},
                                   ui_evidence={"console": ["boom"], "api_token": "leak-me"})
    assert result.filed and not result.spooled
    filing = sink.filings[0]
    assert filing.title.startswith("[bridge-ui] свет в спальне")
    assert filing.labels == ["problem-report", "lens:bridge", "new"]
    assert "-bridge-ui-living_room" in filing.report_id
    with tarfile.open(fileobj=io.BytesIO(filing.bundle_bytes), mode="r:gz") as tar:
        names = tar.getnames()
        assert {"evidence.json", "context.json", "ui_evidence.json"} <= set(names)
        f = tar.extractfile("ui_evidence.json")
        assert f is not None
        ui = json.loads(f.read().decode())
        assert ui["api_token"] == "***"  # B-5 applies to browser evidence too
    # the body is the distilled §5 summary
    assert "report-id" in filing.body and "Last dispatches" in filing.body

    # rate limit: 3/hour default -> the 4th raises
    await svc.file_report("x", {}, None)
    await svc.file_report("y", {}, None)
    with pytest.raises(RateLimited):
        await svc.file_report("z", {}, None)


@pytest.mark.asyncio
async def test_file_report_disabled_raises(tmp_path):
    svc = _service(tmp_path, enabled=False)
    with pytest.raises(RuntimeError):
        await svc.file_report("text", {}, None)


# --- spool round-trip (B-7, temp-dir e2e) ------------------------------------------


@pytest.mark.asyncio
async def test_github_sink_spools_on_failure_and_retries(tmp_path, monkeypatch):
    spool = tmp_path / "spool"
    sink = GitHubReportSink(repo="x/y", token_env="NO_SUCH_TOKEN_ENV", spool_dir=spool)
    monkeypatch.delenv("NO_SUCH_TOKEN_ENV", raising=False)
    filing = ReportFiling(report_id="r1", title="t", body="b", labels=["l"],
                          bundle_name="bundle.tar.gz", bundle_bytes=b"BYTES")
    result = await sink.file_report(filing)
    assert result.spooled and not result.filed
    (spooled_file,) = list(spool.glob("*.json"))

    delivered: list[str] = []

    async def _ok(f: ReportFiling) -> str:
        assert f.bundle_bytes == b"BYTES"  # bundle survives the b64 round-trip
        delivered.append(f.report_id)
        return "http://t/1"

    monkeypatch.setattr(sink, "_deliver", _ok)
    assert await sink.retry_spooled() == 1
    assert delivered == ["r1"] and not spooled_file.exists()


# --- endpoints (B-8 gates + B-11) ----------------------------------------------------


@pytest.fixture()
def client(tmp_path):
    svc = _service(tmp_path)
    reports_router.initialize(svc)
    app = FastAPI()
    app.include_router(reports_router.router)
    return TestClient(app)


def test_evidence_endpoint_returns_envelope(client):
    resp = client.get("/reports/evidence", params={"entity_id": "amp"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["context"]["scoped_devices"] == ["amp", "streamer"]
    assert set(body["states"]) == {"amp", "tv", "streamer"}
    assert body["bridge"]["catalog_version"] == "cafebabe"


def test_post_report_files_and_rate_limits(client):
    ok = client.post("/reports", json={"free_text": "не работает", "context": {"entity_id": "amp"}})
    assert ok.status_code == 200
    body = ok.json()
    assert body["success"] and not body["spooled"] and body["report_id"]
    for _ in range(2):
        assert client.post("/reports", json={"free_text": "x"}).status_code == 200
    assert client.post("/reports", json={"free_text": "x"}).status_code == 429


def test_post_report_disabled_is_503(tmp_path):
    reports_router.initialize(_service(tmp_path, enabled=False))
    app = FastAPI()
    app.include_router(reports_router.router)
    resp = TestClient(app).post("/reports", json={"free_text": "x"})
    assert resp.status_code == 503
    # ...but the B-11 evidence read seam stays available when filing is off
    assert TestClient(app).get("/reports/evidence").status_code == 200
