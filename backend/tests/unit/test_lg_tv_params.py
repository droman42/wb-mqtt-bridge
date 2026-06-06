"""Fresh tests for LgTv, written against the post-hexagonal-refactor driver.

The previous test file used the old dict-shaped config schema and asserted on
internal helpers / mock-attached methods that no longer fit the LgTv driver,
which delegates most actions through `_execute_media_command` against
`self.media`, `self.tv_control`, `self.input_control`, `self.app`, etc.,
populated from `self.client` during setup().

These tests bypass setup() entirely:
  - Construct LgTv with a typed LgTvDeviceConfig
  - Inject AsyncMock instances directly for self.client/media/tv_control/etc.
  - Flip state.connected = True
  - Drive handlers and assert delegation + state mutations
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.lg_tv.driver import LgTv
from wb_mqtt_bridge.infrastructure.config.models import (
    LgTvDeviceConfig,
    LgTvConfig,
    StandardCommandConfig,
    CommandParameterDefinition,
)


pytestmark = pytest.mark.integration


def _make_config() -> LgTvDeviceConfig:
    return LgTvDeviceConfig(
        device_id="test_lg_tv",
        names={"ru": "Test LG TV", "en": "Test LG TV"},
        device_class="LgTv",
        config_class="LgTvDeviceConfig",
        tv=LgTvConfig(
            ip_address="192.168.1.100",
            mac_address="00:11:22:33:44:55",
            broadcast_ip="192.168.1.255",
            secure=False,
            client_key="test_key",
        ),
        commands={
            "power_on": StandardCommandConfig(action="power_on"),
            "power_off": StandardCommandConfig(action="power_off"),
            "volume_up": StandardCommandConfig(action="volume_up"),
            "volume_down": StandardCommandConfig(action="volume_down"),
            "mute": StandardCommandConfig(action="mute"),
            "set_volume": StandardCommandConfig(
                action="set_volume",
                params=[CommandParameterDefinition(name="level", type="range", min=0, max=100, required=True)],
            ),
            "home": StandardCommandConfig(action="home"),
            "back": StandardCommandConfig(action="back"),
            "up": StandardCommandConfig(action="up"),
            "down": StandardCommandConfig(action="down"),
            "left": StandardCommandConfig(action="left"),
            "right": StandardCommandConfig(action="right"),
            "enter": StandardCommandConfig(action="enter"),
            "menu": StandardCommandConfig(action="menu"),
            "play": StandardCommandConfig(action="play"),
            "pause": StandardCommandConfig(action="pause"),
            "stop": StandardCommandConfig(action="stop"),
            "set_input_source": StandardCommandConfig(
                action="set_input_source",
                params=[CommandParameterDefinition(name="source", type="string", required=True)],
            ),
        },
    )


@pytest.fixture
def fake_media():
    """AsyncMock standing in for the WebOS MediaControl."""
    m = AsyncMock()
    m.volume_up = AsyncMock(return_value={})
    m.volume_down = AsyncMock(return_value={})
    m.set_mute = AsyncMock(return_value={})
    m.set_volume = AsyncMock(return_value={})
    m.play = AsyncMock(return_value={})
    m.pause = AsyncMock(return_value={})
    m.stop = AsyncMock(return_value={})
    m.get_volume = AsyncMock(return_value={"volume": 25, "muted": False})
    return m


@pytest.fixture
def fake_tv_control():
    """AsyncMock for TV navigation (home/back/menu)."""
    return AsyncMock()


@pytest.fixture
def fake_input_control():
    """AsyncMock for direction/click keys (up/down/left/right/enter/exit/...)."""
    return AsyncMock()


@pytest.fixture
def device(fake_media, fake_tv_control, fake_input_control):
    """LgTv with WebOS dependencies pre-wired and state.connected=True (no setup() run)."""
    d = LgTv(_make_config(), mqtt_client=MagicMock())
    d.client = AsyncMock()  # the WebOSTV instance
    d.media = fake_media
    d.tv_control = fake_tv_control
    d.input_control = fake_input_control
    d.app = AsyncMock()
    d.system = AsyncMock()
    d.source_control = AsyncMock()
    d.state.connected = True
    return d


# --- Media: volume + mute ---------------------------------------------------


@pytest.mark.asyncio
async def test_volume_up_calls_media_volume_up(device, fake_media):
    result = await device.handle_volume_up(device.config.commands["volume_up"], {})
    fake_media.volume_up.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_volume_down_calls_media_volume_down(device, fake_media):
    result = await device.handle_volume_down(device.config.commands["volume_down"], {})
    fake_media.volume_down.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_mute_toggle_calls_set_mute(device, fake_media):
    """Mute with no explicit state toggles based on current value pulled from media.get_volume()."""
    result = await device.handle_mute(device.config.commands["mute"], {})
    fake_media.set_mute.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_volume_calls_set_volume_with_int(device, fake_media):
    result = await device.handle_set_volume(device.config.commands["set_volume"], {"level": 42})
    fake_media.set_volume.assert_awaited_once_with(42)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_volume_rejects_missing_level(device, fake_media):
    result = await device.handle_set_volume(device.config.commands["set_volume"], {})
    assert result["success"] is False
    fake_media.set_volume.assert_not_awaited()


# --- Disconnect guard -------------------------------------------------------


@pytest.mark.asyncio
async def test_media_commands_fail_when_disconnected(device, fake_media):
    """If state.connected is False, _execute_media_command refuses and returns success=False."""
    device.state.connected = False

    result = await device.handle_volume_up(device.config.commands["volume_up"], {})

    assert result["success"] is False
    fake_media.volume_up.assert_not_awaited()


@pytest.mark.asyncio
async def test_media_commands_fail_when_media_missing(device, fake_media):
    """If self.media is None (setup not run), media commands return success=False."""
    device.media = None
    result = await device.handle_volume_up(device.config.commands["volume_up"], {})
    assert result["success"] is False


# --- Playback ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_calls_media_play(device, fake_media):
    result = await device.handle_play(device.config.commands["play"], {})
    fake_media.play.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_pause_calls_media_pause(device, fake_media):
    result = await device.handle_pause(device.config.commands["pause"], {})
    fake_media.pause.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_stop_calls_media_stop(device, fake_media):
    result = await device.handle_stop(device.config.commands["stop"], {})
    fake_media.stop.assert_awaited_once()
    assert result["success"] is True


# --- State observation ------------------------------------------------------


def test_initial_state_mirrors_config(device):
    """After construction, state reflects the config's tv block (ip_address, mac_address)."""
    assert device.state.device_id == "test_lg_tv"
    assert device.state.device_name == "Test LG TV"
    assert device.state.ip_address == "192.168.1.100"
    assert device.state.mac_address == "00:11:22:33:44:55"


def test_disconnected_state_flag_writable(device):
    """state.connected is a regular Pydantic field that can be toggled in tests."""
    device.state.connected = False
    assert device.state.connected is False
    device.state.connected = True
    assert device.state.connected is True


# ---------------------------------------------------------------------------
# Power-state subscription mapping
#
# The asyncwebostv 0.3.0 spec (docs/subscription_spec.md) ports the
# production-verified power-state value list from aiowebostv + aiopylgtv. Our
# `_lg_tv_is_on` helper must collapse those values to the binary on/off the
# driver state model uses. Lock the mapping in so a future "let me just add
# Suspend to the on-list" change can't silently drift.
#
# The driver wiring (subscribe_power_state → _on_power_state_change → update_state)
# is integration-shaped and verified at the rack; here we just pin the mapping.
# ---------------------------------------------------------------------------

import pytest as _pytest  # alias to avoid colliding with the existing `pytest` import


@_pytest.mark.parametrize(
    "raw_state,expected_on",
    [
        # Operational / accepts commands → ON
        ("Active",       True),
        ("Screen Off",   True),   # display off, system live, still accepts commands
        ("Screen Saver", True),
        # Off or standby / will not accept commands → OFF
        ("Power Off",      False),
        ("Suspend",        False),
        ("Active Standby", False),
        (None,             False),  # older webOS that doesn't implement the endpoint
        # Defensive: any unknown value (future webOS state we haven't characterised)
        # falls through to ON — see _LG_TV_OFF_STATES rationale.
        ("BrandNewState",  True),
        ("",               True),
    ],
)
def test_lg_tv_power_state_mapping(raw_state, expected_on):
    """Regression for _lg_tv_is_on. Values from asyncwebostv 0.3.0
    docs/subscription_spec.md "Power States"."""
    from wb_mqtt_bridge.infrastructure.devices.lg_tv.driver import _lg_tv_is_on
    assert _lg_tv_is_on(raw_state) is expected_on


# --- Input source: action-name + param contract regression ------------------


@pytest.mark.asyncio
async def test_set_input_source_action_resolves_and_switches(device):
    """Regression for the dispatch mismatch that silently 404'd LG input switching.

    The whole system (device config, LgTv capability `select.command`, the reconciler,
    and movie scenarios) uses action **set_input_source** with a **source** param. The
    driver handler must register under that exact name and read `source` — it previously
    was `handle_set_input` reading `params["input"]`, so `execute_action("set_input_source")`
    found no handler (manual UI switch AND scenario-driven HDMI switching both broke).

    Driven through execute_action (not the handler directly) so it exercises the action→
    handler resolution that was the actual bug. Asserts on the REAL asyncwebostv method
    (InputControl.set_input wrapping ssap://tv/switchInput) — the switch verb lives on
    InputControl, not SourceControl; the driver previously called a non-existent
    SourceControl.set_source_input.
    """
    device._cached_input_sources = [{"id": "HDMI_2", "label": "Emotiva XMC"}]
    device.input_control.set_input = AsyncMock(return_value={"returnValue": True})

    result = await device.execute_action("set_input_source", {"source": "HDMI_2"}, source="api")

    assert result["success"] is True, result
    device.input_control.set_input.assert_awaited_once_with("HDMI_2")
    assert device.state.input_source == "Emotiva XMC"
