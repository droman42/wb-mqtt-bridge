import os
import json
import pytest
from typing import Dict, Any
from app.config_manager import ConfigManager, DEVICE_CONFIG_MAPPING
from app.schemas import BroadlinkKitchenHoodConfig, DeviceConfig

@pytest.fixture
def config_manager(tmpdir):
    """Create a ConfigManager with a temporary config directory."""
    # Create the test system config
    config_dir = tmpdir.mkdir("config")
    devices_dir = config_dir.mkdir("devices")
    
    # Create a simple system.json
    system_config = {
        "mqtt_broker": {
            "host": "localhost",
            "port": 1883,
            "client_id": "test_client"
        },
        "web_service": {
            "host": "0.0.0.0",
            "port": 8000
        },
        "log_level": "DEBUG",
        "log_file": "logs/test.log",
        "devices": {
            "test_kitchen_hood": {
                "class": "BroadlinkKitchenHood",
                "config_file": "kitchen_hood.json"
            },
            "test_standard_device": {
                "class": "StandardDevice",
                "config_file": "standard_device.json"
            }
        }
    }
    
    # Write system.json
    with open(os.path.join(config_dir, "system.json"), "w") as f:
        json.dump(system_config, f)
    
    # Create device config files
    kitchen_hood_config = {
        "device_name": "Test Kitchen Hood",
        "device_type": "broadlink_kitchen_hood",
        "mqtt_progress_topic": "/test/kitchen_hood/progress",
        "broadlink": {
            "host": "192.168.1.100",
            "mac": "AA:BB:CC:DD:EE:FF",
            "device_class": "0x520b"
        },
        "rf_codes": {
            "light": {
                "on": "test_code_on",
                "off": "test_code_off"
            },
            "speed": {
                "0": "test_code_speed_0",
                "1": "test_code_speed_1"
            }
        },
        "commands": {
            "set_light": {
                "action": "set_light",
                "description": "Control light",
                "params": [
                    {"name": "state", "type": "string", "required": True}
                ]
            }
        }
    }
    
    standard_device_config = {
        "device_name": "Test Standard Device",
        "device_type": "standard_device",
        "mqtt_progress_topic": "/test/standard_device/progress",
        "commands": {}
    }
    
    # Write device configs
    with open(os.path.join(devices_dir, "kitchen_hood.json"), "w") as f:
        json.dump(kitchen_hood_config, f)
    
    with open(os.path.join(devices_dir, "standard_device.json"), "w") as f:
        json.dump(standard_device_config, f)
    
    # Create and return the config manager
    return ConfigManager(config_dir=str(config_dir))

def test_device_config_mapping():
    """Test that the device config mapping is set up correctly."""
    assert "BroadlinkKitchenHood" in DEVICE_CONFIG_MAPPING
    assert DEVICE_CONFIG_MAPPING["BroadlinkKitchenHood"] == BroadlinkKitchenHoodConfig

def test_load_kitchen_hood_config(config_manager):
    """Test that a kitchen hood config is loaded with the correct class."""
    # Get the kitchen hood config
    kitchen_hood_config = config_manager.get_device_config("test_kitchen_hood")
    
    # Check that it's loaded with the correct class
    assert isinstance(kitchen_hood_config, BroadlinkKitchenHoodConfig)
    
    # Check that rf_codes are present
    assert "light" in kitchen_hood_config.rf_codes
    assert "speed" in kitchen_hood_config.rf_codes
    assert kitchen_hood_config.rf_codes["light"]["on"] == "test_code_on"
    assert kitchen_hood_config.rf_codes["speed"]["0"] == "test_code_speed_0"
    
    # Check that other fields are preserved
    assert kitchen_hood_config.device_name == "Test Kitchen Hood"
    
    # Access commands directly
    commands = kitchen_hood_config.commands
    assert isinstance(commands, dict)
    assert "set_light" in commands
    assert commands["set_light"].action == "set_light"

def test_standard_device_config(config_manager):
    """Test that a standard device config uses the default DeviceConfig class."""
    # Get the standard device config
    standard_config = config_manager.get_device_config("test_standard_device")
    
    # Check that it's loaded with the default class
    assert isinstance(standard_config, DeviceConfig)
    assert not isinstance(standard_config, BroadlinkKitchenHoodConfig)
    
    # Check that fields are preserved
    assert standard_config.device_name == "Test Standard Device"

def test_register_config_class():
    """Test registering a new config class."""
    # Create a test config class
    class TestDeviceConfig(DeviceConfig):
        test_field: str = "test"
    
    # Register it
    ConfigManager.register_device_config_class("TestDevice", TestDeviceConfig)
    
    # Check it was registered
    assert "TestDevice" in DEVICE_CONFIG_MAPPING
    assert DEVICE_CONFIG_MAPPING["TestDevice"] == TestDeviceConfig 