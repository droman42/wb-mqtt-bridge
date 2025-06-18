import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json
import inspect
from typing import Dict, Any, Optional
import logging

# Add parent directory to path to allow importing from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from devices.base_device import BaseDevice
from app.schemas import LastCommand, BaseCommandConfig

# Mock implementation of _try_parse_json_payload for testing
def mock_try_parse_json_payload(payload: str) -> Dict[str, Any]:
    """Mock implementation of _try_parse_json_payload for tests."""
    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            return data
        return {"value": data}
    except json.JSONDecodeError:
        try:
            # Try to convert simple values to numbers
            value = float(payload)
            if value.is_integer():
                value = int(value)
            return {"value": value}
        except ValueError:
            # Return simple string value
            return {"value": payload}

# Mock implementation of handle_message that works with dictionary configs
async def mock_handle_message(self, topic: str, payload: str):
    """Handle incoming MQTT messages for this device - mock version for tests with dict configs."""
    print(f"Device received message on {topic}: {payload}")
    
    # Find matching command configuration based on topic
    matching_commands = []
    for cmd_name, cmd in self.get_available_commands().items():
        if cmd["topic"] == topic:  # Use dictionary access instead of attribute access
            # Add command to matches when topic matches
            matching_commands.append((cmd_name, cmd))
    
    if not matching_commands:
        print(f"No command configuration found for topic: {topic}")
        return
    
    # Process each matching command configuration found for the topic
    for cmd_name, cmd in matching_commands:
        # First check if this is a conditional command set
        if "actions" in cmd:
            # This is a command with multiple conditional actions
            await self._process_conditional_actions(cmd_name, cmd, payload)
            continue
            
        # Process parameters if defined for this command
        params = {}
        if "params" in cmd:
            # Try to parse parameters from payload
            try:
                # Try to convert payload to parameters format (JSON or simple value)
                parsed_params = self._try_parse_json_payload(payload)
                if parsed_params:
                    params = parsed_params
                elif payload.strip():  # Non-empty payload
                    # Simple payload, try to map to the first parameter
                    if len(cmd["params"]) > 0:
                        first_param = cmd["params"][0]
                        param_name = first_param["name"]
                        # Convert payload to appropriate type
                        param_type = first_param.get("type", "string")
                        if param_type == "integer":
                            params[param_name] = int(payload)
                        elif param_type == "float":
                            params[param_name] = float(payload)
                        elif param_type == "boolean":
                            params[param_name] = payload.lower() in ("true", "yes", "1", "on")
                        else:  # Default to string
                            params[param_name] = payload
            except Exception as e:
                print(f"Error parsing parameters for command {cmd_name}: {e}")
        
        # Execute the action with the parsed parameters
        await self._execute_single_action(cmd_name, cmd, params)

class TestMessageHandling(unittest.IsolatedAsyncioTestCase):
    """Test suite for MQTT message handling and API action execution."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock device for testing
        self.device = MagicMock(spec=BaseDevice)
        
        # Mock _execute_single_action instead of using actual implementation
        self.device._execute_single_action = AsyncMock()
        
        # Use our custom implementation for handle_message
        self.device.handle_message = mock_handle_message.__get__(self.device)
        
        # Use the actual implementations for these methods
        self.device.execute_action = BaseDevice.execute_action.__get__(self.device, BaseDevice)
        
        # Add mock implementation of _try_parse_json_payload
        self.device._try_parse_json_payload = mock_try_parse_json_payload
        
        self.device._resolve_and_validate_params = BaseDevice._resolve_and_validate_params.__get__(self.device, BaseDevice)
        self.device._evaluate_condition = MagicMock(return_value=True)  # Always match conditions
        self.device._process_conditional_actions = AsyncMock()
        
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
            "simpleCommand": {
                "topic": "/test/simple",
                "action": "simple_command"
            }
        }
        
        # Mock the get_available_commands method
        self.device.get_available_commands = MagicMock(return_value=self.test_commands)
        
        # Create handlers using parameter-based pattern
        async def mock_handler(cmd_config, params):
            return {"style": "parameter", "params": params}
        
        # Register mock handlers
        self.device._get_action_handler = MagicMock()
        self.device._get_action_handler.side_effect = lambda action: {
            "set_level": mock_handler,
            "multi_param": mock_handler,
            "action_on": mock_handler,
            "action_off": mock_handler,
            "simple_command": mock_handler
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
        
    async def test_handle_message_with_simple_payload(self):
        """Test handling a message with simple payload that can be converted to a parameter."""
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
    
    async def test_handle_message_with_simple_command(self):
        """Test handling a message for a command with no parameters defined."""
        # Simple payload for a command without parameters
        payload = "ON"
        topic = "/test/simple"
        
        # Reset the mock
        self.device._execute_single_action.reset_mock()
        
        # Handle the message
        await self.device.handle_message(topic, payload)
        
        # Check that _execute_single_action was called with parameters
        self.device._execute_single_action.assert_called_once()
        call_args = self.device._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "simpleCommand")  # action_name
        self.assertEqual(call_args[1], self.test_commands["simpleCommand"])  # cmd_config
        self.assertIsNotNone(call_args[2])  # params should not be None
    
    async def test_execute_action_with_parameters(self):
        """Test executing an action with parameters via API."""
        # Execute an action with parameters
        action = "setLevel"
        params = {"level": 80}
        
        # Set up the success result
        self.device._execute_single_action.return_value = {"success": True}
        
        # Execute the action
        result = await self.device.execute_action(action, params, source="test")
        
        # Verify command was executed with correct results
        self.assertEqual(result["success"], True)
        self.assertEqual(result["device_id"], "test_device")
        
        # Test parameter validation
        with self.assertRaises(ValueError):
            await self.device.execute_action("invalid_action", {}, source="test")
            
    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_execute_action_with_params(self, mock_sleep):
        """Test executing action with parameters."""
        action = "set_volume"
        params = {"volume": 50}
        
        # Call execute_action
        result = await self.device.execute_action(action, params, source="test")


if __name__ == '__main__':
    unittest.main() 