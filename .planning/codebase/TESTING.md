# Testing Patterns

**Analysis Date:** 2026-05-20

## Test Framework

**Runner:**
- **pytest** (configured in `pyproject.toml`)
- **pytest-asyncio** with `asyncio_mode = auto` for async test support
- **pytest-mock** for mocking fixtures
- **pytest-cov** for coverage reporting

**Config:** `pyproject.toml` `[tool.pytest.ini_options]`
- `testpaths = ["tests"]` — tests live in top-level `tests/` directory
- `asyncio_default_fixture_loop_scope = "function"` — each test gets a fresh event loop

**Assertion Library:** pytest built-in assertions (no external library; use `assert` statements)

**Run Commands:**
```bash
pytest tests/                                   # Run all tests
pytest tests/ -m "not requires_device"          # Run only CI-safe tests (skip hardware deps)
pytest tests/ -m unit                           # Run unit tests only
pytest tests/ --cov=wb_mqtt_bridge              # With coverage reporting
pytest tests/ -v                                # Verbose output
pytest tests/ -k "test_scenario"                # Run tests matching pattern
pytest tests/devices/test_auralic_device.py    # Run specific test file
```

## Test File Organization

**Location:**
- Co-located with source: `tests/` mirrors structure of `src/wb_mqtt_bridge/`
- Top-level `tests/` for integration tests and helpers
- `tests/unit/` for pure unit tests (no I/O, all mocked)
- `tests/devices/` for device driver tests

**Naming:**
- Test files: `test_<module>.py` (e.g., `test_scenario.py`, `test_lg_tv.py`)
- Non-test helpers: prefixed with `_` or have descriptive names not matching `test_*` pattern (e.g., `device_test.py`, `conftest.py`, `mock_sqlite.py`)
- Test functions: `test_<what_is_being_tested>` (e.g., `test_execute_role_action_success`)
- Test classes: `Test<ClassName>` (e.g., `TestScenario`, `TestAuralicDevice`)

**Directory structure:**
```
tests/
├── conftest.py                      # Global fixtures, pytest configuration
├── device_test.py                   # CLI helper script (not a test, no test_ prefix)
├── mock_sqlite.py                   # SQLite mock for testing (helper)
├── auto_wrap_devices.py             # Device wrapping utility for tests
├── test_scenario.py                 # Top-level scenario tests
├── test_integration.py              # Integration tests
├── unit/
│   ├── test_scenario.py
│   ├── test_scenario_manager.py
│   ├── test_state_store.py
│   └── ...
└── devices/
    ├── README.md                    # Device testing guide
    ├── test_auralic_device.py       # Auralic device tests
    └── test_auralic_update_task.py  # Auralic async task tests
```

## Test Structure

**Suite Organization (pytest markers):**

All test files use module-level `pytestmark` to declare their category:

```python
import pytest
pytestmark = pytest.mark.unit  # For unit tests
pytestmark = pytest.mark.integration  # For integration tests
```

**Available markers** (defined in `pyproject.toml`):
- `unit` — pure unit test (no I/O, all mocked)
- `integration` — integration test with mocked externals (safe for CI)
- `requires_mqtt` — needs a running MQTT broker
- `requires_device` — needs real device hardware on the LAN
- `slow` — takes more than ~5 seconds

**CI runs only:** `pytest -m "not requires_device"` (excludes hardware-dependent tests)

**Typical fixture structure** (from `conftest.py`):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_device_manager():
    """Create a mock device manager with mock devices."""
    tv = MagicMock()
    tv.execute_action = AsyncMock()
    tv.get_current_state = MagicMock(return_value={"power": False})
    
    device_manager = MagicMock()
    device_manager.devices = {"tv": tv}
    return device_manager

@pytest.fixture
def scenario(mock_device_manager):
    """Create a scenario instance for testing."""
    definition = ScenarioDefinition.model_validate(SAMPLE_SCENARIO)
    return Scenario(definition, mock_device_manager)
```

## Test Structure Patterns

**Unit test example** (from `tests/unit/test_scenario.py`):

```python
import pytest
from unittest.mock import MagicMock, AsyncMock

pytestmark = pytest.mark.unit

class TestScenario:
    """Tests for the Scenario class"""
    
    def test_initialization(self, scenario, sample_scenario_definition):
        """Test that Scenario is initialized correctly"""
        assert scenario.definition == sample_scenario_definition
        assert scenario.scenario_id == "test_scenario"
    
    @pytest.mark.asyncio
    async def test_execute_role_action_success(self, scenario, mock_device_manager):
        """Test successful execution of a role action"""
        # Arrange
        mock_device_manager.devices["tv"].execute_action.return_value = {"status": "success"}
        
        # Act
        result = await scenario.execute_role_action("main_display", "power_on", volume=50)
        
        # Assert
        mock_device_manager.devices["tv"].execute_action.assert_called_once_with(
            "power_on", {"volume": 50}, source="scenario"
        )
        assert result == {"status": "success"}
```

**Patterns:**
- Use **Arrange-Act-Assert** (AAA) for test clarity
- Every async test has `@pytest.mark.asyncio` decorator
- Fixture names are descriptive (`mock_device_manager`, `scenario_with_conditions`)
- Assertions are specific and include failure messages where helpful

## Mocking

**Framework:** `unittest.mock` (built-in)

**Patterns:**

**AsyncMock for async methods:**
```python
from unittest.mock import AsyncMock

# Create an async mock
async_method = AsyncMock()

# Set return value
async_method.return_value = {"success": True}

# Assert it was awaited
async_method.assert_awaited_once_with(arg1, arg2)
```

**MagicMock for synchronous methods:**
```python
from unittest.mock import MagicMock

mock = MagicMock()
mock.get_device = MagicMock(return_value=some_device)

# Assert it was called
mock.get_device.assert_called_once_with("device_id")
```

**Device driver mocking pattern** (from `tests/devices/test_auralic_device.py`):

Device drivers are tested by:
1. Creating the driver with a typed config (e.g., `AuralicDeviceConfig`)
2. Injecting a fake external client (e.g., `fake_openhome`) as an `AsyncMock`
3. **Bypassing `setup()`** (it connects to real hardware; we mock the connection state instead)
4. Flipping `state.connected = True` to satisfy handler connectivity checks
5. Calling action handlers directly and asserting on:
   - External client method calls (e.g., `fake_openhome.play.assert_awaited_once()`)
   - State mutations (e.g., `assert device.state.volume == 42`)
   - `CommandResult` shape (e.g., `assert result["success"] is True`)

**Example:**
```python
@pytest.fixture
def fake_openhome():
    """An AsyncMock standing in for OpenHomeDevice."""
    oh = AsyncMock()
    oh.play = AsyncMock()
    oh.volume = AsyncMock(return_value=50)
    return oh

@pytest.fixture
def device(fake_openhome):
    """An AuralicDevice with the openhome dependency pre-wired."""
    cfg = AuralicDeviceConfig(...)
    d = AuralicDevice(cfg, mqtt_client=MagicMock())
    d.openhome_device = fake_openhome  # Inject the mock
    d.state.connected = True            # Satisfy connectivity gate
    return d

@pytest.mark.asyncio
async def test_handle_play_invokes_openhome_play(device, fake_openhome):
    result = await device.handle_play(device.config.commands["play"], {})
    fake_openhome.play.assert_awaited_once()
    assert result["success"] is True
```

**What to Mock:**
- External I/O: MQTT clients, HTTP clients, device drivers
- Long-running operations: database calls, network requests
- Randomness: time.time(), random number generators
- File I/O: config loading, logging

**What NOT to Mock:**
- Pydantic models (use real instances with valid data)
- Simple data structures (dicts, lists)
- Pure functions with no side effects
- Scenarios/domains under test (use real instances, mock their dependencies)

## Fixtures and Factories

**Test Data** (Pydantic models):

```python
# From tests/unit/test_scenario.py
SAMPLE_SCENARIO = {
    "scenario_id": "test_scenario",
    "name": "Test Scenario",
    "roles": {"main_display": "tv", "audio": "soundbar"},
    "devices": ["tv", "soundbar"],
    "startup_sequence": [
        {
            "device": "tv",
            "command": "power_on",
            "params": {},
            "delay_after_ms": 1000
        }
    ],
    "shutdown_sequence": [
        {"device": "tv", "command": "power_off", "params": {}}
    ]
}

@pytest.fixture
def sample_scenario_definition():
    """Return a sample ScenarioDefinition"""
    return ScenarioDefinition.model_validate(SAMPLE_SCENARIO)
```

**Location:** Test data defined at module scope in test files; re-used across test classes

## Coverage

**Requirements:** None enforced (coverage checks are optional)

**View Coverage:**
```bash
pytest tests/ --cov=wb_mqtt_bridge --cov-report=term-missing
pytest tests/devices/ --cov=wb_mqtt_bridge.infrastructure.devices.auralic --cov-report=term-missing
```

**Coverage reporting:** Coverage data written to `.coverage` file (gitignored)

**Focus areas for expansion** (from `tests/devices/README.md`):
- Auralic device: current 56% coverage (120 missing statements out of 270)
- More command handlers and edge cases for all drivers
- Discovery mode testing with complex scenarios
- Error conditions in device setup and update

## Test Types

**Unit Tests** (`tests/unit/`):
- Scope: Single class or function in isolation
- Approach: Mock all external dependencies (MQTT, HTTP, database, other services)
- Example files: `test_scenario.py`, `test_state_store.py`, `test_scenario_manager.py`
- Mark with: `@pytest.mark.unit`

**Integration Tests** (`tests/devices/`, `tests/`):
- Scope: Device driver logic with mocked externals (safe for CI)
- Approach: Mock external clients (openhome, WebOS, etc.) but test the real driver code
- Example files: `test_auralic_device.py`, `test_lg_tv.py`
- Mark with: `@pytest.mark.integration`
- Bypass `setup()` (which connects to real hardware); manually set state.connected = True

**Device Hardware Tests** (not in CI):
- Scope: Real devices on LAN
- Approach: Talk to actual hardware
- Mark with: `@pytest.mark.requires_device`
- Run manually only: `pytest tests/ -m "requires_device"`

**E2E Tests:** Not currently implemented (would require a running service)

## Common Patterns

**Async Testing:**

Every async test needs `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_operation(fixture):
    """Test an async operation"""
    result = await some_async_function()
    assert result == expected
```

**Error Testing:**

```python
import pytest
from domain.scenarios.scenario import ScenarioError

def test_invalid_role_raises_error(scenario):
    """Test that invalid role raises ScenarioError"""
    with pytest.raises(ScenarioError) as excinfo:
        await scenario.execute_role_action("invalid_role", "power_on")
    
    assert "Role 'invalid_role' not defined" in str(excinfo.value)
    assert excinfo.value.error_type == "invalid_role"
```

**State verification (device drivers):**

```python
@pytest.mark.asyncio
async def test_set_volume_persists_in_state(device, fake_openhome):
    """Verify that set_volume updates device state"""
    fake_openhome.volume = AsyncMock(return_value=42)
    result = await device.handle_set_volume(
        device.config.commands["set_volume"], 
        {"volume": 42}
    )
    
    # Verify the command was sent
    fake_openhome.set_volume.assert_awaited_once_with(42)
    
    # Verify state was updated by the post-call refresh
    assert device.state.volume == 42
    assert result["success"] is True
```

**Database test pattern** (from `tests/unit/test_state_store.py`):

```python
@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory database for testing."""
    store = SQLiteStateStore(db_path=":memory:")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()

@pytest.mark.asyncio
async def test_set_and_get(test_db):
    """Test that set() followed by get() returns the original dict"""
    test_data = {"name": "test", "value": 42}
    
    await test_db.set("test_key", test_data)
    result = await test_db.get("test_key")
    
    # get() adds a _timestamp; strip it for comparison
    without_timestamp = {k: v for k, v in result.items() if k != "_timestamp"}
    assert without_timestamp == test_data
```

---

*Testing analysis: 2026-05-20*
