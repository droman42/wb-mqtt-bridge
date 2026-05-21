"""Tests for the scenario reconciler (Layer R): resolve -> diff -> translate -> order.

Pure planning, no execution: devices are fakes carrying a real CapabilityMap + an assumed
state. Verifies the movie_appletv plan, the manual-node path, ordering/delay, and diffing.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.infrastructure.capabilities.models import CapabilityMap
from wb_mqtt_bridge.infrastructure.scenarios.reconciler import build_plan, resolve_targets
from wb_mqtt_bridge.infrastructure.topology.loader import load_topology
from wb_mqtt_bridge.infrastructure.topology.models import Topology

ROOT = Path(__file__).resolve().parents[2]
CAPS = ROOT / "config" / "capabilities"
TOPOLOGY = load_topology(ROOT / "config" / "topology.json")


def _device(device_class: str, device_id: str, **state_fields):
    caps = load_capability_map(device_class, device_id, CAPS)
    state_fields.setdefault("power", "off")
    state = SimpleNamespace(**state_fields)
    return SimpleNamespace(capabilities=caps, get_current_state=lambda s=state: s)


def _movie_appletv_devices(**overrides):
    base = {
        "appletv_living": _device("AppleTVDevice", "appletv_living"),
        "processor": _device("EMotivaXMC2", "processor", zone2_power=None, input_source=None),
        "living_room_tv": _device("LgTv", "living_room_tv", input_source=None),
        "mf_amplifier": _device("WirenboardIRDevice", "mf_amplifier", input=None),
    }
    base.update(overrides)
    return base


def _scenario(name: str) -> ScenarioDefinition:
    data = json.loads((ROOT / "config" / "scenarios" / f"{name}.json").read_text())
    return ScenarioDefinition.model_validate(data)


def _idx(plan, device_id, domain, zone=None):
    for i, a in enumerate(plan.actions):
        if a.device_id == device_id and a.domain == domain and (zone is None or a.zone == zone):
            return i
    return -1


def _find(plan, device_id, domain, zone=None):
    i = _idx(plan, device_id, domain, zone)
    return plan.actions[i] if i >= 0 else None


# --- the headline: movie_appletv from a cold (all-off) start -----------------


def test_movie_appletv_full_plan_from_cold():
    scenario = _scenario("movie_appletv")
    plan = build_plan(scenario, TOPOLOGY, _movie_appletv_devices())

    assert plan.warnings == []
    assert plan.manual_steps == []  # Apple TV path doesn't touch the manual Dodocus hub

    # every involved device powers on; the eMotiva powers both zones
    assert _find(plan, "appletv_living", "power") is not None
    assert _find(plan, "living_room_tv", "power") is not None
    assert _find(plan, "processor", "power", zone="1") is not None
    assert _find(plan, "processor", "power", zone="2") is not None
    assert _find(plan, "mf_amplifier", "power") is not None

    # inputs derived from topology destination ports
    assert _find(plan, "living_room_tv", "input").target == "hdmi2"
    assert _find(plan, "processor", "input").target == "hdmi2"
    assert _find(plan, "mf_amplifier", "input").target == "aux2"
    # Apple TV is a pure source: no input action
    assert _find(plan, "appletv_living", "input") is None


def test_movie_appletv_translation_fixes_rc1_and_value_maps():
    plan = build_plan(_scenario("movie_appletv"), TOPOLOGY, _movie_appletv_devices())

    # RC1: canonical input -> native `source`
    lg_input = _find(plan, "living_room_tv", "input")
    assert lg_input.command == "set_input_source" and lg_input.params == {"source": "hdmi2"}
    # eMotiva identity param
    emo_input = _find(plan, "processor", "input")
    assert emo_input.command == "set_input" and emo_input.params == {"input": "hdmi2"}
    # IR amp: toggle power + value-mapped input
    assert _find(plan, "mf_amplifier", "power").command == "power"
    assert _find(plan, "mf_amplifier", "input").command == "input_aux2"
    # eMotiva zone power carries the zone param
    assert _find(plan, "processor", "power", zone="2").params == {"zone": 2}


def test_movie_appletv_ordering_matches_manual_sequence():
    plan = build_plan(_scenario("movie_appletv"), TOPOLOGY, _movie_appletv_devices())

    # TV.power -> eMotiva.power -> TV.input -> eMotiva.input
    assert _idx(plan, "living_room_tv", "power") < _idx(plan, "processor", "power", zone="1")
    assert _idx(plan, "living_room_tv", "power") < _idx(plan, "processor", "power", zone="2")
    assert _idx(plan, "processor", "power", zone="1") < _idx(plan, "living_room_tv", "input")
    assert _idx(plan, "processor", "power", zone="2") < _idx(plan, "living_room_tv", "input")
    assert _idx(plan, "living_room_tv", "input") < _idx(plan, "processor", "input")
    # per-device: amp power before amp input
    assert _idx(plan, "mf_amplifier", "power") < _idx(plan, "mf_amplifier", "input")


def test_diff_skips_already_satisfied():
    devices = _movie_appletv_devices(
        appletv_living=_device("AppleTVDevice", "appletv_living", power="on"),
        processor=_device("EMotivaXMC2", "processor", power="on", zone2_power="on", input_source="hdmi2"),
        living_room_tv=_device("LgTv", "living_room_tv", power="on", input_source="hdmi2"),
        mf_amplifier=_device("WirenboardIRDevice", "mf_amplifier", power="on", input="aux2"),
    )
    plan = build_plan(_scenario("movie_appletv"), TOPOLOGY, devices)
    assert plan.actions == []
    assert "living_room_tv.power" in plan.already_satisfied
    assert "processor.input" in plan.already_satisfied


# --- manual node (LD path through the Dodocus hub) ---------------------------


def test_resolve_ld_path_emits_manual_step_and_cd_input():
    ld = ScenarioDefinition(
        scenario_id="movie_ld", name="LD",
        source="ld_player", display="living_room_tv", audio="mf_amplifier",
    )
    input_targets, involved, manual_steps, warnings = resolve_targets(ld, TOPOLOGY)

    assert input_targets["upscaler"] == "video"
    assert input_targets["processor"] == "hdmi3"
    assert input_targets["mf_amplifier"] == "cd"  # via the manual hub
    assert {"ld_player", "upscaler", "processor", "living_room_tv", "mf_amplifier"} <= involved
    assert "dodocus" not in involved  # manual node is not a device
    assert any(m.node == "dodocus" and "LD position" in m.instruction for m in manual_steps)


# --- ordering delay propagation (synthetic) ---------------------------------


def test_ordering_edge_delay_becomes_pre_delay():
    topo = Topology.model_validate({
        "links": [{"from": "src:out", "to": "sink:in1", "carries": ["video"]}],
        "ordering": [{"first": "src.power", "then": "sink.input", "delay_ms": 4500}],
    })
    cap_src = CapabilityMap.model_validate({
        "power": {"kind": "stateful", "feedback": False, "state_field": "power",
                  "actions": {"toggle": {"command": "power"}}, "gate": {"delay_ms": 100}}
    })
    cap_sink = CapabilityMap.model_validate({
        "power": {"kind": "stateful", "feedback": False, "state_field": "power",
                  "actions": {"on": {"command": "power_on"}}},
        "input": {"kind": "stateful", "feedback": False, "state_field": "input",
                  "select": {"by_value": {"in1": {"command": "input_1"}}}},
    })
    devices = {
        "src": SimpleNamespace(capabilities=cap_src,
                               get_current_state=lambda: SimpleNamespace(power="off")),
        "sink": SimpleNamespace(capabilities=cap_sink,
                                get_current_state=lambda: SimpleNamespace(power="off", input=None)),
    }
    scenario = ScenarioDefinition(scenario_id="s", name="s", source="src", display="sink")
    plan = build_plan(scenario, topo, devices)

    sink_input = _find(plan, "sink", "input")
    assert sink_input.pre_delay_ms == 4500
    assert _idx(plan, "src", "power") < _idx(plan, "sink", "input")
