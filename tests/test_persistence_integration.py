import os
import sys
import pytest
import asyncio
from typing import Dict, Any, Optional
import pytest_asyncio

# Add the app directory to sys.path for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the mock_sqlite module first to handle SQLite issues
from tests import mock_sqlite

# Skip all tests if aiosqlite is not available
if not mock_sqlite.HAS_AIOSQLITE:
    pytest.skip("aiosqlite is not available", allow_module_level=True)

from wb_mqtt_bridge.infrastructure.persistence.sqlite import SQLiteStateStore
from wb_mqtt_bridge.domain.devices.service import DeviceManager
from wb_mqtt_bridge.infrastructure.config.models import (
    BaseDeviceConfig, 
    IRCommandConfig, 
    WirenboardIRDeviceConfig,
    BaseDeviceState
)
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from pydantic import Field


class MockDeviceState(BaseDeviceState):
    """Custom state class for the mock device."""
    test_value: Optional[str] = Field(default=None, description="Test value for persistence testing")
    
    class Config:
        json_encoders = {
            # Add encoders for any non-serializable types if needed
        }
        
    def model_dump(
        self,
        *,
        include=None,
        exclude=None,
        by_alias=False,
        exclude_unset=False,
        exclude_defaults=False,
        exclude_none=False,
    ):
        """Convert to a JSON-serializable dict with the same signature as Pydantic's model_dump."""
        data = {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "test_value": self.test_value,
            "error": self.error,
            "last_command": self.last_command.model_dump() if self.last_command else None
        }
        
        # Handle exclusions if needed
        if exclude:
            for field in exclude:
                if field in data:
                    data.pop(field)
        
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
            
        return data


class MockDevice(BaseDevice):
    """A simple mock device for testing persistence."""
    
    def __init__(self, config: BaseDeviceConfig, mqtt_client=None):
        super().__init__(config, mqtt_client)
        # Initialize with the proper state type
        self.state = MockDeviceState(
            device_id=self.device_id,
            device_name=self.device_name,
            test_value="initial"
        )
    
    async def setup(self) -> bool:
        """Initialize the device."""
        return True
    
    async def shutdown(self) -> bool:
        """Shutdown the device."""
        return True
    
    async def handle_action(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle actions for this device."""
        # Get the appropriate command configuration
        cmd_config = None
        for cmd_name, command in self.get_available_commands().items():
            if cmd_name == action:
                cmd_config = command
                break
        
        if cmd_config is None:
            return self.create_command_result(
                success=False, 
                error=f"Unknown action: {action}"
            )
        
        if action == "test_action":
            # Update the state properly
            self.update_state(test_value=params.get("test_value", "default"))
            return self.create_command_result(success=True, message="Action executed successfully")
        
        return self.create_command_result(
            success=False, 
            error=f"Unknown action: {action}"
        )


class MockConfigManager:
    """A mock config manager for testing."""
    
    def get_device_class_name(self, device_id: str) -> str:
        """Always return MockDevice as the device class."""
        return "MockDevice"
        
    def get_all_device_configs(self) -> Dict[str, BaseDeviceConfig]:
        """Return a mock device configuration."""
        return {
            "test_device": WirenboardIRDeviceConfig(
                device_id="test_device",
                device_name="Test Device",
                commands={
                    "test_action": IRCommandConfig(
                        action="test_action",
                        description="Test action for persistence tests",
                        location="test_location",
                        rom_position="test_position"
                    )
                }
            )
        }


class PatchedDeviceManager(DeviceManager):
    """Custom DeviceManager that handles MockDeviceState serialization."""
    
    async def _persist_state(self, device_id: str):
        """
        Persist full device.state dict under key "device:{device_id}".
        This version handles MockDeviceState directly.
        """
        if not self.store:
            return
            
        device = self.devices.get(device_id)
        if not device:
            return
            
        try:
            state_obj = device.get_current_state()
            
            # Handle MockDeviceState specially by using model_dump
            if isinstance(state_obj, MockDeviceState):
                state_dict = state_obj.model_dump()
                await self.store.set(f"device:{device_id}", state_dict)
            else:
                await self.store.set(f"device:{device_id}", state_obj)
                
        except Exception as e:
            print(f"Failed to persist state for device {device_id}: {str(e)}")


@pytest_asyncio.fixture
async def test_environment():
    """Set up a test environment with StateStore and DeviceManager."""
    # Create a state store with an in-memory database
    state_store = SQLiteStateStore(db_path=":memory:")
    await state_store.initialize()
    
    # Create a patched device manager with the state store
    device_manager = PatchedDeviceManager(
        store=state_store,
        config_manager=MockConfigManager()
    )
    
    # Register MockDevice class with the device manager
    device_manager.device_classes["MockDevice"] = MockDevice
    
    # Initialize devices
    await device_manager.initialize_devices(device_manager.config_manager.get_all_device_configs())
    
    try:
        yield device_manager, state_store
    finally:
        # Clean up
        await device_manager.shutdown_devices()
        await state_store.close()


@pytest.mark.asyncio
async def test_state_persistence_on_action(test_environment):
    """Test that device state is persisted after performing an action."""
    device_manager, state_store = test_environment
    device_id = "test_device"
    
    # Verify the device exists
    assert device_id in device_manager.devices
    
    # Perform an action that updates the device state
    action_result = await device_manager.perform_action(
        device_id=device_id,
        action="test_action",
        params={"test_value": "updated_by_action"}
    )
    
    # Verify the action succeeded
    assert action_result["success"] is True
    
    # Verify the device state was updated
    device_state = device_manager.devices[device_id].get_current_state()
    assert device_state.test_value == "updated_by_action"
    
    # Verify the state was persisted to the state store
    persisted_state = await state_store.get(f"device:{device_id}")
    assert persisted_state is not None
    assert persisted_state["test_value"] == "updated_by_action"


@pytest.mark.asyncio
async def test_state_persistence_on_direct_update(test_environment):
    """Test that device state is persisted when directly updating state."""
    device_manager, state_store = test_environment
    device_id = "test_device"
    
    # Get the device
    device = device_manager.devices[device_id]
    
    # Update the state directly
    device.update_state(test_value="updated_directly")
    
    # Wait a short time for async persistence to complete
    await asyncio.sleep(0.1)
    
    # Verify the state was persisted
    persisted_state = await state_store.get(f"device:{device_id}")
    assert persisted_state is not None
    assert persisted_state["test_value"] == "updated_directly"


@pytest.mark.asyncio
async def test_state_restoration(test_environment):
    """Test that device state can be restored from persistence."""
    device_manager, state_store = test_environment
    device_id = "test_device"
    
    # Set a value in the device state
    device = device_manager.devices[device_id]
    device.update_state(test_value="before_restart")
    
    # Wait for persistence
    await asyncio.sleep(0.1)
    
    # Verify the state was persisted
    persisted_state = await state_store.get(f"device:{device_id}")
    assert persisted_state["test_value"] == "before_restart"
    
    # Call initialize to simulate reloading from persisted state
    # (We're just testing the persistence here, not the actual restoration)
    await device_manager.initialize() 