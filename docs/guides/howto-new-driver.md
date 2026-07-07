# How-to — add a new device driver with a native library

This is the **code path**: a new physical device whose protocol no shipped
driver speaks. The result is a new `device_class` registered as an
entry-point, with its own typed config, state, capability map, and tests.

Before starting, ask whether it really needs a new driver. If the device
exposes its controls over MQTT in the Wirenboard convention,
`WbPassthroughDevice` already handles it — see
[the config-only how-to](howto-new-device.md). If it's another IR-controlled
piece of gear, the existing `WirenboardIRDevice` covers it from a config
file. A new driver class is justified when:

- The device has its own network/serial protocol with no off-the-shelf
  passthrough (most A/V gear: TVs, AVRs, streamers, players, transports).
- It needs a Python library to speak that protocol.
- Its state shape doesn't fit any existing `BaseDeviceState` subclass.

## Library requirements

The library you pick (or build) should:

- Be **async**-friendly. Drivers run in the FastAPI event loop; blocking
  I/O wedges the bridge.
- Expose **lifecycle hooks** (connect / disconnect / health) so the driver
  can implement `setup()` / `shutdown()` / reconnect.
- Either push **state updates** via a callback / subscription (preferred —
  cheap, accurate) or expose a **polling read** (acceptable, the driver
  schedules a poll loop).
- Have a **PyPI release** if possible; vendored forks are painful to keep
  in sync. The shipped drivers depend on:
  - `asyncwebostv` (LG webOS)
  - `pyatv` (Apple TV)
  - `openhomedevice` (Auralic / OpenHome)
  - `pymotivaxmc2` (eMotiva XMC-2)
  - `broadlink` (Broadlink RM RF)

Two of these (`asyncwebostv`, `pymotivaxmc2`) are sister-project libraries
the user maintains; corrections that surface during driver work round-trip
through them — that's the cleanest place to fix protocol-side bugs.

## The five things you write

A new driver lands in five places, all referenced from `pyproject.toml`:

1. **The typed state model** in `domain/devices/models.py` — a
   `BaseDeviceState` subclass.
2. **The typed config model** in `infrastructure/config/models.py` — a
   `BaseDeviceConfig` subclass.
3. **The driver itself** in `infrastructure/devices/<name>/driver.py` — a
   `BaseDevice[StateT]` subclass.
4. **The class-level capability map** in
   `config/capabilities/classes/<DeviceClass>.json`.
5. **The entry-point** in `backend/pyproject.toml` under
   `[project.entry-points."wb_mqtt_bridge.devices"]`.

Plus the OpenAPI hook (one line in `app/bootstrap.py`) and tests.

## Worked example — the shape of a native driver

The `AuralicDevice` driver shows every required piece in one place
(`backend/src/wb_mqtt_bridge/infrastructure/devices/auralic/driver.py`).
Highlights:

```python
from openhomedevice.device import Device as OpenHomeDevice

from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.domain.devices.models import AuralicDeviceState
from wb_mqtt_bridge.infrastructure.config.models import AuralicDeviceConfig
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.domain.devices.types import CommandResult


class AuralicDevice(BaseDevice[AuralicDeviceState]):
    def __init__(self, config: AuralicDeviceConfig,
                 mqtt_client: Optional[MQTTClient] = None) -> None:
        super().__init__(config, mqtt_client)
        # Initialise typed state AFTER super().__init__
        self.state = AuralicDeviceState(
            device_id=config.device_id,
            device_name=config.names.ru,
            ip_address=config.auralic.ip_address,
            volume=0, mute=False, connected=False, ...
        )

    async def setup(self) -> bool:
        # Discover + connect via the native library, subscribe to events.
        ...

    async def shutdown(self) -> bool:
        # Clean disconnect; release resources.
        ...

    def subscribe_topics(self) -> List[str]:
        # MQTT topics this driver reacts to. Many native drivers return [].
        return []

    async def handle_message(self, topic: str, payload: str) -> None:
        # Route incoming MQTT messages to the right handler. Many native
        # drivers leave this empty.
        ...

    async def handle_power_on(self, cmd_config, params) -> CommandResult:
        # The action handler. Per-action handlers are named
        # `handle_<action>` and dispatched by execute_action.
        ok = await self._device.power_on()
        if ok:
            self.update_state(connected=True)
            return CommandResult(success=True, mqtt_command=None)
        return CommandResult(success=False, error="power_on failed")
```

The pattern: `setup` connects, action handlers wrap the native library
call, `update_state(...)` flows mutations through the single chokepoint
(triggers persistence + SSE — never assign to `self.state.x` directly at
runtime), `CommandResult` is the return type for every handler.

## Typed config — what to put on it

The config holds the *parameters* the driver needs from the JSON: IP,
port, MAC, library-specific tuning. Keep it shallow and Pydantic-typed.
Example from `AuralicDeviceConfig`:

```python
class AuralicConfig(BaseModel):
    ip_address: str
    port: Optional[int] = None
    ir_power_on_topic: Optional[str] = None
    ir_power_off_topic: Optional[str] = None
    device_boot_time: int = 15


class AuralicDeviceConfig(BaseDeviceConfig):
    auralic: AuralicConfig
```

Inheriting from `BaseDeviceConfig` gives you the common fields
(`device_id`, `device_class`, `config_class`, `names`, `room`, `commands`,
`device_category`, WB-emulation toggles) for free.

## Typed state — what to put on it

The state holds everything the UI + persistence layer reads back: power,
input, volume, connection liveness, last command, plus driver-specific
fields (track title for a streamer, transport state, etc.). Example from
`AuralicDeviceState`:

```python
class AuralicDeviceState(BaseDeviceState):
    ip_address: str
    volume: int = 0
    mute: bool = False
    source: Optional[str] = None
    connected: bool = False
    track_title: Optional[str] = None
    track_artist: Optional[str] = None
    track_album: Optional[str] = None
    transport_state: Optional[str] = None
    deep_sleep: bool = False
```

`BaseDeviceState` brings `device_id`, `device_name`, `last_command`,
`error`, and helpers; you add driver-specific fields. Reach state changes
via `self.update_state(field=value, ...)` — that's the chokepoint that
hits SQLite + SSE in one call.

## Capability map — class-level

Drop a `config/capabilities/classes/<DeviceClass>.json` defining the
canonical actions the reconciler can use. The shipped `AuralicDevice.json`:

```json
{
  "power": {
    "kind": "stateful", "feedback": true,
    "state_field": "connected", "on_value": true,
    "actions": {
      "on":  { "command": "power_on" },
      "off": { "command": "power_off" }
    },
    "gate": { "poll_timeout_ms": 25000 }
  },
  "input": {
    "kind": "stateful", "feedback": true, "state_field": "source",
    "select": { "command": "set_input", "param_map": { "input": "input" } },
    "list":   { "command": "get_available_inputs" },
    "gate":   { "poll_timeout_ms": 3000 }
  },
  "volume": {
    "kind": "momentary", "state_field": "volume",
    "actions": {
      "up":   { "command": "volume_up" },
      "down": { "command": "volume_down" },
      "set":  { "command": "set_volume", "param_map": { "level": "volume" } },
      "mute_toggle": { "command": "mute" }
    }
  },
  "playback": { ... }
}
```

`feedback: true` tells the reconciler this capability's state arrives back
through the protocol — it can poll the `state_field` on the gate's
`poll_timeout_ms`. Set `feedback: false` (and supply `gate.delay_ms`) for
no-feedback (IR-style) actions where the driver fires and forgets.

See **[Architecture: key concepts](../architecture/key-concepts.md)** for
every capability field with a worked breakdown.

## Register the driver — `pyproject.toml`

```toml
[project.entry-points."wb_mqtt_bridge.devices"]
my_new_driver = "wb_mqtt_bridge.infrastructure.devices.my_new_driver.driver:MyNewDriver"
```

`DeviceManager.load_device_modules()` discovers all entries at startup;
`device_class` in a config resolves to the entry-point name (not the class
name); `config_class` resolves via `utils/class_loader.py`.

## Register the state model — OpenAPI hook

Add the state model to `OPENAPI_EXTRA_MODELS` in
`backend/src/wb_mqtt_bridge/app/bootstrap.py`:

```python
OPENAPI_EXTRA_MODELS = [
    ..., MyNewDriverState,
]
```

Then regenerate the OpenAPI schema:

```bash
cd backend
wb-openapi -o openapi.json
```

…and commit `openapi.json`. The UI's TypeScript generation
(`npm run gen:api-types`) picks the new model up from there.

A test (`tests/unit/test_openapi_schema.py`) verifies every
`OPENAPI_EXTRA_MODELS` entry actually lands in the schema — run the
suite to catch a forgotten registration.

## Tests — the recipe

Mirror an existing driver test (e.g. `tests/unit/test_auralic.py`). The
recipe in five steps:

```python
@pytest.fixture
def cfg() -> MyNewDriverConfig:
    return MyNewDriverConfig(
        device_id="my_device",
        device_class="my_new_driver",
        config_class="MyNewDriverConfig",
        names=LocalizedName(ru="Тест", en="Test", de="Test"),
        room="cabinet",
        my_thing=MyThingConfig(ip_address="10.0.0.1"),
    )

@pytest.fixture
def driver(cfg) -> MyNewDriver:
    d = MyNewDriver(cfg, mqtt_client=AsyncMock())  # 1. typed config
    d._device = AsyncMock()                          # 2. inject the external client
    # 3. bypass setup() — don't connect to real hardware
    d.state.connected = True                         # 4. prime connectivity
    return d

async def test_handle_power_on(driver):
    driver._device.power_on.return_value = True
    result = await driver.execute_action("power_on", {})
    assert result["success"]
    driver._device.power_on.assert_awaited_once()    # 5. assert external call
    assert driver.state.connected is True            #    and state mutation
```

CI runs `pytest -m "not requires_device"` — keep these tests
hardware-free. Mark genuine hardware tests with `@pytest.mark.requires_device`
so they're skipped in CI but runnable at the rack.

## Hardware-verification checklist

Before declaring a new driver "done":

- [ ] **Clean boot.** `bridge` starts, device shows `connected=True`.
- [ ] **Every action handler runs against the real device.** Power, every
      input, every transport / volume / app launch the driver exposes.
- [ ] **State arrives back through the subscription / poll.** UI page
      updates without a refresh.
- [ ] **Disconnect + reconnect recovery.** Device powered off and back on,
      bridge re-connects without restart.
- [ ] **Scenario integration.** At least one scenario that names this
      device activates end-to-end (the reconciler hits the right action
      handlers in the right order).

## When to commit, when to round-trip

- The driver, its config, state, cap map, entry-point, OpenAPI hook, and
  tests: one commit. Commit body lists the file paths, the entry-point
  name, the hardware verified, and the protocol nuances worth knowing.
- If a sibling library needs a fix (typical for `asyncwebostv` /
  `pymotivaxmc2`), ship the library change first, bump the dependency,
  then commit the driver against the pinned version.
- The action plan tracks driver work item-by-item; close the relevant
  row.

## Where to go next

- **[Architecture: devices and scenarios](../architecture/devices-and-scenarios.md)**
  — driver flavors + `DevicePort`.
- **[Architecture: key concepts](../architecture/key-concepts.md)** —
  capability-map schema in depth.
- **[How-to: add a device with an existing driver](howto-new-device.md)** —
  the config-only path for instances of an existing class.
- **[How-to: define a new AV scenario](howto-new-scenario.md)** — wire
  the new driver into a one-touch activity.
