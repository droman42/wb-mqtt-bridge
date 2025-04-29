import json
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch
import base64
from devices.wirenboard_ir_device import WirenboardIRDevice
from app.schemas import WirenboardIRState


@pytest.fixture
def wirenboard_ir_config():
    """Create a test configuration for the WirenboardIR device."""
    return {
        "device_name": "Test IR Device",
        "device_type": "wirenboard_ir",
        "device_id": "test_ir",
        "alias": "test_ir",
        "mqtt_progress_topic": "/devices/test_ir/controls/progress",
        "commands": {
            "power": {
                "action": "power",
                "topic": "/devices/test_ir/controls/power",
                "location": "wb-msw-v3_207",
                "rom_position": "62",
                "group": "power",
                "description": "Power On/Off"
            }
        }
    }


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
async def test_legacy_handler_pattern(wirenboard_ir_device, mqtt_client):
    """Test the legacy handler pattern with action_config and payload."""
    # Get the action handler
    handler = wirenboard_ir_device._get_action_handler("power")
    
    # Create a mock action config
    action_config = {
        "location": "wb-msw-v3_207",
        "rom_position": "62"
    }
    
    # Call the handler with the legacy pattern
    await handler(action_config=action_config, payload="1")
    
    # Verify MQTT message was published
    mqtt_client.publish.assert_called_once()
    args = mqtt_client.publish.call_args[0]
    assert args[0] == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    assert args[1] == 1


@pytest.mark.asyncio
async def test_new_parameter_pattern(wirenboard_ir_device, mqtt_client):
    """Test the new parameter pattern with cmd_config and params."""
    # Get the action handler
    handler = wirenboard_ir_device._get_action_handler("power")
    
    # Create a mock command config
    cmd_config = {
        "location": "wb-msw-v3_207",
        "rom_position": "62"
    }
    
    # Create empty params (IR commands don't have parameters)
    params = {}
    
    # Reset mock
    mqtt_client.publish.reset_mock()
    
    # Call the handler with the new pattern
    await handler(cmd_config=cmd_config, params=params)
    
    # Verify MQTT message was published
    mqtt_client.publish.assert_called_once()
    args = mqtt_client.publish.call_args[0]
    assert args[0] == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    assert args[1] == 1


@pytest.mark.asyncio
async def test_mqtt_message_handling(wirenboard_ir_device, mqtt_client):
    """Test MQTT message handling with the updated handler."""
    # Reset mock
    mqtt_client.publish.reset_mock()
    
    # Call handle_message
    result = await wirenboard_ir_device.handle_message("/devices/test_ir/controls/power", "1")
    
    # Verify the result is a correctly formatted command
    assert isinstance(result, dict)
    assert "topic" in result
    assert "payload" in result
    assert result["topic"] == "/devices/wb-msw-v3_207/controls/Play from ROM62/on"
    assert result["payload"] == 1
    
    # Verify the last_command state was updated
    last_command = wirenboard_ir_device.get_last_command()
    assert last_command is not None
    assert last_command["topic"] == "/devices/test_ir/controls/power"
    assert last_command["command_topic"] == "/devices/wb-msw-v3_207/controls/Play from ROM62/on" 