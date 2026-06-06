"""Tests for the generic WB-passthrough driver (§P3.7 #13).

Real driver, real config, mocked MQTT client. Exercises:

- handler auto-registration from `config.commands` (one publish per command).
- publish path: static `value` and param-derived value.
- mirror path: a value-topic echo flows through `update_state` into `state.mirrored`.
- error path: a per-control `meta/error` `r` flag flips `reachable` False and records the
  flag in `state.error_flags`; clearing the flag flips it back.
- loop guard: `enable_wb_emulation` defaults to False so the BaseDevice flow skips the
  WB virtual-device callback registration (no feedback loop with the real device).
- single-room schema works end-to-end (config carries `room: "cabinet"`; cross-room
  actions like "выключи свет везде" are Irene's job, resolved from the catalog).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.config.models import (
    CommandParameterDefinition,
    WbPassthroughCommandConfig,
    WbPassthroughDeviceConfig,
)
from wb_mqtt_bridge.infrastructure.devices.wb_passthrough.driver import WbPassthroughDevice


def _slice_config() -> WbPassthroughDeviceConfig:
    """The cabinet_spots slice config from §P3.7 A1, in code."""
    return WbPassthroughDeviceConfig(
        device_id="cabinet_spots",
        names={"ru": "Споты", "en": "Spots"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="cabinet",
        commands={
            "power_on":  WbPassthroughCommandConfig(action="power_on",  topic="/devices/wb-mr6c_51/controls/K4/on", value="1"),
            "power_off": WbPassthroughCommandConfig(action="power_off", topic="/devices/wb-mr6c_51/controls/K4/on", value="0"),
        },
        state_topics={"power": "/devices/wb-mr6c_51/controls/K4"},
    )


def _dimmer_config() -> WbPassthroughDeviceConfig:
    """A param-carrying command (slider) to exercise the param-derived payload path."""
    return WbPassthroughDeviceConfig(
        device_id="cabinet_spots_dim",
        names={"ru": "Споты", "en": "Spots"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="cabinet",
        commands={
            "set_brightness": WbPassthroughCommandConfig(
                action="set_brightness",
                topic="/devices/wb-mdm3_83/controls/Channel 1/on",
                params=[CommandParameterDefinition(name="level", type="range", min=0, max=100, required=True)],
            ),
        },
        state_topics={"brightness": "/devices/wb-mdm3_83/controls/Channel 1"},
    )


@pytest.fixture
def mqtt() -> MagicMock:
    m = MagicMock()
    m.subscribe = AsyncMock()
    m.publish = AsyncMock()
    return m


@pytest.fixture
def device(mqtt) -> WbPassthroughDevice:
    return WbPassthroughDevice(_slice_config(), mqtt_client=mqtt)


# --- Schema + construction ------------------------------------------------


def test_passthrough_config_defaults_disable_wb_emulation():
    """enable_wb_emulation MUST default to False on the passthrough config so the BaseDevice
    flow skips _setup_wb_virtual_device — the structural loop guard."""
    cfg = _slice_config()
    assert cfg.enable_wb_emulation is False


def test_bilingual_names_and_single_room_carry_through(device):
    assert device.config.names.ru == "Споты"
    assert device.config.names.en == "Spots"
    assert device.config.room == "cabinet"
    # BaseDevice's flat compat field projects ru, matching the UI/state surfaces.
    assert device.device_name == "Споты"


def test_handlers_registered_one_per_command(device):
    assert "power_on" in device._action_handlers
    assert "power_off" in device._action_handlers


# --- Setup: subscriptions go out for value + meta/error ------------------


@pytest.mark.asyncio
async def test_setup_subscribes_to_value_and_error_topic_per_state_field(device, mqtt):
    ok = await device.setup()
    assert ok is True
    subs = [c.args[0] for c in mqtt.subscribe.await_args_list]
    assert "/devices/wb-mr6c_51/controls/K4" in subs
    assert "/devices/wb-mr6c_51/controls/K4/meta/error" in subs
    # Two state_topics fields would be two subscribe calls each; slice has one field.
    assert len(subs) == 2


@pytest.mark.asyncio
async def test_setup_returns_false_without_mqtt_client():
    dev = WbPassthroughDevice(_slice_config(), mqtt_client=None)
    assert await dev.setup() is False


# --- Write path: static value -----------------------------------------------


@pytest.mark.asyncio
async def test_power_on_publishes_static_value(device, mqtt):
    result = await device.execute_action("power_on", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "1")


@pytest.mark.asyncio
async def test_power_off_publishes_static_value(device, mqtt):
    result = await device.execute_action("power_off", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "0")


# --- Write path: param-derived value ----------------------------------------


@pytest.mark.asyncio
async def test_set_brightness_publishes_param_value(mqtt):
    dev = WbPassthroughDevice(_dimmer_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_brightness", {"level": 75}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mdm3_83/controls/Channel 1/on", "75")


@pytest.mark.asyncio
async def test_set_brightness_without_param_fails_cleanly(mqtt):
    """Missing required param → graceful failure, no publish."""
    dev = WbPassthroughDevice(_dimmer_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_brightness", {}, source="api")
    assert result["success"] is False
    mqtt.publish.assert_not_called()


# --- Mirror path: value topic flows into state.mirrored ---------------------


@pytest.mark.asyncio
async def test_value_topic_echo_mirrors_into_state(device):
    await device._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert device.state.mirrored == {"power": "1"}
    assert device.state.reachable is True


@pytest.mark.asyncio
async def test_value_topic_echo_clears_previous_error_flag(device):
    # Seed: a previous read error
    device.state.error_flags = {"power": "r"}
    device.state.reachable = False
    await device._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert "power" not in device.state.error_flags
    assert device.state.reachable is True


# --- Error path: meta/error flag flips reachable ----------------------------


@pytest.mark.asyncio
async def test_meta_error_r_flag_flips_reachable_false(device):
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "r")
    assert device.state.error_flags == {"power": "r"}
    assert device.state.reachable is False


@pytest.mark.asyncio
async def test_meta_error_empty_payload_clears_flag(device):
    device.state.error_flags = {"power": "r"}
    device.state.reachable = False
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "")
    assert device.state.error_flags == {}
    assert device.state.reachable is True


@pytest.mark.asyncio
async def test_meta_error_compound_rw_still_marks_unreachable(device):
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "rw")
    assert device.state.error_flags == {"power": "rw"}
    assert device.state.reachable is False


@pytest.mark.asyncio
async def test_w_only_error_does_not_flip_reachable(device):
    """Per the convention, `w` is a write-side failure; the device may still be readable.
    We model `reachable` against read failures (`r`) only."""
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "w")
    assert device.state.error_flags == {"power": "w"}
    assert device.state.reachable is True
