# Coding Conventions

**Analysis Date:** 2026-05-20

## Naming Patterns

**Files:**
- Modules: `snake_case.py` (e.g., `device_manager.py`, `mqtt_client.py`)
- Classes: `PascalCase` (e.g., `DeviceManager`, `ScenarioManager`, `LgTv`)
- Device drivers: `driver.py` in `infrastructure/devices/<device_name>/` (e.g., `infrastructure/devices/lg_tv/driver.py`)
- Config models: stored in `infrastructure/config/models.py` with suffixes `Config`, `State` (e.g., `LgTvDeviceConfig`, `LgTvState`)

**Functions:**
- Standard functions: `snake_case` (e.g., `execute_action`, `handle_message`)
- Action handlers on devices: `handle_<action>` (e.g., `handle_power_on`, `handle_set_volume`), all async
- Lifecycle methods: `async setup()`, `async shutdown()`, `subscribe_topics()` (synchronous)
- Query methods: `get_*` prefix (e.g., `get_device`, `get_current_state`)
- Internal helpers: `_private_method` (single leading underscore)

**Variables:**
- Instance attributes: `snake_case` (e.g., `self.device_id`, `self.state`, `self.config`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `REQUIRED_FIELDS`, `DEFAULT_TIMEOUT`)
- Type parameters: `PascalCase` suffix with `T` (e.g., `StateT` for generic state types)

**Types:**
- Pydantic models: inherit from `BaseModel` or domain-specific bases (`BaseDeviceConfig`, `BaseDeviceState`)
- Type hints: use `Optional[T]` not `Union[T, None]`; use `Dict`, `List` from `typing` (Python 3.11)
- Custom types: stored in `utils/types.py` (e.g., `CommandResult`, `CommandResponse`)

## Code Style

**Formatting:**
- **black** with line length **88** and target **py311** (configured in `pyproject.toml`)
- **isort** with black profile (configured in `pyproject.toml`)
- Format new code before committing: `black src/` and `isort src/`

**Linting:**
- **mypy** via `./run_mypy.sh` (config `mypy.ini`)
- Type hints are expected on new code in domain and infrastructure layers
- mypy relaxes checks in test files (disallow_untyped_defs disabled)
- Unknown third-party library types are ignored (see mypy.ini overrides for pymotivaxmc2, asyncwebostv, broadlink, etc.)

**Code organization:**
- Imports at top, organized in groups (stdlib, third-party, local)
- Docstrings on classes and public functions (triple-quoted, not inline comments)
- Private methods/attributes use single leading underscore

## Import Organization

**Order:**
1. Python standard library (e.g., `import asyncio`, `from typing import ...`)
2. Third-party packages (e.g., `from pydantic import BaseModel`, `import aiohttp`)
3. Local application imports (e.g., `from wb_mqtt_bridge.domain.ports import MessageBusPort`)

**Path Aliases:**
- No path aliases in `pyproject.toml` or build config — all imports use absolute package paths
- Imports always start from `wb_mqtt_bridge.*` (the package root)

**Barrel files:**
- Minimal use; most imports go directly to modules
- `domain/__init__.py`, `infrastructure/__init__.py` are largely empty
- `presentation/api/__init__.py` may export common schemas

## Error Handling

**Patterns:**
- Domain layer defines custom exception classes that inherit from base exception (e.g., `ScenarioError`, `ScenarioExecutionError`)
- Custom exceptions include context (error_type, critical flag, relevant IDs)
- Infrastructure and presentation layers catch domain exceptions and translate to appropriate HTTP responses (500, 400, 404, etc.)
- Drivers use try-except around external client calls; failures return `CommandResult` with `success=False` and `error` detail
- Never swallow exceptions silently; always log with `logger.error()` or re-raise

Example (from `domain/scenarios/scenario.py`):
```python
class ScenarioError(Exception):
    """Base class for scenario-related errors."""
    def __init__(self, msg: str, error_type: str, critical: bool = False):
        super().__init__(msg)
        self.error_type = error_type
        self.critical = critical
```

## Logging

**Framework:** Python standard `logging` module via `logger = logging.getLogger(__name__)`

**Patterns:**
- Every module that logs defines: `logger = logging.getLogger(__name__)` at module scope
- Log levels used:
  - `logger.debug()` — internal operation details
  - `logger.info()` — state changes, startup/shutdown, significant events
  - `logger.warning()` — potential issues that don't stop execution
  - `logger.error()` — errors that need attention but don't crash the app
  - `logger.critical()` — fatal errors that should crash the app
- Include relevant context in messages (device_id, scenario_id, command, etc.)
- When logging exceptions, use `logger.exception()` within an except block to include traceback

## Comments

**When to Comment:**
- Avoid obvious comments; let clear code speak for itself
- Comment the *why*, not the *what* — explain design decisions, edge cases, non-obvious behavior
- Comment regex patterns and complex algorithms
- Mark workarounds with `# HACK:` or `# TODO:` (grepped by CI for follow-up)

**JSDoc/TSDoc:**
- Use **docstrings** (not inline comments) for public classes, methods, and functions
- Format: triple-quoted string immediately after def/class, before code
- Include Args, Returns, Raises sections for functions
- Example (from `domain/ports.py`):
```python
async def publish(
    self, 
    topic: str, 
    payload: str, 
    qos: int = 0, 
    retain: bool = False
) -> None:
    """Publish a message to the message bus.
    
    Args:
        topic: The topic to publish to
        payload: The message payload
        qos: Quality of service level (0, 1, or 2)
        retain: Whether the message should be retained
    """
    pass
```

## Function Design

**Size:** Keep functions small and focused (typically <50 lines); break async handlers into sub-methods if they exceed this

**Parameters:**
- Action handlers use a fixed signature: `async def handle_<action>(self, cmd_config, params) -> CommandResult`
  - `cmd_config`: `StandardCommandConfig` or device-specific config subclass
  - `params`: dict of user-supplied parameters (validated by Pydantic at presentation layer)
- Avoid optional parameters with mutable defaults (use `None` as sentinel)

**Return Values:**
- Action handlers return `CommandResult` (dict): `{"success": bool, "message"?: str, "error"?: str, "mqtt_command"?: dict}`
- Query methods return typed objects (Pydantic models, dicts, or primitives)
- Async lifecycle methods (`setup`, `shutdown`, `handle_message`) return `None`

## Module Design

**Exports:**
- Each module exports the main public class/function(s) it defines
- Test helpers and utilities are prefixed with `_` (underscore) to signal they're internal
- Avoid wildcard imports (`from module import *`)

**Barrel Files:**
- Domain layer packages (`domain/devices/`, `domain/scenarios/`, `domain/rooms/`) do not barrel-export; import directly from submodules
- Presentation schemas may be imported from `presentation/api/schemas.py`

## Hexagonal Architecture Rules

**Hard rule — Dependencies point inward:**
- `domain/` imports nothing from `infrastructure/` or `presentation/`
- `infrastructure/` and `presentation/` import from `domain/`
- Ports (`domain/ports.py`) define the seams; adapters in `infrastructure/` implement them

**Typed configs and state:**
- Device configs are Pydantic models in `infrastructure/config/models.py`, subclassing `BaseDeviceConfig`
- Device state models are in `domain/devices/models.py`, subclassing `BaseDeviceState`
- No dict-shaped configs/state; every config and state is a typed Pydantic model
- Each driver is `BaseDevice[StateT]` parameterized by its state type

**Device drivers:**
- Live in `infrastructure/devices/<name>/driver.py`
- Subclass `BaseDevice[StateT]` from `infrastructure/devices/base.py`
- Implement lifecycle: `async setup()`, `async shutdown()`, `subscribe_topics()`, `async handle_message(topic, payload)`
- Expose action handlers: `async def handle_<action>(self, cmd_config, params) -> CommandResult`
- Inject the MQTT client via constructor; use it to publish commands/state
- All external I/O goes through ports or injected clients; no bare HTTP/MQTT calls

---

*Convention analysis: 2026-05-20*
