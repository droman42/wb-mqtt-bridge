# Scenario System Tests

This directory contains the test suite for the Scenario System. The tests are organized into unit tests and integration tests to validate the functionality of all components.

## Test Structure

- `unit/`: Unit tests for individual classes and components
  - `test_room_manager.py`: Tests for the RoomManager class
  - `test_scenario.py`: Tests for the Scenario class
  - `test_scenario_manager.py`: Tests for the ScenarioManager class
  - `test_scenario_models.py`: Tests for the Pydantic models

- Integration tests (root directory):
  - `test_scenario_api_integration.py`: End-to-end tests for the REST API endpoints
  - `test_scenario_state_persistence.py`: Tests for state persistence across transitions

## Running Tests

To run the entire test suite:

```bash
pytest
```

To run specific test files:

```bash
pytest tests/unit/test_scenario.py
pytest tests/test_scenario_api_integration.py
```

To run tests with verbose output:

```bash
pytest -v
```

To run tests with coverage:

```bash
pytest --cov=app tests/
```

## Test Categories

### Unit Tests

Unit tests verify the functionality of individual components in isolation, using mocks for dependencies.

1. **Room Manager Tests**
   - Loading room definitions from JSON
   - Finding devices in rooms
   - Validating device existences

2. **Scenario Tests**
   - Executing role actions
   - Startup and shutdown sequences
   - Condition evaluation
   - Error handling

3. **Scenario Manager Tests**
   - Loading scenario definitions
   - Transitioning between scenarios (diff-aware)
   - State management
   - Error handling
   - Event handling

4. **Model Tests**
   - Validation of scenario definitions
   - JSON serialization/deserialization
   - Configuration diffs

### Integration Tests

Integration tests verify the interactions between components and external systems.

1. **API Integration Tests**
   - REST API endpoint functionality
   - Error handling and response codes
   - Parameter validation

2. **State Persistence Tests**
   - Saving and restoring scenarios
   - State persistence across system restarts
   - Handling of missing scenarios

## Mock Components

The tests use several mock components to simulate external dependencies:

- `MockDeviceManager`: Simulates device management and control
- `MockDevice`: Simulates a physical device with state and commands
- `MockRoomManager`: Provides room information
- `MockStateStore`: Simulates persistent storage
- `MockMQTTClient`: Simulates MQTT communication

## Adding New Tests

When adding new functionality to the Scenario System, follow these guidelines for testing:

1. Add unit tests for new classes or methods
2. Update integration tests if the new functionality affects external interfaces
3. Add new mock components if needed
4. Ensure tests run independently and don't depend on external state

## Test Fixtures

The test suite uses pytest fixtures to set up test environments. Key fixtures include:

- `scenario_dir`: Creates a temporary directory with sample scenario files
- `mock_device_manager`: Provides a mock device manager with sample devices
- `mock_room_manager`: Provides a mock room manager with sample rooms
- `mock_store`: Provides a mock state store for persistence testing

## Requirements

Tests require the following packages:

- pytest
- pytest-asyncio (for testing async functions)
- pytest-cov (for test coverage)
- fastapi (for API testing)
- httpx (for API client testing via TestClient)

You can install these with:

```bash
pip install pytest pytest-asyncio pytest-cov fastapi httpx
``` 