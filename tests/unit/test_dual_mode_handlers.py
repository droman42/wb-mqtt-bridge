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

class TestParameterHandlers(unittest.IsolatedAsyncioTestCase):
    """Test suite for parameter-based handler functionality."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock device for testing
        self.device = MagicMock(spec=BaseDevice)
        
        # Use the actual implementations for the methods under test
        self.device._execute_single_action = BaseDevice._execute_single_action.__get__(self.device, BaseDevice)
        self.device._call_action_handler = BaseDevice._call_action_handler.__get__(self.device, BaseDevice)
        self.device._try_parse_json_payload = BaseDevice._try_parse_json_payload.__get__(self.device, BaseDevice)
        self.device._resolve_and_validate_params = BaseDevice._resolve_and_validate_params.__get__(self.device, BaseDevice)
        
        # Mock the update_state method
        self.device.update_state = AsyncMock()
        
    async def test_execute_single_action_with_params(self):
        """Test executing an action with parameters."""
        # Mock handler that expects parameters
        async def mock_handler(cmd_config, params):
            return {"status": "success", "params_received": params}
        
        # Set up the device with the mock handler
        self.device._get_action_handler.return_value = mock_handler
        
        # Command config with parameters
        cmd_config = {
            "params": [
                {"name": "level", "type": "integer", "required": True}
            ]
        }
        
        # Parameters to pass to the action
        params = {"level": 50}
        
        # Execute the action
        result = await self.device._execute_single_action("test_action", cmd_config, params)
        
        # Check that the handler was called with the correct parameters
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["params_received"], params)
        
        # Check that update_state was called with the correct LastCommand
        self.device.update_state.assert_called_once()
        call_args = self.device.update_state.call_args[0][0]
        self.assertIn("last_command", call_args)
        last_command = call_args["last_command"]
        self.assertEqual(last_command.action, "test_action")
        self.assertEqual(last_command.params, params)
    
    async def test_call_action_handler_with_parameter_handler(self):
        """Test calling a parameter-based handler."""
        # Define a parameter-based handler
        async def parameter_handler(self, cmd_config: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
            return {"style": "parameter", "params": params}
        
        # Call the handler
        result = await self.device._call_action_handler(
            parameter_handler.__get__(self.device, BaseDevice),
            cmd_config={"test": "config"},
            params={"test": "params"}
        )
        
        # Check that the result contains the params
        self.assertEqual(result["style"], "parameter")
        self.assertEqual(result["params"], {"test": "params"})
    
    def test_try_parse_json_payload_with_valid_json(self):
        """Test parsing a valid JSON payload."""
        payload = '{"level": 50, "color": "red"}'
        result = self.device._try_parse_json_payload(payload)
        
        # Check that the result is a dict with the expected values
        self.assertIsInstance(result, dict)
        self.assertEqual(result["level"], 50)
        self.assertEqual(result["color"], "red")
    
    def test_try_parse_json_payload_with_invalid_json(self):
        """Test parsing an invalid JSON payload."""
        payload = "not_json"
        result = self.device._try_parse_json_payload(payload)
        
        # Check that the result is None
        self.assertIsNone(result)
    
    def test_try_parse_json_payload_with_non_dict_json(self):
        """Test parsing JSON that's not an object."""
        payload = '[1, 2, 3]'  # JSON array, not object
        result = self.device._try_parse_json_payload(payload)
        
        # Check that the result is None since it's not a dict
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main() 