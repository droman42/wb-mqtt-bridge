"""VWB-18 parts 2+3: persisted device state is restored at boot (persist + restore + restart test).

Part 2: DeviceManager re-hydrates each device's assumed state from its `device:{id}` snapshot
inside initialize_devices(), per device BEFORE setup() — previously the restore was a logging
stub that ran after boot, by which point the post-setup initial persist had already clobbered
the last-good snapshot with boot defaults.

Part 3 (toggle-power inversion): with assumed state restored, the reconciler diff is a no-op
for a blind toggle-power device that was ON before the restart — pre-fix, assumed state reset
to the default 'off' and the power-on plan emitted a toggle that turned the live device OFF.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock

import pytest

from locveil_bridge.domain.devices.models import BaseDeviceState
from locveil_bridge.domain.devices.service import DeviceManager
from locveil_bridge.domain.scenarios.reconciler import _power_actions
from locveil_bridge.infrastructure.capabilities.loader import load_capability_map
from locveil_bridge.infrastructure.config.models import BaseDeviceConfig
from locveil_bridge.infrastructure.devices.base import BaseDevice

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
CAPS = ROOT / "config" / "capabilities"


class _RestoreState(BaseDeviceState):
    input_source: Optional[str] = None
    volume: int = 0


class _RestoreDevice(BaseDevice):
    """Minimal concrete BaseDevice with a driver-style state class; setup() records the
    power value it observes, so tests can assert restore ran BEFORE setup."""

    def __init__(self, config, mqtt_client=None, wb_service=None):
        super().__init__(config, mqtt_client, wb_service)
        self.state = _RestoreState(device_id=self.device_id, device_name=self.device_name)
        self.power_at_setup = None

    async def setup(self) -> bool:
        self.power_at_setup = self.state.power
        return True

    async def shutdown(self) -> bool:  # pragma: no cover - not exercised
        return True


class _FailingSetupDevice(_RestoreDevice):
    async def setup(self) -> bool:
        self.power_at_setup = self.state.power
        return False


def _config(device_id="rd"):
    return BaseDeviceConfig(
        device_id=device_id,
        names={"ru": "Restore Device", "en": "Restore Device"},
        device_class="RestoreDev",
        config_class="BaseDeviceConfig",
        commands={},
    )


class _Store:
    """In-memory StateRepositoryPort double."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    async def load(self, key):
        return self.data.get(key)

    async def save(self, key, value):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


def _manager(store, device_class=_RestoreDevice):
    dm = DeviceManager(state_repository=store)
    dm.device_classes["RestoreDev"] = device_class
    return dm


# ---------------------------------------------------------------------------
# BaseDevice.restore_state — field filtering + chokepoint
# ---------------------------------------------------------------------------


def test_restore_state_applies_known_fields_and_skips_identity_ephemeral_unknown():
    device = _RestoreDevice(_config())
    spy = Mock()
    device.register_state_change_callback(spy)

    applied = device.restore_state({
        # identity — never restored, comes from live config
        "device_id": "hijacked",
        "device_name": "hijacked",
        # ephemeral / stale bookkeeping — never restored
        "error": "stale error from last run",
        "last_command": {"action": "old", "source": "api", "timestamp": "2026-01-01T00:00:00"},
        # assumed state — restored
        "power": "on",
        "input_source": "cd",
        "volume": 30,
        # written by an older schema — silently dropped, must not fail the restore
        "vanished_field": 42,
    })

    assert applied == ["input_source", "power", "volume"]
    assert device.state.power == "on"
    assert device.state.input_source == "cd"
    assert device.state.volume == 30
    assert device.state.device_id == "rd"
    assert device.state.device_name == "Restore Device"
    assert device.state.error is None
    assert device.state.last_command is None
    # Restore rode the update_state chokepoint — persistence/WB callbacks saw the change.
    spy.assert_called_once()
    assert set(spy.call_args.args[1]) == {"power", "input_source", "volume"}


# ---------------------------------------------------------------------------
# DeviceManager — restore before setup(); boot persist no longer clobbers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_devices_restores_before_setup_and_boot_persist_keeps_snapshot():
    store = _Store({"device:rd": {"power": "on", "volume": 30}})
    dm = _manager(store)

    await dm.initialize_devices({"rd": _config()})

    device = dm.get_device("rd")
    assert device.power_at_setup == "on"  # restore ran BEFORE setup()
    assert device.state.power == "on"
    assert device.state.volume == 30

    # The post-setup initial persist wrote the RESTORED state back — pre-fix it clobbered
    # the last-good snapshot with boot defaults ('off') at every boot.
    await dm.wait_for_persistence_tasks()
    assert store.data["device:rd"]["power"] == "on"
    assert store.data["device:rd"]["volume"] == 30


@pytest.mark.asyncio
async def test_failed_setup_still_restores_and_preserves_snapshot():
    store = _Store({"device:rd": {"power": "on"}})
    dm = _manager(store, _FailingSetupDevice)

    await dm.initialize_devices({"rd": _config()})

    device = dm.get_device("rd")
    assert device is not None  # failed setup keeps the device registered
    assert device.state.power == "on"  # last-good assumed state re-hydrated anyway
    await dm.wait_for_persistence_tasks()
    assert store.data["device:rd"]["power"] == "on"


@pytest.mark.asyncio
async def test_corrupt_snapshot_degrades_to_defaults_without_blocking_init():
    store = _Store({"device:rd": {"power": "on", "volume": "not-an-int"}})
    dm = _manager(store)

    await dm.initialize_devices({"rd": _config()})

    device = dm.get_device("rd")
    assert device is not None
    assert device.state.power == "off"  # whole snapshot rejected → boot defaults
    assert device.state.volume == 0
    assert device.power_at_setup == "off"  # and setup still ran


# ---------------------------------------------------------------------------
# Restart round trip + part 3 (toggle-power inversion)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_round_trip_restores_assumed_state():
    """The QUAL-56 rule: persist + restore + a restart test ship together."""
    store = _Store()

    dm_a = _manager(store)
    await dm_a.initialize_devices({"rd": _config()})
    dm_a.get_device("rd").update_state(power="on", input_source="cd")
    await dm_a.wait_for_persistence_tasks()

    # "Restart": a fresh manager + fresh device instance on the same store.
    dm_b = _manager(store)
    await dm_b.initialize_devices({"rd": _config()})

    device = dm_b.get_device("rd")
    assert device.state.power == "on"
    assert device.state.input_source == "cd"


@pytest.mark.asyncio
async def test_restored_toggle_device_gets_no_power_toggle():
    """Part 3: mf_amplifier's power is toggle-only. With the assumed state restored to 'on',
    the reconciler's power-on pass emits NOTHING — pre-fix, the state reset to 'off' at boot
    and the pass emitted a toggle that would turn the actually-ON amplifier OFF."""
    cap = load_capability_map("WirenboardIRDevice", "mf_amplifier", CAPS).get("power")
    warnings = []

    # Restored assumed state → already satisfied, no action.
    assert _power_actions("mf_amplifier", cap, SimpleNamespace(power="on"), warnings) == []

    # Boot-default assumed state (the pre-fix situation) → a toggle IS emitted; on a live,
    # already-ON device that toggle is the inversion this task closes.
    actions = _power_actions("mf_amplifier", cap, SimpleNamespace(power="off"), warnings)
    assert len(actions) == 1
    assert actions[0].reason == "power on (toggle)"
    assert warnings == []
