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


# --- DRV-14: all-network power control (the halted state) ---------------------
# Live-verified ladder: on <-> standby via Product.SetStandby; standby <-> halted
# via HardwareConfig.SetHaltStatus. Halted = description reachable, Product
# absent, network up. The IR power path is gone.


def _halted_openhome(mock_standby_error: bool = False) -> MagicMock:
    d = MagicMock()
    d.product_service = None
    d.set_halt = AsyncMock()
    return d


@pytest.mark.asyncio
async def test_adopt_classifies_halted_device():
    device = _make_device()
    halted = _halted_openhome()

    assert await device._adopt_openhome_device(halted) is False

    assert device._deep_sleep_mode is True
    assert device.openhome_device is halted  # handle kept for the halt wake
    assert device.state.deep_sleep is True
    assert device.state.connected is False
    assert device.state.power == "off"


@pytest.mark.asyncio
async def test_adopt_connects_full_device():
    device = _make_device()
    full = MagicMock()
    full.product_service = MagicMock()
    device._update_device_state = AsyncMock()
    device._refresh_sources_cache = AsyncMock()

    assert await device._adopt_openhome_device(full) is True
    assert device._deep_sleep_mode is False
    device._update_device_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_power_on_wakes_halted_via_set_halt(monkeypatch):
    """Halted → rediscover fresh handle → SetHaltStatus(false) → adopt → standby exit.

    The wake is sent to a FRESHLY DISCOVERED handle, never the stored one —
    the halted unit's ports move on every transition (rack finding 13:11: the
    stored port was already dead and the wake call got connection-refused).
    """
    device = _make_device()
    stale = _halted_openhome()
    device.openhome_device = stale
    device._deep_sleep_mode = True

    fresh_halted = _halted_openhome()
    woken = MagicMock()
    woken.product_service = MagicMock()
    woken.is_in_standby = AsyncMock(return_value=True)
    woken.set_standby = AsyncMock()
    device._create_openhome_device = AsyncMock(side_effect=[fresh_halted, woken])
    device._update_device_state = AsyncMock()
    device._refresh_sources_cache = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_power_on(BaseCommandConfig(action="power_on"), {})

    assert result["success"] is True, result
    fresh_halted.set_halt.assert_awaited_once_with(False)
    stale.set_halt.assert_not_awaited()  # never the stale handle
    woken.set_standby.assert_awaited_once_with(False)
    assert device._deep_sleep_mode is False


@pytest.mark.asyncio
async def test_power_on_unreachable_fails_without_ir():
    device = _make_device()
    device.openhome_device = None
    device._deep_sleep_mode = False

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_power_on(BaseCommandConfig(action="power_on"), {})

    assert result["success"] is False
    assert "unreachable" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_power_off_full_goes_standby_then_halt():
    device = _make_device()
    full = MagicMock()
    full.product_service = MagicMock()
    full.transport_state = AsyncMock(return_value="Stopped")
    full.set_standby = AsyncMock()
    full.set_halt = AsyncMock()
    device.openhome_device = full
    device._deep_sleep_mode = False

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_power_off(BaseCommandConfig(action="power_off"), {})

    assert result["success"] is True, result
    full.set_standby.assert_awaited_once_with(True)
    full.set_halt.assert_awaited_once_with(True)
    assert device._deep_sleep_mode is True
    assert device.state.deep_sleep is True


@pytest.mark.asyncio
async def test_power_off_already_halted_is_noop():
    device = _make_device()
    device._deep_sleep_mode = True
    device.openhome_device = _halted_openhome()

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_power_off(BaseCommandConfig(action="power_off"), {})

    assert result["success"] is True
    device.openhome_device.set_halt.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_device_state_detects_halted_handle():
    device = _make_device()
    device.openhome_device = _halted_openhome()

    await device._update_device_state()

    assert device.state.connected is False
    assert device.state.deep_sleep is True


# --- DRV-14 follow-up: source options dialect + true device indices -----------
# The unit reports SourceXml with invisible sources occupying index slots;
# the library returns visible sources carrying their TRUE index. Options must
# emit input_id/input_name (the dialect the UI dropdown maps) with the true
# index, and set_input must select by that index — a filtered-list position
# would switch the wrong source (SetSourceIndex takes the raw index).


def _sources_fixture():
    # Mirrors the live ALTAIR G1: 'AES' is visible-position 5 but device-index 9.
    return [
        {"index": 0, "name": "Playlist", "type": "Playlist"},
        {"index": 2, "name": "AirPlay", "type": "AirPlay"},
        {"index": 9, "name": "AES", "type": "AES"},
    ]


@pytest.mark.asyncio
async def test_sources_cache_uses_ui_dialect_and_true_indices():
    device = _make_device()
    device.openhome_device = MagicMock()
    device.state.connected = True
    device.openhome_device.sources = AsyncMock(return_value=_sources_fixture())

    await device._refresh_sources_cache()

    assert device._sources_cache == [
        {"input_id": "0", "input_name": "Playlist", "type": "Playlist"},
        {"input_id": "2", "input_name": "AirPlay", "type": "AirPlay"},
        {"input_id": "9", "input_name": "AES", "type": "AES"},
    ]


@pytest.mark.asyncio
async def test_set_input_by_index_uses_true_device_index():
    device = _make_device()
    device.openhome_device = MagicMock()
    device.state.connected = True
    device.openhome_device.sources = AsyncMock(return_value=_sources_fixture())
    device.openhome_device.set_source = AsyncMock()
    device._update_device_state = AsyncMock()

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_set_input(BaseCommandConfig(action="set_input"), {"input": "9"})

    assert result["success"] is True, result
    device.openhome_device.set_source.assert_awaited_once_with(9)


@pytest.mark.asyncio
async def test_set_input_by_name_resolves_true_index():
    device = _make_device()
    device.openhome_device = MagicMock()
    device.state.connected = True
    device.openhome_device.sources = AsyncMock(return_value=_sources_fixture())
    device.openhome_device.set_source = AsyncMock()
    device._update_device_state = AsyncMock()

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_set_input(BaseCommandConfig(action="set_input"), {"input": "airplay"})

    assert result["success"] is True, result
    device.openhome_device.set_source.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_set_input_rejects_unknown_index():
    device = _make_device()
    device.openhome_device = MagicMock()
    device.state.connected = True
    device.openhome_device.sources = AsyncMock(return_value=_sources_fixture())

    from wb_mqtt_bridge.infrastructure.config.models import BaseCommandConfig
    result = await device.handle_set_input(BaseCommandConfig(action="set_input"), {"input": "5"})

    assert result["success"] is False
    assert "Invalid source index" in (result.get("error") or "")
