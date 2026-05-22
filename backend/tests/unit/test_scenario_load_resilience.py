"""Bug 2: load_scenarios must never be fatal.

A scenario that references a device which isn't available (off/unreachable at boot, or a
genuine config error) must be logged and skipped, not crash the whole bridge with SystemExit.
"""

import json
from types import SimpleNamespace

import pytest

from wb_mqtt_bridge.domain.scenarios.service import ScenarioManager


def _manager(scenario_dir, available_device_ids):
    devices = {d: SimpleNamespace(device_id=d) for d in available_device_ids}
    device_manager = SimpleNamespace(devices=devices, get_device=lambda i: devices.get(i))

    async def _save(*a, **k):
        return None

    return ScenarioManager(
        device_manager=device_manager,
        room_manager=SimpleNamespace(),
        state_repository=SimpleNamespace(save=_save),
        scenario_dir=scenario_dir,
    )


def _write(scenario_dir, scenario_id, role_device):
    (scenario_dir / f"{scenario_id}.json").write_text(json.dumps({
        "scenario_id": scenario_id,
        "name": scenario_id,
        "source": role_device,
        "display": role_device,
        "audio": role_device,
        "roles": {"volume": role_device},
    }))


@pytest.mark.asyncio
async def test_unavailable_device_skips_scenario_without_crashing(tmp_path):
    _write(tmp_path, "good", "amp")      # references an available device
    _write(tmp_path, "bad", "ghost")     # references a missing device

    mgr = _manager(tmp_path, available_device_ids={"amp"})

    # Must NOT raise SystemExit (or anything) just because one scenario is unavailable.
    await mgr.load_scenarios()

    assert "good" in mgr.scenario_map
    assert "bad" not in mgr.scenario_map
    assert "bad" in mgr.scenario_load_errors
    assert "good" not in mgr.scenario_load_errors


@pytest.mark.asyncio
async def test_malformed_json_is_skipped_not_fatal(tmp_path):
    _write(tmp_path, "good", "amp")
    (tmp_path / "broken.json").write_text("{ this is not valid json")

    mgr = _manager(tmp_path, available_device_ids={"amp"})
    await mgr.load_scenarios()

    assert "good" in mgr.scenario_map
    assert "broken" in mgr.scenario_load_errors


@pytest.mark.asyncio
async def test_all_available_scenarios_load_clean(tmp_path):
    _write(tmp_path, "a", "amp")
    _write(tmp_path, "b", "amp")

    mgr = _manager(tmp_path, available_device_ids={"amp"})
    await mgr.load_scenarios()

    assert set(mgr.scenario_map) == {"a", "b"}
    assert mgr.scenario_load_errors == {}
