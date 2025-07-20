import unittest
import sys
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os

# Add parent directory to path to allow importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wb_mqtt_bridge.infrastructure.devices.lg_tv.driver import LgTv
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from tests.test_helpers import wrap_device_init

# Wrap the LgTv class to handle dictionary configs
wrap_device_init(LgTv)

class TestLgTvParameters(unittest.IsolatedAsyncioTestCase):
    """Test suite for LG TV device parameter handling."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock configuration
        self.config = {
            "device_id": "test_lg_tv",
            "device_name": "Test LG TV",
            "device_type": "lg_tv",
            "tv": {
                "ip_address": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55",
                "client_key": "test_key",
                "secure": False
            },
            "commands": {
                "power_on": {
                    "action": "power_on",
                    "topic": "/test/lg_tv/power_on"
                },
                "power_off": {
                    "action": "power_off",
                    "topic": "/test/lg_tv/power_off"
                },
                "set_volume": {
                    "action": "set_volume",
                    "topic": "/test/lg_tv/set_volume",
                    "params": [
                        {"name": "level", "type": "range", "min": 0, "max": 100, "required": True}
                    ]
                },
                "mute": {
                    "action": "mute",
                    "topic": "/test/lg_tv/mute",
                    "params": [
                        {"name": "state", "type": "boolean", "required": False}
                    ]
                },
                "move_cursor": {
                    "action": "move_cursor",
                    "topic": "/test/lg_tv/move_cursor",
                    "params": [
                        {"name": "x", "type": "range", "min": 0, "max": 100, "required": True},
                        {"name": "y", "type": "range", "min": 0, "max": 100, "required": True}
                    ]
                },
                "launch_app": {
                    "action": "launch_app",
                    "topic": "/test/lg_tv/launch_app",
                    "params": [
                        {"name": "app_id", "type": "string", "required": True}
                    ]
                }
            }
        }
        
        # Create mock objects
        self.mqtt_client = MagicMock()
        
        # Setup LG TV device with mocks
        with patch('wb_mqtt_bridge.infrastructure.devices.lg_tv.driver.WebOSTV'), patch('wb_mqtt_bridge.infrastructure.devices.lg_tv.driver.SecureWebOSTV'):
            self.lg_tv = LgTv(self.config, self.mqtt_client)
            
        # Mock methods to avoid actual network operations
        self.lg_tv.power_on = AsyncMock(return_value=True)
        self.lg_tv.power_off = AsyncMock(return_value=True)
        self.lg_tv._execute_media_command = AsyncMock(return_value=True)
        self.lg_tv._execute_pointer_command = AsyncMock(return_value=True)
        self.lg_tv._execute_input_command = AsyncMock(return_value=True)
        self.lg_tv.update_state = AsyncMock()
        self.lg_tv._update_last_command = AsyncMock()
        self.lg_tv.app = MagicMock()
        self.lg_tv.app.launch = AsyncMock(return_value={"returnValue": True})
        self.lg_tv._find_app_by_name_or_id = MagicMock(return_value={"id": "test_app_id", "title": "Test App"})
        self.lg_tv._get_available_apps_internal = AsyncMock(return_value=[{"id": "test_app_id", "title": "Test App"}])
        self.lg_tv.state = {"connected": True}
        self.lg_tv.client = MagicMock()  # Mock client for connection check
        
        # For message testing, we need to use the original handle_message but
        # mock _execute_single_action to avoid actual execution
        self.lg_tv.handle_message = BaseDevice.handle_message.__get__(self.lg_tv, BaseDevice)
        self.lg_tv._execute_single_action = AsyncMock()
        self.lg_tv.get_available_commands = MagicMock(return_value=self.config["commands"])
        
    async def test_handle_power_on(self):
        """Test power_on handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["power_on"]
        params = {}
        
        # Call the handler
        result = await self.lg_tv.handle_power_on(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv.power_on.assert_called_once()
    
    async def test_handle_power_off(self):
        """Test power_off handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["power_off"]
        params = {}
        
        # Call the handler
        result = await self.lg_tv.handle_power_off(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv.power_off.assert_called_once()
    
    async def test_handle_set_volume(self):
        """Test set_volume handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["set_volume"]
        params = {"level": 75}
        
        # Call the handler
        result = await self.lg_tv.handle_set_volume(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv._execute_media_command.assert_called_once()
        
        # Check the parameters passed to _execute_media_command
        call_args = self.lg_tv._execute_media_command.call_args[1]
        self.assertEqual(call_args["params"]["level"], 75)

    async def test_handle_mute(self):
        """Test mute handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["mute"]
        
        # Test with explicit state parameter
        params = {"state": True}
        result = await self.lg_tv.handle_mute(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv._execute_media_command.assert_called_once()
        
        # Check the parameters passed to _execute_media_command
        call_args = self.lg_tv._execute_media_command.call_args[1]
        self.assertEqual(call_args["params"]["state"], True)
        
        # Reset mocks
        self.lg_tv._execute_media_command.reset_mock()
        
        # Test without state parameter (should toggle)
        params = {}
        result = await self.lg_tv.handle_mute(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv._execute_media_command.assert_called_once()
        
        # Check the parameters passed to _execute_media_command
        call_args = self.lg_tv._execute_media_command.call_args[1]
        self.assertEqual(call_args["params"], {})

    async def test_handle_move_cursor(self):
        """Test move_cursor handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["move_cursor"]
        params = {"x": 40, "y": 60}
        
        # Call the handler
        result = await self.lg_tv.handle_move_cursor(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv._execute_pointer_command.assert_called_once()
        
        # Check the parameters passed to _execute_pointer_command
        call_args = self.lg_tv._execute_pointer_command.call_args[1]
        self.assertEqual(call_args["params"]["x"], 40)
        self.assertEqual(call_args["params"]["y"], 60)
        self.assertEqual(call_args["params"]["drag"], False)

    async def test_handle_launch_app(self):
        """Test launch_app handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["launch_app"]
        params = {"app_id": "netflix"}
        
        # Call the handler
        result = await self.lg_tv.handle_launch_app(cmd_config, params)
        
        # Verify the result
        self.assertTrue(result)
        self.lg_tv._get_available_apps_internal.assert_called_once()
        self.lg_tv._find_app_by_name_or_id.assert_called_once()
        self.lg_tv.app.launch.assert_called_once()
        
        # Check the parameters passed to app.launch
        call_args = self.lg_tv.app.launch.call_args[0]
        self.assertEqual(call_args[0], "test_app_id")

    async def test_handle_launch_app_missing_parameter(self):
        """Test launch_app handler with missing required parameter."""
        # Create command config and params
        cmd_config = self.config["commands"]["launch_app"]
        params = {}  # Missing required app_id
        
        # Call the handler
        result = await self.lg_tv.handle_launch_app(cmd_config, params)
        
        # Verify the result (should fail)
        self.assertFalse(result)
        self.lg_tv._get_available_apps_internal.assert_not_called()
        
    async def test_handle_button_commands(self):
        """Test button command handlers with parameters."""
        # Create a list of button commands to test
        button_commands = [
            ("home", "home"), 
            ("back", "back"),
            ("up", "up"),
            ("down", "down"),
            ("left", "left"),
            ("right", "right"),
            ("enter", "enter"),
            ("exit", "exit"),
            ("menu", "menu"),
            ("settings", "settings")
        ]
        
        for action, method_name in button_commands:
            # Create a mock command config
            cmd_config = {"action": action}
            params = {}
            
            # Get the handler method
            handler_method = getattr(self.lg_tv, f"handle_{action}")
            
            # Reset the mock
            self.lg_tv._execute_input_command.reset_mock()
            
            # Call the handler
            result = await handler_method(cmd_config, params)
            
            # Verify the result
            self.assertTrue(result, f"Handler for {action} failed")
            self.lg_tv._execute_input_command.assert_called_once_with(action, method_name)

    async def test_handle_media_commands(self):
        """Test media playback command handlers with parameters."""
        # Create a list of media commands to test
        media_commands = [
            ("play", "play"),
            ("pause", "pause"),
            ("stop", "stop"),
            ("rewind_forward", "rewind_forward"),
            ("rewind_backward", "rewind_backward")
        ]
        
        for action, method_name in media_commands:
            # Create a mock command config
            cmd_config = {"action": action}
            params = {}
            
            # Get the handler method
            handler_method = getattr(self.lg_tv, f"handle_{action}")
            
            # Reset the mock
            self.lg_tv._execute_media_command.reset_mock()
            
            # Call the handler
            result = await handler_method(cmd_config, params)
            
            # Verify the result
            self.assertTrue(result, f"Handler for {action} failed")
            
            # For these simple media commands, the first arg is action_name and second is media_method_name
            self.lg_tv._execute_media_command.assert_called_once()
            call_args = self.lg_tv._execute_media_command.call_args[0]
            
            # The action name should match the handler name
            expected_action = action
            expected_method = method_name
            
            self.assertEqual(call_args[0], expected_action)
            self.assertEqual(call_args[1], expected_method)

    async def test_handle_volume_controls(self):
        """Test volume control handlers with parameters."""
        # Test volume_up
        cmd_config = {"action": "volume_up"}
        params = {}
        
        result = await self.lg_tv.handle_volume_up(cmd_config, params)
        self.assertTrue(result)
        self.lg_tv._execute_media_command.assert_called_once_with(
            action_name="volume_up",
            media_method_name="volume_up",
            update_volume_after=True
        )
        
        # Reset mock
        self.lg_tv._execute_media_command.reset_mock()
        
        # Test volume_down
        cmd_config = {"action": "volume_down"}
        params = {}
        
        result = await self.lg_tv.handle_volume_down(cmd_config, params)
        self.assertTrue(result)
        self.lg_tv._execute_media_command.assert_called_once_with(
            action_name="volume_down",
            media_method_name="volume_down",
            update_volume_after=True
        )

    @patch.object(BaseDevice, '_resolve_and_validate_params')
    async def test_handle_message_json_payload(self, mock_validate):
        """Test message handling with JSON payload for parameterized commands."""
        # Setup mocks for parameter validation
        mock_validate.return_value = {"level": 80}
        
        # Create a separate handler mock that we'll check
        original_handler = self.lg_tv.handle_set_volume
        self.lg_tv.handle_set_volume = AsyncMock(return_value=True)
        
        # Create a command message with JSON payload
        topic = self.config["commands"]["set_volume"]["topic"]
        payload = json.dumps({"level": 80})
        
        # Mock the _get_action_handler method to return our mocked handler
        self.lg_tv._get_action_handler = MagicMock(return_value=self.lg_tv.handle_set_volume)
        
        # Handle the message
        await self.lg_tv.handle_message(topic, payload)
        
        # Verify that _execute_single_action was called with correct command name
        self.lg_tv._execute_single_action.assert_called_once()
        call_args = self.lg_tv._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "set_volume")  # action name
        self.assertEqual(call_args[1], self.config["commands"]["set_volume"])  # cmd_config
        
        # Restore original handler
        self.lg_tv.handle_set_volume = original_handler

    @patch.object(BaseDevice, '_resolve_and_validate_params')
    async def test_handle_message_simple_payload(self, mock_validate):
        """Test message handling with simple numeric payload for parameterized commands."""
        # Setup mocks for parameter validation
        mock_validate.return_value = {"level": 65}
        
        # Create a separate handler mock that we'll check
        original_handler = self.lg_tv.handle_set_volume
        self.lg_tv.handle_set_volume = AsyncMock(return_value=True)
        
        # Create a command message with raw payload
        topic = self.config["commands"]["set_volume"]["topic"]
        payload = "65"  # Simple numeric payload
        
        # Mock the _get_action_handler method to return our mocked handler
        self.lg_tv._get_action_handler = MagicMock(return_value=self.lg_tv.handle_set_volume)
        
        # Handle the message
        await self.lg_tv.handle_message(topic, payload)
        
        # Verify that _execute_single_action was called with correct command name
        self.lg_tv._execute_single_action.assert_called_once()
        call_args = self.lg_tv._execute_single_action.call_args[0]
        self.assertEqual(call_args[0], "set_volume")  # action name
        self.assertEqual(call_args[1], self.config["commands"]["set_volume"])  # cmd_config
        self.assertIsNotNone(call_args[2])  # params should not be None
        
        # Restore original handler
        self.lg_tv.handle_set_volume = original_handler

class TestLgTvPointerCommands(unittest.TestCase):
    """Test pointer command handling in the LG TV device."""

    def setUp(self):
        """Set up test environment before each test."""
        # Mock config for test TV
        self.config = {
            "device_id": "test_tv",
            "device_name": "Test TV",
            "commands": {
                "move_cursor": {
                    "action": "move_cursor",
                    "topic": "/devices/tv/cursor/move",
                    "params": [
                        {"name": "x", "type": "float", "required": True},
                        {"name": "y", "type": "float", "required": True},
                        {"name": "drag", "type": "boolean", "required": False, "default": False}
                    ]
                },
                "move_cursor_relative": {
                    "action": "move_cursor_relative",
                    "topic": "/devices/tv/cursor/move_relative",
                    "params": [
                        {"name": "dx", "type": "float", "required": True},
                        {"name": "dy", "type": "float", "required": True},
                        {"name": "drag", "type": "boolean", "required": False, "default": False}
                    ]
                },
                "click": {
                    "action": "click",
                    "topic": "/devices/tv/cursor/click",
                    "params": [
                        {"name": "x", "type": "float", "required": False},
                        {"name": "y", "type": "float", "required": False},
                        {"name": "drag", "type": "boolean", "required": False, "default": False}
                    ]
                }
            }
        }
        
        # Create TV instance with mocked client
        self.lg_tv = LgTv(self.config)
        self.lg_tv.client = Mock()
        self.lg_tv.input_control = Mock()
        self.lg_tv.input_control.move = AsyncMock(return_value=True)
        self.lg_tv.input_control.click = AsyncMock(return_value=True)
        
        # Mock state as a dictionary instead of trying to use non-existent attributes
        # This matches how the LgTv class actually stores pointer state
        self.lg_tv.state = Mock()
        self.lg_tv.state.connected = True
        
        # Store pointer state as a separate property to mimic real implementation
        self._pointer_x = 0.5
        self._pointer_y = 0.5
        
        # Mock _update_last_command
        self.lg_tv._update_last_command = AsyncMock()
    
    @pytest.mark.asyncio
    async def test_move_cursor(self):
        """Test move_cursor handler with valid parameters."""
        # Set up test parameters
        cmd_config = self.config["commands"]["move_cursor"]
        params = {"x": 0.75, "y": 0.25, "drag": True}
        
        # Call handler
        result = await self.lg_tv.handle_move_cursor(cmd_config, params)
        
        # Verify result
        self.assertTrue(result)
        self.lg_tv.input_control.move.assert_called_once_with(x=0.75, y=0.25, drag=True)
        self.lg_tv._update_last_command.assert_called_once()
        
        # Check that input_control.move was called with correctly calculated coordinates
        call_args = self.lg_tv.input_control.move.call_args[1]
        self.assertAlmostEqual(call_args["x"], 0.55, places=2)  # 0.5 + (5/100) = 0.55
        self.assertAlmostEqual(call_args["y"], 0.4, places=2)   # 0.5 + (-10/100) = 0.4
        self.assertEqual(call_args["drag"], True)
        
        # Update our local pointer state to match what we expect
        self._pointer_x = 0.55
        self._pointer_y = 0.4
        
    @pytest.mark.asyncio
    async def test_move_cursor_missing_params(self):
        """Test move_cursor handler with missing parameters."""
        # Set up test with missing y parameter
        cmd_config = self.config["commands"]["move_cursor"]
        params = {"x": 0.75}
        
        # Call handler
        result = await self.lg_tv.handle_move_cursor(cmd_config, params)
        
        # Verify result - should fail due to missing y parameter
        self.assertFalse(result)
        self.lg_tv.input_control.move.assert_not_called()
        
    @pytest.mark.asyncio
    async def test_move_cursor_relative(self):
        """Test move_cursor_relative handler with valid parameters."""
        # Set up test parameters
        cmd_config = self.config["commands"]["move_cursor_relative"]
        params = {"dx": 5, "dy": -10, "drag": True}
        
        # Call handler
        result = await self.lg_tv.handle_move_cursor_relative(cmd_config, params)
        
        # Verify result
        self.assertTrue(result)
        
        # Check that input_control.move was called with correctly calculated coordinates
        call_args = self.lg_tv.input_control.move.call_args[1]
        self.assertAlmostEqual(call_args["x"], 0.55, places=2)  # 0.5 + (5/100) = 0.55
        self.assertAlmostEqual(call_args["y"], 0.4, places=2)   # 0.5 + (-10/100) = 0.4
        self.assertEqual(call_args["drag"], True)
        
        # Update our local pointer state to match what we expect
        self._pointer_x = 0.55
        self._pointer_y = 0.4
        
    @pytest.mark.asyncio
    async def test_click_with_coordinates(self):
        """Test click handler with specific coordinates."""
        # Set up test parameters
        cmd_config = self.config["commands"]["click"]
        params = {"x": 0.3, "y": 0.7}
        
        # Call handler
        result = await self.lg_tv.handle_click(cmd_config, params)
        
        # Verify result
        self.assertTrue(result)
        self.lg_tv.input_control.click.assert_called_once_with(x=0.3, y=0.7, drag=False)
        
    @pytest.mark.asyncio
    async def test_click_without_coordinates(self):
        """Test click handler without coordinates (clicks at current position)."""
        # Set up test parameters
        cmd_config = self.config["commands"]["click"]
        params = {}
        
        # Call handler
        result = await self.lg_tv.handle_click(cmd_config, params)
        
        # Verify result
        self.assertTrue(result)
        self.lg_tv.input_control.click.assert_called_once_with()

if __name__ == '__main__':
    unittest.main() 