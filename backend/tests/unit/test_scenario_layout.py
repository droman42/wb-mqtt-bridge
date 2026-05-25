"""Layer-3 scenario manifest — conformance to the design (scenario_system_redesign.md §6).

Scenarios have no trustworthy build-time oracle (the old `.gen.tsx` pages were buggy), so we assert
the *design contract* the composite remote must satisfy, not a render-diff:
  - entityKind="scenario"; manual_instructions carried from the def;
  - the power zone is the scenario lifecycle (power_off/power_on, NO sourceDeviceId);
  - every role-bound control is tagged with its role device's sourceDeviceId;
  - the `inputs` role is NOT rendered (target inputs are reconciler-derived).
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.infrastructure.config.models import StandardCommandConfig
from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.presentation.api.layout_engine import build_scenario_manifest


def _backend_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "scenarios").is_dir():
            return parent
    return None


ROOT = _backend_root()


def _make_device(name: str, device_class: str):
    cfg = json.loads((ROOT / "config" / "devices" / f"{name}.json").read_text())
    commands = {n: StandardCommandConfig.model_validate(c) for n, c in cfg["commands"].items()}
    config = SimpleNamespace(
        device_id=cfg["device_id"], device_name=cfg["device_name"],
        device_class=device_class, device_category="device", commands=commands,
    )
    dev = SimpleNamespace(
        config=config,
        capabilities=load_capability_map(device_class, name, ROOT / "config" / "capabilities"),
        state=None,
    )
    dev.get_available_commands = lambda c=commands: c
    return cfg["device_id"], dev


@pytest.mark.skipif(ROOT is None, reason="config/ not present")
def test_scenario_manifest_movie_appletv():
    devices = {}
    for name, cls in [("appletv_living", "AppleTVDevice"), ("mf_amplifier", "WirenboardIRDevice"),
                      ("emotiva_xmc2", "EMotivaXMC2")]:
        did, dev = _make_device(name, cls)
        devices[did] = dev
    dm = SimpleNamespace(devices=devices)

    sdef = ScenarioDefinition.model_validate(
        json.loads((ROOT / "config" / "scenarios" / "movie_appletv.json").read_text())
    )
    m = build_scenario_manifest(sdef, dm).model_dump(by_alias=True)

    assert m["entityKind"] == "scenario"
    assert m["deviceId"] == "movie_appletv"
    assert m["manualInstructions"]["startup"] and m["manualInstructions"]["shutdown"]

    zones = {z["zoneId"]: z for z in m["remoteZones"]}

    # power zone = scenario lifecycle: power_off (left) / power_on (right), NO sourceDeviceId
    pw = zones["power"]["content"]["powerButtons"]
    assert [b["action"]["actionName"] for b in pw] == ["power_off", "power_on"]
    assert all(b["action"].get("sourceDeviceId") is None for b in pw)

    # role-bound controls carry their role device's sourceDeviceId (movie_appletv roles)
    assert zones["volume"]["content"]["volumeButtons"][0]["upAction"]["sourceDeviceId"] == "mf_amplifier"
    assert all(a["sourceDeviceId"] == "appletv_living"
               for a in zones["media-stack"]["content"]["playbackSection"]["actions"])
    assert zones["apps"]["content"]["appsDropdown"]["sourceDeviceId"] == "appletv_living"
    nc = zones["menu"]["content"]["navigationCluster"]
    assert any(v and v.get("sourceDeviceId") == "appletv_living" for v in nc.values())

    # the `inputs` role (-> processor) is NOT rendered — reconciler-derived, not a UI control
    assert zones["media-stack"]["content"].get("inputsDropdown") is None


@pytest.mark.skipif(ROOT is None, reason="config/ not present")
def test_scenario_manifest_music_tape_passive_source():
    """A passive-source scenario (manual node 'b215', no driver) builds from its roles
    only — the amp volume zone + the static manual instructions; the non-device source is
    never dereferenced, so the manifest builds cleanly."""
    did, amp = _make_device("mf_amplifier", "WirenboardIRDevice")
    dm = SimpleNamespace(devices={did: amp})

    sdef = ScenarioDefinition.model_validate(
        json.loads((ROOT / "config" / "scenarios" / "music_tape.json").read_text())
    )
    m = build_scenario_manifest(sdef, dm).model_dump(by_alias=True)

    assert m["entityKind"] == "scenario"
    assert m["deviceId"] == "music_tape"
    assert any("B215" in s for s in m["manualInstructions"]["startup"])

    zones = {z["zoneId"]: z for z in m["remoteZones"]}
    # power zone = scenario lifecycle (no sourceDeviceId)
    pw = zones["power"]["content"]["powerButtons"]
    assert [b["action"]["actionName"] for b in pw] == ["power_off", "power_on"]
    # the only rendered control is the amp volume (everything else is manual)
    assert zones["volume"]["content"]["volumeButtons"][0]["upAction"]["sourceDeviceId"] == "mf_amplifier"
