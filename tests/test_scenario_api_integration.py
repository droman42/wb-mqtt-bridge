import asyncio
import json
import pytest
from typing import Dict, Any, List, Optional
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.main import app as main_app
from app.routers import scenarios, rooms
from app.scenario_models import ScenarioDefinition, ScenarioState, DeviceState
from app.scenario import Scenario
from app.scenario_manager import ScenarioManager

# Sample scenario data for testing
SAMPLE_SCENARIOS = {
    "movie_night": {
        "scenario_id": "movie_night",
        "name": "Movie Night",
        "description": "Optimal settings for watching movies",
        "room_id": "living_room",
        "roles": {"screen": "tv", "audio": "soundbar"},
        "devices": {
            "tv": {"groups": ["display"]},
            "soundbar": {"groups": ["audio"]}
        },
        "startup_sequence": [
            {"device": "tv", "command": "power_on", "params": {}},
            {"device": "soundbar", "command": "power_on", "params": {}}
        ],
        "shutdown_sequence": {
            "complete": [
                {"device": "tv", "command": "power_off", "params": {}},
                {"device": "soundbar", "command": "power_off", "params": {}}
            ],
            "transition": [
                {"device": "tv", "command": "standby", "params": {}},
                {"device": "soundbar", "command": "standby", "params": {}}
            ]
        }
    },
    "reading_mode": {
        "scenario_id": "reading_mode",
        "name": "Reading Mode",
        "description": "Comfortable lighting for reading",
        "room_id": "living_room",
        "roles": {"lighting": "lights"},
        "devices": {
            "lights": {"groups": ["ambience"]}
        },
        "startup_sequence": [
            {"device": "lights", "command": "set_scene", "params": {"scene": "reading"}}
        ],
        "shutdown_sequence": {
            "complete": [
                {"device": "lights", "command": "set_scene", "params": {"scene": "bright"}}
            ],
            "transition": [
                {"device": "lights", "command": "set_scene", "params": {"scene": "bright"}}
            ]
        }
    }
}

class MockScenarioManager:
    """Mock ScenarioManager for API testing"""
    def __init__(self):
        # Set up sample scenario definitions
        self.scenario_definitions = {}
        self.scenario_map = {}
        self.current_scenario = None
        self.scenario_state = None
        
        # Load sample scenarios
        for scenario_id, data in SAMPLE_SCENARIOS.items():
            definition = ScenarioDefinition.model_validate(data)
            self.scenario_definitions[scenario_id] = definition
            self.scenario_map[scenario_id] = Scenario(definition, MagicMock())
        
        # Setup async methods as AsyncMocks
        self.switch_scenario = AsyncMock()
        self.execute_role_action = AsyncMock(return_value={"status": "success"})
        
        # Setup initial state
        self.switch_scenario.return_value = None
    
    def set_active_scenario(self, scenario_id):
        """Helper to set an active scenario for testing"""
        if scenario_id not in self.scenario_map:
            return
            
        self.current_scenario = self.scenario_map[scenario_id]
        self.scenario_state = ScenarioState(
            scenario_id=scenario_id,
            devices={
                "tv": DeviceState(power=True, input="hdmi1"),
                "soundbar": DeviceState(power=True, volume=50)
            }
        )

class MockRoomManager:
    """Mock RoomManager for API testing"""
    def __init__(self):
        # Create a room object with actual values instead of MagicMock
        self.rooms = {
            "living_room": {
                "room_id": "living_room",
                "names": {"en": "Living Room"},
                "description": "Main living area",  # Use a real string for description
                "devices": ["tv", "soundbar", "lights"],
                "default_scenario": "movie_night"
            }
        }
    
    def get(self, room_id):
        return self.rooms.get(room_id)
    
    def list(self):
        return list(self.rooms.values())
    
    def contains_device(self, room_id, device_id):
        room = self.rooms.get(room_id)
        return room and device_id in room["devices"]

@pytest.fixture
def mock_scenario_manager():
    """Return a mock scenario manager"""
    return MockScenarioManager()

@pytest.fixture
def mock_room_manager():
    """Return a mock room manager"""
    return MockRoomManager()

@pytest.fixture
def mock_mqtt_client():
    """Return a mock MQTT client"""
    mqtt = MagicMock()
    mqtt.publish = AsyncMock()
    return mqtt

@pytest.fixture
def test_client(mock_scenario_manager, mock_room_manager, mock_mqtt_client):
    """Return a FastAPI TestClient with mocked dependencies"""
    # Initialize the routers with our mocks
    scenarios.initialize(mock_scenario_manager, mock_room_manager, mock_mqtt_client)
    rooms.initialize(mock_room_manager)  # Initialize the rooms router
    
    # Create a test client
    client = TestClient(main_app)
    
    # Return the configured client
    return client

class TestScenarioAPI:
    """Integration tests for the scenario API endpoints"""
    
    def test_get_scenario_state_success(self, test_client, mock_scenario_manager):
        """Test successful retrieval of scenario state"""
        # Set up an active scenario
        mock_scenario_manager.set_active_scenario("movie_night")
        
        # Call the API
        response = test_client.get("/scenario/state")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_id"] == "movie_night"
        assert "devices" in data
        assert "tv" in data["devices"]
        assert data["devices"]["tv"]["power"] is True
        assert data["devices"]["tv"]["input"] == "hdmi1"

    def test_get_scenario_state_no_active(self, test_client, mock_scenario_manager):
        """Test error when no active scenario"""
        # Ensure no active scenario
        mock_scenario_manager.current_scenario = None
        mock_scenario_manager.scenario_state = None
        
        # Call the API
        response = test_client.get("/scenario/state")
        
        # Check the response
        assert response.status_code == 404
        assert "No active scenario" in response.json()["detail"]

    def test_get_scenario_definition_success(self, test_client, mock_scenario_manager):
        """Test successful retrieval of scenario definition"""
        # Call the API
        response = test_client.get("/scenario/definition/movie_night")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_id"] == "movie_night"
        assert data["name"] == "Movie Night"
        assert data["room_id"] == "living_room"
        assert "roles" in data
        assert "devices" in data
        assert "startup_sequence" in data
        assert "shutdown_sequence" in data

    def test_get_scenario_definition_not_found(self, test_client):
        """Test error when scenario not found"""
        # Call the API with a nonexistent scenario ID
        response = test_client.get("/scenario/definition/nonexistent")
        
        # Check the response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_switch_scenario_success(self, test_client, mock_scenario_manager, mock_mqtt_client):
        """Test successful scenario switching"""
        # Call the API
        response = test_client.post(
            "/scenario/switch",
            json={"id": "reading_mode", "graceful": True}
        )
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Successfully switched to scenario" in data["message"]
        
        # Verify the manager was called correctly
        mock_scenario_manager.switch_scenario.assert_called_once_with("reading_mode", graceful=True)
        
        # Verify MQTT message was published (if current scenario is set)
        if mock_scenario_manager.scenario_state:
            mock_mqtt_client.publish.assert_called_once()

    def test_switch_scenario_not_found(self, test_client, mock_scenario_manager):
        """Test error when switching to nonexistent scenario"""
        # Setup the mock to raise an error
        mock_scenario_manager.switch_scenario.side_effect = ValueError("Scenario 'nonexistent' not found")
        
        # Call the API
        response = test_client.post(
            "/scenario/switch",
            json={"id": "nonexistent", "graceful": True}
        )
        
        # Check the response
        assert response.status_code == 404
        assert "Scenario 'nonexistent' not found" in response.json()["detail"]

    def test_execute_role_action_success(self, test_client, mock_scenario_manager, mock_mqtt_client):
        """Test successful execution of a role action"""
        # Set up an active scenario
        mock_scenario_manager.set_active_scenario("movie_night")
        
        # Call the API
        response = test_client.post(
            "/scenario/role_action",
            json={
                "role": "screen",
                "command": "set_input",
                "params": {"input": "hdmi1"}
            }
        )
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify the manager was called correctly
        mock_scenario_manager.execute_role_action.assert_called_once_with(
            "screen", "set_input", {"input": "hdmi1"}
        )
        
        # Verify MQTT message was published
        mock_mqtt_client.publish.assert_called_once()

    def test_execute_role_action_no_active_scenario(self, test_client, mock_scenario_manager):
        """Test error when no active scenario"""
        # Ensure no active scenario and setup error
        mock_scenario_manager.current_scenario = None
        mock_scenario_manager.scenario_state = None
        mock_scenario_manager.execute_role_action.side_effect = Exception("No scenario is currently active")
        
        # Call the API
        response = test_client.post(
            "/scenario/role_action",
            json={
                "role": "screen",
                "command": "set_input",
                "params": {"input": "hdmi1"}
            }
        )
        
        # Check the response
        assert response.status_code == 500
        assert "No scenario is currently active" in response.json()["detail"]

    def test_get_scenarios_for_room(self, test_client, mock_scenario_manager):
        """Test getting scenarios for a specific room"""
        # Call the API
        response = test_client.get("/scenario/definition?room=living_room")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # Both our sample scenarios are in living_room
        
        # Verify the content
        scenario_ids = [s["scenario_id"] for s in data]
        assert "movie_night" in scenario_ids
        assert "reading_mode" in scenario_ids

    def test_get_all_scenarios(self, test_client, mock_scenario_manager):
        """Test getting all scenarios when no room filter is specified"""
        # Call the API
        response = test_client.get("/scenario/definition")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # All our sample scenarios
        
        # Verify the content
        scenario_ids = [s["scenario_id"] for s in data]
        assert "movie_night" in scenario_ids
        assert "reading_mode" in scenario_ids

class TestRoomAPI:
    """Integration tests for the room API endpoints"""
    
    def test_list_rooms(self, test_client, mock_room_manager):
        """Test listing all rooms"""
        # Call the API
        response = test_client.get("/room/list")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["room_id"] == "living_room"
        assert data[0]["names"]["en"] == "Living Room"

    def test_get_room(self, test_client, mock_room_manager):
        """Test getting a specific room"""
        # Call the API
        response = test_client.get("/room/living_room")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["room_id"] == "living_room"
        assert data["names"]["en"] == "Living Room"
        assert "tv" in data["devices"]
        assert "soundbar" in data["devices"]
        assert "lights" in data["devices"]

    def test_get_room_not_found(self, test_client, mock_room_manager):
        """Test error when room not found"""
        # Call the API with a nonexistent room ID
        response = test_client.get("/room/nonexistent")
        
        # Check the response
        assert response.status_code == 404
        assert "Room 'nonexistent' not found" in response.json()["detail"] 