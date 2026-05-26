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
from wb_mqtt_bridge.domain.topology.loader import load_topology

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
        "ld_player": fake("WirenboardIRDevice", "ld_player"),
        "vhs_player": fake("WirenboardIRDevice", "vhs_player"),
        "video": fake("WirenboardIRDevice", "video"),
        "upscaler": fake("WirenboardIRDevice", "upscaler", input=None),
    }


def _manager(devices, scenario_name="movie_appletv"):
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
        json.loads((ROOT / "config" / "scenarios" / f"{scenario_name}.json").read_text())
    )
    sm.scenario_map = {scenario_name: Scenario(defn, sm.device_manager)}
    return sm


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import wb_mqtt_bridge.domain.scenarios.reconciler as rec

    async def _nosleep(*a, **k):
        return None

    monkeypatch.setattr(rec.asyncio, "sleep", _nosleep)


@pytest.mark.asyncio
async def test_switch_activates_movie_appletv_via_reconciler():
    calls: list = []
    sm = _manager(_devices(calls))
    result = await sm.switch_scenario("movie_appletv")

    assert result["success"]
    assert sm.current_scenario.scenario_id == "movie_appletv"
    # ScenarioState owns activation manual notes now (single source of truth via /scenario/state).
    # movie_appletv routes via the processor — no Dodocus hop, so no manual steps.
    assert sm.scenario_state is not None and sm.scenario_state.manual_steps == []

    dev_seq = [d for d, _ in calls]
    # TV power before eMotiva power (HDMI-ARC ordering edge)
    assert dev_seq.index("living_room_tv") < dev_seq.index("processor")
    # translated native commands actually dispatched (RC1 fixed)
    assert ("living_room_tv", "set_input_source") in calls
    assert ("processor", "set_input") in calls
    assert ("mf_amplifier", "input_aux2") in calls


@pytest.mark.asyncio
async def test_deactivate_powers_off_involved_devices():
    """Explicit deactivate() (the user's 'turn it all off') powers off the gear."""
    calls: list = []
    devices = _devices(calls)
    for d in devices.values():
        d.get_current_state().power = "on"
    devices["processor"].get_current_state().zone2_power = "on"

    sm = _manager(devices)
    sm.current_scenario = sm.scenario_map["movie_appletv"]
    await sm.deactivate()

    assert ("living_room_tv", "power_off") in calls
    assert ("mf_amplifier", "power") in calls  # toggle off
    assert sm.current_scenario is None


@pytest.mark.asyncio
async def test_process_shutdown_is_transparent_to_hardware():
    """Process shutdown() must NOT touch the gear — restarting the bridge can't power off
    the user's AV system. It only clears the in-memory active scenario."""
    calls: list = []
    devices = _devices(calls)
    for d in devices.values():
        d.get_current_state().power = "on"

    sm = _manager(devices)
    sm.current_scenario = sm.scenario_map["movie_appletv"]
    await sm.shutdown()

    assert calls == []  # no device commands sent on process shutdown
    assert sm.current_scenario is None


@pytest.mark.asyncio
async def test_switch_ld_surfaces_dodocus_manual_step():
    calls: list = []
    sm = _manager(_devices(calls), "movie_ld")
    result = await sm.switch_scenario("movie_ld")

    assert result["success"]
    # Activation manual notes live on ScenarioState now (single source of truth for the UI).
    assert sm.scenario_state is not None
    assert any("LD position" in m.instruction for m in sm.scenario_state.manual_steps)
    # upscaler input switched (to video) but never powered (auto-powers with the source)
    assert ("upscaler", "input_video") in calls
    assert ("upscaler", "power_on") not in calls
    assert ("ld_player", "power") in calls
    assert ("mf_amplifier", "input_cd") in calls


@pytest.mark.asyncio
async def test_transition_to_ld_surfaces_dodocus_note_on_switch_and_clears_on_deactivate():
    """§5.1 #1 (load-bearing): the Dodocus 'Set to LD' note must surface when
    *transitioning* into movie_ld from another scenario (not just on cold start) —
    otherwise the user never sees it and movie_ld has no audio. Also verifies that
    deactivate() clears the activation notes so a later start gets fresh ones."""
    calls: list = []
    devices = _devices(calls)

    async def _save(*a, **k): return None
    sm = ScenarioManager(
        device_manager=SimpleNamespace(devices=devices),
        room_manager=SimpleNamespace(),
        state_repository=SimpleNamespace(save=_save),
        scenario_dir=ROOT / "config" / "scenarios",
    )
    sm.topology = TOPOLOGY
    sm._reconciler_enabled = True
    sm.scenario_map = {
        name: Scenario(
            ScenarioDefinition.model_validate(
                json.loads((ROOT / "config" / "scenarios" / f"{name}.json").read_text())
            ),
            sm.device_manager,
        )
        for name in ("movie_appletv", "movie_ld")
    }

    # Start with appletv — audio routes via the processor, no Dodocus hop, no manual notes.
    await sm.switch_scenario("movie_appletv")
    assert sm.scenario_state is not None and sm.scenario_state.manual_steps == []

    # Transition to movie_ld — Dodocus 'Set to LD' must surface on the switch.
    await sm.switch_scenario("movie_ld")
    assert sm.scenario_state is not None
    assert sm.scenario_state.scenario_id == "movie_ld"
    assert any(
        m.node == "dodocus" and "LD position" in m.instruction
        for m in sm.scenario_state.manual_steps
    )

    # Deactivate clears scenario_state (and the activation notes); the next start
    # gets fresh manual_steps, with no leftover from movie_ld.
    await sm.deactivate()
    assert sm.scenario_state is None
    await sm.switch_scenario("movie_appletv")
    assert sm.scenario_state is not None and sm.scenario_state.manual_steps == []
