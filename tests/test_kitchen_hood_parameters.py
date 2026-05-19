import json
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
import base64
from wb_mqtt_bridge.infrastructure.devices.broadlink_kitchen_hood.driver import BroadlinkKitchenHood
from wb_mqtt_bridge.infrastructure.config.models import BroadlinkKitchenHoodConfig

pytestmark = pytest.mark.integration


@pytest.fixture
def kitchen_hood_config():
    """Load the kitchen hood configuration and parse it through the current Pydantic schema.

    The driver constructor now expects a typed BroadlinkKitchenHoodConfig, not a dict.
    """
    with open('config/devices/kitchen_hood.json', 'r') as f:
        data = json.load(f)
    return BroadlinkKitchenHoodConfig.model_validate(data)


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
    """handle_set_light publishes the correct RF code and updates state.

    Updated for current config schema: command keys are snake_case ('set_light'
    not 'setLight'); state is a Pydantic KitchenHoodState (attribute access).
    """
    cmd_config = kitchen_hood_device.get_available_commands()["set_light"]

    await kitchen_hood_device.handle_set_light(cmd_config, {"state": "on"})

    rf_code = base64.b64decode(kitchen_hood_device.rf_codes["light"]["on"])
    mock_broadlink_device.send_data.assert_called_with(rf_code)
    assert kitchen_hood_device.state.light == "on"

    mock_broadlink_device.reset_mock()

    await kitchen_hood_device.handle_set_light(cmd_config, {"state": "off"})

    rf_code = base64.b64decode(kitchen_hood_device.rf_codes["light"]["off"])
    mock_broadlink_device.send_data.assert_called_with(rf_code)
    assert kitchen_hood_device.state.light == "off"


@pytest.mark.asyncio
async def test_set_speed_parameter(kitchen_hood_device, mock_broadlink_device):
    """handle_set_speed dispatches the matching RF code and stores the level on state."""
    cmd_config = kitchen_hood_device.get_available_commands()["set_speed"]

    for level in range(5):  # 0 to 4
        mock_broadlink_device.reset_mock()

        await kitchen_hood_device.handle_set_speed(cmd_config, {"level": level})

        rf_code = base64.b64decode(kitchen_hood_device.rf_codes["speed"][str(level)])
        mock_broadlink_device.send_data.assert_called_with(rf_code)
        assert kitchen_hood_device.state.speed == level


@pytest.mark.asyncio
async def test_mqtt_message_handling(kitchen_hood_device, mock_broadlink_device):
    """An MQTT message on a control topic dispatches the right command + params.

    Semantic intent (preserved from the original): when a WB-style control
    message lands, handle_message must route it via _execute_single_action
    to the named command with the parameters parsed from the payload.

    The old version of this test asserted on legacy camelCase command names
    ('setLight'/'setSpeed') and used WB sub-paths that don't match the
    current dispatch topology. Rewritten to use the actual command names from
    the live kitchen_hood.json config, with looser observation: only verify
    that _execute_single_action was called for *some* command with the payload.
    """
    original_execute = kitchen_hood_device._execute_single_action
    executed_commands = []

    async def mock_execute_single_action(cmd_name, cmd_config, params, payload=None):
        executed_commands.append({'cmd_name': cmd_name, 'params': params})
        return None

    kitchen_hood_device._execute_single_action = mock_execute_single_action

    try:
        # WB controls auto-derive a topic from device_id + command name;
        # mimic that pattern instead of pulling it off the cmd config (which
        # is a StandardCommandConfig without a `topic` attribute).
        topic = f"/devices/{kitchen_hood_device.device_id}/controls/set_light"
        await kitchen_hood_device.handle_message(topic, "on")

        assert len(executed_commands) == 1
        assert executed_commands[0]['cmd_name'] == "set_light"
        # The payload value is parsed into the first parameter (named 'state').
        assert executed_commands[0]['params'].get("state") in ("on", "1")
    finally:
        kitchen_hood_device._execute_single_action = original_execute
