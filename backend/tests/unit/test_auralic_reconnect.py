"""DRV-12: the periodic loop must probe for the device even in deep-sleep mode.

Rack finding 2026-07-07: the streamer was asleep at backend startup, so setup()
set `_deep_sleep_mode = True` (a guess — "may be in deep sleep"). The old loop's
deep-sleep branch never probed ("power-on is the IR handler's job"), so a unit
woken out-of-band (front panel, the Auralic app) stayed invisible forever —
40 minutes with zero discovery attempts in the live log. The UI/IR power_on
handler schedules a delayed discovery, but nothing else did.

The fix: `_periodic_tick` probes on the `reconnect_interval` cadence in ALL
disconnected branches, deep sleep included.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.auralic.driver import AuralicDevice
from wb_mqtt_bridge.infrastructure.config.models import (
    AuralicDeviceConfig,
    AuralicConfig,
)


def _make_device() -> AuralicDevice:
    config = AuralicDeviceConfig(
        device_id="streamer",
        names={"ru": "Test Auralic", "en": "Test Auralic"},
        device_class="AuralicDevice",
        config_class="AuralicDeviceConfig",
        auralic=AuralicConfig(ip_address="192.168.1.50", update_interval=10),
        commands={},
    )
    return AuralicDevice(config, mqtt_client=MagicMock())


@pytest.mark.asyncio
async def test_deep_sleep_probes_on_reconnect_cadence():
    """Deep-sleep mode still attempts a cadenced rediscovery (the DRV-12 fix)."""
    device = _make_device()
    device._deep_sleep_mode = True
    device.openhome_device = None
    device._attempt_reconnect = AsyncMock()

    await device._periodic_tick(now=device.reconnect_interval + 1.0)

    device._attempt_reconnect.assert_awaited_once()
    # State stays honest while asleep
    assert device.state.connected is False
    assert device.state.deep_sleep is True


@pytest.mark.asyncio
async def test_deep_sleep_probe_respects_cadence():
    """Within the reconnect window no probe fires — the loop stays cheap."""
    device = _make_device()
    device._deep_sleep_mode = True
    device._attempt_reconnect = AsyncMock()

    t0 = device.reconnect_interval + 1.0
    await device._periodic_tick(now=t0)
    await device._periodic_tick(now=t0 + 1.0)  # 1 s later — inside the window

    device._attempt_reconnect.assert_awaited_once()

    await device._periodic_tick(now=t0 + device.reconnect_interval + 1.0)
    assert device._attempt_reconnect.await_count == 2


@pytest.mark.asyncio
async def test_never_connected_probes_on_cadence():
    """The offline-at-boot branch (no deep-sleep guess) also probes on cadence."""
    device = _make_device()
    device._deep_sleep_mode = False
    device.openhome_device = None
    device._attempt_reconnect = AsyncMock()

    await device._periodic_tick(now=device.reconnect_interval + 1.0)

    device._attempt_reconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_connected_device_polls_state_without_probe():
    """A healthy connection polls state and never fires discovery."""
    device = _make_device()
    device._deep_sleep_mode = False
    device.openhome_device = MagicMock()
    device._update_device_state = AsyncMock()
    device._attempt_reconnect = AsyncMock()
    device.state.connected = True

    await device._periodic_tick(now=device.reconnect_interval + 1.0)

    device._update_device_state.assert_awaited_once()
    device._attempt_reconnect.assert_not_awaited()


# --- DRV-13: raw-socket SSDP discovery (SsdpSearchListener received nothing) --


def test_extract_ssdp_locations_filters_by_ip_and_dedups():
    datagram = (
        b"HTTP/1.1 200 OK\r\n"
        b"CACHE-CONTROL: max-age=1800\r\n"
        b"LOCATION: http://192.168.1.50:36243/lightningRender-aa/Upnp/device.xml\r\n"
        b"SERVER: Posix/200809.0 UPnP/1.1 ohNet/1.0\r\n"
        b"ST: upnp:rootdevice\r\n\r\n"
    )
    other = (
        b"HTTP/1.1 200 OK\r\n"
        b"location: http://192.168.1.99:5000/desc.xml\r\n\r\n"
    )
    responses = [
        (datagram, "192.168.1.50"),
        (datagram, "192.168.1.50"),  # duplicate answer
        (other, "192.168.1.99"),     # wrong sender
    ]
    locs = AuralicDevice._extract_ssdp_locations(responses, "192.168.1.50")
    assert locs == ["http://192.168.1.50:36243/lightningRender-aa/Upnp/device.xml"]


def test_extract_ssdp_locations_rejects_location_host_mismatch():
    """A datagram relayed from the right sender but pointing elsewhere is dropped."""
    spoofed = (
        b"HTTP/1.1 200 OK\r\n"
        b"LOCATION: http://10.0.0.1:8080/desc.xml\r\n\r\n"
    )
    assert AuralicDevice._extract_ssdp_locations([(spoofed, "192.168.1.50")], "192.168.1.50") == []


def test_extract_ssdp_locations_tolerates_garbage():
    assert AuralicDevice._extract_ssdp_locations([(b"\xff\xfe garbage", "192.168.1.50")], "192.168.1.50") == []
