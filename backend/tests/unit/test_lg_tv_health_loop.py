"""Tests for the LG TV close-callback + health-loop wiring (2026-05-30, asyncwebostv 0.3.5).

Covers:
  - _on_websocket_close flips connected=False (and clears subscription flag) on remote close.
  - _on_websocket_close is a no-op during shutdown (so intentional teardown doesn't churn state).
  - _on_websocket_close does NOT touch `power` (transient hiccup ambiguity).
  - _tcp_probe returns True on a successful TCP open + close.
  - _tcp_probe returns False on timeout / OSError.
  - _health_loop dispatches correctly across the 4 state combinations (connected × reachable).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from locveil_bridge.infrastructure.devices.lg_tv.driver import LgTv
from locveil_bridge.infrastructure.config.models import (
    LgTvConfig,
    LgTvDeviceConfig,
    StandardCommandConfig,
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
            reconnect_interval=15,
        ),
        commands={
            "power_on": StandardCommandConfig(action="power_on"),
            "power_off": StandardCommandConfig(action="power_off"),
        },
    )


@pytest.fixture
def driver() -> LgTv:
    return LgTv(_make_config(), mqtt_client=MagicMock())


# --- _on_websocket_close ------------------------------------------------------


@pytest.mark.asyncio
async def test_on_websocket_close_marks_disconnected(driver: LgTv):
    driver.update_state(connected=True, power="on")
    driver._subscriptions_active = True

    await driver._on_websocket_close()

    assert driver.state.connected is False
    assert driver._subscriptions_active is False
    # power untouched — could be a hiccup, not a real off
    assert driver.state.power == "on"


@pytest.mark.asyncio
async def test_on_websocket_close_noop_during_shutdown(driver: LgTv):
    driver.update_state(connected=True, power="on")
    driver._subscriptions_active = True
    driver._shutting_down = True

    await driver._on_websocket_close()

    # Nothing should change while we're tearing down on purpose.
    assert driver.state.connected is True
    assert driver._subscriptions_active is True


# --- _tcp_probe ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_tcp_probe_returns_true_on_open(driver: LgTv):
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    reader = MagicMock()

    async def fake_open(host, port):
        return reader, writer

    with patch("asyncio.open_connection", side_effect=fake_open):
        assert await driver._tcp_probe() is True
    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_tcp_probe_returns_false_on_timeout(driver: LgTv):
    async def hang(host, port):
        await asyncio.sleep(10)

    with patch("asyncio.open_connection", side_effect=hang):
        assert await driver._tcp_probe(timeout=0.05) is False


@pytest.mark.asyncio
async def test_tcp_probe_returns_false_on_oserror(driver: LgTv):
    async def refuse(host, port):
        raise OSError("Connection refused")

    with patch("asyncio.open_connection", side_effect=refuse):
        assert await driver._tcp_probe() is False


@pytest.mark.asyncio
async def test_tcp_probe_returns_false_when_no_ip(driver: LgTv):
    driver.update_state(ip_address=None)
    assert await driver._tcp_probe() is False


# --- _health_loop state machine ----------------------------------------------


def _stop_after_one_tick(driver: LgTv):
    """Force the loop to exit after one iteration by flipping _shutting_down
    just before the sleep, and short-circuit asyncio.sleep so the test is fast."""
    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds):
        driver._shutting_down = True
        await original_sleep(0)

    return patch("asyncio.sleep", side_effect=fast_sleep)


@pytest.mark.asyncio
async def test_health_loop_reconnects_when_disconnected_and_reachable(driver: LgTv):
    driver.update_state(connected=False, power="off")
    driver.connect = AsyncMock(return_value=True)

    with patch.object(driver, "_tcp_probe", AsyncMock(return_value=True)), _stop_after_one_tick(driver):
        await driver._health_loop()

    driver.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_loop_marks_off_when_connected_but_unreachable(driver: LgTv):
    """Safety net: library callback didn't fire (or already-dead at boot), but TCP probe
    sees the TV is gone. Loop must flip connected=False + power=off and not call connect()."""
    driver.update_state(connected=True, power="on")
    driver._subscriptions_active = True
    driver.connect = AsyncMock()

    with patch.object(driver, "_tcp_probe", AsyncMock(return_value=False)), _stop_after_one_tick(driver):
        await driver._health_loop()

    assert driver.state.connected is False
    assert driver.state.power == "off"
    assert driver._subscriptions_active is False
    driver.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_loop_noop_when_connected_and_reachable(driver: LgTv):
    driver.update_state(connected=True, power="on")
    driver.connect = AsyncMock()

    with patch.object(driver, "_tcp_probe", AsyncMock(return_value=True)), _stop_after_one_tick(driver):
        await driver._health_loop()

    # No reconnect, no state change.
    driver.connect.assert_not_awaited()
    assert driver.state.connected is True
    assert driver.state.power == "on"


@pytest.mark.asyncio
async def test_health_loop_ensures_power_off_when_unreachable_and_disconnected(driver: LgTv):
    """After the close callback flips connected=False but leaves power alone, the next
    health-loop tick with a failing probe must reconcile power to 'off'."""
    driver.update_state(connected=False, power="on")  # the mid-state right after the callback
    driver.connect = AsyncMock()

    with patch.object(driver, "_tcp_probe", AsyncMock(return_value=False)), _stop_after_one_tick(driver):
        await driver._health_loop()

    assert driver.state.power == "off"
    driver.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_loop_exits_on_cancel(driver: LgTv):
    """asyncio.CancelledError must break the loop, not be swallowed by the bare except."""
    driver.update_state(connected=True)

    with patch.object(driver, "_tcp_probe", AsyncMock(side_effect=asyncio.CancelledError)):
        # _health_loop catches CancelledError internally (breaks the while loop) — so
        # awaiting it should complete without re-raising.
        await driver._health_loop()
