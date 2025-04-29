import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json
import asyncio
from typing import Dict, Any

# Add parent directory to path to allow importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from devices.example_device import ExampleDevice
from devices.base_device import BaseDevice

class TestExampleDeviceParameters(unittest.IsolatedAsyncioTestCase):
    """Test suite for Example device parameter handling."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock configuration
        self.config = {
            "device_id": "test_example",
            "device_name": "Test Example Device",
            "device_type": "example",
            "commands": {
                "power_on": {
                    "action": "power_on",
                    "topic": "/test/example/power_on",
                    "params": [
                        {"name": "delay", "type": "integer", "required": False, "default": 0}
                    ]
                },
                "power_off": {
                    "action": "power_off",
                    "topic": "/test/example/power_off",
                    "params": [
                        {"name": "delay", "type": "integer", "required": False, "default": 0}
                    ]
                },
                "set_temperature": {
                    "action": "set_temperature",
                    "topic": "/test/example/set_temperature",
                    "params": [
                        {"name": "temperature", "type": "range", "min": 10, "max": 30, "required": True},
                        {"name": "mode", "type": "string", "required": False, "default": "auto"}
                    ]
                },
                "set_brightness": {
                    "action": "set_brightness",
                    "topic": "/test/example/set_brightness",
                    "params": [
                        {"name": "level", "type": "range", "min": 0, "max": 100, "required": True},
                        {"name": "transition", "type": "integer", "required": False, "default": 0}
                    ]
                },
                "get_data": {
                    "action": "getData",
                    "topic": "/test/example/get_data",
                    "params": [
                        {"name": "filter", "type": "string", "required": False}
                    ]
                }
            }
        }
        
        # Create mock objects
        self.mqtt_client = MagicMock()
        
        # Setup Example device with mocks
        self.example_device = ExampleDevice(self.config)
        
        # Mock the asyncio.sleep function
        self.original_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        
        # For message testing, we need to use the original handle_message but
        # mock _execute_single_action to avoid actual execution
        self.example_device.handle_message = BaseDevice.handle_message.__get__(self.example_device, BaseDevice)
        self.example_device._execute_single_action = AsyncMock()
        self.example_device.get_available_commands = MagicMock(return_value=self.config["commands"])
        
    def tearDown(self):
        """Clean up after tests."""
        # Restore the original sleep function
        asyncio.sleep = self.original_sleep
        
    async def test_handle_power_on_with_delay(self):
        """Test power_on handler with delay parameter."""
        # Create command config and params
        cmd_config = self.config["commands"]["power_on"]
        params = {"delay": 5}
        
        # Call the handler
        await self.example_device.handle_power_on(cmd_config, params)
        
        # Verify the result
        asyncio.sleep.assert_called_once_with(5)
        self.assertEqual(self.example_device.state["power"], "on")
    
    async def test_handle_power_off_without_delay(self):
        """Test power_off handler without delay."""
        # Create command config and params
        cmd_config = self.config["commands"]["power_off"]
        params = {}  # No delay specified, should use default
        
        # Call the handler
        await self.example_device.handle_power_off(cmd_config, params)
        
        # Verify the result
        asyncio.sleep.assert_not_called()
        self.assertEqual(self.example_device.state["power"], "off")
    
    async def test_handle_set_temperature(self):
        """Test set_temperature handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["set_temperature"]
        params = {"temperature": 25, "mode": "heat"}
        
        # Call the handler
        await self.example_device.handle_set_temperature(cmd_config, params)
        
        # Verify the result
        self.assertEqual(self.example_device.state["temperature"], 25)
        self.assertEqual(self.example_device.state["mode"], "heat")
    
    async def test_handle_set_temperature_missing_required(self):
        """Test set_temperature handler with missing required parameter."""
        # Create command config and params
        cmd_config = self.config["commands"]["set_temperature"]
        params = {"mode": "cool"}  # Missing required temperature
        
        # Call the handler
        result = await self.example_device.handle_set_temperature(cmd_config, params)
        
        # Verify the result
        self.assertFalse(result)
        
    async def test_handle_set_brightness_with_transition(self):
        """Test set_brightness handler with transition parameter."""
        # Create command config and params
        cmd_config = self.config["commands"]["set_brightness"]
        params = {"level": 75, "transition": 3}
        
        # Set initial brightness
        self.example_device.state["brightness"] = 25
        
        # Call the handler
        await self.example_device.handle_set_brightness(cmd_config, params)
        
        # Verify the result
        # Should call sleep 3 times (for transition)
        self.assertEqual(asyncio.sleep.call_count, 3)
        self.assertEqual(self.example_device.state["brightness"], 75)
    
    async def test_handle_get_data_with_filter(self):
        """Test get_data handler with filter parameter."""
        # Create command config and params
        cmd_config = self.config["commands"]["get_data"]
        params = {"filter": "power,temperature"}
        
        # Set some state values
        self.example_device.state["power"] = "on"
        self.example_device.state["temperature"] = 22
        self.example_device.state["brightness"] = 80
        
        # Call the handler
        result = await self.example_device.handle_get_data(cmd_config, params)
        
        # Verify the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result["power"], "on")
        self.assertEqual(result["temperature"], 22)
        self.assertNotIn("brightness", result)
    
    async def test_handle_get_data_without_filter(self):
        """Test get_data handler without filter parameter."""
        # Create command config and params
        cmd_config = self.config["commands"]["get_data"]
        params = {}  # No filter specified
        
        # Call the handler
        result = await self.example_device.handle_get_data(cmd_config, params)
        
        # Verify the result
        self.assertIn("power", result)
        self.assertIn("temperature", result)
        self.assertIn("brightness", result)
        self.assertIn("update_interval", result)
        self.assertIn("threshold", result)
        
    @patch.object(BaseDevice, '_resolve_and_validate_params')
    async def test_handle_message_with_parameters(self, mock_validate):
        """Test message handling with parameters via MQTT."""
        # Setup mocks for parameter validation
        mock_validate.return_value = {"temperature": 23, "mode": "cool"}
        
        # Create a separate handler mock that we'll check
        original_handler = self.example_device.handle_set_temperature
        self.example_device.handle_set_temperature = AsyncMock()
        
        try:
            # Create a command message
            topic = self.config["commands"]["set_temperature"]["topic"]
            payload = json.dumps({"temperature": 23, "mode": "cool"})
            
            # Handle the message
            await self.example_device.handle_message(topic, payload)
            
            # Verify that _execute_single_action was called with correct action name
            self.example_device._execute_single_action.assert_called_once()
            call_args = self.example_device._execute_single_action.call_args[0]
            self.assertEqual(call_args[0], "set_temperature")  # action name
            
        finally:
            # Restore original handler
            self.example_device.handle_set_temperature = original_handler

if __name__ == "__main__":
    unittest.main() 