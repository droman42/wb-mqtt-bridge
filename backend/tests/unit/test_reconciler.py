"""Tests for the scenario reconciler (Layer R): resolve -> diff -> translate -> order.

Pure planning, no execution: devices are fakes carrying a real CapabilityMap + an assumed
state. Verifies the movie_appletv plan, the manual-node path, ordering/delay, and diffing.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition
from wb_mqtt_bridge.infrastructure.capabilities.loader import load_capability_map
from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap
import pytest

from wb_mqtt_bridge.domain.scenarios.reconciler import (
    PlannedAction,
    ReconcilePlan,
    build_plan,
    build_power_off_plan,
    execute_plan,
    resolve_targets,
)
from wb_mqtt_bridge.domain.topology.loader import load_topology
from wb_mqtt_bridge.domain.topology.models import Topology

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
    assert _find(plan, "processor", "input").target == "source2"
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
    assert emo_input.command == "set_input" and emo_input.params == {"input": "source2"}
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
        processor=_device("EMotivaXMC2", "processor", power="on", zone2_power="on", input_source="source2"),
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
    input_targets, _source_targets, involved, manual_steps, warnings = resolve_targets(ld, TOPOLOGY)

    assert input_targets["upscaler"] == "video"
    assert input_targets["processor"] == "source3"
    assert input_targets["mf_amplifier"] == "cd"  # via the manual hub
    assert {"ld_player", "upscaler", "processor", "living_room_tv", "mf_amplifier"} <= involved
    assert "dodocus" not in involved  # manual node is not a device
    assert any(m.node == "dodocus" and "LD position" in m.instruction for m in manual_steps)


def test_manual_source_node_anchors_path_without_being_controlled():
    """A manual-node *source* (a turntable/tape with no driver) anchors the topology path
    so the sink input + the hub's manual note still resolve — but the manual node itself is
    never added to `involved` (nothing to power/control)."""
    topo = Topology.model_validate(
        {
            "nodes": {
                "hub": {"kind": "manual", "name": "RCA hub", "positions": {"tt": "Set the hub to the Phono position"}},
                "turntable": {"kind": "manual", "name": "Kuzma turntable"},
            },
            "links": [
                {"from": "turntable:out", "to": "hub:tt", "carries": ["audio"]},
                {"from": "hub:out", "to": "amp:cd", "carries": ["audio"]},
            ],
        }
    )
    scn = ScenarioDefinition(scenario_id="m", name="m", source="turntable", audio="amp")
    input_targets, _source_targets, involved, manual_steps, warnings = resolve_targets(scn, topo)

    assert input_targets == {"amp": "cd"}        # sink input resolved through the manual source
    assert involved == {"amp"}                   # the manual source is NOT a device to control
    assert "turntable" not in involved
    assert any(m.node == "hub" and "Phono" in m.instruction for m in manual_steps)
    assert warnings == []


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


# --- execution ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_plan_runs_actions_in_plan_order(monkeypatch):
    import wb_mqtt_bridge.domain.scenarios.reconciler as rec

    async def _nosleep(*a, **k):
        return None

    monkeypatch.setattr(rec.asyncio, "sleep", _nosleep)

    calls: list = []

    def fake(device_id, caps, **state):
        st = SimpleNamespace(power="off", **state)

        async def execute_action(command, params, source="unknown", _id=device_id):
            calls.append((_id, command))
            return {"success": True}

        return SimpleNamespace(capabilities=caps, get_current_state=lambda _st=st: _st,
                               execute_action=execute_action)

    devices = {
        "appletv_living": fake("appletv_living", load_capability_map("AppleTVDevice", "appletv_living", CAPS)),
        "processor": fake("processor", load_capability_map("EMotivaXMC2", "processor", CAPS),
                          zone2_power=None, input_source=None),
        "living_room_tv": fake("living_room_tv", load_capability_map("LgTv", "living_room_tv", CAPS),
                               input_source=None),
        "mf_amplifier": fake("mf_amplifier", load_capability_map("WirenboardIRDevice", "mf_amplifier", CAPS),
                             input=None),
    }
    plan = build_plan(_scenario("movie_appletv"), TOPOLOGY, devices)
    result = await execute_plan(plan, devices)

    assert result.success
    assert len(result.executed) == len(plan.actions)
    # actions are dispatched in exactly the planned order
    assert calls == [(a.device_id, a.command) for a in plan.actions]


@pytest.mark.asyncio
async def test_execute_plan_surfaces_failure_and_continues(monkeypatch):
    import wb_mqtt_bridge.domain.scenarios.reconciler as rec

    async def _nosleep(*a, **k):
        return None

    monkeypatch.setattr(rec.asyncio, "sleep", _nosleep)

    async def good(command, params, source="unknown"):
        return {"success": True}

    async def bad(command, params, source="unknown"):
        return {"success": False, "error": "boom"}

    devices = {
        "d1": SimpleNamespace(get_current_state=lambda: SimpleNamespace(), execute_action=bad),
        "d2": SimpleNamespace(get_current_state=lambda: SimpleNamespace(), execute_action=good),
    }
    plan = ReconcilePlan(actions=[
        PlannedAction("d1", "power", "on", "power_on"),
        PlannedAction("d2", "power", "on", "power_on"),
    ])
    result = await execute_plan(plan, devices)

    assert not result.success
    assert len(result.failures) == 1 and result.failures[0][1] == "boom"
    assert len(result.executed) == 1  # d2 still ran (failures don't abort by default)


def test_build_power_off_plan_powers_off_on_devices():
    devices = {
        "living_room_tv": _device("LgTv", "living_room_tv", power="on", input_source="hdmi2"),
        "mf_amplifier": _device("WirenboardIRDevice", "mf_amplifier", power="on", input="aux2"),
        "processor": _device("EMotivaXMC2", "processor", power="on", zone2_power="on", input_source="source2"),
    }
    plan = build_power_off_plan(["living_room_tv", "mf_amplifier", "processor"], devices)
    cmds = {(a.device_id, a.command) for a in plan.actions}
    assert ("living_room_tv", "power_off") in cmds
    assert ("mf_amplifier", "power") in cmds  # toggle off
    assert sum(1 for a in plan.actions if a.device_id == "processor") == 2  # both zones


def test_build_power_off_plan_skips_already_off():
    devices = {"living_room_tv": _device("LgTv", "living_room_tv", power="off")}
    plan = build_power_off_plan(["living_room_tv"], devices)
    assert plan.actions == []


# --- all four scenarios, end to end -----------------------------------------


def _all_devices():
    return {
        "appletv_living": _device("AppleTVDevice", "appletv_living"),
        "processor": _device("EMotivaXMC2", "processor", zone2_power=None, input_source=None),
        "living_room_tv": _device("LgTv", "living_room_tv", input_source=None),
        "mf_amplifier": _device("WirenboardIRDevice", "mf_amplifier", input=None),
        "ld_player": _device("WirenboardIRDevice", "ld_player"),
        "vhs_player": _device("WirenboardIRDevice", "vhs_player"),
        "video": _device("WirenboardIRDevice", "video"),
        "upscaler": _device("WirenboardIRDevice", "upscaler", input=None),
    }


@pytest.mark.parametrize("name", ["movie_appletv", "movie_ld", "movie_vhs", "movie_zappiti"])
def test_all_scenarios_build_clean_plans(name):
    plan = build_plan(_scenario(name), TOPOLOGY, _all_devices())
    assert plan.warnings == [], f"{name}: {plan.warnings}"
    assert plan.actions, f"{name} produced no actions"


def test_movie_ld_plan_uses_manual_hub_and_upscaler_delay():
    plan = build_plan(_scenario("movie_ld"), TOPOLOGY, _all_devices())

    # manual Dodocus step (audio routed via the hub to amp `cd`)
    assert any(m.node == "dodocus" and "LD position" in m.instruction for m in plan.manual_steps)
    assert _find(plan, "mf_amplifier", "input").command == "input_cd"
    # upscaler input via topology (video) with the 4.5s settle; no power action (auto-powers)
    ups_in = _find(plan, "upscaler", "input")
    assert ups_in.target == "video" and ups_in.command == "input_video" and ups_in.pre_delay_ms == 4500
    assert _find(plan, "upscaler", "power") is None
    # processor routed to source3; LD powered via toggle
    assert _find(plan, "processor", "input").target == "source3"
    assert _find(plan, "ld_player", "power").command == "power"


def test_movie_zappiti_has_no_manual_steps():
    plan = build_plan(_scenario("movie_zappiti"), TOPOLOGY, _all_devices())
    assert plan.manual_steps == []  # audio runs through the eMotiva, not the manual hub
    assert _find(plan, "processor", "input").target == "source1"
    assert _find(plan, "mf_amplifier", "input").command == "input_aux2"


# --- round-2 music scenarios (P3.6) -----------------------------------------


def _music_devices(**overrides):
    base = {
        "streamer": _device("AuralicDevice", "streamer", input=None),
        "reel_to_reel": _device("RevoxA77ReelToReel", "reel_to_reel"),
        "mf_amplifier": _device("WirenboardIRDevice", "mf_amplifier", input=None),
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "name,amp_input,manual_pos,passive_source",
    [
        ("music_auralic", "balanced", None, None),
        ("music_reel", "cd", "Reel", None),
        ("music_tape", "cd", "Tape", "b215"),
        ("music_turntable", "cd", "Phono", "kuzma"),
    ],
)
def test_music_scenarios_resolve_and_build_clean(name, amp_input, manual_pos, passive_source):
    scn = _scenario(name)
    input_targets, _source_targets, involved, manual_steps, warnings = resolve_targets(scn, TOPOLOGY)

    assert input_targets["mf_amplifier"] == amp_input  # amp input auto-selected from topology
    assert "mf_amplifier" in involved
    if manual_pos:  # analog sources route via the Dodocus hub → a manual position note
        assert any(m.node == "dodocus" and manual_pos in m.instruction for m in manual_steps)
    if passive_source:  # a manual-node source is never controlled
        assert passive_source not in involved

    plan = build_plan(scn, TOPOLOGY, _music_devices())
    assert plan.warnings == [], f"{name}: {plan.warnings}"
    assert _find(plan, "mf_amplifier", "input").command == f"input_{amp_input}"


def test_music_turntable_surfaces_both_manual_hops():
    """The turntable path runs Kuzma → Sugden PA4 (power on) → Dodocus (Phono) → amp:cd,
    so BOTH inline manual nodes surface a note; neither passive node is controlled."""
    _, _source_targets, involved, manual_steps, warnings = resolve_targets(_scenario("music_turntable"), TOPOLOGY)
    notes = {m.node: m.instruction for m in manual_steps}
    assert "Power on" in notes.get("sugden_pa4", "")
    assert "Phono" in notes.get("dodocus", "")
    assert "kuzma" not in involved and "sugden_pa4" not in involved
    assert warnings == []


# --- Symmetric src_port mechanism (HDMI ARC) ---------------------------------


def _tv_on_speakers_devices(**overrides):
    base = {
        "living_room_tv": _device("LgTv", "living_room_tv", input_source=None),
        "processor": _device("EMotivaXMC2", "processor", zone2_power=None, input_source=None),
        "mf_amplifier": _device("WirenboardIRDevice", "mf_amplifier", input=None),
    }
    base.update(overrides)
    return base


def test_tv_on_speakers_resolves_with_source_targets():
    """tv_on_speakers has source=living_room_tv: the TV is at the START of the audio path.
    The symmetric src_port mechanism puts the TV in source_targets (not input_targets) with
    src_port='arc' from the topology link `living_room_tv:arc → processor:arc`."""
    scn = _scenario("tv_on_speakers")
    input_targets, source_targets, involved, _manual_steps, warnings = resolve_targets(scn, TOPOLOGY)

    # Destinations on the audio path get input_targets per dst_port (existing behavior)
    assert input_targets.get("processor") == "arc"
    assert input_targets.get("mf_amplifier") == "aux2"
    # TV is source — gets source_targets from src_port (new behavior)
    assert source_targets.get("living_room_tv") == "arc"
    # TV is NOT in input_targets (it's not a destination on this path)
    assert "living_room_tv" not in input_targets
    # All three on the audio path are involved
    assert {"living_room_tv", "processor", "mf_amplifier"}.issubset(involved)
    assert warnings == []


def test_tv_on_speakers_plan_emits_tv_internal_via_source_modes():
    """build_plan emits set_input_source(arc) on the TV (driven by source_targets +
    LgTv input capability declaring 'arc' in source_modes). Driver translates to
    handle_home internally — the reconciler stays generic."""
    scn = _scenario("tv_on_speakers")
    plan = build_plan(scn, TOPOLOGY, _tv_on_speakers_devices())

    # TV gets an input action with target='arc'
    tv_input = next(
        (a for a in plan.actions if a.device_id == "living_room_tv" and a.domain == "input"),
        None,
    )
    assert tv_input is not None, "expected an input action on living_room_tv"
    assert tv_input.target == "arc"
    assert tv_input.command == "set_input_source"
    # Processor also gets set_input(arc) from its dst_port
    processor_input = next(
        (a for a in plan.actions if a.device_id == "processor" and a.domain == "input"),
        None,
    )
    assert processor_input is not None and processor_input.target == "arc"

    assert plan.warnings == []


def test_tv_on_speakers_already_satisfied_when_tv_on_internal_and_processor_on_arc():
    """If the TV's input_source is already 'arc' (driver maps 'home'/internal there) AND
    the processor's input_source is already 'arc', the reconciler emits no input actions
    (both already_satisfied). Guards against the power-cycle firing on every activation
    when ARC is already engaged."""
    scn = _scenario("tv_on_speakers")
    devices = _tv_on_speakers_devices(
        living_room_tv=_device("LgTv", "living_room_tv", power="on", input_source="arc"),
        processor=_device(
            "EMotivaXMC2", "processor", power="on", zone2_power="off", input_source="arc",
        ),
        mf_amplifier=_device(
            "WirenboardIRDevice", "mf_amplifier", power="on", input="aux2",
        ),
    )
    plan = build_plan(scn, TOPOLOGY, devices)

    tv_input = [a for a in plan.actions if a.device_id == "living_room_tv" and a.domain == "input"]
    processor_input = [a for a in plan.actions if a.device_id == "processor" and a.domain == "input"]
    assert tv_input == [], "TV input should be already_satisfied"
    assert processor_input == [], "Processor input should be already_satisfied"
    assert "living_room_tv.input" in plan.already_satisfied
    assert "processor.input" in plan.already_satisfied


def test_source_targets_skipped_when_device_has_no_source_modes():
    """A source device with an `input` capability but NO `source_modes` declaration must
    NOT trigger a set_input action from the src_port mechanism. Example: Auralic streamer
    is the source of `streamer:out → mf_amplifier:balanced`, has an input capability, but
    declares no source_modes — reconciler must silently skip the src-side action (Auralic
    would fail set_input('out') since 'out' isn't a valid Auralic input)."""
    # music_auralic: source=streamer, audio=mf_amplifier. Streamer→amp link has src_port='out'.
    scn = _scenario("music_auralic")
    _, source_targets, _, _, _ = resolve_targets(scn, TOPOLOGY)
    # source_targets DOES record the src_port (resolve_targets is unconditional)
    assert source_targets.get("streamer") == "out"
    # ...but build_plan must NOT emit an action for it (no source_modes in Auralic cap)
    devices = {
        "streamer": _device("AuralicDevice", "streamer", source=None),
        "mf_amplifier": _device("WirenboardIRDevice", "mf_amplifier", input=None),
    }
    plan = build_plan(scn, TOPOLOGY, devices)
    streamer_input = [a for a in plan.actions if a.device_id == "streamer" and a.domain == "input"]
    assert streamer_input == [], "streamer should not get a set_input action — no source_modes"
    # And no warning is emitted for the silently-skipped src target
    assert not any("streamer" in w and "input" in w for w in plan.warnings)


def test_source_targets_skipped_when_device_has_no_input_capability():
    """A source device with no input capability at all (Apple TV) must be silently skipped
    by the src_port mechanism — no warnings (warnings are reserved for dst_port targets
    that fail, where the topology made a hard claim about a destination's input)."""
    scn = _scenario("movie_appletv")
    _, source_targets, _, _, _ = resolve_targets(scn, TOPOLOGY)
    assert source_targets.get("appletv_living") == "hdmi"  # src_port from appletv→processor link

    plan = build_plan(scn, TOPOLOGY, _movie_appletv_devices())
    appletv_input = [a for a in plan.actions if a.device_id == "appletv_living" and a.domain == "input"]
    assert appletv_input == []
    # No warning for appletv input (Apple TV has no input capability — expected for sources)
    assert not any("appletv_living" in w and "input capability" in w for w in plan.warnings)
