"""Fresh tests for EMotivaXMC2, targeting the post-hexagonal-refactor driver.

The previous test file hung at collection because its fixture path-of-least-
resistance went through setup(), which makes real network connections to a
pymotivaxmc2 EmotivaController. It also asserted on private helpers
(`_power_zone`, `_set_zone_volume`, `_toggle_zone_mute`) that no longer exist
— the handlers now call `self.client.power_on(zone=...)`, `.power_off(...)`,
`.set_volume(...)`, `.mute(...)`, `.select_source(...)` directly.

Rewritten as targeted handler tests that bypass setup() by injecting a fake
EmotivaController as `self.client` and flipping `state.connected` to True.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.emotiva_xmc2.driver import EMotivaXMC2, PowerState
from wb_mqtt_bridge.infrastructure.config.models import (
    EmotivaXMC2DeviceConfig,
    EmotivaConfig,
    StandardCommandConfig,
    CommandParameterDefinition,
)


pytestmark = pytest.mark.integration


def _zone_param(default: int) -> StandardCommandConfig:
    return StandardCommandConfig(
        action="placeholder",
        params=[CommandParameterDefinition(
            name="zone",
            type="integer",
            required=False,
            default=default,
        )],
    )


def _make_config() -> EmotivaXMC2DeviceConfig:
    """Build a typed EmotivaXMC2DeviceConfig with the commands the tests exercise."""
    commands = {
        "power_on": StandardCommandConfig(
            action="power_on",
            params=[CommandParameterDefinition(name="zone", type="integer", required=False, default=1)],
        ),
        "power_off": StandardCommandConfig(
            action="power_off",
            params=[CommandParameterDefinition(name="zone", type="integer", required=False, default=1)],
        ),
        "set_volume": StandardCommandConfig(
            action="set_volume",
            params=[
                CommandParameterDefinition(name="level", type="range", required=True, min=-96.0, max=0.0),
                CommandParameterDefinition(name="zone", type="integer", required=False, default=1),
            ],
        ),
        "mute_toggle": StandardCommandConfig(
            action="mute_toggle",
            params=[CommandParameterDefinition(name="zone", type="integer", required=False, default=1)],
        ),
        "set_input": StandardCommandConfig(
            action="set_input",
            params=[CommandParameterDefinition(name="input", type="string", required=True)],
        ),
    }
    return EmotivaXMC2DeviceConfig(
        device_id="test_processor",
        device_name="Test XMC2 Processor",
        device_class="EMotivaXMC2",
        config_class="EmotivaXMC2DeviceConfig",
        emotiva=EmotivaConfig(
            host="192.168.1.100",
            port=7002,
            mac="AA:BB:CC:DD:EE:FF",
            update_interval=60,
            timeout=5.0,
            max_retries=3,
            retry_delay=2.0,
            force_connect=False,
        ),
        commands=commands,
    )


@pytest.fixture
def fake_client():
    """An AsyncMock standing in for pymotivaxmc2.EmotivaController."""
    client = AsyncMock()
    client.power_on = AsyncMock()
    client.power_off = AsyncMock()
    client.set_volume = AsyncMock()
    client.mute = AsyncMock()
    client.select_input = AsyncMock()
    client.select_source = AsyncMock()
    client.get_input_names = AsyncMock(return_value={1: {"name": "ZAPPITI", "visible": True}})
    client.status = AsyncMock(return_value={})
    client.subscribe = AsyncMock()
    client.unsubscribe = AsyncMock()
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def device(fake_client):
    """EMotivaXMC2 with fake_client pre-wired and state.connected=True (no setup() run)."""
    d = EMotivaXMC2(_make_config(), mqtt_client=MagicMock())
    d.client = fake_client
    d.state.connected = True
    # Seed plausible power state so handlers don't try to re-synchronize via the client.
    d.state.power = PowerState.OFF
    d.state.zone2_power = PowerState.OFF
    return d


# --- power_on / power_off ---------------------------------------------------


@pytest.mark.asyncio
async def test_power_on_main_zone_calls_client_power_on(device, fake_client):
    result = await device.handle_power_on(device.config.commands["power_on"], {"zone": 1})
    fake_client.power_on.assert_awaited()
    # The call should have included the main zone (Zone.MAIN from pymotivaxmc2.enums).
    call_kwargs = fake_client.power_on.call_args.kwargs
    assert "zone" in call_kwargs
    assert result["success"] is True


@pytest.mark.asyncio
async def test_power_on_zone2_calls_client_power_on(device, fake_client):
    result = await device.handle_power_on(device.config.commands["power_on"], {"zone": 2})
    fake_client.power_on.assert_awaited()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_power_off_main_zone_calls_client_power_off(device, fake_client):
    device.state.power = PowerState.ON
    result = await device.handle_power_off(device.config.commands["power_off"], {"zone": 1})
    fake_client.power_off.assert_awaited()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_power_off_zone2_calls_client_power_off(device, fake_client):
    device.state.zone2_power = PowerState.ON
    result = await device.handle_power_off(device.config.commands["power_off"], {"zone": 2})
    fake_client.power_off.assert_awaited()
    assert result["success"] is True


# --- set_volume -------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_volume_main_zone_calls_client_set_volume(device, fake_client):
    result = await device.handle_set_volume(device.config.commands["set_volume"], {"level": -30.0, "zone": 1})
    fake_client.set_volume.assert_awaited()
    args, kwargs = fake_client.set_volume.call_args
    # set_volume is called as set_volume(level, zone=zone)
    assert args[0] == -30.0
    assert "zone" in kwargs
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_volume_rejects_out_of_range(device, fake_client):
    # max is 0.0, so 5.0 must fail validation.
    result = await device.handle_set_volume(device.config.commands["set_volume"], {"level": 5.0, "zone": 1})
    assert result["success"] is False
    fake_client.set_volume.assert_not_awaited()


# --- mute -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mute_toggle_main_zone(device, fake_client):
    result = await device.handle_mute_toggle(device.config.commands["mute_toggle"], {"zone": 1})
    fake_client.mute.assert_awaited()
    assert result["success"] is True


# --- set_input --------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_input_calls_client_select_source(device, fake_client):
    """set_input selects the logical source via select_source(N) (powered on)."""
    device.state.power = PowerState.ON
    result = await device.handle_set_input(device.config.commands["set_input"], {"input": "source1"})
    fake_client.select_source.assert_awaited_once_with(1)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_input_refused_when_powered_off(device, fake_client):
    """When power=OFF, set_input is refused (semantic safeguard from the driver)."""
    device.state.power = PowerState.OFF
    result = await device.handle_set_input(device.config.commands["set_input"], {"input": "source1"})
    assert result["success"] is False
    fake_client.select_source.assert_not_awaited()
