# core-py — consumed pin

The shared entry-point-group discovery engine (`DynamicLoader`), owned by
locveil-commons (`packages/core-py/`, tags `core-py-vN[.M]`). The bridge vendors it
for driver discovery over the `locveil_bridge.devices` entry-point group.

This folder is the pin: the owner's tagged artifact byte-identical, the owner's
`STAMP.json` verbatim, and the strict `PIN.json` hash record. The **runtime copy**
lives at `backend/src/locveil_bridge/utils/entry_point_loader.py` and must stay
byte-identical to the pinned artifact — the conformance test
(`backend/tests/unit/test_core_py_pin_identity.py`) enforces both legs.

Never hand-edit any of this. A new owner version means a deliberate re-pin
(`python3 scripts/repin.py core-py`), then sync the runtime copy in the same change.
