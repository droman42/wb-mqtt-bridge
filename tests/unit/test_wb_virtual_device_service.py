"""Unit tests for WBVirtualDeviceService."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService, CommandExecutor
from wb_mqtt_bridge.domain.ports import MessageBusPort
from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig, BaseCommandConfig, CommandParameterDefinition


class TestWBVirtualDeviceService:
    """Test cases for WBVirtualDeviceService."""
    
    @pytest.fixture
    def mock_message_bus(self):
        """Create a mock message bus."""
        return AsyncMock(spec=MessageBusPort)
    
    @pytest.fixture
    def wb_service(self, mock_message_bus):
        """Create a WBVirtualDeviceService instance."""
        return WBVirtualDeviceService(mock_message_bus)
    
    @pytest.fixture
    def sample_device_config(self):
        """Create a sample device configuration."""
        return {
            "device_id": "test_device",
            "device_name": "Test Device",
            "device_class": "TestDevice",
            "enable_wb_emulation": True,
            "commands": {
                "power_on": {
                    "action": "power_on",
                    "description": "Turn device on",
                    "group": "power"
                },
                "set_volume": {
                    "action": "set_volume",
                    "description": "Set volume level", 
                    "group": "volume",
                    "params": [
                        {
                            "name": "level",
                            "type": "range",
                            "min": 0,
                            "max": 100,
                            "default": 50
                        }
                    ]
                },
                "mute": {
                    "action": "mute",
                    "description": "Mute audio",
                    "group": "volume"
                }
            }
        }
    
    @pytest.fixture
    def sample_command_executor(self):
        """Create a sample command executor."""
        return AsyncMock()
    
    async def test_setup_wb_device_from_config_success(self, wb_service, mock_message_bus, sample_device_config, sample_command_executor):
        """Test successful WB device setup from config."""
        result = await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor,
            driver_name="test_driver",
            device_type="test_type"
        )
        
        assert result is True
        assert "test_device" in wb_service._active_devices
        assert "test_device" in wb_service._command_executors
        
        # Verify device metadata was published
        device_meta_call = None
        for call in mock_message_bus.publish.call_args_list:
            if "/devices/test_device/meta" in call[0]:
                device_meta_call = call
                break
        
        assert device_meta_call is not None
        topic, payload, retain, qos = device_meta_call[0] + (device_meta_call[1]["retain"], device_meta_call[1]["qos"])
        assert topic == "/devices/test_device/meta"
        
        meta = json.loads(payload)
        assert meta["driver"] == "test_driver"
        assert meta["title"]["en"] == "Test Device"
        assert meta["type"] == "test_type"
        assert retain is True
        assert qos == 1
    
    async def test_setup_wb_device_disabled(self, wb_service, sample_device_config, sample_command_executor):
        """Test WB device setup when emulation is disabled."""
        sample_device_config["enable_wb_emulation"] = False
        
        result = await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        assert result is False
        assert "test_device" not in wb_service._active_devices
    
    async def test_get_subscription_topics_from_config(self, wb_service, sample_device_config):
        """Test getting subscription topics from config."""
        topics = wb_service.get_subscription_topics_from_config(sample_device_config)
        
        expected_topics = [
            "/devices/test_device/controls/power_on/on",
            "/devices/test_device/controls/set_volume/on", 
            "/devices/test_device/controls/mute/on"
        ]
        
        assert set(topics) == set(expected_topics)
    
    async def test_get_subscription_topics_disabled(self, wb_service, sample_device_config):
        """Test getting subscription topics when WB emulation is disabled."""
        sample_device_config["enable_wb_emulation"] = False
        
        topics = wb_service.get_subscription_topics_from_config(sample_device_config)
        
        assert topics == []
    
    async def test_handle_wb_message_success(self, wb_service, mock_message_bus, sample_device_config, sample_command_executor):
        """Test successful WB message handling."""
        # Setup device first
        await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        # Handle a command message
        result = await wb_service.handle_wb_message(
            topic="/devices/test_device/controls/power_on/on",
            payload="1",
            device_id="test_device"
        )
        
        assert result is True
        
        # Verify command executor was called
        sample_command_executor.assert_called_once_with("power_on", "1", {})
        
        # Verify control state was updated
        update_call = None
        for call in mock_message_bus.publish.call_args_list:
            if "/devices/test_device/controls/power_on" in call[0] and not "/meta" in call[0]:
                update_call = call
                break
        
        assert update_call is not None
    
    async def test_handle_wb_message_with_parameters(self, wb_service, mock_message_bus, sample_device_config, sample_command_executor):
        """Test WB message handling with parameters."""
        # Setup device first
        await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        # Handle a command message with parameters
        result = await wb_service.handle_wb_message(
            topic="/devices/test_device/controls/set_volume/on",
            payload="75",
            device_id="test_device"
        )
        
        assert result is True
        
        # Verify command executor was called with parsed parameters
        sample_command_executor.assert_called_once_with("set_volume", "75", {"level": 75.0})
    
    async def test_handle_wb_message_unknown_device(self, wb_service):
        """Test WB message handling for unknown device."""
        result = await wb_service.handle_wb_message(
            topic="/devices/unknown_device/controls/power_on/on",
            payload="1",
            device_id="unknown_device"
        )
        
        assert result is False
    
    async def test_handle_wb_message_invalid_topic(self, wb_service, sample_device_config, sample_command_executor):
        """Test WB message handling with invalid topic."""
        # Setup device first
        await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        # Handle invalid topic
        result = await wb_service.handle_wb_message(
            topic="/devices/test_device/invalid/topic",
            payload="1",
            device_id="test_device"
        )
        
        assert result is False
    
    async def test_cleanup_wb_device_success(self, wb_service, mock_message_bus, sample_device_config, sample_command_executor):
        """Test successful WB device cleanup."""
        # Setup device first
        await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        # Cleanup device
        result = await wb_service.cleanup_wb_device("test_device")
        
        assert result is True
        assert "test_device" not in wb_service._active_devices
        assert "test_device" not in wb_service._command_executors
        
        # Verify offline/unavailable messages were published
        offline_calls = [call for call in mock_message_bus.publish.call_args_list 
                        if "error" in call[0][0] or "available" in call[0][0]]
        assert len(offline_calls) >= 2
    
    async def test_cleanup_wb_device_unknown(self, wb_service):
        """Test cleanup of unknown device."""
        result = await wb_service.cleanup_wb_device("unknown_device")
        
        assert result is False
    
    async def test_update_control_state_success(self, wb_service, mock_message_bus, sample_device_config, sample_command_executor):
        """Test successful control state update."""
        # Setup device first
        await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        # Update control state
        result = await wb_service.update_control_state("test_device", "power_on", "1")
        
        assert result is True
        
        # Verify state update was published
        update_call = None
        for call in mock_message_bus.publish.call_args_list:
            if "/devices/test_device/controls/power_on" in call[0] and not "/meta" in call[0]:
                update_call = call
                break
        
        assert update_call is not None
    
    async def test_handle_mqtt_reconnection_success(self, wb_service, mock_message_bus, sample_device_config, sample_command_executor):
        """Test successful MQTT reconnection handling."""
        # Setup device first
        await wb_service.setup_wb_device_from_config(
            config=sample_device_config,
            command_executor=sample_command_executor
        )
        
        # Clear previous calls
        mock_message_bus.publish.reset_mock()
        
        # Handle reconnection
        result = await wb_service.handle_mqtt_reconnection("test_device")
        
        assert result is True
        
        # Verify device metadata and controls were republished
        meta_calls = [call for call in mock_message_bus.publish.call_args_list 
                     if "/meta" in call[0][0]]
        assert len(meta_calls) > 0
    
    def test_generate_wb_control_meta_from_config_pushbutton(self, wb_service, sample_device_config):
        """Test generating WB control metadata for pushbutton."""
        cmd_config = sample_device_config["commands"]["power_on"]
        
        meta = wb_service._generate_wb_control_meta_from_config("power_on", cmd_config, sample_device_config)
        
        assert meta["type"] == "pushbutton"
        assert meta["title"]["en"] == "Turn device on"
        assert meta["readonly"] is False
        assert isinstance(meta["order"], int)
    
    def test_generate_wb_control_meta_from_config_range(self, wb_service, sample_device_config):
        """Test generating WB control metadata for range control."""
        cmd_config = sample_device_config["commands"]["set_volume"]
        
        meta = wb_service._generate_wb_control_meta_from_config("set_volume", cmd_config, sample_device_config)
        
        assert meta["type"] == "range"
        assert meta["title"]["en"] == "Set volume level"
        assert meta["min"] == 0
        assert meta["max"] == 100
        assert meta["readonly"] is False
    
    def test_generate_wb_control_meta_from_config_switch(self, wb_service, sample_device_config):
        """Test generating WB control metadata for switch control."""
        cmd_config = sample_device_config["commands"]["mute"]
        
        meta = wb_service._generate_wb_control_meta_from_config("mute", cmd_config, sample_device_config)
        
        assert meta["type"] == "switch"
        assert meta["title"]["en"] == "Mute audio"
        assert meta["readonly"] is False
    
    def test_determine_wb_control_type_from_config_group_based(self, wb_service):
        """Test WB control type determination based on group."""
        # Volume + set action = range
        cmd_config = {"group": "volume", "action": "set_volume"}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "range"
        
        # Volume + mute action = switch
        cmd_config = {"group": "volume", "action": "mute"}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "switch"
        
        # Power group = pushbutton
        cmd_config = {"group": "power", "action": "power_on"}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "pushbutton"
    
    def test_determine_wb_control_type_from_config_param_based(self, wb_service):
        """Test WB control type determination based on parameters."""
        # Range parameter = range control
        cmd_config = {"params": [{"type": "range", "min": 0, "max": 100}]}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "range"
        
        # Boolean parameter = switch control
        cmd_config = {"params": [{"type": "boolean"}]}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "switch"
        
        # String parameter = text control
        cmd_config = {"params": [{"type": "string"}]}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "text"
    
    def test_determine_wb_control_type_from_config_default(self, wb_service):
        """Test WB control type determination default case."""
        # No group or parameters = pushbutton
        cmd_config = {"action": "some_action"}
        assert wb_service._determine_wb_control_type_from_config(cmd_config) == "pushbutton"
    
    def test_get_initial_wb_control_state_from_config_with_default(self, wb_service):
        """Test getting initial WB control state with explicit default."""
        cmd_config = {
            "params": [{"name": "level", "type": "range", "default": 42}]
        }
        
        state = wb_service._get_initial_wb_control_state_from_config("test_cmd", cmd_config)
        assert state == "42"
    
    def test_get_initial_wb_control_state_from_config_name_based(self, wb_service):
        """Test getting initial WB control state based on command name."""
        # Volume command
        state = wb_service._get_initial_wb_control_state_from_config("set_volume", {})
        assert state == "50"
        
        # Mute command
        state = wb_service._get_initial_wb_control_state_from_config("mute", {})
        assert state == "0"
        
        # Generic command
        state = wb_service._get_initial_wb_control_state_from_config("generic_action", {})
        assert state == "0"
    
    def test_process_wb_command_payload_from_config_boolean(self, wb_service):
        """Test processing WB command payload for boolean parameter."""
        cmd_config = {
            "params": [{"name": "enabled", "type": "boolean"}]
        }
        
        # Test various boolean representations
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "1")
        assert params == {"enabled": True}
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "0")
        assert params == {"enabled": False}
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "true")
        assert params == {"enabled": True}
    
    def test_process_wb_command_payload_from_config_numeric(self, wb_service):
        """Test processing WB command payload for numeric parameters."""
        # Integer parameter
        cmd_config = {
            "params": [{"name": "level", "type": "integer"}]
        }
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "42")
        assert params == {"level": 42}
        
        # Float parameter
        cmd_config = {
            "params": [{"name": "level", "type": "float"}]
        }
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "42.5")
        assert params == {"level": 42.5}
        
        # Range parameter
        cmd_config = {
            "params": [{"name": "level", "type": "range"}]
        }
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "75")
        assert params == {"level": 75.0}
    
    def test_process_wb_command_payload_from_config_string(self, wb_service):
        """Test processing WB command payload for string parameter."""
        cmd_config = {
            "params": [{"name": "input", "type": "string"}]
        }
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "hdmi1")
        assert params == {"input": "hdmi1"}
    
    def test_process_wb_command_payload_from_config_no_params(self, wb_service):
        """Test processing WB command payload with no parameters."""
        cmd_config = {}
        
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "1")
        assert params == {}
    
    def test_process_wb_command_payload_from_config_error_handling(self, wb_service):
        """Test processing WB command payload with error handling."""
        cmd_config = {
            "params": [{"name": "level", "type": "integer", "default": 0}]
        }
        
        # Invalid payload should use default
        params = wb_service._process_wb_command_payload_from_config("test_cmd", cmd_config, "invalid")
        assert params == {"level": 0}
    
    def test_is_wb_command_topic(self, wb_service):
        """Test WB command topic detection."""
        assert wb_service._is_wb_command_topic("/devices/test_device/controls/power_on/on", "test_device") is True
        assert wb_service._is_wb_command_topic("/devices/test_device/controls/power_on", "test_device") is False
        assert wb_service._is_wb_command_topic("/devices/other_device/controls/power_on/on", "test_device") is False
        assert wb_service._is_wb_command_topic("/invalid/topic", "test_device") is False
    
    def test_generate_control_title(self, wb_service):
        """Test control title generation."""
        assert wb_service._generate_control_title("power_on") == "Power On"
        assert wb_service._generate_control_title("set_volume") == "Set Volume"
        assert wb_service._generate_control_title("toggleMute") == "Toggle Mute"
        assert wb_service._generate_control_title("simple") == "Simple"
    
    def test_get_control_order_from_config(self, wb_service):
        """Test control order generation."""
        # Power group should have low order
        cmd_config = {"group": "power", "action": "power_on"}
        order1 = wb_service._get_control_order_from_config(cmd_config)
        
        # Display group should have higher order
        cmd_config = {"group": "display", "action": "set_brightness"}
        order2 = wb_service._get_control_order_from_config(cmd_config)
        
        assert order1 < order2
    
    def test_validate_wb_configuration_from_config_valid(self, wb_service, sample_device_config):
        """Test WB configuration validation for valid config."""
        is_valid, results = wb_service._validate_wb_configuration_from_config(sample_device_config)
        
        assert is_valid is True
        assert len(results['wb_controls_errors']) == 0
    
    def test_validate_wb_configuration_from_config_missing_actions(self, wb_service):
        """Test WB configuration validation with missing actions."""
        config = {
            "device_id": "test_device",
            "commands": {
                "cmd_without_action": {
                    "description": "Command without action"
                    # Missing 'action' field
                }
            }
        }
        
        is_valid, results = wb_service._validate_wb_configuration_from_config(config)
        
        assert is_valid is True  # Still valid, just generates warnings
        assert any("Commands without actions" in warning for warning in results['warnings'])
    
    def test_validate_wb_configuration_from_config_no_commands(self, wb_service):
        """Test WB configuration validation with no commands."""
        config = {
            "device_id": "test_device",
            "commands": {}
        }
        
        is_valid, results = wb_service._validate_wb_configuration_from_config(config)
        
        assert is_valid is True  # Still valid, just generates warnings
        assert any("No commands defined" in warning for warning in results['warnings']) 