"""Tests for AuralicDevice._update_device_state behavior.

The original tests exercised the background update task lifecycle (start on
setup(), cancel on shutdown(), continue running after errors, respect the
configured interval). They hung at collection because the real setup() path
launches a long-lived update loop and attempts openhomedevice network
discovery. Rewritten to drive `_update_device_state` directly — the same
state-update semantics, without the task-lifecycle infrastructure.
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
        },
        auralic=AuralicConfig(
            ip_address="192.168.1.100",
            update_interval=30,
            discovery_mode=False,
            device_url=None,
        ),
    )


def _make_fake_openhome():
    oh = AsyncMock()
    oh.transport_state = AsyncMock(return_value="Playing")
    oh.is_in_standby = AsyncMock(return_value=False)
    oh.track_info = AsyncMock(return_value={
        "title": "Track1", "artist": "Artist", "album": "Album",
    })
    oh.volume = AsyncMock(return_value=55)
    oh.is_muted = AsyncMock(return_value=False)
    oh.sources = AsyncMock(return_value=[{"name": "Spotify", "type": "digital"}])
    oh.source = AsyncMock(return_value=0)
    return oh


@pytest.fixture
def device():
    """An AuralicDevice with no openhome wired yet (tests inject as needed)."""
    return AuralicDevice(_make_config(), mqtt_client=MagicMock())


@pytest.mark.asyncio
async def test_update_device_state_when_openhome_missing_marks_disconnected(device):
    """If openhome_device is None, _update_device_state marks the device disconnected."""
    device.openhome_device = None
    await device._update_device_state()
    assert device.state.connected is False


@pytest.mark.asyncio
async def test_update_device_state_populates_state_from_openhome(device):
    """A normal pass through _update_device_state pulls every field off the openhome client."""
    device.openhome_device = _make_fake_openhome()

    await device._update_device_state()

    assert device.state.connected is True
    assert device.state.transport_state == "Playing"
    assert device.state.power == "on"          # is_in_standby=False -> "on"
    assert device.state.volume == 55
    assert device.state.mute is False
    assert device.state.source == "Spotify"
    assert device.state.track_title == "Track1"
    assert device.state.track_artist == "Artist"
    assert device.state.track_album == "Album"


@pytest.mark.asyncio
async def test_update_device_state_handles_openhome_errors(device):
    """If openhome raises mid-fetch, the state captures the error and marks disconnected.

    Semantic intent (preserved from the old test_update_task_error_handling): a
    transient device error should not crash the update path; it should surface
    via state.error and mark the device disconnected so subsequent reads know.
    """
    oh = _make_fake_openhome()
    oh.transport_state = AsyncMock(side_effect=Exception("Connection lost"))
    device.openhome_device = oh

    # Should not raise.
    await device._update_device_state()

    assert device.state.connected is False
    assert device.state.error is not None
    assert "Connection lost" in device.state.error
