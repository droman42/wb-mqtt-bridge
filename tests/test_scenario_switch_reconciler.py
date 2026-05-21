"""Integration test: ScenarioManager routes thin scenarios through the reconciler.

Builds a ScenarioManager with fake devices (real capability maps + recording execute_action)
and the real topology, then drives switch_scenario / shutdown for movie_appletv.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.domain.scenarios.scenario import Scenario
from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager
from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.infrastructure.topology.loader import load_topology

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
CAPS = ROOT / "config" / "capabilities"
TOPOLOGY = load_topology(ROOT / "config" / "topology.json")


def _devices(calls):
    def fake(device_class, device_id, **state):
        caps = load_capability_map(device_class, device_id, CAPS)
        st = SimpleNamespace(power="off", **state)

        async def execute_action(command, params, source="unknown", _id=device_id):
            calls.append((_id, command))
            return {"success": True}

        return SimpleNamespace(capabilities=caps, get_current_state=lambda _st=st: _st,
                               execute_action=execute_action)

    return {
        "appletv_living": fake("AppleTVDevice", "appletv_living"),
        "processor": fake("EMotivaXMC2", "processor", zone2_power=None, input_source=None),
        "living_room_tv": fake("LgTv", "living_room_tv", input_source=None),
        "mf_amplifier": fake("WirenboardIRDevice", "mf_amplifier", input=None),
    }


def _manager(devices):
    async def _save(*a, **k):
        return None

    sm = ScenarioManager(
        device_manager=SimpleNamespace(devices=devices),
        room_manager=SimpleNamespace(),
        state_repository=SimpleNamespace(save=_save),
        scenario_dir=ROOT / "config" / "scenarios",
    )
    sm.topology = TOPOLOGY
    sm._reconciler_enabled = True
    defn = ScenarioDefinition.model_validate(
        json.loads((ROOT / "config" / "scenarios" / "movie_appletv.json").read_text())
    )
    sm.scenario_map = {"movie_appletv": Scenario(defn, sm.device_manager)}
    return sm


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import wb_mqtt_bridge.infrastructure.scenarios.reconciler as rec

    async def _nosleep(*a, **k):
        return None

    monkeypatch.setattr(rec.asyncio, "sleep", _nosleep)


@pytest.mark.asyncio
async def test_switch_activates_movie_appletv_via_reconciler():
    calls: list = []
    sm = _manager(_devices(calls))
    result = await sm.switch_scenario("movie_appletv")

    assert result["success"] and result["manual_steps"] == []
    assert sm.current_scenario.scenario_id == "movie_appletv"

    dev_seq = [d for d, _ in calls]
    # TV power before eMotiva power (HDMI-ARC ordering edge)
    assert dev_seq.index("living_room_tv") < dev_seq.index("processor")
    # translated native commands actually dispatched (RC1 fixed)
    assert ("living_room_tv", "set_input_source") in calls
    assert ("processor", "set_input") in calls
    assert ("mf_amplifier", "input_aux2") in calls


@pytest.mark.asyncio
async def test_shutdown_powers_off_involved_devices():
    calls: list = []
    devices = _devices(calls)
    for d in devices.values():
        d.get_current_state().power = "on"
    devices["processor"].get_current_state().zone2_power = "on"

    sm = _manager(devices)
    sm.current_scenario = sm.scenario_map["movie_appletv"]
    await sm.shutdown()

    assert ("living_room_tv", "power_off") in calls
    assert ("mf_amplifier", "power") in calls  # toggle off
    assert sm.current_scenario is None
