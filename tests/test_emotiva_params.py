import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock

from devices.emotiva_xmc2 import EMotivaXMC2
from app.mqtt_client import MQTTClient


@pytest.fixture
def emotiva_config():
    return {
        "device_id": "test_processor",
        "device_name": "Test XMC2 Processor",
        "device_class": "emotiva_xmc2",
        "device_info": {
            "name": "Test XMC2 Processor",
            "model": "XMC2",
            "manufacturer": "Emotiva",
            "host": "192.168.1.100",
            "port": 7000
        },
        "commands": {
            "power_on": {
                "action": "power_on",
                "topic": "/devices/test_processor/controls/power_on",
                "group": "power",
                "description": "Turn on the processor",
                "params": []
            },
            "power_off": {
                "action": "power_off",
                "topic": "/devices/test_processor/controls/power_off",
                "group": "power",
                "description": "Turn off the processor",
                "params": []
            },
            "zone2_on": {
                "action": "zone2_on",
                "topic": "/devices/test_processor/controls/zone2_on",
                "group": "power",
                "description": "Turn on zone 2",
                "params": []
            },
            "zappiti": {
                "action": "zappiti",
                "topic": "/devices/test_processor/controls/zappiti",
                "group": "inputs",
                "description": "Switch to Zappiti",
                "params": []
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
                    }
                ]
            },
            "set_mute": {
                "action": "set_mute",
                "topic": "/devices/test_processor/controls/mute",
                "group": "volume",
                "description": "Set mute state",
                "params": [
                    {
                        "name": "state",
                        "type": "boolean",
                        "required": True,
                        "description": "Mute state (true for muted, false for unmuted)"
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
    
    # Create properly connected futures for the event loop
    power_on_future = asyncio.Future()
    power_on_future.set_result({"status": "success"})
    device.client.set_power_on = AsyncMock(return_value=power_on_future)
    
    power_off_future = asyncio.Future()
    power_off_future.set_result({"status": "success"})
    device.client.set_power_off = AsyncMock(return_value=power_off_future)
    
    volume_future = asyncio.Future()
    volume_future.set_result({"status": "success"})
    device.client.set_volume = AsyncMock(return_value=volume_future)
    
    mute_future = asyncio.Future()
    mute_future.set_result({"status": "success"})
    device.client.set_mute = AsyncMock(return_value=mute_future)
    
    input_future = asyncio.Future()
    input_future.set_result({"status": "success"})
    device.client.set_input = AsyncMock(return_value=input_future)
    
    notif_future = asyncio.Future()
    notif_future.set_result({"status": "success"})
    device.client.subscribe_to_notifications = AsyncMock(return_value=notif_future)
    
    return device


@pytest.mark.asyncio
async def test_power_on_with_parameters(emotiva_device):
    """Test the power_on handler with parameter-based approach."""
    # Extract config for a command
    power_on_config = emotiva_device.get_available_commands()["power_on"]
    
    # Call using the parameter pattern
    result = await emotiva_device.handle_power_on(
        cmd_config=power_on_config,
        params={}
    )
    
    # Verify the client method was called
    emotiva_device.client.set_power_on.assert_called_once()
    
    # Verify the result is a valid response
    assert isinstance(result, dict)
    assert "success" in result
    assert result["success"] is True


@pytest.mark.asyncio
async def test_parameter_pattern(emotiva_device):
    """Test that the parameter pattern works."""
    # Extract config for the set_volume command
    volume_config = emotiva_device.get_available_commands()["set_volume"]
    
    # Call using the parameter pattern
    result = await emotiva_device.handle_set_volume(
        cmd_config=volume_config, 
        params={"level": -30.0}
    )
    
    # Verify the client method was called with the right parameters
    emotiva_device.client.set_volume.assert_called_once()
    call_args = emotiva_device.client.set_volume.call_args[0]
    assert call_args[0] == -30.0
    
    # Verify the result is a valid response
    assert isinstance(result, dict)
    assert "success" in result
    assert result["success"] is True


@pytest.mark.asyncio
async def test_mqtt_message_handling(emotiva_device):
    """Test that MQTT messages trigger the correct handler."""
    # Mock the handle_set_volume method
    original_handler = emotiva_device.handle_set_volume
    
    with patch.object(emotiva_device, 'handle_set_volume') as mock_handle:
        # Set up the mock return value
        mock_handle.return_value = {"success": True}
        
        try:
            # Add a reference to the mock in the action handlers dictionary
            emotiva_device._action_handlers["set_volume"] = mock_handle
            
            # Call handle_message with the volume topic and a valid JSON payload
            volume_topic = emotiva_device.get_available_commands()["set_volume"]["topic"]
            payload = json.dumps({"level": -40.0})
            result = await emotiva_device.handle_message(volume_topic, payload)
            
            # Verify handle_set_volume was called with the right parameters
            mock_handle.assert_called_once()
            
            # Check that it was called with the cmd_config and params
            assert mock_handle.call_args[1]["cmd_config"] is not None
            assert mock_handle.call_args[1]["params"] == {"level": -40.0}
            
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
            result = await emotiva_device.handle_message(volume_topic, payload)
            
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