"""A device whose setup() fails (off/unreachable/hung at boot) must stay registered.

Dropping it meant scenarios referencing it failed to load and the device was uncontrollable
until a full restart. Keeping it registered (disconnected) lets scenarios load, keeps the
device visible, and allows a later reconnect.
"""

from types import SimpleNamespace

import pytest

from locveil_bridge.domain.devices.service import DeviceManager


class _Dev:
    def __init__(self, config, mqtt_client=None, wb_service=None):
        self.config = config
        self.device_id = config.device_id

    def register_state_change_callback(self, cb):
        pass

    def get_current_state(self):
        return SimpleNamespace(device_id=self.device_id)


class _GoodDev(_Dev):
    async def setup(self):
        return True


class _BadDev(_Dev):
    async def setup(self):
        return False


class _RaisingDev(_Dev):
    async def setup(self):
        raise RuntimeError("device unreachable")


@pytest.mark.asyncio
async def test_failed_and_raising_setup_keep_device_registered():
    dm = DeviceManager(state_repository=None)
    dm.device_classes.update({"GoodDev": _GoodDev, "BadDev": _BadDev, "RaisingDev": _RaisingDev})

    await dm.initialize_devices({
        "good": SimpleNamespace(device_class="GoodDev", device_id="good"),
        "bad": SimpleNamespace(device_class="BadDev", device_id="bad"),
        "boom": SimpleNamespace(device_class="RaisingDev", device_id="boom"),
    })

    # All three remain registered — a failed/raising setup no longer drops the device.
    assert set(dm.devices) == {"good", "bad", "boom"}
    assert dm.get_device("bad") is not None
    assert dm.get_device("boom") is not None


def test_no_persistence_during_shutdown():
    """During shutdown the persist callback must skip — teardown states (disconnected/off)
    must not overwrite the assumed state the reconciler relies on. (Also: the old sync path
    here always raised 'event loop is already running'.)"""
    saved = []

    async def _save(*a, **k):
        saved.append(a)

    dm = DeviceManager(state_repository=SimpleNamespace(save=_save))
    dm.devices["d"] = SimpleNamespace(device_id="d", get_current_state=lambda: SimpleNamespace(device_id="d"))

    dm._shutting_down = True
    dm._persist_state_callback("d")  # shutdown path: must NOT persist

    assert saved == []
