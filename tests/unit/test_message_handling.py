import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json
import inspect
from typing import Dict, Any, Optional

# Add parent directory to path to allow importing from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from devices.base_device import BaseDevice
from app.schemas import LastCommand

class TestMessageHandling(unittest.IsolatedAsyncioTestCase):
    """Test suite for MQTT message handling and API action execution."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock device for testing
        self.device = MagicMock(spec=BaseDevice)
        
        # Mock _execute_single_action instead of using actual implementation
        self.device._execute_single_action = AsyncMock()
        
        # Use the actual implementations for these methods
        self.device.handle_message = BaseDevice.handle_message.__get__(self.device, BaseDevice)
        self.device.execute_action = BaseDevice.execute_action.__get__(self.device, BaseDevice)
        self.device._try_parse_json_payload = BaseDevice._try_parse_json_payload.__get__(self.device, BaseDevice)
        self.device._resolve_and_validate_params = BaseDevice._resolve_and_validate_params.__get__(self.device, BaseDevice)
        self.device._evaluate_condition = MagicMock(return_value=True)  # Always match conditions
        
        # Set mock values for required attributes
        self.device.device_id = "test_device"
        self.device.device_name = "Test Device"
        self.device.update_state = AsyncMock()
        self.device.publish_progress = AsyncMock()
        
        # Mock the get_current_state method
        self.device.get_current_state = MagicMock(return_value={"device_id": "test_device"})
        
        # Mock command configuration
        self.test_commands = {
            "setLevel": {
                "topic": "/test/level",
                "action": "set_level",
                "params": [
                    {"name": "level", "type": "range", "min": 0, "max": 100, "required": True}
                ]
            },
            "multiParam": {
                "topic": "/test/multi",
                "action": "multi_param",
                "params": [
                    {"name": "level", "type": "integer", "required": True},
                    {"name": "color", "type": "string", "required": False, "default": "white"}
                ]
            },
            "conditionalAction": {
                "topic": "/test/conditional",
                "actions": [
                    {
                        "name": "action_on",
                        "condition": "payload == '1'",
                        "params": [
                            {"name": "speed", "type": "integer", "required": True}
                        ]
                    },
                    {
                        "name": "action_off",
                        "condition": "payload == '0'"
                    }
                ]
            },
            "legacyCommand": {
                "topic": "/test/legacy"
                # No params defined
            }
        }
        
        # Mock the get_available_commands method
        self.device.get_available_commands = MagicMock(return_value=self.test_commands)
        
        # Create handlers for both old and new style
        async def mock_new_handler(cmd_config, params):
            return {"style": "new", "params": params}
            
        async def mock_old_handler(action_config, payload):
            return {"style": "old", "payload": payload}
        
        # Register mock handlers
        self.device._get_action_handler = MagicMock()
        self.device._get_action_handler.side_effect = lambda action: {
            "set_level": mock_new_handler,
            "multi_param": mock_new_handler,
            "action_on": mock_new_handler,
            "action_off": mock_old_handler,
            "legacycommand": mock_old_handler
        }.get(action.lower())
    
    async def test_handle_message_with_json_payload(self):
        """Test handling a message with JSON payload."""
        # JSON payload for a command with parameters
        payload = json.dumps({"level": 75})
        topic = "/test/level"
        
        # Handle the message
        await self.device.handle_message(topic, payload)
        
        # Check that _execute_single_action was called with correct parameters
        self.device._execute_single_action.assert_called_once()
        call_args = self.device._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "setLevel")  # action_name
        self.assertEqual(call_args[1], self.test_commands["setLevel"])  # cmd_config
        
        # Since we're mocking _resolve_and_validate_params differently, check if params were passed
        self.assertIsNotNone(call_args[2])  # params
        
    async def test_handle_message_with_raw_payload(self):
        """Test handling a message with raw payload that can be converted to a parameter."""
        # Raw payload (non-JSON) for a command with parameters
        payload = "50"  # Simple integer payload
        topic = "/test/level"
        
        # Handle the message
        await self.device.handle_message(topic, payload)
        
        # Check that _execute_single_action was called with correct parameters
        self.device._execute_single_action.assert_called_once()
        call_args = self.device._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "setLevel")  # action_name
        self.assertEqual(call_args[1], self.test_commands["setLevel"])  # cmd_config
        self.assertIsNotNone(call_args[2])  # params should not be None
        
    async def test_handle_message_with_conditional_actions(self):
        """Test handling a message that triggers a conditional action."""
        # Payload that should trigger the first action
        payload = "1"
        topic = "/test/conditional"
        
        # Reset the mock
        self.device._execute_single_action.reset_mock()
        
        # Handle the message
        await self.device.handle_message(topic, payload)
        
        # Check that _execute_single_action was called for the matching action
        self.device._execute_single_action.assert_called_once()
        call_args = self.device._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "action_on")  # action_name
    
    async def test_handle_message_with_legacy_command(self):
        """Test handling a message for a command with no parameters defined."""
        # Simple payload for a command without parameters
        payload = "ON"
        topic = "/test/legacy"
        
        # Reset the mock
        self.device._execute_single_action.reset_mock()
        
        # Handle the message
        await self.device.handle_message(topic, payload)
        
        # Check that _execute_single_action was called with raw payload
        self.device._execute_single_action.assert_called_once()
        call_args = self.device._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "legacyCommand")  # action_name
        self.assertEqual(call_args[1], self.test_commands["legacyCommand"])  # cmd_config
        self.assertEqual(call_args[3], "ON")  # raw_payload
    
    async def test_execute_action_with_parameters(self):
        """Test executing an action with parameters via API."""
        # Execute an action with parameters
        action = "setLevel"
        params = {"level": 80}
        
        # Set up the success result
        self.device._execute_single_action.return_value = {"success": True}
        
        # Execute the action
        result = await self.device.execute_action(action, params)
        
        # Check that the method returned success
        self.assertTrue(result["success"])
        
        # Check that _execute_single_action was called
        self.device._execute_single_action.assert_called_once()
        call_args = self.device._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "setLevel")  # action_name
        self.assertEqual(call_args[1], self.test_commands["setLevel"])  # cmd_config
    
    async def test_execute_action_with_invalid_parameters(self):
        """Test executing an action with invalid parameters."""
        # Execute an action with invalid parameters (level out of range)
        action = "setLevel"
        params = {"level": 200}  # Above max of 100
        
        # Mock _resolve_and_validate_params to raise ValueError for invalid parameters
        original_validate = self.device._resolve_and_validate_params
        def side_effect(*args, **kwargs):
            if args[1].get("level", 0) > 100:
                raise ValueError(f"Parameter 'level' value {args[1].get('level')} is above maximum 100")
            return original_validate(*args, **kwargs)
        
        self.device._resolve_and_validate_params = MagicMock(side_effect=side_effect)
        
        # Execute the action (should fail)
        result = await self.device.execute_action(action, params)
        
        # Check that the method returned failure
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("above maximum", result["error"])


if __name__ == '__main__':
    unittest.main() 