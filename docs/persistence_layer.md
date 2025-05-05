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
* Provide placeholder `initialize()` for recovery similar to DeviceManager.

### 3.3 `app/main.py`

* Replace hard-coded database path with value read from the system configuration loaded by `ConfigurationManager`.

````python
from pathlib import Path
from fastapi import FastAPI
from .state_store import SQLiteStateStore
from .config_manager import ConfigurationManager
from .device_manager import DeviceManager
from .scenario_manager import ScenarioManager

app = FastAPI()

# Load system-wide configuration (including persistence settings)
config_manager = ConfigurationManager(config_file_path="config.json")
system_config = config_manager.system_config

# Read database filename from system configuration
# Expects: system_config.persistence.db_path is defined in your config schema
db_path = Path(system_config.persistence.db_path)
store = SQLiteStateStore(db_path=str(db_path))

# Inject shared state store into managers
# Note: pass the same system_config (or relevant sub-config) into each manager
device_manager = DeviceManager(system_config, store=store)
scenario_manager = ScenarioManager(system_config, store=store)

@app.on_event("startup")
async def startup_event():
    await device_manager.initialize()
    await scenario_manager.initialize()

@app.get("/devices/{device_id}/state")
async def get_device_state(device_id: str):
    return await store.get(f"device:{device_id}") or {}

@app.get("/scenario/state")
async def get_scenario_state():
    return await store.get("scenario:last") or {}
```python
-from .device_manager import DeviceManager
-from .scenario_manager import ScenarioManager
+from .state_store import SQLiteStateStore
+from .device_manager import DeviceManager
+from .scenario_manager import ScenarioManager

db_path = Path("state_store.db")
store = SQLiteStateStore(db_path=str(db_path))

device_manager = DeviceManager(config, store=store)
scenario_manager = ScenarioManager(config, store=store)
````

* Call both `initialize()` methods during FastAPI startup.

* Add HTTP endpoints to expose persisted state:

```python
@app.get("/devices/{device_id}/state")
async def get_device_state(device_id: str):
    return await store.get(f"device:{device_id}") or {}

@app.get("/scenario/state")
async def get_scenario_state():
    return await store.get("scenario:last") or {}
```

---

## 4. New Classes

### 4.1 `StateStore` Protocol

```python
from typing import Protocol, Optional, Dict, Any

class StateStore(Protocol):
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
        # asynchronously create table
        asyncio.create_task(self._init_db())

    async def _init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''
                CREATE TABLE IF NOT EXISTS state_store (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                )
                '''
            )
            await db.commit()

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT value FROM state_store WHERE key = ?', (key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
        return json.loads(row[0]) if row else None

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        text = json.dumps(value)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''
                INSERT INTO state_store (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                ''',
                (key, text)
            )
            await db.commit()

    async def delete(self, key: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM state_store WHERE key = ?', (key,))
            await db.commit()
```

---

## 5. Integration & Dependency Injection

1. **Instantiate** `SQLiteStateStore` once in `main.py`.
2. **Pass** the same `store` into every manager’s constructor.
3. **Remove** any direct Redis calls in services; replace with `store.get/set/delete`.

---

## 6. Testing & Validation

* **Unit Tests** for `SQLiteStateStore`:

  * `get()` returns `None` for missing keys.
  * `set()` followed by `get()` returns original dict.
  * `delete()` removes key.
* **Integration Tests**:

  * Simulate `DeviceManager.perform_action` and verify state persists to DB.
  * Simulate `ScenarioManager.switch_scenario` and verify scenario snapshot persists.

---

## 7. Future Enhancements

* Add **history logging** table for versioned snapshots.
* Support **configurable backends** by loading implementation class from settings.
* Add **batch persistence** or **throttling** if write-rate concerns arise.
* Extend protocol with **query** methods for partial reads (e.g. JSON1 queries).

---

*End of Specification.*
