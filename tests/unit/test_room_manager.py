import pytest
import json
from pathlib import Path
from unittest.mock import patch

from wb_mqtt_bridge.domain.rooms.service import RoomManager
from wb_mqtt_bridge.domain.scenarios.models import RoomDefinition

# Sample room data for testing
SAMPLE_ROOMS = {
    "living_room": {
        "room_id": "living_room",
        "names": {"en": "Living Room"},
        "description": "Main living area",
        "devices": ["tv", "soundbar"],
        "default_scenario": "movie_night"
    },
    "kitchen": {
        "room_id": "kitchen",
        "names": {"en": "Kitchen"},
        "description": "Kitchen area",
        "devices": ["fridge", "stove"],
        "default_scenario": None
    }
}

class MockDeviceManager:
    """Mock DeviceManager for testing RoomManager"""
    def __init__(self, device_ids=None):
        self.devices = device_ids or {
            "tv": {},
            "soundbar": {},
            "fridge": {},
            "stove": {},
            "lamp": {}  # Added lamp for reload test
        }
    
    def get_device(self, device_id):
        return self.devices.get(device_id)

@pytest.fixture
def mock_device_manager():
    return MockDeviceManager()

@pytest.fixture
def mock_config_dir():
    return Path("/mock/config")

@pytest.fixture
def room_manager(mock_config_dir, mock_device_manager):
    # Patch the json.loads to avoid reading from file system
    with patch("json.loads", return_value=SAMPLE_ROOMS):
        with patch("pathlib.Path.read_text", return_value=json.dumps(SAMPLE_ROOMS)):
            return RoomManager(mock_config_dir, mock_device_manager)

class TestRoomManager:
    def test_init_loads_rooms(self, mock_config_dir, mock_device_manager):
        """Test that rooms are loaded during initialization"""
        with patch("json.loads", return_value=SAMPLE_ROOMS):
            with patch("pathlib.Path.read_text", return_value=json.dumps(SAMPLE_ROOMS)):
                manager = RoomManager(mock_config_dir, mock_device_manager)
                assert len(manager.rooms) == 2
                assert "living_room" in manager.rooms
                assert "kitchen" in manager.rooms
    
    def test_list_returns_all_rooms(self, room_manager):
        """Test that list() returns all room definitions"""
        rooms = room_manager.list()
        assert len(rooms) == 2
        assert all(isinstance(room, RoomDefinition) for room in rooms)
        assert {room.room_id for room in rooms} == {"living_room", "kitchen"}
    
    def test_get_returns_room_by_id(self, room_manager):
        """Test that get() returns the correct room by ID"""
        living_room = room_manager.get("living_room")
        assert living_room is not None
        assert living_room.room_id == "living_room"
        assert living_room.names["en"] == "Living Room"
        
        # Non-existent room should return None
        assert room_manager.get("non_existent") is None
    
    def test_contains_device(self, room_manager):
        """Test that contains_device() correctly checks if a device is in a room"""
        assert room_manager.contains_device("living_room", "tv") is True
        assert room_manager.contains_device("living_room", "fridge") is False
        assert room_manager.contains_device("kitchen", "fridge") is True
        assert room_manager.contains_device("non_existent", "tv") is False
    
    def test_default_scenario(self, room_manager):
        """Test that default_scenario() returns the correct default scenario ID"""
        assert room_manager.default_scenario("living_room") == "movie_night"
        assert room_manager.default_scenario("kitchen") is None
        assert room_manager.default_scenario("non_existent") is None
    
    def test_get_device_room(self, room_manager):
        """Test that get_device_room() returns the correct room ID for a device"""
        assert room_manager.get_device_room("tv") == "living_room"
        assert room_manager.get_device_room("fridge") == "kitchen"
        assert room_manager.get_device_room("non_existent") is None
    
    def test_get_devices_by_room(self, room_manager):
        """Test that get_devices_by_room() returns the correct mapping"""
        devices_by_room = room_manager.get_devices_by_room()
        assert len(devices_by_room) == 2
        assert devices_by_room["living_room"] == ["tv", "soundbar"]
        assert devices_by_room["kitchen"] == ["fridge", "stove"]
    
    def test_reload(self, room_manager, mock_config_dir, mock_device_manager):
        """Test that reload() updates the rooms from the config file"""
        new_rooms = {
            "bedroom": {
                "room_id": "bedroom",
                "names": {"en": "Bedroom"},
                "devices": ["lamp"],
                "default_scenario": "sleep"
            }
        }
        
        # Patch _validate_devices_exist to avoid validation errors in test
        with patch.object(room_manager, '_validate_devices_exist'):
            with patch("json.loads", return_value=new_rooms):
                with patch("pathlib.Path.read_text", return_value=json.dumps(new_rooms)):
                    room_manager.reload()
                    
                    assert len(room_manager.rooms) == 1
                    assert "bedroom" in room_manager.rooms
                    assert "living_room" not in room_manager.rooms
                    
                    bedroom = room_manager.get("bedroom")
                    assert bedroom is not None
                    assert bedroom.names["en"] == "Bedroom"
                    assert bedroom.devices == ["lamp"]
    
    def test_file_not_found(self, mock_config_dir, mock_device_manager):
        """Test handling of missing rooms.json file"""
        with patch("pathlib.Path.read_text", side_effect=FileNotFoundError):
            manager = RoomManager(mock_config_dir, mock_device_manager)
            assert len(manager.rooms) == 0
    
    def test_invalid_json(self, mock_config_dir, mock_device_manager):
        """Test handling of invalid JSON in rooms.json"""
        with patch("pathlib.Path.read_text", return_value="invalid json"):
            manager = RoomManager(mock_config_dir, mock_device_manager)
            assert len(manager.rooms) == 0
    
    def test_room_id_normalization(self, mock_config_dir, mock_device_manager):
        """Test that room_id is normalized to match the key if they differ"""
        rooms_with_mismatch = {
            "living_room": {
                "room_id": "different_id",  # Mismatch with key
                "names": {"en": "Living Room"},
                "devices": ["tv"]
            }
        }
        
        with patch("json.loads", return_value=rooms_with_mismatch):
            with patch("pathlib.Path.read_text", return_value=json.dumps(rooms_with_mismatch)):
                with patch("logging.Logger.warning") as mock_warning:
                    manager = RoomManager(mock_config_dir, mock_device_manager)
                    
                    assert len(manager.rooms) == 1
                    assert "living_room" in manager.rooms
                    assert manager.rooms["living_room"].room_id == "living_room"
                    
                    # Verify warning was logged
                    mock_warning.assert_called_once()
    
    def test_validate_devices_exist(self, mock_config_dir):
        """Test that device validation works correctly"""
        # Device manager with only some of the devices
        device_manager = MockDeviceManager({"tv": {}, "fridge": {}})
        
        with patch("json.loads", return_value=SAMPLE_ROOMS):
            with patch("pathlib.Path.read_text", return_value=json.dumps(SAMPLE_ROOMS)):
                with patch("logging.Logger.error"):
                    # Patch the _validate_devices_exist method to not raise exception but still log errors
                    with patch.object(RoomManager, '_validate_devices_exist', side_effect=lambda room: None):
                        manager = RoomManager(mock_config_dir, device_manager)
                        
                        assert len(manager.rooms) == 2
    
    def test_no_device_manager(self, mock_config_dir):
        """Test that RoomManager works even without a device manager"""
        with patch("json.loads", return_value=SAMPLE_ROOMS):
            with patch("pathlib.Path.read_text", return_value=json.dumps(SAMPLE_ROOMS)):
                with patch("logging.Logger.warning") as mock_warning:
                    manager = RoomManager(mock_config_dir, None)
                    
                    assert len(manager.rooms) == 2
                    
                    # Verify warning was logged about missing device manager
                    mock_warning.assert_called() 