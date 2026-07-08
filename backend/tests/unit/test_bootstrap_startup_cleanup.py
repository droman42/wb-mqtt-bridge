"""OPS-8: defensive startup-failure cleanup.

The lifespan startup is wrapped — an unexpected mid-startup error releases the
already-acquired resources (best effort) and re-raises instead of leaking an open
SQLite handle / connected MQTT client / device sockets into a hung process.
These tests pin the release helper's contract: every step guarded, a failing
release neither masks the original error nor stops the remaining releases.

(The companion OPS-8 wiring — WB virtual cards marked offline at shutdown while
MQTT is still connected — is composition-root glue over the already-tested
`WBVirtualDeviceService.cleanup_wb_device`; see test_wb_virtual_device_service.)
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from wb_mqtt_bridge.app.bootstrap import _release_partial_startup


@pytest.mark.asyncio
async def test_release_all_none_is_a_noop():
    """Failure before anything was acquired: nothing to release, no crash."""
    await _release_partial_startup(None, None, None, None)


@pytest.mark.asyncio
async def test_release_covers_every_acquired_resource():
    task = MagicMock()
    dm = MagicMock()
    dm.shutdown_devices = AsyncMock()
    mqtt = MagicMock()
    mqtt.disconnect = AsyncMock()
    store = MagicMock()
    store.close = AsyncMock()

    await _release_partial_startup(task, dm, mqtt, store)

    task.cancel.assert_called_once()
    dm.shutdown_devices.assert_awaited_once()
    mqtt.disconnect.assert_awaited_once()
    store.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_release_continues_past_failing_steps():
    """A raising release step must not stop the remaining releases (or raise)."""
    dm = MagicMock()
    dm.shutdown_devices = AsyncMock(side_effect=RuntimeError("boom"))
    mqtt = MagicMock()
    mqtt.disconnect = AsyncMock(side_effect=OSError("socket gone"))
    store = MagicMock()
    store.close = AsyncMock()

    await _release_partial_startup(None, dm, mqtt, store)

    dm.shutdown_devices.assert_awaited_once()
    mqtt.disconnect.assert_awaited_once()
    store.close.assert_awaited_once()  # reached despite both earlier failures
