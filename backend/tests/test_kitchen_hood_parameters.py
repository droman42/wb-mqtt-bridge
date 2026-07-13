"""Fresh tests for BroadlinkKitchenHood, written against the post-hexagonal-refactor driver.

The previous test file ran the full setup() path (which authenticates with a
real Broadlink RF blaster) and used a CLI-style mock pattern that mostly
exercised peripheral behavior. This rewrite injects a fake `broadlink_device`
directly on the device instance, bypasses setup(), and drives the handle_*
methods to verify:

  - handle_set_light: sends the right RF code for on/off; updates state.light;
    triggers speed-restoration compensation when previous speed was non-zero;
    rejects invalid state values; rejects when RF codes are missing.
  - handle_set_speed: sends the right RF code for levels 0–4; updates
    state.speed; rejects out-of-range levels and non-integer payloads.
  - handle_message: routes WB-style control topics to the matching command via
    BaseDevice's _execute_single_action path.
"""
import base64
import json
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

from locveil_bridge.infrastructure.devices.broadlink_kitchen_hood.driver import BroadlinkKitchenHood
from locveil_bridge.infrastructure.config.models import BroadlinkKitchenHoodConfig


pytestmark = pytest.mark.integration


@pytest.fixture
def kitchen_hood_config():
    """Parse the real kitchen_hood.json through the current Pydantic schema."""
    with open('config/devices/kitchen_hood.json', 'r') as f:
        data = json.load(f)
    return BroadlinkKitchenHoodConfig.model_validate(data)


@pytest.fixture
def fake_broadlink():
    """A MagicMock standing in for the broadlink rm4pro RF blaster.

    Only the surface the driver touches is mocked: send_data() (called via
    run_in_executor inside the driver). Returning None mirrors the real lib.
    """
    bl = MagicMock()
    bl.send_data = MagicMock(return_value=None)
    bl.auth = MagicMock(return_value=None)
    return bl


@pytest_asyncio.fixture
async def device(kitchen_hood_config, fake_broadlink):
    """BroadlinkKitchenHood with broadlink_device pre-wired (setup() bypassed)."""
    # Use a context patch only for the (unused) construction path; the actual
    # client we inject manually below to avoid setup()'s real network handshake.
    with patch('broadlink.rm4pro', return_value=fake_broadlink):
        d = BroadlinkKitchenHood(kitchen_hood_config, mqtt_client=MagicMock())
    d.broadlink_device = fake_broadlink
    return d


# --- handle_set_light: happy paths -------------------------------------------


@pytest.mark.asyncio
async def test_set_light_on_sends_correct_rf_code(device, fake_broadlink):
    """When state=on, send_data is called with the decoded 'light/on' RF code."""
    cmd = device.get_available_commands()["set_light"]
    result = await device.handle_set_light(cmd, {"state": "on"})

    expected = base64.b64decode(device.rf_codes["light"]["on"])
    fake_broadlink.send_data.assert_called_with(expected)
    assert result["success"] is True
    assert device.state.light == "on"


@pytest.mark.asyncio
async def test_set_light_off_sends_correct_rf_code(device, fake_broadlink):
    cmd = device.get_available_commands()["set_light"]
    await device.handle_set_light(cmd, {"state": "off"})
    expected = base64.b64decode(device.rf_codes["light"]["off"])
    fake_broadlink.send_data.assert_called_with(expected)
    assert device.state.light == "off"


@pytest.mark.asyncio
async def test_set_light_accepts_numeric_state(device, fake_broadlink):
    """'1' and '0' (numeric strings) are coerced to 'on'/'off'."""
    cmd = device.get_available_commands()["set_light"]
    await device.handle_set_light(cmd, {"state": "1"})
    assert device.state.light == "on"
    await device.handle_set_light(cmd, {"state": 0})
    assert device.state.light == "off"


# --- handle_set_light: compensation logic -----------------------------------


@pytest.mark.asyncio
async def test_set_light_with_previous_speed_restores_speed(device, fake_broadlink):
    """Toggling the light when speed > 0 sends the light RF code AND restores speed.

    The physical hood resets fan speed to 0 when the light toggles, so the
    driver compensates by re-sending the previous speed's RF code.
    """
    device.state.speed = 3
    cmd = device.get_available_commands()["set_light"]
    await device.handle_set_light(cmd, {"state": "on"})

    # send_data was called twice: once for light/on, once for speed/3.
    assert fake_broadlink.send_data.call_count == 2
    light_code = base64.b64decode(device.rf_codes["light"]["on"])
    speed3_code = base64.b64decode(device.rf_codes["speed"]["3"])
    sent_codes = [call.args[0] for call in fake_broadlink.send_data.call_args_list]
    assert light_code in sent_codes
    assert speed3_code in sent_codes
    # State.speed is restored to its pre-light value.
    assert device.state.speed == 3


@pytest.mark.asyncio
async def test_set_light_with_zero_previous_speed_no_compensation(device, fake_broadlink):
    """When speed was 0, no compensation RF code is sent — only the light code."""
    device.state.speed = 0
    cmd = device.get_available_commands()["set_light"]
    await device.handle_set_light(cmd, {"state": "on"})

    assert fake_broadlink.send_data.call_count == 1
    assert device.state.speed == 0


# --- handle_set_light: error paths ------------------------------------------


@pytest.mark.asyncio
async def test_set_light_invalid_state_rejected(device, fake_broadlink):
    cmd = device.get_available_commands()["set_light"]
    result = await device.handle_set_light(cmd, {"state": "purple"})
    assert result["success"] is False
    fake_broadlink.send_data.assert_not_called()


@pytest.mark.asyncio
async def test_set_light_missing_rf_codes(device, fake_broadlink):
    """If the rf_codes['light'] mapping is gone, the handler refuses cleanly."""
    device.rf_codes.pop("light")
    cmd = device.get_available_commands()["set_light"]
    result = await device.handle_set_light(cmd, {"state": "on"})
    assert result["success"] is False
    fake_broadlink.send_data.assert_not_called()


# --- handle_set_speed -------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
async def test_set_speed_each_level_sends_correct_rf_code(device, fake_broadlink, level):
    """Every supported speed level (0–4) maps to the matching RF code and updates state."""
    cmd = device.get_available_commands()["set_speed"]
    fake_broadlink.reset_mock()
    result = await device.handle_set_speed(cmd, {"level": level})

    expected = base64.b64decode(device.rf_codes["speed"][str(level)])
    fake_broadlink.send_data.assert_called_with(expected)
    assert result["success"] is True
    assert device.state.speed == level


@pytest.mark.asyncio
async def test_set_speed_out_of_range_rejected(device, fake_broadlink):
    cmd = device.get_available_commands()["set_speed"]
    result = await device.handle_set_speed(cmd, {"level": 7})
    assert result["success"] is False
    fake_broadlink.send_data.assert_not_called()


@pytest.mark.asyncio
async def test_set_speed_non_numeric_rejected(device, fake_broadlink):
    cmd = device.get_available_commands()["set_speed"]
    result = await device.handle_set_speed(cmd, {"level": "not-a-number"})
    assert result["success"] is False
    fake_broadlink.send_data.assert_not_called()


# --- handle_message routing -------------------------------------------------


@pytest.mark.asyncio
async def test_handle_message_routes_to_correct_command(device, fake_broadlink):
    """An MQTT message on a control topic dispatches the right handler.

    BaseDevice.handle_message resolves the topic (auto-generated path
    /devices/<id>/controls/<cmd>) to the matching command in get_available_commands()
    and routes through _execute_single_action. We spy on _execute_single_action
    to verify the dispatch decision without exercising the full handler chain.
    """
    captured = []

    async def fake_execute(cmd_name, cmd_config, params, payload=None):
        captured.append({"cmd_name": cmd_name, "params": params})

    original = device._execute_single_action
    device._execute_single_action = fake_execute
    try:
        topic = f"/devices/{device.device_id}/controls/set_light"
        await device.handle_message(topic, "on")
        assert len(captured) == 1
        assert captured[0]["cmd_name"] == "set_light"
        # The payload 'on' is parsed into the first parameter (named 'state').
        assert captured[0]["params"].get("state") in ("on", "1")
    finally:
        device._execute_single_action = original


# --- RF codes round-trip from config ----------------------------------------


@pytest.mark.asyncio
async def test_rf_codes_loaded_from_config(device):
    """The driver lifts rf_codes directly from the typed config — light + speed 0..4 present."""
    assert "light" in device.rf_codes
    assert "speed" in device.rf_codes
    for key in ("on", "off"):
        assert key in device.rf_codes["light"]
    for level in range(5):
        assert str(level) in device.rf_codes["speed"]
