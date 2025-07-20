import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock

from wb_mqtt_bridge.infrastructure.devices.emotiva_xmc2.driver import EMotivaXMC2, PowerState
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from tests.test_helpers import wrap_device_init

# Apply the wrapper to automatically convert dict configs to Pydantic models
EMotivaXMC2 = wrap_device_init(EMotivaXMC2)


@pytest.fixture
def emotiva_config():
    return {
        "device_id": "test_processor",
        "device_name": "Test XMC2 Processor",
        "device_class": "EMotivaXMC2",
        "config_class": "EmotivaXMC2DeviceConfig",
        "emotiva": {
            "host": "192.168.1.100",
            "port": 7002,
            "mac": "AA:BB:CC:DD:EE:FF",
            "update_interval": 60,
            "timeout": 5.0,
            "max_retries": 3,
            "retry_delay": 2.0,
            "force_connect": False
        },
        "commands": {
            "power_on": {
                "action": "power_on",
                "topic": "/devices/test_processor/controls/power_on",
                "group": "power",
                "description": "Turn on the processor",
                "params": [
                    {
                        "name": "zone",
                        "type": "integer",
                        "required": False,
                        "default": 1,
                        "description": "Zone ID (1 for main, 2 for zone2)"
                    }
                ]
            },
            "power_off": {
                "action": "power_off",
                "topic": "/devices/test_processor/controls/power_off",
                "group": "power",
                "description": "Turn off the processor",
                "params": [
                    {
                        "name": "zone",
                        "type": "integer",
                        "required": False,
                        "default": 1,
                        "description": "Zone ID (1 for main, 2 for zone2)"
                    }
                ]
            },
            "zone2_on": {
                "action": "power_on",
                "topic": "/devices/test_processor/controls/zone2_on",
                "group": "power",
                "description": "Turn on zone 2",
                "params": [
                    {
                        "name": "zone",
                        "type": "integer",
                        "required": False,
                        "default": 2,
                        "description": "Zone ID (2 for zone2)"
                    }
                ]
            },
            "set_input": {
                "action": "set_input",
                "topic": "/devices/test_processor/controls/set_input",
                "group": "inputs",
                "description": "Switch to input",
                "params": [
                    {
                        "name": "input",
                        "type": "string",
                        "required": True,
                        "description": "Input name (hdmi1, hdmi2, etc.)"
                    }
                ]
            },
            "set_volume": {
                "action": "set_volume",
                "topic": "/devices/test_processor/controls/volume",
                "group": "volume",
                "description": "Set volume level",
                "params": [
                    {
                        "name": "level",
                        "type": "range",
                        "min": -96.0,
                        "max": 0.0,
                        "required": True,
                        "description": "Volume level in dB (between -96.0 and 0.0)"
                    },
                    {
                        "name": "zone",
                        "type": "integer",
                        "required": False,
                        "default": 1,
                        "description": "Zone ID (1 for main, 2 for zone2)"
                    }
                ]
            },
            "mute_toggle": {
                "action": "mute_toggle",
                "topic": "/devices/test_processor/controls/mute_toggle",
                "group": "volume",
                "description": "Toggle mute state",
                "params": [
                    {
                        "name": "zone",
                        "type": "integer",
                        "required": False,
                        "default": 1,
                        "description": "Zone ID (1 for main, 2 for zone2)"
                    }
                ]
            }
        }
    }


@pytest.fixture
def mock_mqtt_client():
    mqtt_client = MagicMock(spec=MQTTClient)
    mqtt_client.publish = MagicMock(return_value=asyncio.Future())
    mqtt_client.publish.return_value.set_result(None)
    return mqtt_client


@pytest.fixture
def emotiva_device(emotiva_config, mock_mqtt_client):
    device = EMotivaXMC2(emotiva_config, mock_mqtt_client)
    # Mock client for testing
    device.client = MagicMock()
    
    # Create the _power_zone method mock
    device._power_zone = AsyncMock(return_value=True)
    
    # Create the _set_zone_volume method mock
    device._set_zone_volume = AsyncMock(return_value=True)
    
    # Create the _toggle_zone_mute method mock
    device._toggle_zone_mute = AsyncMock(return_value=(True, True))
    
    # Mock input selection
    device.client.select_input = AsyncMock()
    
    # Mock notif subscription
    device.client.subscribe = AsyncMock()
    
    # Mock state refresh
    device._refresh_device_state = AsyncMock(return_value={})
    
    return device


@pytest.mark.asyncio
async def test_power_on_with_zone_parameter(emotiva_device):
    """Test the power_on handler with zone parameter."""
    # Extract config for power_on command
    power_on_config = emotiva_device.get_available_commands()["power_on"]
    
    # Call with zone=1 (main zone)
    result_main = await emotiva_device.handle_power_on(
        cmd_config=power_on_config,
        params={"zone": 1}
    )
    
    # Verify _power_zone was called with correct parameters
    emotiva_device._power_zone.assert_called_with(1, True)
    
    # Verify the result is successful
    assert result_main["success"] is True
    assert result_main["zone"] == 1
    
    # Reset mock for next test
    emotiva_device._power_zone.reset_mock()
    
    # Call with zone=2 (zone 2)
    result_zone2 = await emotiva_device.handle_power_on(
        cmd_config=power_on_config,
        params={"zone": 2}
    )
    
    # Verify _power_zone was called with correct parameters
    emotiva_device._power_zone.assert_called_with(2, True)
    
    # Verify the result is successful with zone 2
    assert result_zone2["success"] is True
    assert result_zone2["zone"] == 2


@pytest.mark.asyncio
async def test_power_off_with_zone_parameter(emotiva_device):
    """Test the power_off handler with zone parameter."""
    # Extract config for power_off command
    power_off_config = emotiva_device.get_available_commands()["power_off"]
    
    # Set mock state for main zone
    emotiva_device.state.power = PowerState.ON
    
    # Call with zone=1 (main zone)
    result_main = await emotiva_device.handle_power_off(
        cmd_config=power_off_config,
        params={"zone": 1}
    )
    
    # Verify _power_zone was called with correct parameters
    emotiva_device._power_zone.assert_called_with(1, False)
    
    # Verify the result is successful
    assert result_main["success"] is True
    assert result_main["zone"] == 1
    
    # Reset mock for next test
    emotiva_device._power_zone.reset_mock()
    
    # Set mock state for zone 2
    emotiva_device.state.zone2_power = PowerState.ON
    
    # Call with zone=2 (zone 2)
    result_zone2 = await emotiva_device.handle_power_off(
        cmd_config=power_off_config,
        params={"zone": 2}
    )
    
    # Verify _power_zone was called with correct parameters
    emotiva_device._power_zone.assert_called_with(2, False)
    
    # Verify the result is successful with zone 2
    assert result_zone2["success"] is True
    assert result_zone2["zone"] == 2


@pytest.mark.asyncio
async def test_set_volume_with_zone_parameter(emotiva_device):
    """Test the set_volume handler with zone parameter."""
    # Extract config for set_volume command
    volume_config = emotiva_device.get_available_commands()["set_volume"]
    
    # Call with zone=1 (main zone)
    result_main = await emotiva_device.handle_set_volume(
        cmd_config=volume_config, 
        params={"level": -30.0, "zone": 1}
    )
    
    # Verify _set_zone_volume was called with correct parameters
    emotiva_device._set_zone_volume.assert_called_with(1, -30.0)
    
    # Verify the result is successful
    assert result_main["success"] is True
    assert result_main["zone"] == 1
    assert result_main["volume"] == -30.0
    
    # Reset mock for next test
    emotiva_device._set_zone_volume.reset_mock()
    
    # Call with zone=2 (zone 2)
    result_zone2 = await emotiva_device.handle_set_volume(
        cmd_config=volume_config, 
        params={"level": -40.0, "zone": 2}
    )
    
    # Verify _set_zone_volume was called with correct parameters
    emotiva_device._set_zone_volume.assert_called_with(2, -40.0)
    
    # Verify the result is successful with zone 2
    assert result_zone2["success"] is True
    assert result_zone2["zone"] == 2
    assert result_zone2["volume"] == -40.0


@pytest.mark.asyncio
async def test_mute_toggle_with_zone_parameter(emotiva_device):
    """Test the mute_toggle handler with zone parameter."""
    # Extract config for mute_toggle command
    mute_config = emotiva_device.get_available_commands()["mute_toggle"]
    
    # Call with zone=1 (main zone)
    result_main = await emotiva_device.handle_mute_toggle(
        cmd_config=mute_config, 
        params={"zone": 1}
    )
    
    # Verify _toggle_zone_mute was called with correct parameters
    emotiva_device._toggle_zone_mute.assert_called_with(1)
    
    # Verify the result is successful
    assert result_main["success"] is True
    assert result_main["zone"] == 1
    assert result_main["mute"] is True  # Mock returns True
    
    # Reset mock for next test
    emotiva_device._toggle_zone_mute.reset_mock()
    
    # Call with zone=2 (zone 2)
    result_zone2 = await emotiva_device.handle_mute_toggle(
        cmd_config=mute_config, 
        params={"zone": 2}
    )
    
    # Verify _toggle_zone_mute was called with correct parameters
    emotiva_device._toggle_zone_mute.assert_called_with(2)
    
    # Verify the result is successful with zone 2
    assert result_zone2["success"] is True
    assert result_zone2["zone"] == 2
    assert result_zone2["mute"] is True  # Mock returns True


@pytest.mark.asyncio
async def test_set_input(emotiva_device):
    """Test the set_input handler."""
    # Extract config for set_input command
    input_config = emotiva_device.get_available_commands()["set_input"]
    
    # Call with input parameter
    result = await emotiva_device.handle_set_input(
        cmd_config=input_config, 
        params={"input": "hdmi1"}
    )
    
    # Verify the client.select_input was called with the correct input
    emotiva_device.client.select_input.assert_called_once()
    
    # Verify the result is successful
    assert result["success"] is True
    assert result["input"] == "hdmi1"


@pytest.mark.asyncio
async def test_mqtt_message_handling(emotiva_device):
    """Test that MQTT messages trigger the correct handler with zone parameters."""
    # Mock the handle_set_volume method
    original_handler = emotiva_device.handle_set_volume
    
    with patch.object(emotiva_device, 'handle_set_volume') as mock_handle:
        # Set up the mock return value
        mock_handle.return_value = {"success": True}
        
        try:
            # Add a reference to the mock in the action handlers dictionary
            emotiva_device._action_handlers["set_volume"] = mock_handle
            
            # Call handle_message with the volume topic and a JSON payload including zone
            volume_topic = emotiva_device.get_available_commands()["set_volume"]["topic"]
            payload = json.dumps({"level": -40.0, "zone": 2})
            await emotiva_device.handle_message(volume_topic, payload)
            
            # Verify handle_set_volume was called with the right parameters
            mock_handle.assert_called_once()
            
            # Check that it was called with params including zone
            assert mock_handle.call_args[1]["params"] == {"level": -40.0, "zone": 2}
            
        finally:
            # Restore the original handler
            emotiva_device._action_handlers["set_volume"] = original_handler


@pytest.mark.asyncio
async def test_mqtt_message_with_single_param(emotiva_device):
    """Test handling a message with a non-JSON payload for a single parameter command."""
    # Mock the handle_set_volume method
    original_handler = emotiva_device.handle_set_volume
    
    with patch.object(emotiva_device, 'handle_set_volume') as mock_handle:
        # Set up the mock return value
        mock_handle.return_value = {"success": True}
        
        try:
            # Add a reference to the mock in the action handlers dictionary
            emotiva_device._action_handlers["set_volume"] = mock_handle
            
            # Call handle_message with the volume topic and a raw (non-JSON) payload
            volume_topic = emotiva_device.get_available_commands()["set_volume"]["topic"]
            payload = "-35.5"  # Raw volume value as a string
            await emotiva_device.handle_message(volume_topic, payload)
            
            # Verify handle_set_volume was called with the right parameters
            mock_handle.assert_called_once()
            
            # Check that the params parameter contains the correctly parsed level
            assert "params" in mock_handle.call_args[1]
            params = mock_handle.call_args[1]["params"]
            assert isinstance(params, dict)
            assert "level" in params
            assert params["level"] == -35.5
            
        finally:
            # Restore the original handler
            emotiva_device._action_handlers["set_volume"] = original_handler 