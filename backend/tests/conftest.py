"""
Pytest configuration for all tests.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock
from wb_mqtt_bridge.domain.scenarios.scenario import Scenario
from wb_mqtt_bridge.domain.scenarios.models import ScenarioDefinition

# Add the parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.auto_wrap_devices import import_and_wrap_devices

# Import the sample scenario data if available
try:
    from tests.unit.test_scenario import SAMPLE_SCENARIO
except ImportError:
    # Default sample scenario if not available (thin format: source/display/audio)
    SAMPLE_SCENARIO = {
        "scenario_id": "test_scenario",
        "names": {"ru": "Тестовый сценарий", "en": "Test Scenario"},
        "description": "A test scenario",
        "roles": {"main_display": "tv", "audio": "soundbar"},
        "devices": ["tv", "soundbar"],
        "source": "tv",
        "display": "tv",
        "audio": "soundbar",
        "manual_instructions": {
            "startup": ["Turn on the lights"],
            "shutdown": ["Turn off the lights"]
        }
    }

def pytest_configure(config):
    """Configure pytest before any tests are run."""
    # Wrap all device classes to handle dictionary configs
    wrapped_classes = import_and_wrap_devices()
    print(f"Wrapped {len(wrapped_classes)} device classes for testing") 

@pytest.fixture
def mock_device_manager():
    """Create a mock device manager with mock devices."""
    tv = MagicMock()
    tv.execute_action = AsyncMock()
    tv.get_current_state = MagicMock(return_value={"power": False})
    
    soundbar = MagicMock()
    soundbar.execute_action = AsyncMock()
    soundbar.get_current_state = MagicMock(return_value={"power": False})
    
    device_manager = MagicMock()
    device_manager.get_device = MagicMock(side_effect=lambda device_id: {
        "tv": tv,
        "soundbar": soundbar
    }.get(device_id))
    
    device_manager.devices = {
        "tv": tv,
        "soundbar": soundbar
    }
    
    return device_manager

@pytest.fixture
def scenario(mock_device_manager):
    """Create a scenario instance for testing."""
    definition = ScenarioDefinition.model_validate(SAMPLE_SCENARIO)
    scenario = Scenario(definition, mock_device_manager)
    return scenario

# Add other fixtures as needed