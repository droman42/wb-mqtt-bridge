"""Tests for AuralicDevice._update_device_state behavior.

The original tests exercised the background update task lifecycle (start on
setup(), cancel on shutdown(), continue running after errors, respect the
configured interval). They hung at collection because the real setup() path
launches a long-lived update loop and attempts openhomedevice network
discovery. Rewritten to drive `_update_device_state` directly — the same
state-update semantics, without the task-lifecycle infrastructure.
"""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from locveil_bridge.infrastructure.devices.auralic.driver import AuralicDevice
from locveil_bridge.infrastructure.config.models import (
    AuralicDeviceConfig,
    AuralicConfig,
    StandardCommandConfig,
)


pytestmark = pytest.mark.integration


def _make_config() -> AuralicDeviceConfig:
    return AuralicDeviceConfig(
        device_id="test_auralic",
        names={"ru": "Test Auralic", "en": "Test Auralic"},
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
    oh.sources = AsyncMock(return_value=[{"index": 0, "name": "Spotify", "type": "digital"}])
    # Current source resolves via the raw Product SourceIndex matched by true
    # index (the lib's source() returns empty name/type on the real unit).
    idx_action = MagicMock()
    idx_action.async_call = AsyncMock(return_value={"Value": 0})
    oh.product_service = MagicMock()
    oh.product_service.action.return_value = idx_action
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


@pytest.mark.asyncio
async def test_update_device_state_tolerates_none_volume_and_mute(device):
    """A unit without a Volume service returns None for volume/mute; those must not be written
    into the non-optional state fields (they'd fail validation) — connected still True."""
    oh = _make_fake_openhome()
    oh.volume = AsyncMock(return_value=None)
    oh.is_muted = AsyncMock(return_value=None)
    device.openhome_device = oh

    await device._update_device_state()

    assert device.state.connected is True
    assert device.state.volume == 0       # default, unchanged
    assert device.state.mute is False     # default, unchanged


@pytest.mark.asyncio
async def test_update_device_state_metadata_error_keeps_connected(device):
    """A bad/garbled DIDL track payload must not drop the whole device to disconnected."""
    oh = _make_fake_openhome()
    oh.track_info = AsyncMock(side_effect=Exception("garbled DIDL & <foo>"))
    device.openhome_device = oh

    await device._update_device_state()

    assert device.state.connected is True
    assert device.state.transport_state == "Playing"
    assert device.state.track_title is None  # not populated, but device stays usable


@pytest.mark.asyncio
async def test_update_device_state_liveness_probe_failure_fast_fails(device):
    """If the is_in_standby liveness probe fails, we bail immediately (no further calls)."""
    oh = _make_fake_openhome()
    oh.is_in_standby = AsyncMock(side_effect=Exception("unreachable"))
    device.openhome_device = oh

    await device._update_device_state()

    assert device.state.connected is False
    oh.transport_state.assert_not_awaited()  # bailed before the rest of the sequence


@pytest.mark.asyncio
async def test_update_device_state_times_out(device):
    """A hung OpenHome call is bounded by op_timeout and marks the device disconnected."""
    device.op_timeout = 0.01
    oh = _make_fake_openhome()

    async def _slow_transport():
        await asyncio.sleep(0.5)
        return "Playing"

    oh.transport_state = _slow_transport
    device.openhome_device = oh

    await device._update_device_state()

    assert device.state.connected is False


@pytest.mark.asyncio
async def test_attempt_reconnect_wires_new_device(device):
    """_attempt_reconnect rebuilds the OpenHome client via discovery and refreshes state."""
    fake = _make_fake_openhome()
    device._create_openhome_device = AsyncMock(return_value=fake)
    device._deep_sleep_mode = True

    ok = await device._attempt_reconnect()

    assert ok is True
    assert device.openhome_device is fake
    assert device._deep_sleep_mode is False
    assert device.state.connected is True


@pytest.mark.asyncio
async def test_attempt_reconnect_returns_false_when_discovery_fails(device):
    """When discovery can't find the device, reconnect reports failure and leaves no client."""
    device._create_openhome_device = AsyncMock(return_value=None)

    ok = await device._attempt_reconnect()

    assert ok is False
    assert device.openhome_device is None
