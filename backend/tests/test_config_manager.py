import os
import json
import pytest
from wb_mqtt_bridge.infrastructure.config.manager import ConfigManager
from wb_mqtt_bridge.infrastructure.config.models import BroadlinkKitchenHoodConfig, BaseDeviceConfig

pytestmark = pytest.mark.unit

@pytest.fixture
def config_manager(tmpdir):
    """Create a ConfigManager with a temporary config directory."""
    # Create the test system config
    config_dir = tmpdir.mkdir("config")
    devices_dir = config_dir.mkdir("devices")
    
    # system.json — device discovery happens via the devices/ subdir, so the
    # "devices" section at the top level is no longer needed.
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
    }

    with open(os.path.join(config_dir, "system.json"), "w") as f:
        json.dump(system_config, f)

    # Kitchen hood config in the current schema (device_class + config_class
    # required by BaseDeviceConfig; broadlink/rf_codes are required by
    # BroadlinkKitchenHoodConfig).
    kitchen_hood_config = {
        "device_id": "test_kitchen_hood",
        "names": {"ru": "Test Kitchen Hood", "en": "Test Kitchen Hood"},
        "device_class": "BroadlinkKitchenHood",
        "config_class": "BroadlinkKitchenHoodConfig",
        "broadlink": {
            "host": "192.168.1.100",
            "mac": "AA:BB:CC:DD:EE:FF",
            "device_code": "0x520b"
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

    # A device whose config_class doesn't resolve — used to verify the
    # ConfigManager rejects unknown classes (replaces the old
    # test_standard_device_config behavior).
    unknown_class_config = {
        "device_id": "test_unknown_class",
        "names": {"ru": "Test Unknown Class Device", "en": "Test Unknown Class Device"},
        "device_class": "DeviceClassThatDoesNotExist",
        "config_class": "ConfigClassThatDoesNotExist",
        "commands": {},
    }

    with open(os.path.join(devices_dir, "kitchen_hood.json"), "w") as f:
        json.dump(kitchen_hood_config, f)

    with open(os.path.join(devices_dir, "unknown_class.json"), "w") as f:
        json.dump(unknown_class_config, f)

    return ConfigManager(config_dir=str(config_dir))


def test_load_kitchen_hood_config(config_manager):
    """A kitchen-hood JSON in the devices/ dir is loaded with the right Pydantic class."""
    kitchen_hood_config = config_manager.get_device_config("test_kitchen_hood")

    assert isinstance(kitchen_hood_config, BroadlinkKitchenHoodConfig)
    assert kitchen_hood_config.names.ru == "Test Kitchen Hood"
    assert kitchen_hood_config.names.en == "Test Kitchen Hood"
    assert kitchen_hood_config.device_class == "BroadlinkKitchenHood"
    assert kitchen_hood_config.config_class == "BroadlinkKitchenHoodConfig"

    # rf_codes round-trip
    assert "light" in kitchen_hood_config.rf_codes
    assert "speed" in kitchen_hood_config.rf_codes
    assert kitchen_hood_config.rf_codes["light"]["on"] == "test_code_on"
    assert kitchen_hood_config.rf_codes["speed"]["0"] == "test_code_speed_0"

    # commands parsed into Pydantic objects
    commands = kitchen_hood_config.commands
    assert isinstance(commands, dict)
    assert "set_light" in commands
    assert commands["set_light"].action == "set_light"


def test_unknown_config_class_skipped(config_manager):
    """A device JSON pointing at a config_class that doesn't resolve must not load."""
    cfg = config_manager.get_device_config("test_unknown_class")
    assert cfg is None
