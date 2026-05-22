"""Fresh tests for AuralicDevice, written against the post-hexagonal-refactor driver.

These tests target the public action-handler surface of AuralicDevice without
running setup(). setup() launches an async update loop and instantiates an
openhomedevice client that doesn't cleanly tear down inside pytest-asyncio —
the prior tests hung at collection because of those side-effects. We instead:

  - Construct the device with a typed AuralicDeviceConfig
  - Inject a fake `openhome_device` directly (the driver's only external dep)
  - Flip state.connected to True to satisfy the handlers' connectivity gate
  - Drive handle_* methods directly and assert on observable side-effects
    (state mutations + the calls made on the openhome mock)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.auralic.driver import AuralicDevice
from wb_mqtt_bridge.infrastructure.config.models import (
    AuralicDeviceConfig,
    AuralicConfig,
    StandardCommandConfig,
)


pytestmark = pytest.mark.integration


def _make_config() -> AuralicDeviceConfig:
    return AuralicDeviceConfig(
        device_id="test_auralic",
        device_name="Test Auralic",
        device_class="AuralicDevice",
        config_class="AuralicDeviceConfig",
        commands={
            "power_on": StandardCommandConfig(action="power_on"),
            "power_off": StandardCommandConfig(action="power_off"),
            "play": StandardCommandConfig(action="play"),
            "pause": StandardCommandConfig(action="pause"),
            "stop": StandardCommandConfig(action="stop"),
            "next": StandardCommandConfig(action="next"),
            "previous": StandardCommandConfig(action="previous"),
            "set_volume": StandardCommandConfig(action="set_volume"),
            "volume_up": StandardCommandConfig(action="volume_up"),
            "volume_down": StandardCommandConfig(action="volume_down"),
            "mute": StandardCommandConfig(action="mute"),
        },
        auralic=AuralicConfig(
            ip_address="192.168.1.100",
            update_interval=30,
            discovery_mode=False,
            device_url=None,
        ),
    )


@pytest.fixture
def fake_openhome():
    """An AsyncMock standing in for OpenHomeDevice.

    Provides concrete return values for the methods AuralicDevice._update_device_state
    awaits, so post-action state refreshes don't pollute AuralicDeviceState with
    raw coroutine/AsyncMock objects (which would then fail Pydantic validation).
    """
    oh = AsyncMock()
    # Action methods (no return value needed)
    oh.play = AsyncMock()
    oh.pause = AsyncMock()
    oh.stop = AsyncMock()
    oh.skip = AsyncMock()           # handle_next uses skip(), not next()
    oh.set_volume = AsyncMock()
    oh.increase_volume = AsyncMock()
    oh.decrease_volume = AsyncMock()
    oh.set_mute = AsyncMock()
    oh.set_standby = AsyncMock()
    oh.set_source = AsyncMock()
    # State-fetch methods used by _update_device_state — must return concrete values.
    oh.transport_state = AsyncMock(return_value="Playing")
    oh.is_in_standby = AsyncMock(return_value=False)
    oh.track_info = AsyncMock(return_value={
        "title": "T", "artist": "A", "album": "Al",
    })
    oh.volume = AsyncMock(return_value=50)
    oh.is_muted = AsyncMock(return_value=False)
    oh.sources = AsyncMock(return_value=[{"name": "Spotify", "type": "digital"}])
    oh.source = AsyncMock(return_value=0)
    return oh


@pytest.fixture
def device(fake_openhome):
    """An AuralicDevice with the openhome dependency pre-wired (no setup() call)."""
    cfg = _make_config()
    d = AuralicDevice(cfg, mqtt_client=MagicMock())
    d.openhome_device = fake_openhome
    d.state.connected = True
    return d


# --- Playback handlers -------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_play_invokes_openhome_play(device, fake_openhome):
    result = await device.handle_play(device.config.commands["play"], {})
    fake_openhome.play.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_pause_invokes_openhome_pause(device, fake_openhome):
    result = await device.handle_pause(device.config.commands["pause"], {})
    fake_openhome.pause.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_stop_invokes_openhome_stop(device, fake_openhome):
    result = await device.handle_stop(device.config.commands["stop"], {})
    fake_openhome.stop.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_next_invokes_openhome_skip(device, fake_openhome):
    """handle_next maps to openhome.skip() (the openhomedevice lib has no next())."""
    result = await device.handle_next(device.config.commands["next"], {})
    fake_openhome.skip.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_previous_returns_unsupported(device, fake_openhome):
    """handle_previous is intentionally unsupported (openhomedevice has no previous())."""
    result = await device.handle_previous(device.config.commands["previous"], {})
    assert result["success"] is False
    # And nothing on the openhome client should have been called.
    fake_openhome.previous.assert_not_awaited() if hasattr(fake_openhome, "previous") else None


# --- Volume handlers ---------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_set_volume_clamps_and_persists(device, fake_openhome):
    """set_volume forwards the value to openhome; the post-call state refresh stores it."""
    # After the call, _update_device_state runs and re-reads volume from openhome.
    # We set the openhome.volume mock to return 42 so the refreshed state shows 42.
    fake_openhome.volume = AsyncMock(return_value=42)
    result = await device.handle_set_volume(device.config.commands["set_volume"], {"volume": 42})
    fake_openhome.set_volume.assert_awaited_once_with(42)
    assert result["success"] is True
    assert device.state.volume == 42


@pytest.mark.asyncio
async def test_handle_set_volume_clamps_out_of_range(device, fake_openhome):
    """Values >100 / <0 are clamped to the valid range before being sent to openhome."""
    fake_openhome.volume = AsyncMock(return_value=100)
    await device.handle_set_volume(device.config.commands["set_volume"], {"volume": 150})
    fake_openhome.set_volume.assert_awaited_once_with(100)


@pytest.mark.asyncio
async def test_handle_set_volume_missing_param(device, fake_openhome):
    """Without 'volume' (or legacy 'level') a friendly success=False is returned."""
    result = await device.handle_set_volume(device.config.commands["set_volume"], {})
    assert result["success"] is False
    fake_openhome.set_volume.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_volume_up_calls_increase(device, fake_openhome):
    result = await device.handle_volume_up(device.config.commands["volume_up"], {})
    fake_openhome.increase_volume.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_volume_down_calls_decrease(device, fake_openhome):
    result = await device.handle_volume_down(device.config.commands["volume_down"], {})
    fake_openhome.decrease_volume.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_mute_toggles(device, fake_openhome):
    """mute() flips the cached mute state and informs openhome accordingly."""
    device.state.mute = False
    await device.handle_mute(device.config.commands["mute"], {})
    fake_openhome.set_mute.assert_awaited_once()
    args, _ = fake_openhome.set_mute.call_args
    # First arg is the new mute target — toggled from False to True.
    assert args[0] is True


# --- Disconnect guard --------------------------------------------------------


@pytest.mark.asyncio
async def test_handlers_fail_gracefully_when_openhome_missing(device, fake_openhome):
    """When openhome_device is None, handlers return success=False with a clear error."""
    device.openhome_device = None

    result = await device.handle_play(device.config.commands["play"], {})

    assert result["success"] is False
    assert "not connected" in (result.get("error") or "").lower()
