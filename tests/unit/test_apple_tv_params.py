import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json
from typing import Dict, Any, Optional
import asyncio

# Add parent directory to path to allow importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from devices.apple_tv_device import AppleTVDevice
from devices.base_device import BaseDevice
from app.schemas import LastCommand
from pyatv.const import PowerState
from pyatv.interface import Playing

class TestAppleTVParameters(unittest.IsolatedAsyncioTestCase):
    """Test suite for AppleTV device parameter handling."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock configuration
        self.config = {
            "device_id": "test_appletv",
            "device_name": "Test Apple TV",
            "device_type": "apple_tv_device",
            "apple_tv": {
                "ip_address": "192.168.1.100",
                "name": "Test AppleTV",
                "protocols": {
                    "Companion": {
                        "identifier": None,
                        "credentials": "test_credentials",
                        "data": None
                    }
                }
            },
            "commands": {
                "power_on": {
                    "action": "power_on",
                    "topic": "/test/appletv/power_on",
                    "description": "Power On",
                    "group": "power"
                },
                "power_off": {
                    "action": "power_off",
                    "topic": "/test/appletv/power_off",
                    "description": "Power Off",
                    "group": "power"
                },
                "set_volume": {
                    "action": "set_volume",
                    "topic": "/test/appletv/set_volume",
                    "description": "Set Volume",
                    "group": "volume",
                    "params": [
                        {"name": "level", "type": "range", "min": 0, "max": 100, "required": True, "description": "Volume level (0-100)"}
                    ]
                },
                "launch_app": {
                    "action": "launch_app",
                    "topic": "/test/appletv/launch_app",
                    "description": "Launch App",
                    "group": "apps",
                    "params": [
                        {"name": "app", "type": "string", "required": True, "description": "App name to launch"}
                    ]
                }
            }
        }
        
        # Create mock objects
        self.mqtt_client = MagicMock()
        self.mock_loop = MagicMock()
        
        # Create mocks for pyatv components
        self.mock_atv = MagicMock()
        self.mock_atv_config = MagicMock()
        
        # Create mocks for pyatv interfaces
        self.mock_power = MagicMock()
        self.mock_remote_control = MagicMock()
        self.mock_audio = MagicMock()
        self.mock_apps = MagicMock()
        self.mock_metadata = MagicMock()
        
        # Configure mocks
        self.mock_atv.power = self.mock_power
        self.mock_atv.remote_control = self.mock_remote_control
        self.mock_atv.audio = self.mock_audio
        self.mock_atv.apps = self.mock_apps
        self.mock_atv.metadata = self.mock_metadata
        
        # Mock common methods
        self.mock_audio.set_volume = AsyncMock()
        self.mock_audio.volume = AsyncMock(return_value=0.5)  # 50% volume
        self.mock_apps.launch_app = AsyncMock()
        self.mock_apps.app_list = AsyncMock(return_value=[
            MagicMock(name="YouTube", identifier="com.google.youtube"),
            MagicMock(name="Netflix", identifier="com.netflix.Netflix")
        ])
        self.mock_apps.current_app = AsyncMock(return_value=MagicMock(name="YouTube"))
        self.mock_power.turn_on = AsyncMock()
        self.mock_power.turn_off = AsyncMock()
        self.mock_power.power_state = PowerState.On
        
        # Mock Playing instance for metadata
        self.mock_playing = MagicMock(spec=Playing)
        self.mock_playing.device_state = MagicMock(name="idle")
        self.mock_metadata.playing = AsyncMock(return_value=self.mock_playing)
        
        # Setup AppleTV device with mocks
        with patch('devices.apple_tv_device.asyncio.get_event_loop', return_value=self.mock_loop):
            self.appletv = AppleTVDevice(self.config, self.mqtt_client)
            
        # Replace instance variables with mocks
        self.appletv.loop = self.mock_loop
        self.appletv.atv = self.mock_atv
        self.appletv.atv_config = self.mock_atv_config
        self.appletv.state.connected = True
        self.appletv.state.power = "on"
        
        # Mock internal methods to avoid network operations
        self.appletv.publish_state = AsyncMock()
        self.appletv._delayed_refresh = AsyncMock()
        self.appletv._ensure_connected = AsyncMock(return_value=True)
        
        # For message testing, use the original handle_message but mock executions
        self.appletv.handle_message = BaseDevice.handle_message.__get__(self.appletv, BaseDevice)
        self.appletv._execute_single_action = AsyncMock()
        self.appletv.get_available_commands = MagicMock(return_value=self.config["commands"])
        
    async def test_set_volume_with_parameters(self):
        """Test set_volume handler with parameters."""
        # Create command config and params
        cmd_config = self.config["commands"]["set_volume"]
        params = {"level": 75}
        
        # Call the handler
        await self.appletv.set_volume(cmd_config, params)
        
        # Verify the method was called with the correct level
        self.mock_audio.set_volume.assert_called_once_with(0.75)  # 75% converted to 0.75
        
        # Verify state was updated
        self.assertEqual(self.appletv.state.volume, 75)
        
        # Verify refresh was scheduled
        self.appletv._delayed_refresh.assert_called_once()
        
    async def test_set_volume_backwards_compatibility(self):
        """Test set_volume handler with payload (backwards compatibility)."""
        # Create command config and params
        cmd_config = self.config["commands"]["set_volume"]
        
        # Call with payload instead of params
        await self.appletv.set_volume(cmd_config, {}, payload="50")
        
        # Verify the method was called with the correct level
        self.mock_audio.set_volume.assert_called_once_with(0.5)  # 50% converted to 0.5
        
        # Verify state was updated
        self.assertEqual(self.appletv.state.volume, 50)
        
    async def test_launch_app_with_parameters(self):
        """Test launch_app handler with parameters."""
        # Populate app list for lookup
        self.appletv._app_list = {
            "youtube": "com.google.youtube",
            "netflix": "com.netflix.Netflix"
        }
        
        # Create command config and params
        cmd_config = self.config["commands"]["launch_app"]
        params = {"app": "YouTube"}
        
        # Call the handler
        await self.appletv.launch_app(cmd_config, params)
        
        # The handler should look up the app ID (case insensitive)
        # and call launch_app with the correct ID
        self.mock_apps.launch_app.assert_called_once_with("com.google.youtube")
        
        # Verify refresh was scheduled
        self.appletv._delayed_refresh.assert_called_once()
        
    async def test_launch_app_backwards_compatibility(self):
        """Test launch_app handler with appname in config (backwards compatibility)."""
        # Populate app list for lookup
        self.appletv._app_list = {
            "youtube": "com.google.youtube",
            "netflix": "com.netflix.Netflix"
        }
        
        # Create command config with appname
        cmd_config = {
            "action": "launch_app",
            "appname": "Netflix"
        }
        
        # Call without params
        await self.appletv.launch_app(cmd_config, {})
        
        # Should use appname from config
        self.mock_apps.launch_app.assert_called_once_with("com.netflix.Netflix")
        
    async def test_playback_commands(self):
        """Test playback command handlers with parameters."""
        # Create mock for _execute_remote_command
        original_execute = self.appletv._execute_remote_command
        self.appletv._execute_remote_command = AsyncMock(return_value=True)
        
        try:
            # Test play command
            await self.appletv.play({"action": "play"}, {})
            self.appletv._execute_remote_command.assert_called_with("play")
            
            # Reset mock
            self.appletv._execute_remote_command.reset_mock()
            
            # Test pause command
            await self.appletv.pause({"action": "pause"}, {})
            self.appletv._execute_remote_command.assert_called_with("pause")
            
            # Reset mock
            self.appletv._execute_remote_command.reset_mock()
            
            # Test stop command
            await self.appletv.stop({"action": "stop"}, {})
            self.appletv._execute_remote_command.assert_called_with("stop")
            
        finally:
            # Restore original method
            self.appletv._execute_remote_command = original_execute

    @patch.object(BaseDevice, '_resolve_and_validate_params')
    async def test_handle_message_with_parameters(self, mock_validate):
        """Test message handling with parameters via MQTT."""
        # Setup mocks for parameter validation
        mock_validate.return_value = {"level": 65}
        
        # Create a command message
        topic = self.config["commands"]["set_volume"]["topic"]
        payload = "65"  # Raw integer payload
        
        # Create a separate handler mock that we'll check
        original_handler = self.appletv.set_volume
        self.appletv.set_volume = AsyncMock()
        
        try:
            # Handle the message
            await self.appletv.handle_message(topic, payload)
            
            # Verify that _execute_single_action was called with correct action name
            self.appletv._execute_single_action.assert_called_once()
            call_args = self.appletv._execute_single_action.call_args[0]
            self.assertEqual(call_args[0], "set_volume")  # action name
            
        finally:
            # Restore original handler
            self.appletv.set_volume = original_handler
            
if __name__ == "__main__":
    unittest.main() 