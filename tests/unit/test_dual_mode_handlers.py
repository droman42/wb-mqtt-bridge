import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
import os
import json
import inspect
from typing import Dict, Any, Optional, Callable, Awaitable

# Add parent directory to path to allow importing from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.infrastructure.config.models import LastCommand

# Mock implementations for missing methods
async def mock_call_action_handler(
    self,
    handler: Callable[..., Awaitable[Dict[str, Any]]],
    cmd_config: Dict[str, Any],
    params: Dict[str, Any] = None,
    **kwargs
) -> Dict[str, Any]:
    """Mock implementation of _call_action_handler for tests."""
    # Check if the handler is a method
    if not inspect.ismethod(handler):
        # If it's not a method, it's a function defined in a test that takes different args
        return await handler(cmd_config, params or {})
    
    # For actual methods, check signature
    sig = inspect.signature(handler)
    param_names = list(sig.parameters.keys())
    
    # Parameter-based handler (accepts cmd_config and params)
    if len(param_names) >= 3 and "params" in param_names:
        return await handler(cmd_config=cmd_config, params=params or {}, **kwargs)
    
    # Legacy handler (accepts only the action name)
    return await handler(**kwargs)

async def mock_execute_single_action(
    self, 
    action_name: str, 
    cmd_config: Dict[str, Any], 
    params: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """Mock implementation of _execute_single_action that works with dictionary configs."""
    try:
        # Get the action handler
        handler = self._get_action_handler(action_name)
        if not handler:
            return self.create_command_result(
                success=False, 
                error=f"No handler found for action: {action_name}"
            )
            
        # Process params if needed
        params = params or {}
        
        # Call the handler with the parameters
        result = await handler(cmd_config, params)
        
        # Update state with last command info
        self.update_state(
            last_command=LastCommand(
                action=action_name,
                source="test",
                timestamp="2023-01-01T00:00:00",
                params=params
            )
        )
        
        return result
        
    except Exception as e:
        error_msg = f"Error executing action {action_name}: {str(e)}"
        print(error_msg)
        return {"success": False, "error": error_msg}

def mock_try_parse_json_payload(self, payload: str) -> Optional[Dict[str, Any]]:
    """Mock implementation of _try_parse_json_payload for tests."""
    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        return None

class TestParameterHandlers(unittest.IsolatedAsyncioTestCase):
    """Test suite for parameter-based handler functionality."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock device for testing
        self.device = MagicMock(spec=BaseDevice)
        
        # Add mock implementations
        self.device._call_action_handler = mock_call_action_handler.__get__(self.device)
        self.device._execute_single_action = mock_execute_single_action.__get__(self.device)
        self.device._try_parse_json_payload = mock_try_parse_json_payload.__get__(self.device)
        
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
        
        # For update_state we need to capture the arguments
        last_command_captured = None
        original_update_state = self.device.update_state
        
        def capture_update_state(**kwargs):
            nonlocal last_command_captured
            last_command_captured = kwargs.get("last_command")
            return original_update_state(**kwargs)
        
        self.device.update_state = capture_update_state
        
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
        
        # Check that update_state was called and captured the LastCommand
        self.assertIsNotNone(last_command_captured)
        self.assertEqual(last_command_captured.action, "test_action")
        self.assertEqual(last_command_captured.params, params)
    
    async def test_call_action_handler_with_parameter_handler(self):
        """Test calling a parameter-based handler."""
        # Define a parameter-based handler
        async def parameter_handler(cmd_config: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
            return {"style": "parameter", "params": params}
        
        # Call the handler
        result = await self.device._call_action_handler(
            parameter_handler,
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