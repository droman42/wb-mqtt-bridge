"""VWB-19 — select-form capabilities routed through the canonical endpoint.

`set` is the reserved canonical action for a capability whose invocation lives in
`select`: `input.set {value}` resolves through `CapabilitySelect.expand()` — the same
single resolution site the scenario reconciler uses. Parametric selects (LG
`set_input_source`) rename the value via `param_map`; `by_value` selects (the IR amp's
`input_cd`/`input_aux2`) look the value up in the table. The by_value option set is
closed and statically known, so `GET /devices/{id}/options/inputs` serves the table
keys when no `list` query exists, and the catalog embeds them as static `values`.

Harness mirrors test_canonical_endpoint.py (FakeDevice/FakeDeviceManager doubles).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap, CapabilitySelect
from wb_mqtt_bridge.presentation.api.catalog import _project_capability_actions
from wb_mqtt_bridge.presentation.api.routers import devices as devices_router


# ----- Test doubles (test_canonical_endpoint.py pattern) --------------------


class FakeDevice:
    def __init__(
        self,
        device_id: str,
        capabilities: CapabilityMap,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.device_id = device_id
        self.capabilities = capabilities
        self.state = SimpleNamespace(**(initial_state or {"input": "none"}))
        if not hasattr(self.state, "reachable"):
            self.state.reachable = True
        self.state.model_dump = lambda: {
            k: v for k, v in self.state.__dict__.items() if not callable(v)
        }
        self._state_change_callbacks: List[Any] = []

    def register_state_change_callback(self, cb) -> None:
        self._state_change_callbacks.append(cb)

    def _notify(self):
        for cb in list(self._state_change_callbacks):
            cb(self.device_id, [])


class FakeDeviceManager:
    def __init__(self, devices: Dict[str, FakeDevice], handlers: Dict[str, Any]) -> None:
        self.devices = devices
        self.handlers = handlers

    def get_device(self, device_id: str) -> Optional[FakeDevice]:
        return self.devices.get(device_id)

    async def perform_action(self, device_id: str, command: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        device = self.devices.get(device_id)
        assert device is not None
        return await self.handlers[device_id](device, command, params)


# ----- Capability-map fixtures (the two shipped select forms) ---------------


def _parametric_input_map() -> CapabilityMap:
    """LG-TV shape: parametric select + runtime list query."""
    return CapabilityMap.model_validate({
        "input": {
            "kind": "stateful",
            "feedback": True,
            "state_field": "input_source",
            "select": {"command": "set_input_source", "param_map": {"input": "source"}},
            "list": {"command": "get_available_inputs"},
        }
    })


def _by_value_input_map() -> CapabilityMap:
    """IR-amp shape: one native command per value, no list query."""
    return CapabilityMap.model_validate({
        "input": {
            "kind": "stateful",
            "feedback": False,
            "state_field": "input",
            "select": {"by_value": {
                "cd":   {"command": "input_cd"},
                "aux2": {"command": "input_aux2"},
                "usb":  {"command": "input_usb"},
            }},
        }
    })


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(devices_router.router)
    return app


@pytest.fixture
def faked():
    devices: Dict[str, FakeDevice] = {}
    handlers: Dict[str, Any] = {}
    dm = FakeDeviceManager(devices, handlers)
    devices_router.initialize(cfg_manager=None, dev_manager=dm, mqt_client=None)
    client = TestClient(_app())
    yield SimpleNamespace(client=client, devices=devices, handlers=handlers, dm=dm)
    devices_router.initialize(None, None, None)


# ----- Domain: CapabilitySelect.expand / option_values ----------------------


def test_expand_parametric_renames_and_overlays():
    sel = CapabilitySelect.model_validate({
        "command": "set_input_source",
        "param_map": {"input": "source"},
        "params": {"zone": 1},
    })
    steps = sel.expand("hdmi2")
    assert len(steps) == 1
    assert steps[0].command == "set_input_source"
    assert steps[0].params == {"source": "hdmi2", "zone": 1}


def test_expand_parametric_defaults_to_input_param():
    sel = CapabilitySelect.model_validate({"command": "set_source"})
    steps = sel.expand("tape")
    assert steps[0].params == {"input": "tape"}


def test_expand_by_value_looks_up_table():
    sel = CapabilitySelect.model_validate(
        {"by_value": {"cd": {"command": "input_cd"}, "usb": {"command": "input_usb"}}}
    )
    steps = sel.expand("cd")
    assert len(steps) == 1
    assert steps[0].command == "input_cd" and steps[0].params == {}


def test_expand_by_value_unknown_names_valid_set():
    sel = CapabilitySelect.model_validate(
        {"by_value": {"cd": {"command": "input_cd"}, "usb": {"command": "input_usb"}}}
    )
    with pytest.raises(ValueError) as ei:
        sel.expand("bluetooth")
    assert "cd" in str(ei.value) and "usb" in str(ei.value)


def test_option_values_static_for_by_value_none_for_parametric():
    by_value = CapabilitySelect.model_validate(
        {"by_value": {"cd": {"command": "input_cd"}, "aux2": {"command": "input_aux2"}}}
    )
    assert by_value.option_values() == ["cd", "aux2"]  # declaration order
    parametric = CapabilitySelect.model_validate({"command": "set_input_source"})
    assert parametric.option_values() is None


# ----- Endpoint: canonical `set` through select ------------------------------


def test_canonical_set_parametric(faked):
    dev = FakeDevice("lg_tv", _parametric_input_map(), {"input_source": "home"})
    faked.devices["lg_tv"] = dev

    async def handler(d, cmd, params):
        assert cmd == "set_input_source"
        assert params == {"source": "hdmi2"}
        d.state.input_source = "hdmi2"
        d._notify()
        return {"success": True}

    faked.handlers["lg_tv"] = handler
    r = faked.client.post(
        "/devices/lg_tv/canonical",
        json={"capability": "input", "action": "set", "params": {"value": "hdmi2"}},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["success"] is True
    assert body["state"]["input_source"] == "hdmi2"


def test_canonical_set_by_value(faked):
    dev = FakeDevice("mf_amplifier", _by_value_input_map(), {"input": "aux1"})
    faked.devices["mf_amplifier"] = dev

    async def handler(d, cmd, params):
        assert cmd == "input_cd" and params == {}
        d.state.input = "cd"
        d._notify()
        return {"success": True}

    faked.handlers["mf_amplifier"] = handler
    r = faked.client.post(
        "/devices/mf_amplifier/canonical",
        json={"capability": "input", "action": "set", "params": {"value": "cd"}},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["state"]["input"] == "cd"


def test_canonical_set_unknown_value_is_param_invalid(faked):
    faked.devices["mf_amplifier"] = FakeDevice("mf_amplifier", _by_value_input_map())
    r = faked.client.post(
        "/devices/mf_amplifier/canonical",
        json={"capability": "input", "action": "set", "params": {"value": "bluetooth"}},
    )
    assert r.status_code == 400
    err = r.json()["detail"]["error"]
    assert err["code"] == "param_invalid"
    assert err["reason"] == "unknown_value"
    assert "cd" in err["message"]  # speakable: names the valid set


def test_canonical_set_missing_value_is_param_invalid(faked):
    faked.devices["lg_tv"] = FakeDevice("lg_tv", _parametric_input_map())
    r = faked.client.post(
        "/devices/lg_tv/canonical",
        json={"capability": "input", "action": "set"},
    )
    assert r.status_code == 400
    err = r.json()["detail"]["error"]
    assert err["code"] == "param_invalid" and err["field"] == "value"


def test_canonical_set_without_select_stays_action_not_supported(faked):
    cap_map = CapabilityMap.model_validate({
        "power": {"kind": "momentary", "actions": {"on": {"command": "power_on"}}}
    })
    faked.devices["plain"] = FakeDevice("plain", cap_map)
    r = faked.client.post(
        "/devices/plain/canonical",
        json={"capability": "power", "action": "set", "params": {"value": "on"}},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "action_not_supported"


def test_authored_set_action_wins_over_select(faked):
    """Dispatch precedence: an authored `set` action beats the select-form route."""
    cap_map = CapabilityMap.model_validate({
        "input": {
            "kind": "stateful",
            "state_field": "input",
            "actions": {"set": {"command": "authored_set"}},
            "select": {"command": "select_set"},
        }
    })
    dev = FakeDevice("both", cap_map, {"input": "a"})
    faked.devices["both"] = dev

    async def handler(d, cmd, params):
        assert cmd == "authored_set"
        d.state.input = "b"
        d._notify()
        return {"success": True}

    faked.handlers["both"] = handler
    r = faked.client.post(
        "/devices/both/canonical",
        json={"capability": "input", "action": "set", "params": {"value": "b"}},
    )
    assert r.status_code == 200, r.json()


# ----- Options endpoint: by_value static fallback ----------------------------


def test_options_inputs_serves_by_value_keys_without_list(faked):
    faked.devices["mf_amplifier"] = FakeDevice("mf_amplifier", _by_value_input_map())
    r = faked.client.get("/devices/mf_amplifier/options/inputs")
    assert r.status_code == 200
    assert r.json() == {"success": True, "data": ["cd", "aux2", "usb"]}


def test_options_inputs_404_when_neither_list_nor_by_value(faked):
    cap_map = CapabilityMap.model_validate({
        "input": {"kind": "stateful", "state_field": "input",
                  "select": {"command": "set_source"}}
    })
    faked.devices["bare"] = FakeDevice("bare", cap_map)
    r = faked.client.get("/devices/bare/options/inputs")
    assert r.status_code == 404


# ----- Catalog projection: `set` advertised ----------------------------------


def test_catalog_advertises_set_with_static_values_for_by_value():
    caps = _project_capability_actions(_by_value_input_map())
    (input_cap,) = [c for c in caps if c.name == "input"]
    (set_action,) = [a for a in (input_cap.actions or []) if a.name == "set"]
    (param,) = set_action.params or []
    assert param.name == "value" and param.required is True
    assert param.options_from is None
    assert [v.canonical for v in (param.values or [])] == ["cd", "aux2", "usb"]


def test_catalog_advertises_set_with_options_from_for_parametric():
    caps = _project_capability_actions(_parametric_input_map())
    (input_cap,) = [c for c in caps if c.name == "input"]
    (set_action,) = [a for a in (input_cap.actions or []) if a.name == "set"]
    (param,) = set_action.params or []
    assert param.values is None
    assert param.options_from == "inputs"


def test_catalog_husk_unsuppressed_by_set():
    """Pre-VWB-19 the select-only `input` capability projected as an empty husk and was
    suppressed (VWB-20); with `set` advertised it is a real catalog entry again."""
    caps = _project_capability_actions(_parametric_input_map())
    assert [c.name for c in caps] == ["input"]


def test_catalog_does_not_duplicate_authored_set():
    cap_map = CapabilityMap.model_validate({
        "input": {
            "kind": "stateful",
            "state_field": "input",
            "actions": {"set": {"command": "authored_set"}},
            "select": {"command": "select_set"},
        }
    })
    caps = _project_capability_actions(cap_map)
    (input_cap,) = caps
    assert [a.name for a in (input_cap.actions or [])].count("set") == 1


# ----- DRV-21: reserved cross-cutting params survive select-form dispatch ----
# The actions-form path forwards ALL incoming params through CapabilityAction.expand,
# but select-form expand takes only `value`. Before the fix the reserved force/
# assume_state params were dropped, so the UI's re-tap-to-force escape hatch was dead
# for AV inputs (Emotiva/LG/Auralic) and an input desync could never be recovered.


def test_canonical_set_parametric_forwards_force(faked):
    """`input.set {value, force}` -> the handler must see force alongside the renamed
    native value on the parametric (LG/Emotiva/Auralic) path."""
    dev = FakeDevice("lg_tv", _parametric_input_map(), {"input_source": "home"})
    faked.devices["lg_tv"] = dev
    seen: Dict[str, Any] = {}

    async def handler(d, cmd, params):
        seen["cmd"], seen["params"] = cmd, params
        d.state.input_source = "hdmi2"
        d._notify()
        return {"success": True}

    faked.handlers["lg_tv"] = handler
    r = faked.client.post(
        "/devices/lg_tv/canonical",
        json={"capability": "input", "action": "set",
              "params": {"value": "hdmi2", "force": True}},
    )
    assert r.status_code == 200, r.json()
    assert seen["cmd"] == "set_input_source"
    assert seen["params"] == {"source": "hdmi2", "force": True}


def test_canonical_set_by_value_forwards_force(faked):
    """`input.set {value, force}` -> the by_value (IR amp) step is `input_cd {}`, so the
    handler sees exactly {force: True}."""
    dev = FakeDevice("mf_amplifier", _by_value_input_map(), {"input": "aux1"})
    faked.devices["mf_amplifier"] = dev
    seen: Dict[str, Any] = {}

    async def handler(d, cmd, params):
        seen["cmd"], seen["params"] = cmd, params
        d.state.input = "cd"
        d._notify()
        return {"success": True}

    faked.handlers["mf_amplifier"] = handler
    r = faked.client.post(
        "/devices/mf_amplifier/canonical",
        json={"capability": "input", "action": "set",
              "params": {"value": "cd", "force": True}},
    )
    assert r.status_code == 200, r.json()
    assert seen["cmd"] == "input_cd"
    assert seen["params"] == {"force": True}


def test_canonical_set_forwards_assume_state(faked):
    """The other reserved param (assume_state, SCN-11) rides through select-form too."""
    dev = FakeDevice("mf_amplifier", _by_value_input_map(), {"input": "aux1"})
    faked.devices["mf_amplifier"] = dev
    seen: Dict[str, Any] = {}

    async def handler(d, cmd, params):
        seen["params"] = params
        d.state.input = "cd"
        d._notify()
        return {"success": True}

    faked.handlers["mf_amplifier"] = handler
    r = faked.client.post(
        "/devices/mf_amplifier/canonical",
        json={"capability": "input", "action": "set",
              "params": {"value": "cd", "assume_state": "cd"}},
    )
    assert r.status_code == 200, r.json()
    assert seen["params"] == {"assume_state": "cd"}
