"""Fresh tests for WirenboardIRDevice, written against the post-hexagonal-refactor driver.

WirenboardIRDevice is a pure MQTT bridge — it doesn't have per-command
handle_X handlers. Its only public surface is `handle_message(topic, payload)`,
which:
  1. Resolves the topic to a configured command via the auto-generated path
     /devices/<id>/controls/<cmd>.
  2. Parses any payload into typed params via the command's param definitions.
  3. Builds an IR-blaster MQTT command (topic = /devices/<location>/controls/
     Play from ROM<rom>/on, payload = 1) and returns it as a CommandResult
     with `mqtt_command` set, so the caller (BaseDevice / scenario) can
     publish it onto the bus.

These tests verify each branch of that dispatch contract.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from wb_mqtt_bridge.infrastructure.devices.wirenboard_ir_device.driver import WirenboardIRDevice
from wb_mqtt_bridge.infrastructure.config.models import (
    WirenboardIRDeviceConfig,
    IRCommandConfig,
    CommandParameterDefinition,
)


pytestmark = pytest.mark.integration


def _make_config() -> WirenboardIRDeviceConfig:
    power_command = IRCommandConfig(
        action="power",
        topic="/devices/test_ir/controls/power",
        location="wb-msw-v3_207",
        rom_position="62",
        group="power",
        description="Power On/Off",
    )
    volume_command = IRCommandConfig(
        action="set_volume",
        topic="/devices/test_ir/controls/set_volume",
        location="wb-msw-v3_207",
        rom_position="33",
        group="volume",
        description="Set volume level",
        params=[CommandParameterDefinition(
            name="level", type="range", min=0, max=100, required=True,
        )],
    )
    input_command = IRCommandConfig(
        action="input_aux2",
        topic="/devices/test_ir/controls/input_aux2",
        location="wb-msw-v3_207",
        rom_position="24",
        group="inputs",
        description="AUX2",
    )
    return WirenboardIRDeviceConfig(
        device_id="test_ir",
        device_name="Test IR Device",
        device_class="WirenboardIRDevice",
        config_class="WirenboardIRDeviceConfig",
        commands={"power": power_command, "set_volume": volume_command, "input_aux2": input_command},
    )


@pytest.fixture
def mqtt_client():
    mqtt = MagicMock()
    fut = asyncio.Future()
    fut.set_result(True)
    mqtt.publish = MagicMock(return_value=fut)
    return mqtt


@pytest_asyncio.fixture
async def device(mqtt_client):
    """A configured WirenboardIRDevice. setup() is cheap (no network) so we run it."""
    d = WirenboardIRDevice(_make_config(), mqtt_client)
    await d.setup()
    return d


# --- handle_message: happy paths --------------------------------------------


@pytest.mark.asyncio
async def test_handle_message_routes_power_command(device):
    """A WB control message for 'power' produces a CommandResult with the IR-blaster MQTT command."""
    result = await device.handle_message("/devices/test_ir/controls/power", "1")
    assert isinstance(result, dict)
    assert result.get("success") is True
    assert "mqtt_command" in result
    mqtt_cmd = result["mqtt_command"]
    # The IR blaster topic format: /devices/<location>/controls/Play from ROM<rom>/on
    assert mqtt_cmd["topic"] == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    assert str(mqtt_cmd["payload"]) == "1"


@pytest.mark.asyncio
async def test_input_command_sets_optimistic_input(device):
    """An inputs-group IR command records optimistic state.input (no IR feedback)."""
    resp = await device.execute_action("input_aux2", {})
    assert resp["success"] is True
    assert device.state.input == "aux2"


@pytest.mark.asyncio
async def test_power_toggle_succeeds_and_flips_optimistic_power(device):
    """Power toggle must report success and flip optimistic state.power.

    Regression (found on hardware): the handler did `result.success` on a CommandResult
    *dict*, raising "'dict' object has no attribute 'success'" — so the IR fired but the
    command reported failure and the power state was never updated (breaking the reconciler).
    """
    initial = device.state.power
    resp = await device.execute_action("power", {})
    assert resp["success"] is True
    assert device.state.power != initial  # toggled
    assert device.state.power in ("on", "off")

    # toggle back
    resp2 = await device.execute_action("power", {})
    assert resp2["success"] is True
    assert device.state.power == initial


@pytest.mark.asyncio
async def test_execute_action_publishes_ir_once_and_no_mqtt_command(device, mqtt_client):
    """The execute_action path publishes the IR directly and must NOT also return mqtt_command.

    Regression (found on hardware): the driver published the IR directly AND returned it as
    mqtt_command, so the API action router (devices.py) published the same IR a *second* time
    — a double blast (two toggles). The result must carry no mqtt_command so the router has
    nothing to re-publish.
    """
    for action in ("power", "input_aux2", "set_volume"):
        mqtt_client.publish.reset_mock()
        params = {"level": 50} if action == "set_volume" else {}
        resp = await device.execute_action(action, params)
        assert resp["success"] is True, action
        mqtt_client.publish.assert_called_once()      # exactly one IR blast
        assert not resp.get("mqtt_command"), action   # nothing for the router to re-publish


@pytest.mark.asyncio
async def test_handle_message_routes_parameterized_command(device):
    """A command with a 'level' param converts the raw payload to the typed value.

    Note: the driver's handle_message first tries json.loads on the payload,
    so a bare number like "42" gets parsed as the int 42 (not as the named
    parameter 'level'). To exercise the "single-param, raw payload" branch
    cleanly we use a string payload that fails JSON parsing — the driver
    then falls back to mapping the raw string into the first parameter via
    _validate_parameter, which handles range coercion.
    """
    result = await device.handle_message("/devices/test_ir/controls/set_volume", "50abc")
    # "50abc" is not valid JSON; the fallback path runs and the range validator
    # rejects "50abc" as not-a-number, so we expect a failure result.
    assert result is not None
    assert result.get("success") is False


@pytest.mark.asyncio
async def test_handle_message_parameterized_command_json_payload(device):
    """A JSON-shaped payload for a parameterized command is parsed and the IR command emitted."""
    result = await device.handle_message(
        "/devices/test_ir/controls/set_volume",
        '{"level": 50}',
    )
    assert result.get("success") is True
    mqtt_cmd = result["mqtt_command"]
    assert "Play from ROM33" in mqtt_cmd["topic"]


# --- handle_message: ignore / refuse branches -------------------------------


@pytest.mark.asyncio
async def test_handle_message_unknown_topic_returns_none(device):
    """If no command's auto-topic matches, handle_message returns None (no dispatch)."""
    result = await device.handle_message("/devices/test_ir/controls/nonexistent", "1")
    assert result is None


@pytest.mark.asyncio
async def test_handle_message_zero_payload_ignored(device):
    """For non-parameterized commands, payloads other than '1'/'true' are no-ops (still success)."""
    result = await device.handle_message("/devices/test_ir/controls/power", "0")
    # The driver returns a success CommandResult with a "Command ignored" message.
    assert result.get("success") is True
    assert "mqtt_command" not in result or result["mqtt_command"] is None


@pytest.mark.asyncio
async def test_handle_message_invalid_param_rejected(device):
    """For a parameterized command, a payload that doesn't validate yields a failure result."""
    result = await device.handle_message("/devices/test_ir/controls/set_volume", "not-a-number")
    assert result is not None
    assert result.get("success") is False


# --- direct handler invocation (auto-discovered) ----------------------------


@pytest.mark.asyncio
async def test_direct_handler_for_power_publishes_to_mqtt(device, mqtt_client):
    """BaseDevice auto-registers a handler for each command — calling it sends IR via MQTT."""
    handler = device._get_action_handler("power")
    assert handler is not None
    cmd_config = device.get_available_commands()["power"]

    mqtt_client.publish.reset_mock()
    await handler(cmd_config=cmd_config, params={})

    mqtt_client.publish.assert_called_once()
    topic_arg, payload_arg = mqtt_client.publish.call_args[0][:2]
    assert topic_arg == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    assert str(payload_arg) == "1"


# --- command registry -------------------------------------------------------


def test_commands_are_typed_ir_command_configs(device):
    """get_available_commands surfaces typed IRCommandConfig instances (not dicts)."""
    cmds = device.get_available_commands()
    for cmd_name in ("power", "set_volume"):
        cfg = cmds[cmd_name]
        assert isinstance(cfg, IRCommandConfig)
        assert cfg.location
        assert cfg.rom_position
