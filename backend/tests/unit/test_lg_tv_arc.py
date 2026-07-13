"""Tests for the LG TV's handle_set_input_source(arc) → handle_home translation.

Symmetric src_port mechanism (reconciler-side, 2026-05-30): when the audio topology
link from the LG TV uses src_port="arc" AND the input capability declares
source_modes=["arc"], the reconciler emits set_input_source(source="arc"). The
driver translates that to "be on internal mode" — which on webOS means pressing
Home (no native API for "go to internal mode"; the home / any non-HDMI source
satisfies the precondition for the eMotiva's HDMI ARC auto-engagement).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from locveil_bridge.infrastructure.devices.lg_tv.driver import LgTv
from locveil_bridge.infrastructure.config.models import (
    LgTvConfig,
    LgTvDeviceConfig,
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
            "set_input_source": StandardCommandConfig(
                action="set_input_source",
                params=[CommandParameterDefinition(name="source", type="string", required=True)],
            ),
            "home": StandardCommandConfig(action="home"),
        },
    )


@pytest.fixture
def driver() -> LgTv:
    d = LgTv(_make_config(), mqtt_client=MagicMock())
    # Stub handle_home so we don't try to talk to a real webOS API.
    d.handle_home = AsyncMock(
        return_value={"success": True, "message": "Home button pressed"}
    )
    return d


@pytest.mark.asyncio
async def test_set_input_source_arc_calls_handle_home(driver: LgTv):
    """set_input_source(source='arc') is the synthetic value from the reconciler's
    symmetric src_port path. Driver translates to handle_home (TV internal mode)."""
    cmd = driver.config.commands["set_input_source"]
    result = await driver.handle_set_input_source(cmd, {"source": "arc"})

    driver.handle_home.assert_awaited_once()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_input_source_arc_does_not_call_input_control(driver: LgTv):
    """set_input_source(arc) must NOT hit the webOS input switching API — there's no
    'arc' input on the TV side; the value is a synthetic token meaning 'be on internal
    mode'. Routes to handle_home before any input_control lookup runs."""
    driver.input_control = MagicMock()
    driver.input_control.set_input = AsyncMock()
    driver.state.connected = True

    cmd = driver.config.commands["set_input_source"]
    await driver.handle_set_input_source(cmd, {"source": "arc"})

    driver.input_control.set_input.assert_not_called()
    driver.handle_home.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_input_source_non_arc_still_uses_input_control(driver: LgTv):
    """Regular set_input_source(HDMI_1) must NOT route through handle_home — only the
    'arc' value triggers the home-button translation."""
    driver.client = MagicMock()
    driver.input_control = MagicMock()
    driver.input_control.set_input = AsyncMock(return_value={"returnValue": True})
    driver.source_control = MagicMock()
    driver.state.connected = True
    driver._cached_input_sources = [{"id": "HDMI_1", "label": "HDMI 1"}]

    cmd = driver.config.commands["set_input_source"]
    await driver.handle_set_input_source(cmd, {"source": "HDMI_1"})

    driver.handle_home.assert_not_called()
    driver.input_control.set_input.assert_awaited_once()
