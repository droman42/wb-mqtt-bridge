import json
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import MagicMock, patch
import base64
from devices.broadlink_kitchen_hood import BroadlinkKitchenHood
from app.schemas import KitchenHoodState


@pytest.fixture
def kitchen_hood_config():
    """Load the kitchen hood configuration."""
    with open('config/devices/kitchen_hood.json', 'r') as f:
        return json.load(f)


@pytest.fixture
def mock_broadlink_device():
    """Create a mock for the Broadlink device."""
    mock_device = MagicMock()
    mock_device.auth.return_value = None
    mock_device.send_data.return_value = None
    return mock_device


@pytest_asyncio.fixture
async def kitchen_hood_device(kitchen_hood_config, mock_broadlink_device):
    """Create a kitchen hood device with mocked Broadlink device."""
    with patch('broadlink.rm4pro', return_value=mock_broadlink_device):
        device = BroadlinkKitchenHood(kitchen_hood_config)
        await device.setup()
        return device


@pytest.mark.asyncio
async def test_rf_codes_loaded(kitchen_hood_device):
    """Test that RF codes are loaded correctly from config."""
    assert "light" in kitchen_hood_device.rf_codes
    assert "speed" in kitchen_hood_device.rf_codes
    assert "on" in kitchen_hood_device.rf_codes["light"]
    assert "off" in kitchen_hood_device.rf_codes["light"]
    assert "0" in kitchen_hood_device.rf_codes["speed"]
    assert "1" in kitchen_hood_device.rf_codes["speed"]
    assert "2" in kitchen_hood_device.rf_codes["speed"]
    assert "3" in kitchen_hood_device.rf_codes["speed"]
    assert "4" in kitchen_hood_device.rf_codes["speed"]


@pytest.mark.asyncio
async def test_set_light_parameter(kitchen_hood_device, mock_broadlink_device):
    """Test the new handle_set_light handler with parameters."""
    cmd_config = kitchen_hood_device.get_available_commands()["setLight"]
    
    # Test turning light on
    await kitchen_hood_device.handle_set_light(cmd_config, {"state": "on"})
    
    # Check that the correct RF code was sent
    rf_code_base64 = kitchen_hood_device.rf_codes["light"]["on"]
    rf_code = base64.b64decode(rf_code_base64)
    mock_broadlink_device.send_data.assert_called_with(rf_code)
    
    # Check state was updated
    assert kitchen_hood_device.state["light"] == "on"
    
    # Reset mock
    mock_broadlink_device.reset_mock()
    
    # Test turning light off
    await kitchen_hood_device.handle_set_light(cmd_config, {"state": "off"})
    
    # Check that the correct RF code was sent
    rf_code_base64 = kitchen_hood_device.rf_codes["light"]["off"]
    rf_code = base64.b64decode(rf_code_base64)
    mock_broadlink_device.send_data.assert_called_with(rf_code)
    
    # Check state was updated
    assert kitchen_hood_device.state["light"] == "off"


@pytest.mark.asyncio
async def test_set_speed_parameter(kitchen_hood_device, mock_broadlink_device):
    """Test the new handle_set_speed handler with parameters."""
    cmd_config = kitchen_hood_device.get_available_commands()["setSpeed"]
    
    # Test each speed level
    for level in range(5):  # 0 to 4
        # Reset mock
        mock_broadlink_device.reset_mock()
        
        # Set speed
        await kitchen_hood_device.handle_set_speed(cmd_config, {"level": level})
        
        # Check that the correct RF code was sent
        rf_code_base64 = kitchen_hood_device.rf_codes["speed"][str(level)]
        rf_code = base64.b64decode(rf_code_base64)
        mock_broadlink_device.send_data.assert_called_with(rf_code)
        
        # Check state was updated
        assert kitchen_hood_device.state["speed"] == level


@pytest.mark.asyncio
async def test_handle_legacy_actions(kitchen_hood_device, mock_broadlink_device):
    """Test that legacy action handlers use new parameter-based implementations when rf_codes are available."""
    # Create mock action_config for legacy handlers
    action_config = {
        "rf_code": "dummy_code"  # This should NOT be used if rf_codes map is available
    }
    
    # Test light_on legacy handler
    await kitchen_hood_device.handle_light_on(action_config, "1")
    
    # It should use the parameter-based approach, sending the code from rf_codes map
    rf_code_base64 = kitchen_hood_device.rf_codes["light"]["on"]
    rf_code = base64.b64decode(rf_code_base64)
    mock_broadlink_device.send_data.assert_called_with(rf_code)
    
    # Check state was updated
    assert kitchen_hood_device.state["light"] == "on"
    
    # Reset mock
    mock_broadlink_device.reset_mock()
    
    # Test hood_off legacy handler
    await kitchen_hood_device.handle_hood_off(action_config, "0")
    
    # It should use the parameter-based approach, sending the code from rf_codes map
    rf_code_base64 = kitchen_hood_device.rf_codes["speed"]["0"]
    rf_code = base64.b64decode(rf_code_base64)
    mock_broadlink_device.send_data.assert_called_with(rf_code)
    
    # Check state was updated
    assert kitchen_hood_device.state["speed"] == 0


@pytest.mark.asyncio
async def test_mqtt_message_handling(kitchen_hood_device, mock_broadlink_device):
    """Test that MQTT messages are properly processed with the new parameter system."""
    # We need to replace the async method with an async mock
    original_execute = kitchen_hood_device._execute_single_action
    
    # Create tracking variables to verify calls
    executed_commands = []
    
    # Create an async replacement function
    async def mock_execute_single_action(cmd_name, cmd_config, params, payload=None):
        executed_commands.append({
            'cmd_name': cmd_name, 
            'params': params
        })
        return None
    
    # Replace the method
    kitchen_hood_device._execute_single_action = mock_execute_single_action
    
    try:
        # Test light control via MQTT
        await kitchen_hood_device.handle_message("/devices/kitchen_hood/controls/light", "1")
        
        # Check that execute_single_action was called with correct parameters
        assert len(executed_commands) == 1
        assert executed_commands[0]['cmd_name'] == "setLight"
        assert "state" in executed_commands[0]['params']
        # The raw value "1" is passed through as the state
        assert executed_commands[0]['params']["state"] == "1"
        
        # Clear tracking
        executed_commands.clear()
        
        # Test speed control via MQTT
        await kitchen_hood_device.handle_message("/devices/kitchen_hood/controls/speed", "2")
        
        # Check that execute_single_action was called with correct parameters
        assert len(executed_commands) == 1
        assert executed_commands[0]['cmd_name'] == "setSpeed"
        assert "level" in executed_commands[0]['params']
        # The level is converted to an integer in the handler
        assert executed_commands[0]['params']["level"] == 2
    finally:
        # Restore original method
        kitchen_hood_device._execute_single_action = original_execute 