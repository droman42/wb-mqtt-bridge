import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from devices.revox_a77_reel_to_reel import RevoxA77ReelToReel
from app.mqtt_client import MQTTClient


@pytest.fixture
def revox_config():
    return {
        "name": "Test Revox A77",
        "type": "RevoxA77ReelToReel",
        "id": "test_revox",
        "alias": "Revox A77",
        "parameters": {
            "sequence_delay": 3
        },
        "commands": {
            "play": {
                "topic": "/devices/test_revox/controls/play",
                "location": "revox_ir",
                "rom_position": "1"
            },
            "stop": {
                "topic": "/devices/test_revox/controls/stop",
                "location": "revox_ir",
                "rom_position": "2"
            },
            "rewind_forward": {
                "topic": "/devices/test_revox/controls/rewind_forward",
                "location": "revox_ir",
                "rom_position": "3"
            },
            "rewind_backward": {
                "topic": "/devices/test_revox/controls/rewind_backward",
                "location": "revox_ir",
                "rom_position": "4"
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
def revox_device(revox_config, mock_mqtt_client):
    device = RevoxA77ReelToReel(revox_config, mock_mqtt_client)
    return device


@pytest.mark.asyncio
async def test_parameter_pattern(revox_device):
    """Test that the parameter pattern works."""
    # Extract config for a command
    stop_config = revox_device.get_available_commands()["stop"]
    
    # Mock the _send_ir_command method
    with patch.object(revox_device, '_send_ir_command') as mock_send:
        mock_send.return_value = {
            "topic": "/devices/revox_ir/controls/Play from ROM2/on", 
            "payload": "1"
        }
        
        # Call using the parameter pattern
        result = await revox_device.handle_stop(
            cmd_config=stop_config, 
            params={"value": "1"}
        )
        
        # Verify it called the method correctly
        mock_send.assert_called_once_with(stop_config, "stop")
        
        # Verify the result is a valid MQTT command
        assert isinstance(result, dict)
        assert "topic" in result
        assert "payload" in result


@pytest.mark.asyncio
async def test_sequence_execution(revox_device):
    """Test that sequence execution correctly sends stop before action."""
    # Mock the _send_ir_command method
    with patch.object(revox_device, '_send_ir_command') as mock_send, \
         patch.object(asyncio, 'sleep') as mock_sleep:
        
        # Setup return values for two calls (stop then play)
        mock_send.side_effect = [
            {"topic": "/devices/revox_ir/controls/Play from ROM2/on", "payload": "1"},  # stop
            {"topic": "/devices/revox_ir/controls/Play from ROM1/on", "payload": "1"}   # play
        ]
        
        # Call execute_sequence for play
        play_config = revox_device.get_available_commands()["play"]
        result = await revox_device._execute_sequence(play_config, "play")
        
        # Verify it called the methods correctly
        assert mock_send.call_count == 2
        mock_sleep.assert_called_once_with(3)  # Using our fixture's sequence_delay value
        
        # Check publish was called with stop command
        revox_device.mqtt_client.publish.assert_called_once()
        topic_arg = revox_device.mqtt_client.publish.call_args[0][0]
        assert "ROM2" in topic_arg  # The stop command ROM position


@pytest.mark.asyncio
async def test_mqtt_message_handling(revox_device):
    """Test that MQTT messages trigger the correct handler."""
    # Mock the handle_play method but preserve it in _action_handlers
    original_handler = revox_device._action_handlers["play"]
    with patch.object(revox_device, 'handle_play') as mock_handle:
        # Ensure the mock is still accessible through _action_handlers
        revox_device._action_handlers["play"] = mock_handle
        mock_handle.return_value = {"topic": "/test/topic", "payload": "1"}
        
        try:
            # Call handle_message with play topic
            play_topic = revox_device.get_available_commands()["play"]["topic"]
            result = await revox_device.handle_message(play_topic, "1")
            
            # Verify handle_play was called with the right parameters
            mock_handle.assert_called_once()
            # Check that it was called with the parameter pattern
            assert mock_handle.call_args[1]["cmd_config"] is not None
            assert "params" in mock_handle.call_args[1]
        finally:
            # Restore the original handler
            revox_device._action_handlers["play"] = original_handler 