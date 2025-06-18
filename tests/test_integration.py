#!/usr/bin/env python3
"""
Integration tests for WB-MQTT Bridge application layer.

This test suite verifies:
1. State type preservation during updates
2. MQTT command propagation from device handlers
3. API responses including typed states and MQTT commands
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import json
import asyncio
from typing import Dict, Any, cast

# Add parent directory to path to allow importing from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the mock_sqlite module first to handle SQLite issues
from tests import mock_sqlite

# Import required modules
from devices.base_device import BaseDevice
from devices.broadlink_kitchen_hood import BroadlinkKitchenHood
from devices.wirenboard_ir_device import WirenboardIRDevice
from app.schemas import (
    BaseDeviceState, KitchenHoodState, WirenboardIRState,
    BroadlinkKitchenHoodConfig, WirenboardIRDeviceConfig,
    LastCommand, StandardCommandConfig, IRCommandConfig
)
from app.types import CommandResult, CommandResponse
from app.mqtt_client import MQTTClient
import httpx
from fastapi.testclient import TestClient
from app.main import app

class TestStateTypePreservation(unittest.TestCase):
    """Test that state concrete types are preserved through updates."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock MQTT client
        self.mock_mqtt_client = MagicMock(spec=MQTTClient)
        
        # Create a mock config for KitchenHood
        self.hood_config = MagicMock(spec=BroadlinkKitchenHoodConfig)
        self.hood_config.device_id = "kitchen_hood"
        self.hood_config.device_name = "Kitchen Hood"
        self.hood_config.commands = {}
        self.hood_config.rf_codes = {"light": {"on": "code1", "off": "code2"}, "speed": {"0": "code3", "1": "code4"}}
        
        # Create a mock broadlink config
        self.hood_config.broadlink = MagicMock()
        self.hood_config.broadlink.host = "192.168.1.100"
        self.hood_config.broadlink.mac = "00:11:22:33:44:55"
        self.hood_config.broadlink.device_code = "0x5213"
        
        # Create a mock config for WirenboardIR
        self.ir_config = MagicMock(spec=WirenboardIRDeviceConfig)
        self.ir_config.device_id = "wirenboard_ir"
        self.ir_config.device_name = "Wirenboard IR"
        self.ir_config.commands = {}
        
    def test_kitchen_hood_state_preservation(self):
        """Test that KitchenHoodState type is preserved during update_state."""
        # Create a real KitchenHood device with mocked config
        device = BroadlinkKitchenHood(self.hood_config, self.mock_mqtt_client)
        
        # Verify initial state type
        self.assertIsInstance(device.state, KitchenHoodState)
        
        # Update state with new values
        device.update_state(light="on", speed=2)
        
        # Verify type is preserved and values are updated
        self.assertIsInstance(device.state, KitchenHoodState)
        self.assertEqual(device.state.light, "on")
        self.assertEqual(device.state.speed, 2)
        
        # Add LastCommand and verify type is still preserved
        last_cmd = LastCommand(action="set_light", source="test", timestamp="2023-01-01T12:00:00")
        device.update_state(last_command=last_cmd)
        
        # Verify type and values
        self.assertIsInstance(device.state, KitchenHoodState)
        self.assertEqual(device.state.light, "on")
        self.assertEqual(device.state.speed, 2)
        self.assertEqual(device.state.last_command, last_cmd)
    
    def test_wirenboard_ir_state_preservation(self):
        """Test that WirenboardIRState type is preserved during update_state."""
        # Create a real WirenboardIR device with mocked config
        device = WirenboardIRDevice(self.ir_config, self.mock_mqtt_client)
        
        # Verify initial state type
        self.assertIsInstance(device.state, WirenboardIRState)
        
        # Update state with new values
        device.update_state(alias="Test Alias")
        
        # Verify type is preserved and values are updated
        self.assertIsInstance(device.state, WirenboardIRState)
        self.assertEqual(device.state.alias, "Test Alias")

class TestMQTTCommandPropagation(unittest.TestCase):
    """Test that MQTT commands are properly propagated through the system."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a mock MQTT client
        self.mock_mqtt_client = AsyncMock(spec=MQTTClient)
        
        # Create a mock config for KitchenHood
        self.hood_config = MagicMock(spec=BroadlinkKitchenHoodConfig)
        self.hood_config.device_id = "kitchen_hood"
        self.hood_config.device_name = "Kitchen Hood"
        self.hood_config.commands = {
            "set_light": MagicMock(spec=StandardCommandConfig)
        }
        self.hood_config.rf_codes = {"light": {"on": "code1", "off": "code2"}, "speed": {"0": "code3", "1": "code4"}}
        
        # Create a mock broadlink config
        self.hood_config.broadlink = MagicMock()
        self.hood_config.broadlink.host = "192.168.1.100"
        self.hood_config.broadlink.mac = "00:11:22:33:44:55"
        self.hood_config.broadlink.device_code = "0x5213"
        
        # Create a mock config for WirenboardIR
        self.ir_config = MagicMock(spec=WirenboardIRDeviceConfig)
        self.ir_config.device_id = "wirenboard_ir"
        self.ir_config.device_name = "Wirenboard IR"
        self.ir_config.commands = {
            "power_on": MagicMock(spec=IRCommandConfig)
        }
        
    @patch.object(BroadlinkKitchenHood, '_send_rf_code')
    async def test_kitchen_hood_mqtt_command_propagation(self, mock_send_rf_code):
        """Test that kitchen hood handler includes mqtt_command in result."""
        # Configure mock
        mock_send_rf_code.return_value = True
        
        # Create a real KitchenHood device with mocked config and client
        device = BroadlinkKitchenHood(self.hood_config, self.mock_mqtt_client)
        
        # Execute action
        cmd_config = StandardCommandConfig(action="set_light")
        params = {"state": "on"}
        result = await device.handle_set_light(cmd_config, params)
        
        # Verify result includes mqtt_command
        self.assertTrue("mqtt_command" in result, "mqtt_command should be in result")
        mqtt_command = result.get("mqtt_command")
        self.assertIsInstance(mqtt_command, dict)
        # Check if mqtt_command has the expected keys
        self.assertIsNotNone(mqtt_command)
        if mqtt_command is not None:  # This check is for type checking only
            self.assertIn("topic", mqtt_command)
            self.assertIn("payload", mqtt_command)
        
        # Verify action propagates through execute_action
        response = await device.execute_action("set_light", {"state": "on"}, source="test")
        
        # Verify CommandResponse includes mqtt_command
        self.assertTrue("mqtt_command" in response, "mqtt_command should be in CommandResponse")
        mqtt_command = response.get("mqtt_command")
        self.assertIsInstance(mqtt_command, dict)
        # Check if mqtt_command has the expected keys
        self.assertIsNotNone(mqtt_command)
        if mqtt_command is not None:  # This check is for type checking only
            self.assertIn("topic", mqtt_command)
            self.assertIn("payload", mqtt_command)
    
    @patch.object(WirenboardIRDevice, '_get_command_topic')
    async def test_wirenboard_ir_mqtt_command_propagation(self, mock_get_command_topic):
        """Test that IR device handler includes mqtt_command in result."""
        # Configure mock
        mock_get_command_topic.return_value = "wb/devices/ir/send"
        
        # Create a real WirenboardIR device with mocked config
        device = WirenboardIRDevice(self.ir_config, self.mock_mqtt_client)
        
        # Set up to bypass sending actual MQTT messages
        with patch.object(device.mqtt_client, 'publish', new_callable=AsyncMock) as mock_publish:
            mock_publish.return_value = True
            
            # Create a handler dynamically
            cmd_config = IRCommandConfig(action="power_on", location="living_room", rom_position="1")
            handler = device._create_generic_handler("power_on", cmd_config)
            
            # Execute handler
            result = await handler(cmd_config, {})
            
            # Verify result includes mqtt command information
            # WirenboardIR uses different field names than the standard
            self.assertTrue("mqtt_topic" in result, "mqtt_topic should be in result")
            self.assertTrue("mqtt_payload" in result, "mqtt_payload should be in result")
            
            # Get the values to verify they're not None
            mqtt_topic = result.get("mqtt_topic")
            mqtt_payload = result.get("mqtt_payload")
            self.assertIsNotNone(mqtt_topic)
            self.assertIsNotNone(mqtt_payload)

class TestAPIResponse(unittest.TestCase):
    """Test that API endpoints return properly typed responses."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a TestClient instance
        self.client = TestClient(app)
        
        # Prepare patches
        self.device_manager_patch = patch('app.main.device_manager')
        self.mqtt_client_patch = patch('app.main.mqtt_client')
        
        # Start patches
        self.mock_device_manager = self.device_manager_patch.start()
        self.mock_mqtt_client = self.mqtt_client_patch.start()
        
        # Set up mock device
        self.mock_device = MagicMock(spec=BroadlinkKitchenHood)
        self.mock_device.device_id = "kitchen_hood"
        self.mock_device_manager.get_device.return_value = self.mock_device
        
        # Set up mock state
        self.mock_state = KitchenHoodState(
            device_id="kitchen_hood",
            device_name="Kitchen Hood",
            light="on",
            speed=2,
            connection_status="connected"
        )
        
        # Set up mock command response
        self.mock_command_response = {
            "success": True,
            "device_id": "kitchen_hood",
            "action": "set_light",
            "state": self.mock_state,
            "mqtt_command": {
                "topic": "kitchen_hood/light/state",
                "payload": "on"
            }
        }
        
    def tearDown(self):
        """Clean up after tests."""
        # Stop patches
        self.device_manager_patch.stop()
        self.mqtt_client_patch.stop()
    
    def test_get_device_returns_typed_state(self):
        """Test that GET /devices/{device_id} returns properly typed state."""
        # Configure mock
        self.mock_device.get_current_state.return_value = self.mock_state
        
        # Make request
        response = self.client.get("/devices/kitchen_hood")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify it's not wrapped (no 'state' field at the top level)
        self.assertNotIn("state", data)
        
        # Verify fields are directly accessible
        self.assertEqual(data["device_id"], "kitchen_hood")
        self.assertEqual(data["device_name"], "Kitchen Hood")
        self.assertEqual(data["light"], "on")
        self.assertEqual(data["speed"], 2)
        self.assertEqual(data["connection_status"], "connected")
    
    def test_execute_action_returns_command_response(self):
        """Test that POST /devices/{device_id}/action returns CommandResponse."""
        # Configure mock
        self.mock_device.execute_action = AsyncMock(return_value=self.mock_command_response)
        
        # Make request
        response = self.client.post(
            "/devices/kitchen_hood/action",
            json={"action": "set_light", "params": {"state": "on"}}
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure
        self.assertEqual(data["success"], True)
        self.assertEqual(data["device_id"], "kitchen_hood")
        self.assertEqual(data["action"], "set_light")
        
        # Verify state is included directly (not wrapped)
        self.assertIsInstance(data["state"], dict)
        self.assertEqual(data["state"]["light"], "on")
        self.assertEqual(data["state"]["speed"], 2)
        
        # Verify mqtt_command is included
        self.assertIn("mqtt_command", data)
        self.assertEqual(data["mqtt_command"]["topic"], "kitchen_hood/light/state")
        self.assertEqual(data["mqtt_command"]["payload"], "on")

if __name__ == '__main__':
    unittest.main() 