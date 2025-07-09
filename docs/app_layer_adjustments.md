# App Layer Adjustments

This document outlines the necessary changes to the `app/` layer to align with the strong-typing standardization plan and the four new requirements.

## 1. Configuration Loading & Validation

- Load `config/system.json` at startup, extracting for each device its:
  - `device_id` key
  - `class` name
  - `config_file` path
- When reading the JSON for each device, verify the embedded `"device_id"` field exactly matches the key in `system.json`.  Abort startup with an error if any mismatch is detected.
- Drop all legacy fallback logic: failure to load or parse a typed Pydantic config must be treated as a hard error.

## 2. Unify Factory & Device Instantiation

- Eliminate the hard-coded mapping in `DeviceConfigFactory`.
- In `DeviceManager.initialize_devices()`:
  1. Read the typed config from `ConfigManager` for each `device_id` defined in `system.json`.
  2. Reflectively instantiate `devices.<ClassName>(config, mqtt_client)`.
  3. Remove any separate factory file or mapping; centralize all instantiation logic here.

## 3. Deprecate HTTP `DeviceState` Wrapper

- Remove or mark deprecated the Pydantic `DeviceState` model in `app/schemas.py`.
- Change the GET `/devices/{device_id}` endpoint to return each device's own `BaseDeviceState` (or subclass) directly, instead of embedding under a `state: { ... }` envelope.
- Modify `BaseDevice.update_state()` to preserve the actual subclass of `BaseDeviceState`, so that `device_manager.get_device_state()` emits the correct typed state model.

## 4. Tighten Command API Types & Payloads

- In `app/types.py`, make `CommandResponse` generic over the state type (`StateT`) and define `state: StateT` instead of `Dict[str, Any]`.
- Update the POST `/devices/{device_id}/action` handler to:
  - Return the full `CommandResponse[StateT]` (including optional `mqtt_command`) rather than mapping into `DeviceActionResponse`.
  - Remove the redundant `message: str` field; rely on HTTP status codes and `HTTPException` for error handling.
- Audit all `emit_progress` and `mqtt_client.publish` flows to ensure `mqtt_command` payloads created in handlers propagate through unchanged.

## 5. Endpoints Requiring Changes

| Endpoint                                        | Model Before                    | Model After                               | Notes                                                 |
|-------------------------------------------------|---------------------------------|-------------------------------------------|-------------------------------------------------------|
| GET `/config/device/{device_id}`                | `DeviceConfig` (legacy)         | `BaseDeviceConfig` (typed)               | Return only typed config; 404 if missing             |
| GET `/config/devices`                           | `Dict[str,DeviceConfig]`        | `Dict[str,BaseDeviceConfig]`             | Use `get_all_typed_configs()`                         |
| GET `/devices/{device_id}`                      | `DeviceState` wrapper           | `BaseDeviceState` (subclass)             | Return `device.get_current_state()` directly          |
| POST `/devices/{device_id}/action`              | `DeviceActionResponse`          | `CommandResponse[StateT]`                | Return raw command response, include `mqtt_command`   |
| POST `/reload`                                  | `ReloadResponse`                | `ReloadResponse`                         | Now fails with 500 on config `device_id` mismatch     |

## Next Steps

1. Implement strict `device_id` mismatch checks in `ConfigManager._load_device_configs()`.
2. Collapse or remove `DeviceConfigFactory`; migrate its logic into `DeviceManager`.
3. Refactor `DeviceManager.initialize_devices()`, ensure typed configs drive instantiation.
4. Update `BaseDevice.update_state()` to preserve subclass identity.
5. Replace or remove `DeviceState` and `DeviceActionResponse` in `app/schemas.py`, adjusting route signatures in `app/main.py`.
6. Make `CommandResponse` generic in `app/types.py`, and wire through the HTTP layer. 