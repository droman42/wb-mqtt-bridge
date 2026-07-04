"""SCN-7 (canonical-first phase 2): device manifests carry canonical annotations, the
canonical endpoint's wait:false mode, option enumeration as a READ, and the shared §6
param-descriptor projection."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from wb_mqtt_bridge.app import app as main_app
from wb_mqtt_bridge.domain.capabilities.models import CapabilityAction, CapabilityMap
from wb_mqtt_bridge.presentation.api.layout_engine import build_device_manifest
from wb_mqtt_bridge.presentation.api.param_projection import project_action_params, project_params
from wb_mqtt_bridge.presentation.api.routers import devices as devices_router

pytestmark = pytest.mark.unit


# ---- §6 param projection ------------------------------------------------------

def _param(name, **kw):
    return SimpleNamespace(name=name, type=kw.get("type", "range"), required=kw.get("required", True),
                           default=kw.get("default"), min=kw.get("min"), max=kw.get("max"),
                           description=kw.get("description", ""))


def test_projection_excludes_capability_fixed_params():
    cmd = SimpleNamespace(params=[_param("value", min=-96, max=11), _param("zone", type="integer")])
    cap_action = CapabilityAction.model_validate(
        {"command": "set_volume", "param_map": {"level": "value"}, "params": {"zone": 2}}
    )
    native_view = project_params(cmd, cap_action, canonical_names=False)
    assert [d["name"] for d in native_view] == ["value"]  # zone is fixed -> excluded

    canonical_view = project_params(cmd, cap_action, canonical_names=True)
    assert [d["name"] for d in canonical_view] == ["level"]  # renamed via reversed param_map
    assert canonical_view[0]["min"] == -96 and canonical_view[0]["max"] == 11


def test_projection_sequence_unions_step_params():
    action = CapabilityAction.model_validate({
        "sequence": [
            {"command": "wake"},
            {"command": "seek", "param_map": {"pos": "position"}},
        ]
    })
    cmds = {
        "wake": SimpleNamespace(params=[]),
        "seek": SimpleNamespace(params=[_param("position", type="integer")]),
    }
    descriptors = project_action_params(action, cmds)
    assert descriptors is not None
    assert [d["name"] for d in descriptors] == ["pos"]


# ---- device manifest annotations ------------------------------------------------

DEVICE_MAP = {
    "power": {
        "kind": "stateful",
        "state_field": "power",
        "actions": {"on": {"command": "power_on"}, "off": {"command": "power_off"}},
    },
    "volume": {
        "kind": "momentary",
        "actions": {"up": {"command": "volume_up"}, "down": {"command": "volume_down"}},
    },
}


def _device(device_id="amp"):
    cmds = {
        name: SimpleNamespace(action=name, description="", params=[])
        for name in ["power_on", "power_off", "volume_up", "volume_down"]
    }
    d = SimpleNamespace(
        device_id=device_id,
        capabilities=CapabilityMap.model_validate(DEVICE_MAP),
        config=SimpleNamespace(
            device_id=device_id, names=SimpleNamespace(ru="Усилитель", en="Amp"),
            device_class="TestAmp", device_category="device",
        ),
        state={"power": "off"},
    )
    d.get_available_commands = lambda: cmds
    return d


def test_device_manifest_actions_carry_canonical_tuples():
    manifest = build_device_manifest(_device())
    dumped = manifest.model_dump(by_alias=True)

    found = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("actionName") and node.get("canonicalCapability"):
                found[node["actionName"]] = (node["canonicalCapability"], node["canonicalAction"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(dumped["remoteZones"])
    assert found["power_on"] == ("power", "on")
    assert found["volume_up"] == ("volume", "up")
    # device manifests carry no sourceDeviceId (the target is the device itself)
    assert dumped.get("canonicalEntityId") is None


# ---- wait:false + options endpoint -----------------------------------------------

@pytest.fixture
def client_world():
    device = _device()
    device.capabilities = CapabilityMap.model_validate({
        **DEVICE_MAP,
        "input": {
            "kind": "stateful",
            "state_field": "input",
            "select": {"by_value": {"cd": {"command": "input_cd"}}},
            "list": {"command": "get_available_inputs"},
        },
    })
    device.execute_action = AsyncMock(return_value={"success": True, "data": [
        {"input_id": "cd", "input_name": "CD"},
    ]})
    dm = SimpleNamespace(
        devices={"amp": device},
        get_device=lambda i: {"amp": device}.get(i),
        perform_action=AsyncMock(return_value={"success": True, "data": {}}),
    )
    devices_router.initialize(MagicMock(), dm, None, None)
    return SimpleNamespace(client=TestClient(main_app), device=device, dm=dm)


def test_wait_false_returns_without_echo(client_world):
    # No state-change callback hook on this fake: with wait:true this would 503 on
    # echo timeout; wait:false must return current state immediately.
    r = client_world.client.post(
        "/devices/amp/canonical",
        json={"capability": "volume", "action": "up", "wait": False},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_options_endpoint_is_the_read_surface(client_world):
    r = client_world.client.get("/devices/amp/options/inputs")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"][0]["input_id"] == "cd"
    # executed internally with source="system" (a dormant list command still answers)
    client_world.device.execute_action.assert_awaited_with(
        "get_available_inputs", {}, source="system"
    )


def test_options_endpoint_404s(client_world):
    assert client_world.client.get("/devices/amp/options/nope").status_code == 404
    assert client_world.client.get("/devices/ghost/options/inputs").status_code == 404
    # apps: no apps capability on this device -> 404 with a clear message
    r = client_world.client.get("/devices/amp/options/apps")
    assert r.status_code == 404
    assert "apps.list" in r.json()["detail"]
