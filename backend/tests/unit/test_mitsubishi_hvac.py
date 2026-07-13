"""Tests for the MitsubishiHvac driver (DRV-28).

Real driver, real class capability map, real device config, mocked MQTT client — the
device-test recipe. The contract under test is the mitsubishi2wb firmware dialect
(`docs/design/mitsubishi_hvac_driver.md` §2): numeric wire indices both directions
(the firmware silently drops non-numeric commands), value tables living in the class
map ONLY (loader enrichment), heartbeat-driven reachability (no LWT exists), typed
declared state riding restore-at-boot, and — structurally — NO WB virtual device
(the firmware owns its own card).
"""
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from locveil_bridge.infrastructure.capabilities.loader import (
    enrich_state_topics_from_map,
    load_capability_map,
)
from locveil_bridge.infrastructure.config.models import MitsubishiHvacConfig
from locveil_bridge.infrastructure.devices.mitsubishi_hvac import driver as hvac_driver
from locveil_bridge.infrastructure.devices.mitsubishi_hvac.driver import MitsubishiHvac

REPO = Path(__file__).resolve().parents[3]
CAPS = REPO / "config" / "capabilities"
CONFIG = REPO / "config" / "devices" / "children_room_hvac.json"


@pytest.fixture
def mqtt() -> MagicMock:
    m = MagicMock()
    m.subscribe = AsyncMock()
    m.publish = AsyncMock()
    return m


@pytest.fixture
def device(mqtt) -> MitsubishiHvac:
    """Real children-room config + real class map, enriched exactly as bootstrap does
    (attach_capability_maps -> enrich_state_topics_from_map, before any MQTT echo)."""
    cfg = MitsubishiHvacConfig.model_validate(json.loads(CONFIG.read_text()))
    dev = MitsubishiHvac(cfg, mqtt_client=mqtt)
    dev.capabilities = load_capability_map("MitsubishiHvac", cfg.device_id, CAPS)
    enrich_state_topics_from_map(dev)
    return dev


# --- config: the firmware contract is validated at load -------------------------


def test_config_validates_firmware_contract_completeness():
    """A missing command or state field is a LOUD config error (design D4), not silent
    degradation — the firmware contract is fixed."""
    data = json.loads(CONFIG.read_text())
    del data["commands"]["set_vane"]
    del data["state_topics"]["room_temperature"]
    with pytest.raises(Exception) as ei:
        MitsubishiHvacConfig.model_validate(data)
    msg = str(ei.value)
    assert "set_vane" in msg and "room_temperature" in msg


def test_config_never_enables_wb_emulation():
    """THE structural guard the owner insisted on: the mitsubishi2wb firmware creates
    its own WB virtual device — the bridge driver must NEVER create one. Inherited
    from the passthrough loop-guard default and pinned here forever."""
    cfg = MitsubishiHvacConfig.model_validate(json.loads(CONFIG.read_text()))
    assert cfg.enable_wb_emulation is False


# --- setup: subscriptions + no meta/error, retained opt-in ----------------------


@pytest.mark.asyncio
async def test_setup_subscribes_each_state_topic_retained_no_meta_error(device, mqtt):
    ok = await device.setup()
    assert ok is True
    subs = [c.args[0] for c in mqtt.subscribe.await_args_list]
    assert "/devices/hvac_children/controls/mode" in subs
    assert "/devices/hvac_children/controls/room_temperature" in subs
    # 7 state fields, one subscription each — and NO meta/error companions
    # (the firmware publishes none; subscribing would be dead weight).
    assert len(subs) == 7
    assert not any(t.endswith("/meta/error") for t in subs)
    for call in mqtt.subscribe.await_args_list:
        assert call.kwargs.get("process_retained") is True
    # watchdog armed
    assert device._watchdog_task is not None
    device._watchdog_task.cancel()


@pytest.mark.asyncio
async def test_setup_returns_false_without_mqtt_client():
    cfg = MitsubishiHvacConfig.model_validate(json.loads(CONFIG.read_text()))
    dev = MitsubishiHvac(cfg, mqtt_client=None)
    assert await dev.setup() is False


# --- inbound: numeric wire -> canonical typed state ------------------------------


@pytest.mark.asyncio
async def test_inbound_wire_translates_to_canonical_typed_fields(device):
    await device._on_value_message("mode", "/t", "2")
    await device._on_value_message("fan", "/t", "0")
    await device._on_value_message("vane", "/t", "1")
    await device._on_value_message("widevane", "/t", "3")
    await device._on_value_message("power", "/t", "1")
    await device._on_value_message("setpoint", "/t", "22")
    await device._on_value_message("room_temperature", "/t", "25.5")
    s = device.state
    assert (s.mode, s.fan, s.vane, s.widevane) == ("cool", "auto", "swing", "center")
    assert s.power == "on"
    assert s.setpoint == 22.0 and isinstance(s.setpoint, float)
    assert s.room_temperature == 25.5


@pytest.mark.asyncio
async def test_inbound_unparseable_payload_kept_raw_not_dropped(device):
    await device._on_value_message("mode", "/t", "9")  # outside the table
    assert device.state.mode == "9"  # visible for diagnosis, not silently dropped


# --- outbound: canonical -> numeric wire (the firmware drops anything else) ------


@pytest.mark.asyncio
async def test_outbound_canonical_translates_to_numeric_wire(device, mqtt):
    result = await device._execute_command(
        "set_mode", device.config.commands["set_mode"], {"mode": "heat"})
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/hvac_children/controls/mode/on", "3")


@pytest.mark.asyncio
async def test_outbound_power_uses_static_numeric_values(device, mqtt):
    await device._on_value_message("power", "/t", "0")  # believed off
    r = await device._execute_command("power_on", device.config.commands["power_on"], {})
    assert r["success"] is True and r["data"]["no_op"] is False
    mqtt.publish.assert_awaited_once_with("/devices/hvac_children/controls/power/on", "1")


@pytest.mark.asyncio
async def test_outbound_setpoint_publishes_float_string(device, mqtt):
    r = await device._execute_command(
        "set_setpoint", device.config.commands["set_setpoint"], {"temp": 21.5})
    assert r["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/hvac_children/controls/temperature/on", "21.5")


# --- idempotence: the DRV-5 chokepoint, force bypass ------------------------------


@pytest.mark.asyncio
async def test_idempotence_skips_when_already_at_target(device, mqtt):
    await device._on_value_message("mode", "/t", "2")  # state: cool
    r = await device._execute_command(
        "set_mode", device.config.commands["set_mode"], {"mode": "cool"})
    assert r["success"] is True
    assert r["data"]["no_op"] is True
    assert r["data"]["skipped_reason"] == "idempotence"
    mqtt.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_bypasses_idempotence(device, mqtt):
    await device._on_value_message("mode", "/t", "2")  # state: cool
    r = await device._execute_command(
        "set_mode", device.config.commands["set_mode"], {"mode": "cool", "force": True})
    assert r["success"] is True and r["data"]["no_op"] is False
    mqtt.publish.assert_awaited_once_with("/devices/hvac_children/controls/mode/on", "2")


@pytest.mark.asyncio
async def test_cold_start_unknown_state_always_publishes(device, mqtt):
    """No echo seeded (broker wipe / fresh boot): state fields are None — the guard
    must NOT fire on unknown state."""
    r = await device._execute_command(
        "set_mode", device.config.commands["set_mode"], {"mode": "cool"})
    assert r["success"] is True and r["data"]["no_op"] is False


# --- heartbeat reachability --------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_flips_reachable_after_silence_and_recovers(device, monkeypatch):
    # Seed a heartbeat, then age it past the timeout and run one watchdog cycle.
    await device._on_value_message("room_temperature", "/t", "24.0")
    assert device.state.reachable is True
    device._last_heartbeat = time.monotonic() - (hvac_driver.HEARTBEAT_TIMEOUT_S + 1)

    async def _one_cycle_sleep(_):
        raise asyncio.CancelledError  # stop the loop after the first check

    real_sleep = asyncio.sleep

    calls = {"n": 0}
    async def fake_sleep(seconds):
        if calls["n"] == 0:
            calls["n"] += 1
            return  # let the first check run
        raise asyncio.CancelledError

    monkeypatch.setattr(hvac_driver.asyncio, "sleep", fake_sleep)
    await device._heartbeat_watchdog()
    assert device.state.reachable is False

    # A fresh heartbeat message restores reachability immediately.
    await device._on_value_message("room_temperature", "/t", "24.5")
    assert device.state.reachable is True


# --- restore-at-boot (the broker-wipe fix) ----------------------------------------


@pytest.mark.asyncio
async def test_declared_state_restores_from_snapshot(device, mqtt):
    await device._on_value_message("mode", "/t", "2")
    await device._on_value_message("setpoint", "/t", "22")
    await device._on_value_message("power", "/t", "1")
    snapshot = device.state.model_dump()

    cfg = MitsubishiHvacConfig.model_validate(json.loads(CONFIG.read_text()))
    fresh = MitsubishiHvac(cfg, mqtt_client=mqtt)
    applied = fresh.restore_state(snapshot)
    assert {"mode", "setpoint", "power"} <= set(applied)
    assert fresh.state.mode == "cool"
    assert fresh.state.setpoint == 22.0
    assert fresh.state.power == "on"


# --- catalog projection ------------------------------------------------------------


def test_catalog_advertises_six_capabilities_with_value_param(device):
    """The catalog surface: six capabilities; every enum/float `set` advertises the
    canonical `{value}` param (the voice contract shape — VWB-19's select-form
    convention, delivered here through param_map on ordinary command-form actions)."""
    from locveil_bridge.presentation.api.param_projection import project_action_params

    caps = device.capabilities
    assert set(caps.root) == {"power", "mode", "fan", "vane", "widevane", "temperature"}
    for name in ("mode", "fan", "vane", "widevane", "temperature"):
        action = caps.get(name).actions["set"]
        params = project_action_params(action, device.config.commands)
        assert params is not None and [p["name"] for p in params] == ["value"], name
