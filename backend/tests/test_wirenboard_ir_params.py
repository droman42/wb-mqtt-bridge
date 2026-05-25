"""Tests for WirenboardIRDevice (post-hexagonal-refactor driver).

Two entry points actuate an IR command, and both converge on the device's action handlers,
which publish the IR-blaster MQTT command directly, exactly once
(topic = /devices/<location>/controls/Play from ROM<rom>/on, payload = 1):

  * execute_action(...)  — used by the FastAPI device-action router and the scenario reconciler.
  * handle_message(...)  — inbound MQTT / WB-UI control. WirenboardIRDevice no longer overrides
    this; it uses BaseDevice.handle_message, which routes WB `.../<control>/on` messages through
    wb_service to the same handlers. (The old override matched the wrong topic — without `/on` —
    and only *returned* an mqtt_command instead of executing, so WB-UI control never actuated.)

These tests cover the handler / execute_action contract. The full WB-service control path
(wb_service present) is verified at integration / hardware level.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.infrastructure.devices.wirenboard_ir_device.driver import WirenboardIRDevice
from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap
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
    """A configured WirenboardIRDevice. setup() is cheap (no network) so we run it.

    Attach a minimal capability map (the `input` domain's by_value mapping) so the driver's
    optimistic-input tracking — now keyed off capabilities, not a command-name convention — can
    resolve input_aux2 -> "aux2"."""
    d = WirenboardIRDevice(_make_config(), mqtt_client)
    d.capabilities = CapabilityMap.model_validate({
        "input": {
            "kind": "stateful",
            "feedback": False,
            "state_field": "input",
            "select": {"by_value": {"aux2": {"command": "input_aux2"}}},
        }
    })
    await d.setup()
    return d


# --- handle_message: now inherited from BaseDevice (broken override removed) -----


def test_wirenboard_ir_uses_base_handle_message():
    """The broken handle_message override is gone.

    Regression: the override matched `/devices/<id>/controls/<cmd>` (no `/on`) and only
    returned an mqtt_command instead of executing — so WB-UI / MQTT control of IR devices hit
    "No command configuration found for .../on" and never fired. WirenboardIRDevice now uses
    BaseDevice.handle_message, which routes WB `.../on` controls through wb_service to the same
    action handlers (single direct publish).
    """
    assert WirenboardIRDevice.handle_message is BaseDevice.handle_message


# --- execute_action: the action handlers both entry points converge on ----------


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


# --- direct handler invocation (auto-discovered) --------------------------------


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


# --- command registry -----------------------------------------------------------


def test_commands_are_typed_ir_command_configs(device):
    """get_available_commands surfaces typed IRCommandConfig instances (not dicts)."""
    cmds = device.get_available_commands()
    for cmd_name in ("power", "set_volume"):
        cfg = cmds[cmd_name]
        assert isinstance(cfg, IRCommandConfig)
        assert cfg.location
        assert cfg.rom_position
