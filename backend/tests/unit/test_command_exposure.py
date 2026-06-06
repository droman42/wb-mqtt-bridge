"""Step-1 batch 3/3 — command exposure: the load-time validation rule + the execute_action gate.

- `referenced_commands` / `validate_command_exposure`: a command on a `device_category=device`
  device must be `exposed: false` OR backed by a capability (else it'd be invisible in a Layer-3
  manifest). Appliances are exempt.
- `execute_action` rejects `exposed: false` actions from external sources (api/mqtt); internal
  callers (scenario/system/cli) bypass.
"""
import json
from pathlib import Path

from wb_mqtt_bridge.infrastructure.capabilities.loader import (
    load_capability_map,
    referenced_commands,
    validate_command_exposure,
)


def _config_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "devices").is_dir():
            return parent / "config"
    raise RuntimeError("backend/config not found")


CONFIG = _config_dir()


def test_real_configs_have_no_exposure_violations():
    """Drift guard: every in-scope command is exposed:false OR capability-backed."""
    violations = []
    for f in sorted((CONFIG / "devices").glob("*.json")):
        cfg = json.loads(f.read_text())
        if cfg.get("device_category", "device") == "appliance":
            continue
        cap = load_capability_map(cfg.get("device_class", ""), f.stem, CONFIG / "capabilities")
        backed = referenced_commands(cap)
        for name, cmd in (cfg.get("commands") or {}).items():
            if (cmd or {}).get("exposed", True) and name not in backed:
                violations.append(f"{f.stem}.{name}")
    assert violations == [], f"exposed but not capability-backed: {violations}"


class _Cfg:
    def __init__(self, category):
        self.device_category = category


class _Cmd:
    def __init__(self, exposed=True):
        self.exposed = exposed


class _Dev:
    def __init__(self, config, cap, cmds):
        self.config, self.capabilities, self._cmds = config, cap, cmds

    def get_available_commands(self):
        return self._cmds


def test_validate_command_exposure_rule():
    empty = load_capability_map("Nope", "nope", CONFIG / "capabilities")  # empty map
    bad = _Dev(_Cfg("device"), empty, {"x": _Cmd(exposed=True)})
    assert validate_command_exposure({"bad": bad}) == ["bad.x"]
    dormant = _Dev(_Cfg("device"), empty, {"x": _Cmd(exposed=False)})
    assert validate_command_exposure({"ok": dormant}) == []
    appliance = _Dev(_Cfg("appliance"), empty, {"x": _Cmd(exposed=True)})
    assert validate_command_exposure({"app": appliance}) == []


async def test_execute_action_exposure_gate():
    from wb_mqtt_bridge.infrastructure.config.models import BaseDeviceConfig, StandardCommandConfig
    from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice

    class _StubDev(BaseDevice):
        async def setup(self):
            return True

        async def shutdown(self):
            return True

        def subscribe_topics(self):
            return []

        async def handle_message(self, topic, payload):
            return None

    cfg = BaseDeviceConfig(
        device_id="stub", names={"ru": "Stub", "en": "Stub"}, device_class="X", config_class="Y",
        commands={"secret": StandardCommandConfig(action="secret", exposed=False)},
    )
    dev = _StubDev(cfg)

    api = await dev.execute_action("secret", source="api")
    assert not api["success"] and "not exposed" in (api.get("error") or "")

    # internal sources bypass the gate (they fail later for a missing handler, not "not exposed")
    internal = await dev.execute_action("secret", source="scenario")
    assert "not exposed" not in (internal.get("error") or "")
