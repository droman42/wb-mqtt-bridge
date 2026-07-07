"""Regression tests for the eMotiva XMC-2 notification-driven state path
(post 2026-05-30 cleanup, pymotivaxmc2 0.6.9).

After dropping the post-ack optimistic writes for volume + main-zone power_on,
state.volume / state.power / state.input_source / etc. are populated ONLY by
the notification path:

  pymotivaxmc2 dispatches @on(prop) callbacks for:
    (a) the initial values from the subscribe() response (new in 0.6.9)
    (b) every subsequent <emotivaNotify> packet from the device

  Each callback calls EMotivaXMC2._handle_property_change(prop_name, None, value)
  which converts the raw value, maps it to the right state field, and calls
  self.update_state(**) → chokepoint.

These tests verify the notification path directly. They also lock in that:
  - handle_set_volume no longer optimistically writes state.volume (the previous
    belt-and-suspenders pattern is gone)
  - The unreachable mute branches in _handle_property_change / _process_property_value
    are removed (mute is never pushed by the device per protocol §4.2)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.emotiva_xmc2.driver import EMotivaXMC2, PowerState
from wb_mqtt_bridge.infrastructure.config.models import (
    EmotivaXMC2DeviceConfig,
    CommandParameterDefinition,
    StandardCommandConfig,
)
from wb_mqtt_bridge.infrastructure.config.models import EmotivaConfig as AppEmotivaConfig


pytestmark = pytest.mark.unit


def _make_config() -> EmotivaXMC2DeviceConfig:
    return EmotivaXMC2DeviceConfig(
        device_id="processor",
        names={"ru": "Test eMotiva", "en": "Test eMotiva"},
        device_class="EMotivaXMC2",
        config_class="EmotivaXMC2DeviceConfig",
        emotiva=AppEmotivaConfig(host="192.168.1.100"),
        commands={
            "power_on": StandardCommandConfig(action="power_on"),
            "power_off": StandardCommandConfig(action="power_off"),
            "set_volume": StandardCommandConfig(
                action="set_volume",
                params=[
                    CommandParameterDefinition(name="level", type="range", min=-96.0, max=0.0, required=True),
                    CommandParameterDefinition(name="zone", type="integer", min=1, max=2, required=False),
                ],
            ),
            "mute_toggle": StandardCommandConfig(
                action="mute_toggle",
                params=[CommandParameterDefinition(name="zone", type="integer", min=1, max=2, required=False)],
            ),
            "set_input": StandardCommandConfig(
                action="set_input",
                params=[CommandParameterDefinition(name="input", type="string", required=True)],
            ),
        },
    )


@pytest.fixture
def device() -> EMotivaXMC2:
    d = EMotivaXMC2(_make_config(), mqtt_client=MagicMock())
    d.client = MagicMock()  # not None → handlers won't trigger reconnect
    d.state.connected = True
    # Wire async client methods
    d.client.set_volume = AsyncMock()
    d.client.power_on = AsyncMock()
    d.client.power_off = AsyncMock()
    d.client.mute = AsyncMock()
    return d


# --- _handle_property_change: the new single update path -------------------


def test_handle_property_change_power(device: EMotivaXMC2):
    device._handle_property_change("power", None, "On")
    assert device.state.power == PowerState.ON


def test_handle_property_change_zone2_power(device: EMotivaXMC2):
    device._handle_property_change("zone2_power", None, "Off")
    assert device.state.zone2_power == PowerState.OFF


def test_handle_property_change_volume(device: EMotivaXMC2):
    device._handle_property_change("volume", None, "-30.0")
    assert device.state.volume == -30.0


def test_handle_property_change_zone2_volume(device: EMotivaXMC2):
    device._handle_property_change("zone2_volume", None, "-25.0")
    assert device.state.zone2_volume == -25.0


def test_handle_property_change_source_with_token_mapping(device: EMotivaXMC2):
    """SOURCE notifications carry the device's source NAME; the driver translates
    via _source_token to a canonical 'sourceN' for input_source state."""
    device._source_index_by_name = {"zappiti": 1}
    device._handle_property_change("source", None, "ZAPPITI")
    assert device.state.input_source == "source1"


def test_handle_property_change_source_unknown_name_falls_back(device: EMotivaXMC2):
    """Unknown source name falls back to the stripped raw name (no token translation).
    Distinguished from 'HDMI ARC' which has a dedicated mapping to 'arc' — see
    test_source_token_maps_hdmi_arc_to_arc below."""
    device._handle_property_change("source", None, "Some Vendor Source")
    assert device.state.input_source == "Some Vendor Source"


# --- The dead mute branches must stay dead --------------------------------


def test_handle_property_change_mute_is_a_noop(device: EMotivaXMC2):
    """Emotiva protocol §4.2 has no notification for `mute` — pymotivaxmc2's Property
    enum correctly omits it. If a synthetic 'mute' property name ever gets dispatched
    here, the handler must NOT update state.mute (which is owned by handle_mute_toggle
    optimistically). Guards against cargo-culted re-addition of the dead branch."""
    device.state.mute = False  # pre-existing optimistic value
    device._handle_property_change("mute", None, "On")
    assert device.state.mute is False  # unchanged — no notification path for mute


def test_handle_property_change_zone2_mute_is_a_noop(device: EMotivaXMC2):
    """Same as above for zone 2."""
    device.state.zone2_mute = True
    device._handle_property_change("zone2_mute", None, "Off")
    assert device.state.zone2_mute is True


# --- Command handlers no longer optimistically write the value fields -----


@pytest.mark.asyncio
async def test_handle_set_volume_does_not_optimistically_write_volume(device: EMotivaXMC2):
    """set_volume sends the command and returns success — but state.volume is NOT
    updated until the device's Volume notification arrives via _handle_property_change."""
    device.state.volume = None  # pre-call state
    result = await device.handle_set_volume(
        device.config.commands["set_volume"], {"level": -30.0, "zone": 1}
    )
    assert result["success"] is True
    device.client.set_volume.assert_awaited_once()
    # The optimistic write is gone — state.volume should NOT have been written by the handler.
    assert device.state.volume is None


@pytest.mark.asyncio
async def test_handle_set_volume_zone2_does_not_optimistically_write_zone2_volume(
    device: EMotivaXMC2,
):
    device.state.zone2_power = PowerState.ON
    device.state.zone2_volume = None
    result = await device.handle_set_volume(
        device.config.commands["set_volume"], {"level": -25.0, "zone": 2}
    )
    assert result["success"] is True
    device.client.set_volume.assert_awaited_once()
    assert device.state.zone2_volume is None


@pytest.mark.asyncio
async def test_handle_power_on_main_zone_does_not_optimistically_write_power(
    device: EMotivaXMC2,
):
    """Main-zone power_on relies on the device's notification + post-command refresh
    path to update state.power. No optimistic write in the handler."""
    device.state.power = PowerState.OFF
    # Stub the post-command subscribe + refresh path so they don't actually run.
    device.client.subscribe = AsyncMock()
    device._refresh_device_state = AsyncMock(return_value={})
    result = await device.handle_power_on(
        device.config.commands["power_on"], {"zone": 1}
    )
    assert result["success"] is True
    device.client.power_on.assert_awaited_once()
    # Optimistic write is gone — state.power stays OFF until the notification arrives
    # (the stubbed _refresh_device_state didn't fire any notification).
    assert device.state.power == PowerState.OFF


# --- Mute KEEPS the optimistic write (protocol-impossible read-back) ------


@pytest.mark.asyncio
async def test_handle_mute_toggle_does_optimistically_write_mute(device: EMotivaXMC2):
    """Emotiva protocol §4.2 has no `mute` notification — the device never reports
    its mute state. handle_mute_toggle is the ONLY source of truth for state.mute,
    so the optimistic write MUST stay here. Guards against accidental removal in a
    future cleanup pass."""
    device.state.mute = False
    result = await device.handle_mute_toggle(
        device.config.commands["mute_toggle"], {"zone": 1}
    )
    assert result["success"] is True
    device.client.mute.assert_awaited_once()
    assert device.state.mute is True  # optimistic write happened


# --- HDMI ARC handling (set_input(arc) + _source_token mapping) -----------


def test_source_token_maps_hdmi_arc_to_arc(device: EMotivaXMC2):
    """The device reports its source name as 'HDMI ARC' (rack-verified). _source_token
    translates that to the canonical 'arc' token used by topology + reconciler. Without
    this mapping, state.input_source stays 'HDMI ARC' and reconciler's already_satisfied
    check fails forever (target='arc' != state='HDMI ARC' → power-cycle on every pass)."""
    assert device._source_token("HDMI ARC") == "arc"
    assert device._source_token("HDMI ARC ") == "arc"  # trim whitespace
    # Configured Input buttons still map via the source_index_by_name path
    device._source_index_by_name = {"zappiti": 1}
    assert device._source_token("ZAPPITI") == "source1"
    # Unknown names fall back to stripped raw
    assert device._source_token("Some Other Source") == "Some Other Source"


@pytest.mark.asyncio
async def test_handle_set_input_arc_routes_to_power_cycle(device: EMotivaXMC2):
    """set_input(arc) must NOT call select_source (which would fail — arc isn't 1-8);
    it must trigger the power-cycle workaround. Command.ARC was rack-verified to hang
    the device (2026-05-30), so power-cycle is the only safe path."""
    device.state.power = PowerState.ON
    device.state.input_source = "source2"

    # Stub the power_cycle helper so we don't actually sleep in the test
    device._power_cycle_for_arc = AsyncMock(
        return_value={"success": True, "input": "arc", "message": "Power-cycled for HDMI ARC engagement"}
    )

    cmd = device.config.commands["set_input"]
    result = await device.handle_set_input(cmd, {"input": "arc"})

    device._power_cycle_for_arc.assert_awaited_once()
    device.client.select_source.assert_not_called()  # no source_N command
    assert result["success"] is True
    assert result["input"] == "arc"


@pytest.mark.asyncio
async def test_power_cycle_for_arc_short_circuits_when_already_arc(device: EMotivaXMC2):
    """If state.input_source is already 'arc', no power-cycle. Guards against the
    cycle firing on every reconciler pass when ARC is already engaged (would
    otherwise be unbearable — the eMotiva would cycle 30+ seconds on every scenario
    activation when nothing needs to change)."""
    device.state.power = PowerState.ON
    device.state.input_source = "arc"

    result = await device._power_cycle_for_arc()

    assert result["success"] is True
    device.client.power_off.assert_not_called()
    device.client.power_on.assert_not_called()


@pytest.mark.asyncio
async def test_power_cycle_for_arc_emits_off_then_on_when_powered(device: EMotivaXMC2):
    """When the eMotiva is on and on a different source, power-cycle = off → sleep → on.
    Sleep is short-circuited to 0 in the test."""
    import asyncio as _asyncio
    device.state.power = PowerState.ON
    device.state.input_source = "source2"

    # short-circuit the 3s sleep
    real_sleep = _asyncio.sleep
    sleep_calls = []
    async def fast_sleep(s):
        sleep_calls.append(s)
        await real_sleep(0)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_asyncio, "sleep", fast_sleep)
        result = await device._power_cycle_for_arc()

    device.client.power_off.assert_awaited_once()
    device.client.power_on.assert_awaited_once()
    assert sleep_calls and sleep_calls[0] >= 1.0  # confirms the standby wait
    assert result["success"] is True
    assert result["input"] == "arc"


@pytest.mark.asyncio
async def test_power_cycle_for_arc_skips_power_off_when_already_off(device: EMotivaXMC2):
    """If the eMotiva is already off, no need for power_off first — just power_on,
    and rely on auto-engagement of ARC on power-up."""
    import asyncio as _asyncio
    device.state.power = PowerState.OFF
    device.state.input_source = None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_asyncio, "sleep", AsyncMock())
        result = await device._power_cycle_for_arc()

    device.client.power_off.assert_not_called()
    device.client.power_on.assert_awaited_once()
    assert result["success"] is True


# --- DRV-11: the XMC-2 pads short negative volumes with a space ---------------
# Observed live at the rack 2026-07-07: the device notified
# zone2_volume = '- 3.0' (space after the sign for values shorter than the
# field width). Plain float() raised and the converter silently fell back to
# 0.0 — the bridge showed 0 dB while the hardware sat at -3.0 dB. Any zone's
# volume in the -9.9..-0.1 range hits the same form.


def test_handle_property_change_volume_space_padded(device: EMotivaXMC2):
    device._handle_property_change("volume", None, "- 5.0")
    assert device.state.volume == -5.0


def test_handle_property_change_zone2_volume_space_padded(device: EMotivaXMC2):
    device._handle_property_change("zone2_volume", None, "- 3.0")
    assert device.state.zone2_volume == -3.0


def test_process_property_value_unparseable_volume_falls_back(device: EMotivaXMC2):
    assert device._process_property_value("volume", "garbage") == 0.0
