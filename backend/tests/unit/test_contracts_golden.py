"""VWB-15: the committed contract artifacts must never go stale (the drift guard).

Regenerates the golden catalog (offline, deterministic — the same builder the
`wb-catalog` CLI uses) and the OpenAPI schema, and fails if the committed copies in
`contracts/` (and the UI-consumed `backend/openapi.json`) differ. Runs inside the
normal backend test job, so the check is self-contained in CI: any config /
capability-map / API change that alters the contract without a re-dump fails here
with a one-command fix.

Fix on failure (from backend/):
    uv run wb-catalog -o ../contracts/catalog.golden.json --stamp ../contracts/STAMP.json
    uv run wb-openapi -o openapi.json && cp openapi.json ../contracts/openapi.json
"""

import json
from pathlib import Path

import pytest

from wb_mqtt_bridge.cli.dump_catalog import build_offline_catalog
from wb_mqtt_bridge.cli.dump_openapi import generate_openapi

pytestmark = pytest.mark.unit

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
CONTRACTS = REPO / "contracts"

_REGEN_HINT = (
    "contract artifact stale — regenerate: "
    "`uv run wb-catalog -o ../contracts/catalog.golden.json --stamp ../contracts/STAMP.json` "
    "(and `uv run wb-openapi -o openapi.json && cp openapi.json ../contracts/openapi.json` "
    "for the API schema)"
)


def test_golden_catalog_matches_configs():
    committed = json.loads((CONTRACTS / "catalog.golden.json").read_text(encoding="utf-8"))
    regenerated = build_offline_catalog(str(BACKEND / "config")).model_dump()
    assert regenerated == committed, _REGEN_HINT


def test_openapi_pin_matches_app():
    regenerated = generate_openapi()
    committed_backend = json.loads((BACKEND / "openapi.json").read_text(encoding="utf-8"))
    assert regenerated == committed_backend, _REGEN_HINT
    committed_contract = json.loads((CONTRACTS / "openapi.json").read_text(encoding="utf-8"))
    assert regenerated == committed_contract, _REGEN_HINT


def _golden():
    return json.loads((CONTRACTS / "catalog.golden.json").read_text(encoding="utf-8"))


def _device(golden, device_id):
    return next(d for d in golden["devices"] if d["id"] == device_id)


def test_contract_v11_params_are_typed_with_units():
    """VWB-20/G1+G4: every action param descriptor is CatalogParam-shaped and
    semantic units ride the descriptor (voice parses «двадцать два градуса»
    against a °C-shaped target)."""
    golden = _golden()
    hvac = _device(golden, "living_room_hvac")
    climate = next(c for c in hvac["capabilities"] if c["name"] == "climate")
    setpoint = next(a for a in climate["actions"] if a["name"] == "set_setpoint")
    (temp,) = setpoint["params"]
    assert temp["unit"] == "°C" and temp["min"] == 16.0 and temp["max"] == 31.0

    processor = _device(golden, "processor")
    volume = next(c for c in processor["capabilities"] if c["name"] == "volume")
    vol_set = next(a for a in volume["actions"] if a["name"] == "set")
    level = next(p for p in vol_set["params"] if p["name"] == "level")
    assert level["unit"] == "dB"


def test_contract_v11_scenario_labels_are_localized():
    """VWB-20/G3: the scenario enum carries ru labels — «включи кино» has a surface."""
    golden = _golden()
    sm = _device(golden, "scenario_manager_living_room")
    scenario = next(c for c in sm["capabilities"] if c["name"] == "scenario")
    set_action = next(a for a in scenario["actions"] if a["name"] == "set")
    for v in set_action["params"][0]["values"]:
        assert v["labels"].get("ru"), f"scenario {v['canonical']} lacks a ru label"
        assert v["labels"].get("en")


def test_contract_v11_dynamic_sets_carry_options_from():
    """VWB-20/G5 (corrected): app launching is an intentionally OPEN set — the param
    points at the runtime options endpoint instead of lying with a static enum."""
    golden = _golden()
    tv = _device(golden, "living_room_tv")
    apps = next(c for c in tv["capabilities"] if c["name"] == "apps")
    launch = next(a for a in apps["actions"] if a["params"])
    app_param = launch["params"][0]
    assert app_param["options_from"] == "apps"
    assert app_param["values"] is None


def test_contract_v11_no_empty_capability_husks():
    """VWB-20 minor flag: a capability with neither actions nor fields is suppressed
    (the TVs' select-form `input` — reappears when VWB-19 makes select routable)."""
    golden = _golden()
    for d in golden["devices"]:
        for c in d["capabilities"]:
            assert c["actions"] or c["fields"], f"{d['id']}.{c['name']} is an empty husk"


def test_stamp_names_a_bridge_build():
    stamp = json.loads((CONTRACTS / "STAMP.json").read_text(encoding="utf-8"))
    assert set(stamp) == {"bridge_commit", "bridge_version", "catalog_version"}
    committed = json.loads((CONTRACTS / "catalog.golden.json").read_text(encoding="utf-8"))
    # the stamp's catalog hash must match the committed golden (they travel together)
    assert stamp["catalog_version"] == committed["version"], _REGEN_HINT


def test_contract_v13_hvac_action_params_carry_field_value_tables():
    """VWB-24 (voice intake): `set_mode`/`set_fan` params are typed with the same
    {wire, canonical, labels} tables their read-side fields carry — closed sets a
    voice consumer can validate against with zero round-trips. Canonical param names
    equal the field names (fan, not native speed) — that correspondence IS the
    derivation rule."""
    golden = _golden()
    for device_id in ("bedroom_hvac", "children_room_hvac", "living_room_hvac"):
        hvac = _device(golden, device_id)
        climate = next(c for c in hvac["capabilities"] if c["name"] == "climate")
        fields = {f["name"]: f for f in climate["fields"]}
        for action_name, param_name in (
            ("set_mode", "mode"), ("set_fan", "fan"),
            ("set_vane", "vane"), ("set_widevane", "widevane"),
        ):
            action = next(a for a in climate["actions"] if a["name"] == action_name)
            (param,) = action["params"]
            assert param["name"] == param_name, f"{device_id}.{action_name}"
            assert param["values"] == fields[param_name]["values"], (
                f"{device_id}.{action_name}({param_name}) must mirror the field table"
            )
        mode_values = {v["canonical"]: v for v in fields["mode"]["values"]}
        assert mode_values["cool"]["labels"]["ru"] == "охлаждение"
