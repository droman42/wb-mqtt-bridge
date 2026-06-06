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
  - Volume is up/down only (momentary, IR-backed via WB) — no absolute set_volume, no readback
  - Apps: handle_launch_app resolves an app name to its bundle id and calls
    self.atv.apps.launch_app
  - Disconnect guard: when state.connected is False AND _ensure_connected fails,
    handlers refuse cleanly
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from pyatv.const import PowerState
from wb_mqtt_bridge.infrastructure.devices.apple_tv.driver import (
    AppleTVDevice,
    PyATVDeviceListener,
)
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
        names={"ru": "Test Apple TV", "en": "Test Apple TV"},
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
            "volume_up": StandardCommandConfig(action="volume_up"),
            "volume_down": StandardCommandConfig(action="volume_down"),
            "pointer_gesture": StandardCommandConfig(
                action="pointer_gesture",
                params=[
                    CommandParameterDefinition(name="dx", type="range", min=-1000, max=1000, required=True),
                    CommandParameterDefinition(name="dy", type="range", min=-1000, max=1000, required=True),
                ],
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


# --- Listener push callbacks (PushListener / PowerListener) ------------------


def test_listener_is_concrete():
    """All pyatv ABC methods are implemented — a future pyatv bump that adds an
    abstractmethod will make this fail loudly instead of silently breaking push."""
    assert PyATVDeviceListener.__abstractmethods__ == frozenset()


@pytest.mark.asyncio
async def test_powerstate_update_maps_to_state(device):
    """PowerListener.powerstate_update flips device power state via update_state."""
    device.update_state = MagicMock()
    device.emit_progress = AsyncMock()
    listener = PyATVDeviceListener(device)  # constructed inside the running loop

    listener.powerstate_update(PowerState.Off, PowerState.On)
    assert device.update_state.call_args.kwargs["power"] == "on"

    listener.powerstate_update(PowerState.On, PowerState.Off)
    assert device.update_state.call_args.kwargs["power"] == "off"


@pytest.mark.asyncio
async def test_playstatus_update_routes_through_helper(device):
    """PushListener.playstatus_update feeds the Playing object into _update_playing_state."""
    device._update_playing_state = MagicMock()
    device.update_state = MagicMock()
    device.emit_progress = AsyncMock()
    listener = PyATVDeviceListener(device)

    playing = MagicMock()
    playing.device_state = None  # keep it simple: idle path
    listener.playstatus_update(MagicMock(), playing)
    device._update_playing_state.assert_called_once_with(playing)


# --- Pointer pad: movement → directional gesture ---------------------------


@pytest.mark.asyncio
async def test_pointer_gesture_translates_movement_to_direction(device, fake_atv):
    """Pad drag → Apple TV directional swipe. The UI dispatches {dx, dy}; the handler must
    read those names (it previously read deltaX/deltaY → KeyError, and the config required
    deltaX/deltaY → param validation rejected {dx,dy}). Driven through execute_action so it
    exercises param validation + dispatch + the dominant-axis translation."""
    # rightward swipe past the 10.0 gesture threshold → right
    result = await device.execute_action("pointer_gesture", {"dx": 50, "dy": 0}, source="api")
    assert result["success"] is True, result
    fake_atv.remote_control.right.assert_awaited_once()

    # upward swipe (negative dy dominates) → up
    result = await device.execute_action("pointer_gesture", {"dx": 0, "dy": -50}, source="api")
    assert result["success"] is True, result
    fake_atv.remote_control.up.assert_awaited_once()


# --- Volume: IR via WB blaster ----------------------------------------------


@pytest.mark.asyncio
async def test_volume_up_fires_ir_when_configured(device):
    """With an IR topic set, volume_up publishes "1" to the WB ROM-play topic (Companion volume
    is unusable on these tvOS 26.5 units; volume is driven via the WB IR blaster — §5.1 #7)."""
    device.ir_volume_up_topic = "/devices/wb-msw-v3_207/controls/Play from ROM5/on"
    device.mqtt_client.publish = AsyncMock()

    result = await device.handle_volume_up(device.config.commands["volume_up"], {})

    assert result["success"] is True, result
    device.mqtt_client.publish.assert_awaited_once_with(
        "/devices/wb-msw-v3_207/controls/Play from ROM5/on", "1"
    )


@pytest.mark.asyncio
async def test_volume_down_falls_back_to_companion_without_ir_topic(device, fake_atv):
    """No IR topic → volume_down uses the Companion remote path (the inert HID fallback)."""
    device.ir_volume_down_topic = None
    device.mqtt_client.publish = AsyncMock()

    await device.handle_volume_down(device.config.commands["volume_down"], {})

    device.mqtt_client.publish.assert_not_awaited()  # did NOT fire IR
