"""DRV-5: the reserved `force` param bypasses IDEMPOTENCE guards (never availability
guards), and every guarded skip carries the structured marker the UI's
re-tap-to-force affordance keys on (`data.skipped_reason = "idempotence"`) plus
`data.no_op = True` (so a wait:true canonical call short-circuits instead of
503-ing the echo wait — an idempotence skip never fires update_state).

One regression per guarded handler, per the DRV-5 inventory:
  WirenboardIRDevice  power_on / power_off        (IR, one-way — the desync trap)
  EMotivaXMC2         power_on / power_off / set_input / set_volume / ARC cycle
  AuralicDevice       power_on                     (live-query guard, LOW value)
  LgTv                power_on                     (DRV-10 guard)
plus the base plumbing: idempotence_skip() itself and the reserved-param
pass-through in _resolve_and_validate_params.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.devices.wirenboard_ir_device.driver import WirenboardIRDevice
from wb_mqtt_bridge.infrastructure.devices.emotiva_xmc2.driver import EMotivaXMC2, PowerState
from wb_mqtt_bridge.infrastructure.devices.auralic.driver import AuralicDevice
from wb_mqtt_bridge.infrastructure.devices.lg_tv.driver import LgTv
from wb_mqtt_bridge.infrastructure.config.models import (
    WirenboardIRDeviceConfig,
    IRCommandConfig,
    EmotivaXMC2DeviceConfig,
    EmotivaConfig,
    AuralicDeviceConfig,
    AuralicConfig,
    LgTvDeviceConfig,
    LgTvConfig,
    StandardCommandConfig,
    CommandParameterDefinition,
)


pytestmark = pytest.mark.integration

SKIP_MARKER = {"no_op": True, "skipped_reason": "idempotence"}


def _assert_skip(result):
    """A guarded skip: success, nothing actuated, and the DRV-5 marker present."""
    assert result["success"] is True
    assert result["data"] == SKIP_MARKER


# --- base plumbing -----------------------------------------------------------


def _ir_config() -> WirenboardIRDeviceConfig:
    def cmd(action: str, rom: str) -> IRCommandConfig:
        return IRCommandConfig(
            action=action,
            topic=f"/devices/test_ir/controls/{action}",
            location="wb-msw-v3_207",
            rom_position=rom,
            group="power",
            description=action,
        )

    return WirenboardIRDeviceConfig(
        device_id="test_ir",
        names={"ru": "Test IR", "en": "Test IR"},
        device_class="WirenboardIRDevice",
        config_class="WirenboardIRDeviceConfig",
        commands={"power_on": cmd("power_on", "26"), "power_off": cmd("power_off", "27")},
    )


@pytest_asyncio.fixture
async def ir_device():
    mqtt = MagicMock()
    mqtt.publish = AsyncMock(return_value=True)
    d = WirenboardIRDevice(_ir_config(), mqtt)
    await d.setup()
    return d


def test_idempotence_skip_helper(ir_device):
    """The chokepoint helper: skip only when at target AND not forced."""
    # Not at target -> proceed.
    assert ir_device.idempotence_skip({}, False, "msg") is None
    # At target, no force -> marked skip.
    skip = ir_device.idempotence_skip({}, True, "msg")
    assert skip is not None
    _assert_skip(skip)
    assert skip["message"] == "msg"
    # At target but forced -> proceed. None params tolerated.
    assert ir_device.idempotence_skip({"force": True}, True, "msg") is None
    assert ir_device.idempotence_skip(None, False, "msg") is None
    # Extra fields ride along (the eMotiva zone= convention).
    skip = ir_device.idempotence_skip({}, True, "msg", zone=2)
    assert skip is not None and skip["zone"] == 2


def test_force_is_a_reserved_param(ir_device):
    """`force` survives validation even when a command declares params (only
    declared names are copied into the validated dict otherwise)."""
    defs = [CommandParameterDefinition(name="level", type="integer", required=True)]
    out = ir_device._resolve_and_validate_params(defs, {"level": 3, "force": True})
    assert out == {"level": 3, "force": True}
    # No declared params: raw pass-through already preserved it (regression pin).
    assert ir_device._resolve_and_validate_params([], {"force": True}) == {"force": True}


# --- WirenboardIRDevice: the desync trap (HIGH force value) -------------------


@pytest.mark.asyncio
async def test_ir_power_on_skip_and_force(ir_device):
    ir_device.update_state(power="on")

    result = await ir_device.execute_action("power_on", {})
    assert result["success"] is True
    assert result["data"] == SKIP_MARKER  # data flows through execute_action
    ir_device.mqtt_client.publish.assert_not_awaited()  # nothing sent

    result = await ir_device.execute_action("power_on", {"force": True})
    assert result["success"] is True
    ir_device.mqtt_client.publish.assert_awaited_once()  # IR fired despite state
    assert ir_device.state.power == "on"


@pytest.mark.asyncio
async def test_ir_power_off_skip_and_force(ir_device):
    ir_device.update_state(power="off")

    result = await ir_device.execute_action("power_off", {})
    assert result["success"] is True
    assert result["data"] == SKIP_MARKER
    ir_device.mqtt_client.publish.assert_not_awaited()

    result = await ir_device.execute_action("power_off", {"force": True})
    assert result["success"] is True
    ir_device.mqtt_client.publish.assert_awaited_once()
    assert ir_device.state.power == "off"


# --- EMotivaXMC2 ---------------------------------------------------------------


def _emotiva_config() -> EmotivaXMC2DeviceConfig:
    zone = CommandParameterDefinition(name="zone", type="integer", required=False, default=1)
    return EmotivaXMC2DeviceConfig(
        device_id="test_processor",
        names={"ru": "Test XMC2", "en": "Test XMC2"},
        device_class="EMotivaXMC2",
        config_class="EmotivaXMC2DeviceConfig",
        emotiva=EmotivaConfig(host="192.168.1.100"),
        commands={
            "power_on": StandardCommandConfig(action="power_on", params=[zone]),
            "power_off": StandardCommandConfig(action="power_off", params=[zone]),
            "set_volume": StandardCommandConfig(
                action="set_volume",
                params=[
                    CommandParameterDefinition(name="level", type="range", required=True, min=-96.0, max=0.0),
                    zone,
                ],
            ),
            "set_input": StandardCommandConfig(
                action="set_input",
                params=[CommandParameterDefinition(name="input", type="string", required=True)],
            ),
        },
    )


@pytest.fixture
def emotiva():
    d = EMotivaXMC2(_emotiva_config(), mqtt_client=MagicMock())
    d.client = AsyncMock()
    d.state.connected = True
    d.state.power = PowerState.OFF
    d.state.zone2_power = PowerState.OFF
    return d


@pytest.mark.asyncio
async def test_emotiva_power_on_skip_and_force(emotiva):
    emotiva.state.power = PowerState.ON

    result = await emotiva.handle_power_on(emotiva.config.commands["power_on"], {"zone": 1})
    _assert_skip(result)
    assert result["zone"] == 1
    emotiva.client.power_on.assert_not_awaited()

    result = await emotiva.handle_power_on(
        emotiva.config.commands["power_on"], {"zone": 1, "force": True}
    )
    assert result["success"] is True
    emotiva.client.power_on.assert_awaited_once()


@pytest.mark.asyncio
async def test_emotiva_power_off_skip_and_force(emotiva):
    emotiva.state.power = PowerState.OFF

    result = await emotiva.handle_power_off(emotiva.config.commands["power_off"], {"zone": 1})
    _assert_skip(result)
    emotiva.client.power_off.assert_not_awaited()

    result = await emotiva.handle_power_off(
        emotiva.config.commands["power_off"], {"zone": 1, "force": True}
    )
    assert result["success"] is True
    emotiva.client.power_off.assert_awaited_once()


@pytest.mark.asyncio
async def test_emotiva_set_input_skip_and_force(emotiva):
    emotiva.state.power = PowerState.ON
    emotiva.state.input_source = "source3"

    result = await emotiva.handle_set_input(
        emotiva.config.commands["set_input"], {"input": "source3"}
    )
    _assert_skip(result)
    emotiva.client.select_source.assert_not_awaited()

    result = await emotiva.handle_set_input(
        emotiva.config.commands["set_input"], {"input": "source3", "force": True}
    )
    assert result["success"] is True
    emotiva.client.select_source.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_emotiva_set_volume_skip_and_force(emotiva):
    emotiva.state.power = PowerState.ON
    emotiva.state.volume = -30.0

    result = await emotiva.handle_set_volume(
        emotiva.config.commands["set_volume"], {"level": -30.0, "zone": 1}
    )
    _assert_skip(result)
    emotiva.client.set_volume.assert_not_awaited()

    result = await emotiva.handle_set_volume(
        emotiva.config.commands["set_volume"], {"level": -30.0, "zone": 1, "force": True}
    )
    assert result["success"] is True
    emotiva.client.set_volume.assert_awaited_once()


@pytest.mark.asyncio
async def test_emotiva_arc_cycle_skip_and_force(emotiva):
    """The ARC power-cycle guard is idempotence too — believed 'arc' can be stale."""
    emotiva.state.power = PowerState.ON
    emotiva.state.input_source = "arc"

    result = await emotiva.handle_set_input(emotiva.config.commands["set_input"], {"input": "arc"})
    _assert_skip(result)
    emotiva.client.power_off.assert_not_awaited()

    result = await emotiva.handle_set_input(
        emotiva.config.commands["set_input"], {"input": "arc", "force": True}
    )
    assert result["success"] is True
    emotiva.client.power_off.assert_awaited()  # the off half of the off->on ARC cycle
    emotiva.client.power_on.assert_awaited()


# --- AuralicDevice --------------------------------------------------------------


@pytest.fixture
def auralic():
    config = AuralicDeviceConfig(
        device_id="streamer",
        names={"ru": "Test Auralic", "en": "Test Auralic"},
        device_class="AuralicDevice",
        config_class="AuralicDeviceConfig",
        auralic=AuralicConfig(ip_address="192.168.1.50", update_interval=10),
        commands={"power_on": StandardCommandConfig(action="power_on")},
    )
    d = AuralicDevice(config, mqtt_client=MagicMock())
    d._deep_sleep_mode = False
    d.openhome_device = AsyncMock()
    d.openhome_device.is_in_standby = AsyncMock(return_value=False)  # already on
    d._refresh_sources_cache = AsyncMock()
    d._update_device_state = AsyncMock()
    return d


@pytest.mark.asyncio
async def test_auralic_power_on_skip_and_force(auralic):
    result = await auralic.handle_power_on(auralic.config.commands["power_on"], {})
    _assert_skip(result)
    auralic.openhome_device.set_standby.assert_not_awaited()

    result = await auralic.handle_power_on(
        auralic.config.commands["power_on"], {"force": True}
    )
    assert result["success"] is True
    auralic.openhome_device.set_standby.assert_awaited_once_with(False)  # harmless idempotent target


# --- LgTv -------------------------------------------------------------------------


@pytest.fixture
def lg_tv():
    config = LgTvDeviceConfig(
        device_id="test_lg_tv",
        names={"ru": "Test LG TV", "en": "Test LG TV"},
        device_class="LgTv",
        config_class="LgTvDeviceConfig",
        tv=LgTvConfig(
            ip_address="192.168.1.101",
            mac_address="00:11:22:33:44:55",
            secure=False,
            client_key="test_key",
        ),
        commands={"power_on": StandardCommandConfig(action="power_on")},
    )
    d = LgTv(config, mqtt_client=MagicMock())
    d.client = AsyncMock()
    d.state.connected = True
    d.state.power = "on"
    return d


@pytest.mark.asyncio
async def test_lg_power_on_skip_and_force(lg_tv):
    result = await lg_tv.handle_power_on(lg_tv.config.commands["power_on"], {})
    _assert_skip(result)
    assert lg_tv.state.last_command.params == {"method": "already_on"}

    # Forced: the handler must delegate to power_on(force=True) — the guard inside
    # power_on() must not re-swallow it. Patch the method; the WebOS/WoL machinery
    # itself is exercised by the LG driver tests.
    lg_tv.power_on = AsyncMock(return_value=True)
    result = await lg_tv.handle_power_on(lg_tv.config.commands["power_on"], {"force": True})
    assert result["success"] is True
    lg_tv.power_on.assert_awaited_once_with(force=True)
