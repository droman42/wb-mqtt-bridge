# tsState Persistence Layer Specification

This document specifies the design and implementation details for a universal State Persistence Layer, to be integrated into existing services (e.g., `DeviceManager`, `ScenarioManager`) within the **wb-mqtt-bridge** project. It is intended for an experienced Python developer.

---

## 1. Objectives

1. **Centralize state storage** for all services (DeviceManager, ScenarioManager, etc.) behind a common interface.
2. **Persist full state dictionaries** on every change (no crash-survival guarantee at this stage).
3. **Use SQLite** as an in-process key–value JSON store.
4. **Minimize intrusion**: adapt existing classes with clear interface injections and placeholders for recovery logic.
5. **Prepare for extension**: allow future backends (Redis, LMDB) via implementation of the same protocol.

---

## 2. High-Level Architecture

```text
+----------------+         +----------------------+        +-----------------------+
| DeviceManager  |  uses   | StateStore Protocol  |  backed | SQLiteStateStore      |
| ScenarioManager| ------> | (get, set, delete)   | <------| (aiosqlite + JSON)    |
+----------------+         +----------------------+        +-----------------------+
```

* **StateStore Protocol**: defines async methods `get()`, `set()`, `delete()`.
* **SQLiteStateStore**: implements `StateStore` using `aiosqlite`, storing JSON blobs in a single table.
* **Injection**: A single shared instance of `SQLiteStateStore` is created at startup and passed into all managers.

---

## 3. Changes to Existing Classes

### 3.1 `app/device_manager.py`

#### Modify constructor

```python
- class DeviceManager:
-     def __init__(self, config):
-         self.config = config
-         self.devices = {}
+ class DeviceManager:
+     def __init__(
+         self,
+         config: ConfigModel,
+         store: StateStore,
+     ):
+         """
+         :param config: loaded device config models
+         :param store: injected StateStore for persisting device state
+         """
+         self.config = config
+         self.store = store
+         self.devices: Dict[str, BaseDevice] = {}
```

#### Persist on state change

* Add a private helper:

```python
+     async def _persist_state(self, device_id: str):
+         """
+         Persist full device.state dict under key "device:{device_id}".
+         """
+         state_dict = self.devices[device_id].state
+         await self.store.set(f"device:{device_id}", state_dict)
```

* Update `perform_action` (and any other state-changing methods) to call this helper:

```python
-     async def perform_action(...):
-         result = await device.handle_action(...)
-         return result
+     async def perform_action(...):
+         result = await device.handle_action(...)
+         # persist after action
+         await self._persist_state(device_id)
+         return result
```

#### Add initialization placeholder

```python
+     async def initialize(self) -> None:
+         """
+         Placeholder for recovery logic: reload persisted state on startup.
+         Note: Full implementation will be provided in a later phase
+         once scenario management is implemented.
+         """
+         # for each device in config:
+         #   stored = await self.store.get(f"device:{device_id}")
+         #   if stored: seed self.devices[device_id].state = stored
+         # else: use default state
+         pass
```

### 3.2 `app/scenario_manager.py`

* Mirror injection and persistence patterns used in `DeviceManager`:

```python
- class ScenarioManager:
-     def __init__(self, config):
-         ...
+ class ScenarioManager:
+     def __init__(
+         self,
+         config: ConfigModel,
+         store: StateStore,
+     ):
+         ...
+         self.store = store
```

* Replace any ad-hoc Redis usage with `self.store.get/set(...)`.
* Ensure `switch_scenario()` persists new `ScenarioState` under key `"scenario:last"` after transition.
* Provide placeholder `initialize()` for recovery similar to DeviceManager (to be fully implemented in a later phase).
* All persistence operations must strictly adhere to the Pydantic models defined in the scenario system specification.

### 3.3 `app/main.py`

* Integrate with the existing lifespan context manager by initializing the StateStore at the right point in the startup/shutdown sequence.

```python
# Add import
from .state_store import SQLiteStateStore

# Add to global instances
config_manager = None
device_manager = None
mqtt_client = None
state_store = None  # Add state store to globals

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    global config_manager, device_manager, mqtt_client, state_store
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Setup logging with system config
    system_config = config_manager.get_system_config()
    log_file = system_config.log_file or 'logs/service.log'
    log_level = system_config.log_level
    setup_logging(log_file, log_level)
    
    # Apply logger-specific configuration
    # ... existing code ...
    
    logger = logging.getLogger(__name__)
    logger.info("Starting MQTT Web Service")
    
    # Initialize state store after config but before device manager
    db_path = Path(system_config.persistence.db_path)
    state_store = SQLiteStateStore(db_path=str(db_path))
    await state_store.initialize()
    logger.info(f"State persistence initialized with SQLite at {db_path}")
    
    # Initialize MQTT client
    # ... existing MQTT client initialization ...
    
    # Initialize device manager with MQTT client and state store
    device_manager = DeviceManager(
        mqtt_client=None,
        config_manager=config_manager,
        store=state_store  # Inject state store here
    )
    
    # ... rest of existing initialization ...
    
    yield  # Service is running
    
    # Shutdown
    logger.info("System shutting down...")
    await mqtt_client.disconnect()
    await device_manager.shutdown_devices()
    
    # Close state store after device shutdown but before final log
    await state_store.close()
    logger.info("State persistence connection closed")
    
    logger.info("System shutdown complete")
```

* Update `SystemConfig` schema to include persistence configuration:

```python
# In app/schemas.py
class PersistenceConfig(BaseModel):
    db_path: str = "data/state_store.db"
    
class SystemConfig(BaseModel):
    # ... existing fields ...
    persistence: PersistenceConfig = PersistenceConfig()
```

* Add the HTTP endpoints to the appropriate router file (likely `app/routers/system.py`):

```python
# In app/routers/system.py

@router.get("/devices/{device_id}/state")
async def get_device_state(device_id: str):
    """Get the persisted state of a specific device."""
    return await state_store.get(f"device:{device_id}") or {}

@router.get("/scenario/state")
async def get_scenario_state():
    """Get the persisted state of the last active scenario."""
    return await state_store.get("scenario:last") or {}
```

---

## 4. New Classes

### 4.1 `StateStore` Protocol

```python
from typing import Protocol, Optional, Dict, Any

class StateStore(Protocol):
    async def initialize(self) -> None:
        """Initialize database connection and create necessary tables."""
        
    async def close(self) -> None:
        """Close database connection and release resources."""
        
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return the JSON-loaded dict for `key`, or None if missing."""
        
    async def set(self, key: str, value: Dict[str, Any]) -> None:
        """Persist `value` as JSON under `key`. Overwrite if exists."""
        
    async def delete(self, key: str) -> None:
        """Remove the persisted entry for `key`, if any."""
```

### 4.2 `SQLiteStateStore`

```python
import json
import aiosqlite
import asyncio
import sys
from typing import Optional, Dict, Any

class SQLiteStateStore:
    """
    Implements StateStore using an SQLite database for JSON blobs.
    Table schema:
      - key TEXT PRIMARY KEY
      - value TEXT NOT NULL (JSON-encoded)
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None

    async def initialize(self) -> None:
        """Open database connection and create table if needed."""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            await self.connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS state_store (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                )
                '''
            )
            await self.connection.commit()
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during initialization: {e}", file=sys.stderr)
            sys.exit(1)

    async def close(self) -> None:
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = await self.connection.execute(
                'SELECT value FROM state_store WHERE key = ?', (key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            return json.loads(row[0]) if row else None
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during get operation: {e}", file=sys.stderr)
            sys.exit(1)

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        try:
            text = json.dumps(value)
            await self.connection.execute(
                '''
                INSERT INTO state_store (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                ''',
                (key, text)
            )
            await self.connection.commit()
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during set operation: {e}", file=sys.stderr)
            sys.exit(1)

    async def delete(self, key: str) -> None:
        try:
            await self.connection.execute('DELETE FROM state_store WHERE key = ?', (key,))
            await self.connection.commit()
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during delete operation: {e}", file=sys.stderr)
            sys.exit(1)
```

---

## 5. Integration & Dependency Injection

1. **Instantiate** `SQLiteStateStore` once in `main.py`.
2. **Initialize** the store at application startup and close it at shutdown.
3. **Pass** the same `store` into every manager's constructor.
4. **Remove** any direct Redis calls in services; replace with `store.get/set/delete`.
5. **Enforce** that all stored values strictly adhere to the Pydantic models defined in the scenario system specification.

---

## 6. Testing & Validation

* **Unit Tests** for `SQLiteStateStore`:

  * `get()` returns `None` for missing keys.
  * `set()` followed by `get()` returns original dict.
  * `delete()` removes key.
  * Error handling correctly terminates the application on SQLite failures.
* **Integration Tests**:

  * Simulate `DeviceManager.perform_action` and verify state persists to DB.
  * Simulate `ScenarioManager.switch_scenario` and verify scenario snapshot persists.
  * Verify Pydantic models are correctly serialized and deserialized.

---

## 7. Future Enhancements

* Add **history logging** table for versioned snapshots.
* Support **configurable backends** by loading implementation class from settings.
* Add **batch persistence** or **throttling** if write-rate concerns arise.
* Extend protocol with **query** methods for partial reads (e.g. JSON1 queries).
* Implement full recovery logic for `initialize()` methods in each manager class.

---

*End of Specification.*
