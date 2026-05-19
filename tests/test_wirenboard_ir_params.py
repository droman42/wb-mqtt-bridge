import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock
from wb_mqtt_bridge.infrastructure.devices.wirenboard_ir_device.driver import WirenboardIRDevice
from wb_mqtt_bridge.infrastructure.config.models import WirenboardIRDeviceConfig, IRCommandConfig

pytestmark = pytest.mark.integration

@pytest.fixture
def wirenboard_ir_config():
    """Create a test configuration for the WirenboardIR device."""
    # Create IRCommandConfig for the power command
    power_command = IRCommandConfig(
        action="power",
        topic="/devices/test_ir/controls/power",
        location="wb-msw-v3_207",
        rom_position="62",
        group="power",
        description="Power On/Off"
    )
    
    # Create the device config
    return WirenboardIRDeviceConfig(
        device_id="test_ir",
        device_name="Test IR Device",
        device_class="WirenboardIRDevice",
        config_class="WirenboardIRDeviceConfig",
        commands={"power": power_command}
    )


@pytest.fixture
def mqtt_client():
    """Create a mock MQTT client."""
    mock_mqtt = MagicMock()
    mock_mqtt.publish.return_value = asyncio.Future()
    mock_mqtt.publish.return_value.set_result(True)
    return mock_mqtt


@pytest_asyncio.fixture
async def wirenboard_ir_device(wirenboard_ir_config, mqtt_client):
    """Create a WirenboardIR device with mocked MQTT client."""
    device = WirenboardIRDevice(wirenboard_ir_config, mqtt_client)
    await device.setup()
    return device


@pytest.mark.asyncio
async def test_new_parameter_pattern(wirenboard_ir_device, mqtt_client):
    """Calling the IR handler directly publishes the right MQTT topic+payload.

    cmd_config must be the typed IRCommandConfig (handlers attribute-access it).
    The old test passed a plain dict, which now triggers an internal 'dict has no
    attribute success' error downstream.
    """
    handler = wirenboard_ir_device._get_action_handler("power")
    # Use the real typed cmd_config from the device's commands.
    cmd_config = wirenboard_ir_device.get_available_commands()["power"]

    mqtt_client.publish.reset_mock()

    await handler(cmd_config=cmd_config, params={})

    mqtt_client.publish.assert_called_once()
    topic_arg, payload_arg = mqtt_client.publish.call_args[0][:2]
    assert topic_arg == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    # Payload is now passed as a string "1" (broker accepts either; production
    # writes it as a string for consistency with the WB control schema).
    assert str(payload_arg) == "1"


@pytest.mark.asyncio
async def test_mqtt_message_handling(wirenboard_ir_device, mqtt_client):
    """handle_message returns a CommandResult whose mqtt_command holds topic/payload.

    The old return shape was a flat {"topic": ..., "payload": ...}; the current
    BaseDevice.CommandResult wraps the dispatch metadata under 'mqtt_command'
    and adds success/message fields.
    """
    mqtt_client.publish.reset_mock()

    result = await wirenboard_ir_device.handle_message("/devices/test_ir/controls/power", "1")

    assert isinstance(result, dict)
    assert result.get("success") is True
    assert "mqtt_command" in result
    mqtt_cmd = result["mqtt_command"]
    assert mqtt_cmd["topic"] == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    assert str(mqtt_cmd["payload"]) == "1"

    # The old test additionally asserted on get_last_command() — that helper no
    # longer exists on WirenboardIRDevice; equivalent observation (the action was
    # dispatched against the right device-internal command) is already covered by
    # the mqtt_command checks above.