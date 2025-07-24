"""
Tests for Phase 3 WB Virtual Device implementation.

This test suite validates:
1. Last Will Testament integration with maintenance guard
2. Enhanced configuration validation and error handling
3. Configuration Migration Phase B deprecation warnings
4. Overall Phase 3 functionality
"""

import pytest
import logging
from unittest.mock import Mock, AsyncMock

from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig, StandardCommandConfig
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.config.manager import ConfigManager
from wb_mqtt_bridge.infrastructure.maintenance.wirenboard_guard import WirenboardMaintenanceGuard


class MockDeviceForTesting(BaseDevice):
    """Mock device for testing WB virtual device functionality."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client=None):
        # Add default command configurations if not provided
        if not hasattr(config, 'commands') or not config.commands:
            from wb_mqtt_bridge.infrastructure.config.models import StandardCommandConfig, CommandParameterDefinition
            config.commands = {
                'power_on': StandardCommandConfig(
                    action='power_on',
                    description='Power On'
                ),
                'set_volume': StandardCommandConfig(
                    action='set_volume', 
                    description='Set Volume',
                    params=[CommandParameterDefinition(
                        name='volume',
                        type='integer',
                        required=True,
                        min=0,
                        max=100,
                        description='Volume level (0-100)'
                    )]
                ),
                'mute': StandardCommandConfig(
                    action='mute',
                    description='Mute'
                ),
                'get_status': StandardCommandConfig(
                    action='get_status',
                    description='Get Status'
                )
            }
        super().__init__(config, mqtt_client)
        
    def _register_handlers(self):
        """Register test handlers."""
        self._action_handlers.update({
            'power_on': self.handle_power_on,
            'set_volume': self.handle_set_volume,
            'mute': self.handle_mute,
            'get_status': self.handle_get_status
        })
    
    async def handle_power_on(self, cmd_config, params):
        return self.create_command_result(success=True)
    
    async def handle_set_volume(self, cmd_config, params):
        return self.create_command_result(success=True)
    
    async def handle_mute(self, cmd_config, params):
        return self.create_command_result(success=True)
    
    async def handle_get_status(self, cmd_config, params):
        return self.create_command_result(success=True, data={"status": "ok"})
    
    async def setup(self) -> bool:
        return True
    
    async def shutdown(self) -> bool:
        return True


class TestLastWillTestamentIntegration:
    """Test Last Will Testament integration with maintenance guard."""
    
    def test_mqtt_client_lwt_support(self):
        """Test that MQTTClient supports LWT functionality."""
        
        mqtt_client = MQTTClient({'host': 'localhost', 'port': 1883, 'client_id': 'test'})
        
        # Test adding will messages
        mqtt_client.add_will_message('test_device', '/test/topic', 'offline')
        
        assert len(mqtt_client._will_messages) == 1
        assert mqtt_client._will_messages[0].topic == '/test/topic'
        assert mqtt_client._will_messages[0].payload == 'offline'
        assert mqtt_client._will_messages[0].retain
        
        # Test device registry
        assert 'test_device' in mqtt_client._device_lwt_registry
        assert '/test/topic' in mqtt_client._device_lwt_registry['test_device']
    
    def test_mqtt_client_remove_device_lwt(self):
        """Test removing device LWT messages."""
        mqtt_client = MQTTClient({'host': 'localhost', 'port': 1883, 'client_id': 'test'})
        
        # Add multiple will messages for the same device
        mqtt_client.add_will_message('test_device', '/test/error', 'offline')
        mqtt_client.add_will_message('test_device', '/test/available', '0')
        mqtt_client.add_will_message('other_device', '/other/error', 'offline')
        
        assert len(mqtt_client._will_messages) == 3
        
        # Remove will messages for one device
        mqtt_client.remove_device_will_messages('test_device')
        
        assert len(mqtt_client._will_messages) == 1
        assert mqtt_client._will_messages[0].topic == '/other/error'
        assert 'test_device' not in mqtt_client._device_lwt_registry
        assert 'other_device' in mqtt_client._device_lwt_registry
    
    @pytest.mark.asyncio
    async def test_device_lwt_setup(self):
        """Test device LWT setup with BaseDevice."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            enable_wb_emulation=True
        )
        
        mock_mqtt_client = Mock()
        mock_mqtt_client.add_will_message = Mock()
        mock_mqtt_client.publish = AsyncMock()
        
        device = MockDeviceForTesting(config, mock_mqtt_client)
        
        # Test LWT setup
        await device._setup_wb_last_will()
        
        # Verify LWT messages were added
        expected_calls = [
            (('test_device', '/devices/test_device/meta/error', 'offline'), {'qos': 1, 'retain': True}),
            (('test_device', '/devices/test_device/meta/available', '0'), {'qos': 1, 'retain': True})
        ]
        
        from unittest.mock import call
        mock_mqtt_client.add_will_message.assert_has_calls([
            call(*args, **kwargs) for args, kwargs in expected_calls
        ])
        
        # Verify availability messages were published
        mock_mqtt_client.publish.assert_any_call('/devices/test_device/meta/error', '', retain=True)
        mock_mqtt_client.publish.assert_any_call('/devices/test_device/meta/available', '1', retain=True)
    
    def test_maintenance_guard_integration(self):
        """Test maintenance guard integration with LWT."""
        maintenance_guard = WirenboardMaintenanceGuard(duration=5, topic='/devices/wbrules/meta/driver')
        mqtt_client = MQTTClient(
            {'host': 'localhost', 'port': 1883, 'client_id': 'test'},
            maintenance_guard=maintenance_guard
        )
        
        # Verify maintenance guard is stored
        assert mqtt_client.guard == maintenance_guard
        
        # Test that guard subscription topics are accessible
        guard_topics = maintenance_guard.subscription_topics()
        assert '/devices/wbrules/meta/driver' in guard_topics


class TestConfigurationValidation:
    """Test enhanced configuration validation and error handling."""
    
    def test_wb_controls_validation_success(self):
        """Test successful WB controls validation."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            wb_controls={
                'power_on': {
                    'type': 'pushbutton',
                    'title': {'en': 'Power On'},
                    'order': 1,
                    'readonly': False
                },
                'set_volume': {
                    'type': 'range',
                    'min': 0,
                    'max': 100,
                    'units': '%',
                    'title': {'en': 'Volume'},
                    'order': 2
                }
            }
        )
        
        device = MockDeviceForTesting(config)
        errors = device._validate_wb_controls_config()
        
        # Should have no errors for valid configuration
        assert len(errors) == 0
    
    def test_wb_controls_validation_errors(self):
        """Test WB controls validation with various errors."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            wb_controls={
                'invalid_handler': {  # Handler doesn't exist
                    'type': 'pushbutton'
                },
                'power_on': {
                    'type': 'invalid_type',  # Invalid type
                    'min': 'not_a_number',   # Invalid min for range
                    'max': 50,
                    'title': {'no_en_key': 'Title'},  # Missing 'en' key
                    'order': 'not_an_int',   # Invalid order type
                    'readonly': 'not_a_bool' # Invalid readonly type
                },
                'set_volume': {
                    'type': 'range',
                    'min': 100,  # min >= max
                    'max': 50
                }
            }
        )
        
        device = MockDeviceForTesting(config)
        errors = device._validate_wb_controls_config()
        
        # Should have errors for all invalid controls
        assert 'invalid_handler' in errors
        assert 'power_on' in errors
        assert 'set_volume' in errors
        
        # Check specific error messages
        assert any('No handler found' in error for error in errors['invalid_handler'])
        assert any('Invalid control type' in error for error in errors['power_on'])
        assert any("'min' value must be less than 'max' value" in error for error in errors['set_volume'])
    
    def test_wb_state_mappings_validation(self):
        """Test WB state mappings validation."""
        # First test valid configuration
        BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            wb_state_mappings={
                'power': 'power_on',           # Valid single mapping
                'volume': ['set_volume'],      # Valid list mapping
            }
        )
        
        # Then test with invalid configuration
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            wb_state_mappings={
                'power': 'power_on',           # Valid single mapping
                'volume': ['set_volume'],      # Valid list mapping
                'invalid': 'unknown_handler', # Invalid handler
                'empty_field': '',            # Invalid empty field
            }
        )
        
        device = MockDeviceForTesting(config)
        errors = device._validate_wb_state_mappings()
        
        # Should have errors for invalid mappings
        assert len(errors) > 0
        assert any('unknown control' in error for error in errors)
        assert any('empty_field' in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_comprehensive_wb_validation(self):
        """Test comprehensive WB configuration validation."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            enable_wb_emulation=True,
            wb_controls={
                'power_on': {'type': 'pushbutton', 'title': {'en': 'Power On'}}
            }
        )
        
        mock_mqtt_client = Mock()
        device = MockDeviceForTesting(config, mock_mqtt_client)
        
        is_valid, results = await device.validate_wb_configuration()
        
        # Should be valid with mock MQTT client
        assert is_valid
        assert 'wb_controls_errors' in results
        assert 'wb_state_mappings_errors' in results
        assert 'handler_validation' in results
        assert 'warnings' in results


class TestDeprecationWarnings:
    """Test Configuration Migration Phase B deprecation warnings."""
    
    def test_explicit_topic_deprecation_warning(self, caplog):
        """Test deprecation warning for explicit topic usage."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            commands={
                'power_on': StandardCommandConfig(
                    action='power_on',
                    topic='/devices/test_device/controls/power_on',  # Explicit topic
                    description='Power On'
                )
            }
        )
        
        device = MockDeviceForTesting(config)
        
        # This should trigger deprecation warning
        with caplog.at_level(logging.WARNING):
            topic = device.get_command_topic('power_on', config.commands['power_on'])
        
        # Verify warning was logged
        assert 'DEPRECATION WARNING' in caplog.text
        assert 'explicit topic field' in caplog.text
        assert 'will be removed in a future version' in caplog.text
        
        # Verify it still returns the explicit topic
        assert topic == '/devices/test_device/controls/power_on'
    
    def test_auto_generated_topic_no_warning(self, caplog):
        """Test no warning for auto-generated topics."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            commands={
                'power_on': StandardCommandConfig(
                    action='power_on',
                    description='Power On'
                    # No explicit topic field
                )
            }
        )
        
        device = MockDeviceForTesting(config)
        
        with caplog.at_level(logging.WARNING):
            topic = device.get_command_topic('power_on', config.commands['power_on'])
        
        # Verify no deprecation warning
        assert 'DEPRECATION WARNING' not in caplog.text
        
        # Verify auto-generated topic
        assert topic == '/devices/test_device/controls/power_on'
    
    def test_config_manager_migration_guidance(self):
        """Test ConfigManager migration guidance functionality."""
        # Create a mock ConfigManager with test configurations
        config_manager = ConfigManager()
        
        # Add mock configs with explicit topics
        config_with_topics = BaseDeviceConfig(
            device_id='device_with_topics',
            device_name='Device With Topics',
            device_class='MockDevice',
            config_class='BaseDeviceConfig',
            commands={
                'power_on': StandardCommandConfig(
                    action='power_on',
                    topic='/explicit/topic',
                    description='Power On'
                ),
                'set_volume': StandardCommandConfig(
                    action='set_volume',
                    topic='/another/explicit/topic',
                    description='Set Volume'
                )
            }
        )
        
        config_without_topics = BaseDeviceConfig(
            device_id='device_without_topics',
            device_name='Device Without Topics',
            device_class='MockDevice',
            config_class='BaseDeviceConfig',
            commands={
                'power_on': StandardCommandConfig(
                    action='power_on',
                    description='Power On'
                )
            }
        )
        
        config_manager.typed_configs = {
            'device_with_topics': config_with_topics,
            'device_without_topics': config_without_topics
        }
        
        # Test deprecated usage detection
        deprecated_usage = config_manager.check_deprecated_topic_usage()
        
        assert 'device_with_topics' in deprecated_usage
        assert 'device_without_topics' not in deprecated_usage
        assert len(deprecated_usage['device_with_topics']) == 2
        assert 'power_on' in deprecated_usage['device_with_topics']
        assert 'set_volume' in deprecated_usage['device_with_topics']
        
        # Test migration guidance
        guidance = config_manager.get_migration_guidance()
        
        assert guidance['summary']['total_devices'] == 2
        assert guidance['summary']['devices_needing_migration'] == 1
        assert guidance['summary']['total_commands_with_explicit_topics'] == 2
        assert len(guidance['migration_steps']) > 0
        assert len(guidance['benefits']) > 0
        assert 'auto_generated_topic_format' in guidance


class TestPhase3Integration:
    """Test overall Phase 3 functionality integration."""
    
    @pytest.mark.asyncio
    async def test_wb_setup_with_validation(self):
        """Test WB setup with validation integration."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            enable_wb_emulation=True
        )
        
        mock_mqtt_client = Mock()
        mock_mqtt_client.publish = AsyncMock()
        mock_mqtt_client.add_will_message = Mock()
        
        device = MockDeviceForTesting(config, mock_mqtt_client)
        
        # This should run validation before setup
        await device._setup_wb_virtual_device()
        
        # Verify MQTT publishes happened (indicating validation passed)
        assert mock_mqtt_client.publish.call_count > 0
        
        # Verify LWT was set up
        assert mock_mqtt_client.add_will_message.call_count > 0
    
    @pytest.mark.asyncio
    async def test_wb_setup_validation_failure(self):
        """Test WB setup stops on validation failure."""
        config = BaseDeviceConfig(
            device_id='test_device',
            device_name='Test Device',
            device_class='MockDeviceForTesting',
            config_class='BaseDeviceConfig',
            enable_wb_emulation=True,
            wb_controls={
                'invalid_control': {
                    'type': 'invalid_type'  # This will cause validation to fail
                }
            }
        )
        
        mock_mqtt_client = Mock()
        mock_mqtt_client.publish = AsyncMock()
        
        device = MockDeviceForTesting(config, mock_mqtt_client)
        
        # This should fail validation and not proceed with setup
        await device._setup_wb_virtual_device()
        
        # Verify no MQTT publishes happened (setup was aborted)
        mock_mqtt_client.publish.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 