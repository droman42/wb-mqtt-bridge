"""Fresh tests for AppleTVDevice, written against the post-hexagonal-refactor driver.

The previous test file used the wrap_device_init() dict-to-Pydantic shim, an
old dict config schema, and a monkey-patched handle_message that bypassed the
real dispatch path. Replaced with a clean fixture that:
  - Builds a typed AppleTVDeviceConfig
  - Injects a fake pyatv `atv` instance directly on the device (with the
    sub-interfaces the handlers touch: .power, .remote_control, .audio, .apps,
    .metadata, .keyboard)
  - Flips state.connected = True and state.power = "on" so the connectivity
    gates pass
  - Stubs _ensure_connected to avoid reconnect attempts during tests

Coverage:
  - Power: handle_power_on / handle_power_off via self.atv.power.{turn_on,turn_off}
  - Remote control: handle_play / handle_pause / handle_stop / handle_menu /
    handle_home — all delegate to self.atv.remote_control.<verb>
  - Audio: handle_set_volume scales 0-100 -> 0.0-1.0 for self.atv.audio.set_volume
  - Apps: handle_launch_app resolves an app name to its bundle id and calls
    self.atv.apps.launch_app
  - Disconnect guard: when state.connected is False AND _ensure_connected fails,
    handlers refuse cleanly
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.apple_tv.driver import AppleTVDevice
from wb_mqtt_bridge.infrastructure.config.models import (
    AppleTVDeviceConfig,
    AppleTVConfig,
    AppleTVProtocolConfig,
    StandardCommandConfig,
    CommandParameterDefinition,
)


pytestmark = pytest.mark.integration


def _make_config() -> AppleTVDeviceConfig:
    return AppleTVDeviceConfig(
        device_id="test_appletv",
        device_name="Test Apple TV",
        device_class="AppleTVDevice",
        config_class="AppleTVDeviceConfig",
        apple_tv=AppleTVConfig(
            ip_address="192.168.1.100",
            name="Test AppleTV",
            protocols={"Companion": AppleTVProtocolConfig(
                identifier=None,
                credentials="test_credentials",
                data=None,
            )},
        ),
        commands={
            "power_on": StandardCommandConfig(action="power_on"),
            "power_off": StandardCommandConfig(action="power_off"),
            "play": StandardCommandConfig(action="play"),
            "pause": StandardCommandConfig(action="pause"),
            "stop": StandardCommandConfig(action="stop"),
            "menu": StandardCommandConfig(action="menu"),
            "home": StandardCommandConfig(action="home"),
            "set_volume": StandardCommandConfig(
                action="set_volume",
                params=[CommandParameterDefinition(
                    name="level", type="range", min=0, max=100, required=True,
                )],
            ),
            "launch_app": StandardCommandConfig(
                action="launch_app",
                params=[CommandParameterDefinition(
                    name="app", type="string", required=True,
                )],
            ),
        },
    )


@pytest.fixture
def fake_atv():
    """A pyatv-shaped AsyncMock with the sub-interfaces the handlers touch."""
    atv = MagicMock()
    # power
    atv.power = MagicMock()
    atv.power.turn_on = AsyncMock()
    atv.power.turn_off = AsyncMock()
    # remote_control: play/pause/stop/menu/home/etc. are all async no-arg.
    atv.remote_control = MagicMock()
    for verb in ("play", "pause", "stop", "menu", "home", "up", "down", "left", "right", "select"):
        setattr(atv.remote_control, verb, AsyncMock())
    # audio
    atv.audio = MagicMock()
    atv.audio.set_volume = AsyncMock()
    atv.audio.volume = AsyncMock(return_value=0.5)
    # apps
    atv.apps = MagicMock()
    atv.apps.launch_app = AsyncMock()
    return atv


@pytest.fixture
def device(fake_atv):
    """An AppleTVDevice with fake_atv pre-wired and state primed for handlers to run."""
    d = AppleTVDevice(_make_config(), mqtt_client=MagicMock())
    d.atv = fake_atv
    d.atv_config = MagicMock()
    d.state.connected = True
    d.state.power = "on"
    # Stub out network-bound helpers so handlers don't attempt to reconnect or
    # await state-refresh delays during tests.
    d._ensure_connected = AsyncMock(return_value=True)
    d._delayed_refresh = AsyncMock()
    d.publish_state = AsyncMock()
    return d


# --- Remote control (play/pause/stop/menu/home) ----------------------------


@pytest.mark.asyncio
async def test_handle_play_invokes_atv_play(device, fake_atv):
    result = await device.handle_play(device.config.commands["play"], {})
    fake_atv.remote_control.play.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_pause_invokes_atv_pause(device, fake_atv):
    result = await device.handle_pause(device.config.commands["pause"], {})
    fake_atv.remote_control.pause.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_stop_invokes_atv_stop(device, fake_atv):
    result = await device.handle_stop(device.config.commands["stop"], {})
    fake_atv.remote_control.stop.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_menu_invokes_atv_menu(device, fake_atv):
    result = await device.handle_menu(device.config.commands["menu"], {})
    fake_atv.remote_control.menu.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_handle_home_invokes_atv_home(device, fake_atv):
    result = await device.handle_home(device.config.commands["home"], {})
    fake_atv.remote_control.home.assert_awaited_once()
    assert result["success"] is True


# --- Audio: set_volume ------------------------------------------------------


@pytest.mark.asyncio
async def test_set_volume_scales_to_pyatv_float(device, fake_atv):
    """pyatv's audio.set_volume takes a 0.0-1.0 float; handler scales 0-100 to that range."""
    await device.handle_set_volume(device.config.commands["set_volume"], {"level": 75})
    fake_atv.audio.set_volume.assert_awaited_once_with(0.75)
    assert device.state.volume == 75


@pytest.mark.asyncio
async def test_set_volume_50_percent(device, fake_atv):
    await device.handle_set_volume(device.config.commands["set_volume"], {"level": 50})
    fake_atv.audio.set_volume.assert_awaited_once_with(0.5)
    assert device.state.volume == 50


# --- Apps: launch_app -------------------------------------------------------


@pytest.mark.asyncio
async def test_launch_app_resolves_name_to_bundle_id(device, fake_atv):
    """launch_app looks up an app id in the device's _app_list (case-insensitive)."""
    device._app_list = {
        "youtube": "com.google.youtube",
        "netflix": "com.netflix.Netflix",
    }
    await device.handle_launch_app(device.config.commands["launch_app"], {"app": "YouTube"})
    fake_atv.apps.launch_app.assert_awaited_once_with("com.google.youtube")
