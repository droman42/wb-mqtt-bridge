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


def test_stamp_names_a_bridge_build():
    stamp = json.loads((CONTRACTS / "STAMP.json").read_text(encoding="utf-8"))
    assert set(stamp) == {"bridge_commit", "bridge_version", "catalog_version"}
    committed = json.loads((CONTRACTS / "catalog.golden.json").read_text(encoding="utf-8"))
    # the stamp's catalog hash must match the committed golden (they travel together)
    assert stamp["catalog_version"] == committed["version"], _REGEN_HINT
