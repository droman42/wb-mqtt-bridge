"""End-to-end persistence integration tests.

Verifies that the DeviceManager + state_repository plumbing actually persists
device state to the SQLiteStateStore after actions and direct state updates.
The fine-grained SQLiteStateStore round-trip is covered in
tests/unit/test_state_store.py; here we exercise the wiring that connects
a BaseDevice -> DeviceManager._persist_state -> state_repository.save.
"""
import os
import sys
import pytest
import asyncio
import pytest_asyncio
from typing import Any, Dict, Optional

# Add the parent directory to sys.path for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the mock_sqlite module first to handle SQLite issues
from tests import mock_sqlite

# Skip all tests if aiosqlite is not available
if not mock_sqlite.HAS_AIOSQLITE:
    pytest.skip("aiosqlite is not available", allow_module_level=True)

from pydantic import Field
from wb_mqtt_bridge.infrastructure.persistence.sqlite import SQLiteStateStore
from wb_mqtt_bridge.domain.devices.service import DeviceManager
from wb_mqtt_bridge.infrastructure.config.models import (
    BaseCommandConfig,
    WirenboardIRDeviceConfig,
    IRCommandConfig,
)
from wb_mqtt_bridge.domain.devices.models import BaseDeviceState
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice


pytestmark = pytest.mark.integration


class _MockDeviceState(BaseDeviceState):
    """State model carrying a single test_value field."""
    test_value: Optional[str] = Field(default=None)


class _MockDevice(BaseDevice):
    """A minimal device whose actions update test_value on the state."""

    def __init__(self, config, mqtt_client=None, wb_service=None):
        super().__init__(config, mqtt_client, wb_service=wb_service)
        self.state = _MockDeviceState(
            device_id=self.device_id,
            device_name=self.device_name,
            test_value="initial",
        )

    async def setup(self) -> bool:
        return True

    async def shutdown(self) -> bool:
        return True

    async def handle_message(self, topic: str, payload: str):  # pragma: no cover - not exercised
        return None

    async def handle_test_action(self, cmd_config, params: Dict[str, Any] = None):
        """Handler discovered by BaseDevice._auto_register_handlers (handle_<action>)."""
        params = params or {}
        self.update_state(test_value=params.get("test_value", "default"))
        return self.create_command_result(success=True, message="ok")


def _make_config(device_id: str = "test_device") -> WirenboardIRDeviceConfig:
    return WirenboardIRDeviceConfig(
        device_id=device_id,
        names={"ru": "Test Persistence Device", "en": "Test Persistence Device"},
        device_class="_MockDevice",
        config_class="WirenboardIRDeviceConfig",
        commands={
            "test_action": IRCommandConfig(
                action="test_action",
                topic=f"/devices/{device_id}/controls/test_action",
                location="test_location",
                rom_position="1",
            ),
        },
    )


@pytest_asyncio.fixture
async def env():
    """Build a real DeviceManager wired to an in-memory SQLiteStateStore."""
    store = SQLiteStateStore(db_path=":memory:")
    await store.initialize()

    dm = DeviceManager(state_repository=store)
    # Register our local device class without going through entry_points.
    dm.device_classes["_MockDevice"] = _MockDevice
    await dm.initialize_devices({"test_device": _make_config()})

    try:
        yield dm, store
    finally:
        await dm.shutdown_devices()
        await store.close()


@pytest.mark.asyncio
async def test_state_persistence_on_action(env):
    """perform_action -> handler updates state -> state is persisted to the store."""
    dm, store = env
    device_id = "test_device"

    assert device_id in dm.devices

    result = await dm.perform_action(
        device_id=device_id,
        action="test_action",
        params={"test_value": "updated_by_action"},
    )

    assert result["success"] is True

    # Local state mutated.
    assert dm.devices[device_id].get_current_state().test_value == "updated_by_action"

    # Allow the persistence task scheduled by update_state to complete.
    await asyncio.sleep(0.1)

    persisted = await store.get(f"device:{device_id}")
    assert persisted is not None
    assert persisted["test_value"] == "updated_by_action"


@pytest.mark.asyncio
async def test_state_persistence_on_direct_update(env):
    """device.update_state(...) also triggers persistence via the registered callback."""
    dm, store = env
    device_id = "test_device"

    dm.devices[device_id].update_state(test_value="updated_directly")

    await asyncio.sleep(0.1)

    persisted = await store.get(f"device:{device_id}")
    assert persisted is not None
    assert persisted["test_value"] == "updated_directly"


@pytest.mark.asyncio
async def test_state_round_trip_via_state_repository(env):
    """A device.update_state value can be read back via state_repository.load (the StateRepositoryPort alias for get)."""
    dm, store = env
    device_id = "test_device"

    dm.devices[device_id].update_state(test_value="before_reload")
    await asyncio.sleep(0.1)

    # load() is the StateRepositoryPort alias for get(); should observe the same dict.
    loaded = await store.load(f"device:{device_id}")
    assert loaded is not None
    assert loaded["test_value"] == "before_reload"
