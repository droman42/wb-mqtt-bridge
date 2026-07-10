"""Tests for the canonical action endpoint (§P3.7 slice #15).

The endpoint resolves `(capability, action, params)` through the device's capability map
(class → profile → per-device override; the profile mechanism landed in #14) and invokes
the native command via `perform_action`. The response is synchronous with a ~500 ms timeout
waiting for the value-topic echo, and surfaces the 6-code structured error enum.

We test the full slice on three device shapes:

- A fake **AV-style synchronous** device whose handler updates state inside
  `perform_action` (LG TV / Apple TV pattern): the state-change waiter fires immediately;
  the response carries the post-state.
- A fake **WB-passthrough-style asynchronous** device whose handler publishes-and-returns
  and where the value-topic echo arrives later via a background task (the
  `WbPassthroughDevice._on_value_message` pattern). The state-change waiter unblocks the
  instant the echo lands, well within the 500 ms budget.
- A **silent** device whose handler succeeds but never updates state → `device_unreachable`
  by timeout. Exercises the contract's "no echo within 500 ms" path.

Each error code from the enum gets a dedicated test:
  device_not_found · capability_not_supported · action_not_supported · param_invalid ·
  device_unreachable · internal_error.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wb_mqtt_bridge.domain.capabilities.models import CapabilityMap
from wb_mqtt_bridge.presentation.api.routers import devices as devices_router


# ----- Test doubles ---------------------------------------------------------


class FakeDevice:
    """Minimal device shape the canonical endpoint touches: capabilities + state +
    register_state_change_callback. Subclasses customise execute_action's effects."""

    def __init__(
        self,
        device_id: str,
        capabilities: CapabilityMap,
        initial_state: Optional[Dict[str, Any]] = None,
        reachable: bool = True,
    ) -> None:
        self.device_id = device_id
        self.capabilities = capabilities
        self.state = SimpleNamespace(**(initial_state or {"power": "off"}))
        if not hasattr(self.state, "reachable"):
            self.state.reachable = reachable
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
    """Mimics the bits of DeviceManager the endpoint uses. perform_action delegates to a
    handler the test injects per device."""

    def __init__(self, devices: Dict[str, FakeDevice], handlers: Dict[str, Any]) -> None:
        self.devices = devices
        self.handlers = handlers  # device_id -> async fn (device, command, params) -> result

    def get_device(self, device_id: str) -> Optional[FakeDevice]:
        return self.devices.get(device_id)

    async def perform_action(self, device_id: str, command: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        device = self.devices.get(device_id)
        assert device is not None  # endpoint catches missing before calling us
        return await self.handlers[device_id](device, command, params)


# ----- Fixtures -------------------------------------------------------------


def _light_switch_cap_map() -> CapabilityMap:
    """The same `light_switch` profile shape that lives in `config/capabilities/profiles/`."""
    return CapabilityMap.model_validate({
        "power": {
            "kind": "momentary",
            "actions": {
                "on":  {"command": "power_on"},
                "off": {"command": "power_off"},
            },
        }
    })


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(devices_router.router)
    return app


@pytest.fixture
def faked():
    """Build an app + injected dependencies, returning a small bundle the tests use."""
    devices: Dict[str, FakeDevice] = {}
    handlers: Dict[str, Any] = {}
    dm = FakeDeviceManager(devices, handlers)
    devices_router.initialize(cfg_manager=None, dev_manager=dm, mqt_client=None)
    client = TestClient(_app())
    yield SimpleNamespace(client=client, devices=devices, handlers=handlers, dm=dm)
    devices_router.initialize(None, None, None)


# ----- Happy path: sync (AV-style) + async (WB-passthrough-style) -----------


def test_av_sync_state_update_returns_immediately(faked):
    """AV-style: the handler updates state inside perform_action; the waiter is already
    set when the endpoint awaits. The response carries the post-state."""
    dev = FakeDevice("lg_tv", _light_switch_cap_map(), {"power": "off"})
    faked.devices["lg_tv"] = dev

    async def handler(d, cmd, params):
        assert cmd == "power_on"  # canonical->native resolution worked
        d.state.power = "on"
        d._notify()  # AV drivers fire callbacks via update_state during execute
        return {"success": True, "device_id": "lg_tv", "action": cmd, "state": {}}

    faked.handlers["lg_tv"] = handler
    r = faked.client.post(
        "/devices/lg_tv/canonical",
        json={"capability": "power", "action": "on", "params": None},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["success"] is True
    assert body["capability"] == "power" and body["action"] == "on"
    assert body["state"]["power"] == "on"
    assert body["error"] is None


def test_wb_passthrough_async_echo_unblocks_waiter(faked):
    """WB-passthrough-style: the handler publishes-and-returns; the echo arrives on a
    background task, fires the device's state-change callbacks. The endpoint unblocks
    well within the 500 ms budget."""
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(), {"mirrored": {}, "reachable": True})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        # Simulate the MQTT echo arriving asynchronously a few ms after the publish.
        async def echo():
            await asyncio.sleep(0.05)
            d.state.mirrored = {"power": "1"}
            d._notify()
        asyncio.create_task(echo())
        return {"success": True, "device_id": "cabinet_spots", "action": cmd, "state": {}}

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["success"] is True
    assert body["state"]["mirrored"] == {"power": "1"}


# ----- Each of the 6 error codes -------------------------------------------


def test_device_not_found_returns_404_with_code(faked):
    r = faked.client.post(
        "/devices/nope/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["success"] is False
    assert detail["error"]["code"] == "device_not_found"


def test_capability_not_supported_returns_404(faked):
    cap_map = CapabilityMap.model_validate({})  # nothing supported
    dev = FakeDevice("cabinet_spots", cap_map, {"power": "off"})
    faked.devices["cabinet_spots"] = dev
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "volume", "action": "up"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "capability_not_supported"


def test_action_not_supported_returns_404(faked):
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(), {"power": "off"})
    faked.devices["cabinet_spots"] = dev
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "toggle"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "action_not_supported"


def test_param_invalid_returns_400_when_handler_reports_a_param_error(faked):
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(), {"power": "off"})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        return {"success": False, "error": "required param 'level' missing"}

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "param_invalid"


def test_device_unreachable_returns_503_on_timeout(faked, monkeypatch):
    """No state-change ever fires → the wait hits the timeout → device_unreachable."""
    monkeypatch.setattr(devices_router, "CANONICAL_ECHO_TIMEOUT_S", 0.05)
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(), {"power": "off"})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        # Silent: succeeds without notifying.
        return {"success": True, "device_id": "cabinet_spots", "action": cmd, "state": {}}

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"]["code"] == "device_unreachable"


def test_device_unreachable_returns_503_when_reachable_flips_false(faked):
    """A `meta/error` `r` flag landing during the wait flips state.reachable to False -- per
    the Wirenboard MQTT convention (A3). The endpoint surfaces device_unreachable."""
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(),
                     {"mirrored": {}, "reachable": True, "error_flags": {}})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        async def err_echo():
            await asyncio.sleep(0.02)
            d.state.reachable = False
            d.state.error_flags = {"power": "r"}
            d._notify()
        asyncio.create_task(err_echo())
        return {"success": True, "device_id": "cabinet_spots", "action": cmd, "state": {}}

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 503
    err = r.json()["detail"]["error"]
    assert err["code"] == "device_unreachable"


def test_internal_error_returns_500_for_non_param_handler_failure(faked):
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(), {"power": "off"})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        return {"success": False, "error": "MQTT client unavailable"}

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 500
    assert r.json()["detail"]["error"]["code"] == "internal_error"


# ----- No-op short-circuit -------------------------------------------------


def test_no_op_result_skips_wait_and_returns_immediately(faked):
    """When the driver flags `data.no_op = True` (WB-passthrough's idempotency case --
    device already at the requested value, no echo will arrive), the endpoint must NOT
    wait for the echo. Otherwise voice gets a spurious 503 on "включи свет" when the
    light is already on."""
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(),
                     {"mirrored": {"power": "1"}, "reachable": True})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        # Critically: handler does NOT call d._notify(). If the endpoint waited, it would
        # 503-timeout. The no_op flag must short-circuit that wait.
        return {
            "success": True, "device_id": "cabinet_spots", "action": cmd,
            "state": {}, "data": {"no_op": True},
        }

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["success"] is True
    # Current state is returned -- still shows mirrored at "1".
    assert body["state"]["mirrored"] == {"power": "1"}


def test_no_op_false_still_waits_for_echo(faked):
    """Driver result with `data.no_op = False` (real change) must still wait for the
    echo as before. AV handlers without `no_op` in data take the same path."""
    dev = FakeDevice("cabinet_spots", _light_switch_cap_map(),
                     {"mirrored": {}, "reachable": True})
    faked.devices["cabinet_spots"] = dev

    async def handler(d, cmd, params):
        # Async echo schedules into the wait window.
        async def echo():
            import asyncio as _a
            await _a.sleep(0.02)
            d.state.mirrored = {"power": "1"}
            d._notify()
        import asyncio as _a
        _a.create_task(echo())
        return {
            "success": True, "device_id": "cabinet_spots", "action": cmd,
            "state": {}, "data": {"no_op": False},
        }

    faked.handlers["cabinet_spots"] = handler
    r = faked.client.post(
        "/devices/cabinet_spots/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 200
    assert r.json()["state"]["mirrored"] == {"power": "1"}


# ----- DRV-5: idempotence-skip marker + reserved force param -----------------


def test_idempotence_skip_marker_rides_wait_false(faked):
    """An idempotence-guard skip (`data.skipped_reason='idempotence'`) must surface in
    the wait:false response — the UI's mash-click mode is exactly where the re-tap-to-
    force offer arms. The reserved `force` param must also pass through the canonical
    expansion untouched (names absent from param_map pass through by name)."""
    dev = FakeDevice("ir_amp", _light_switch_cap_map(), {"power": "on", "reachable": True})
    faked.devices["ir_amp"] = dev
    seen_params = {}

    async def handler(d, cmd, params):
        seen_params.update(params or {})
        return {
            "success": True, "device_id": "ir_amp", "action": cmd,
            "state": {}, "data": {"no_op": True, "skipped_reason": "idempotence"},
        }

    faked.handlers["ir_amp"] = handler
    r = faked.client.post(
        "/devices/ir_amp/canonical",
        json={"capability": "power", "action": "on", "params": {"force": True}, "wait": False},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["success"] is True
    assert body["no_op"] is True
    assert body["skipped_reason"] == "idempotence"
    assert seen_params.get("force") is True  # reserved param reached the handler


def test_idempotence_skip_short_circuits_echo_wait(faked):
    """wait:true + an idempotence skip: the guard fires no update_state, so no echo will
    ever land — the no_op short-circuit must return success (with the marker) instead of
    a spurious 503 device_unreachable. This is the voice path for «включи» on an IR
    device the bridge already believes is on."""
    dev = FakeDevice("ir_amp", _light_switch_cap_map(), {"power": "on", "reachable": True})
    faked.devices["ir_amp"] = dev

    async def handler(d, cmd, params):
        # Critically: no d._notify() — the endpoint would 503 if it waited.
        return {
            "success": True, "device_id": "ir_amp", "action": cmd,
            "state": {}, "data": {"no_op": True, "skipped_reason": "idempotence"},
        }

    faked.handlers["ir_amp"] = handler
    r = faked.client.post(
        "/devices/ir_amp/canonical",
        json={"capability": "power", "action": "on"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["success"] is True
    assert body["no_op"] is True
    assert body["skipped_reason"] == "idempotence"


# ----- Resolution detail: param_map renames canonical -> native ------------


def test_param_map_renames_canonical_param_to_native(faked):
    """A capability with `param_map: {level: source}` should rewrite the param key before
    handing it to perform_action. Pinned because Irene speaks canonical names; native
    drivers can keep their existing handler signatures."""
    cap_map = CapabilityMap.model_validate({
        "input": {
            "kind": "stateful", "feedback": True, "state_field": "input_source",
            "actions": {"select": {"command": "set_input_source", "param_map": {"input": "source"}}},
        },
    })
    dev = FakeDevice("lg_tv", cap_map, {"power": "on", "input_source": None})
    faked.devices["lg_tv"] = dev

    captured = {}

    async def handler(d, cmd, params):
        captured["cmd"] = cmd
        captured["params"] = params
        d.state.input_source = params["source"]
        d._notify()
        return {"success": True, "device_id": "lg_tv", "action": cmd, "state": {}}

    faked.handlers["lg_tv"] = handler
    r = faked.client.post(
        "/devices/lg_tv/canonical",
        json={"capability": "input", "action": "select", "params": {"input": "hdmi2"}},
    )
    assert r.status_code == 200, r.json()
    assert captured["cmd"] == "set_input_source"
    # `input` (canonical) was renamed to `source` (native) before perform_action saw it.
    assert captured["params"] == {"source": "hdmi2"}


# ----- DRV-29: the echo window honors the capability's gate ------------------
# The mitsubishi2wb ACs confirm on a multi-second packet rotation (settings read-back:
# PACKET_SENT_INTERVAL 1 s + 6 info packets x 2 s), so the flat 500 ms window 503'd
# every AC command while it succeeded. Capabilities now declare gate.poll_timeout_ms
# (the same per-capability timing the reconciler has always honored) and the canonical
# endpoint waits that long; ungated capabilities keep the 500 ms relay default.


def _slow_confirm_cap_map(poll_timeout_ms) -> CapabilityMap:
    return CapabilityMap.model_validate({
        "mode": {
            "kind": "stateful",
            "feedback": True,
            "state_field": "mode",
            "gate": {"poll_timeout_ms": poll_timeout_ms},
            "actions": {"set": {"command": "set_mode", "param_map": {"value": "mode"}}},
        }
    })


def test_slow_echo_succeeds_when_gate_extends_the_window(faked):
    """Echo lands at ~0.8 s — beyond the 500 ms default, inside the 3 s gate. Before
    DRV-29 this returned 503 device_unreachable for a command that worked."""
    dev = FakeDevice("children_room_hvac", _slow_confirm_cap_map(3000), {"mode": "cool"})
    faked.devices["children_room_hvac"] = dev

    async def handler(d, cmd, params):
        async def late_echo():
            await asyncio.sleep(0.8)
            d.state.mode = "heat"
            d._notify()
        asyncio.get_running_loop().create_task(late_echo())
        return {"success": True, "data": {"no_op": False}}

    faked.handlers["children_room_hvac"] = handler
    r = faked.client.post(
        "/devices/children_room_hvac/canonical",
        json={"capability": "mode", "action": "set", "params": {"value": "heat"}},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["state"]["mode"] == "heat"


def test_slow_echo_still_503s_when_no_gate(faked):
    """An ungated capability keeps the 500 ms default — the relay fleet's behavior is
    byte-identical to before DRV-29."""
    dev = FakeDevice("children_room_hvac", _slow_confirm_cap_map(None), {"mode": "cool"})
    faked.devices["children_room_hvac"] = dev

    async def handler(d, cmd, params):
        return {"success": True, "data": {"no_op": False}}  # no echo ever

    faked.handlers["children_room_hvac"] = handler
    r = faked.client.post(
        "/devices/children_room_hvac/canonical",
        json={"capability": "mode", "action": "set", "params": {"value": "heat"}},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"]["code"] == "device_unreachable"
    assert "500 ms" in r.json()["detail"]["error"]["message"]
