"""VWB-41 (PROD-16, council HK-5): the device-integration convention's owner-side
guard — an owned machine schema ships a committed schema-validating example fixture
plus a CI check from day one (no unguarded model layouts).

The bridge owns the convention (`contracts/device-integration/`, tags
`device-integration-vN`); the satellite repo pins it and authors conforming
descriptors. This test keeps the owner's side honest:

- the schema itself is a valid JSON Schema (draft 2020-12);
- the committed example descriptor validates against it;
- the example in the convention README is THE example — byte-for-byte the same
  document as the committed fixture, so the guide can never teach a shape the
  schema rejects;
- the i18n floor holds (ru+en required — an en-only descriptor is rejected).
"""

import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

pytestmark = pytest.mark.unit

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "device-integration"

SCHEMA = json.loads((CONTRACT / "device-descriptor.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((CONTRACT / "example.descriptor.json").read_text(encoding="utf-8"))


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


def test_example_descriptor_validates():
    Draft202012Validator(SCHEMA).validate(EXAMPLE)


def test_readme_example_is_the_committed_fixture():
    readme = (CONTRACT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", readme, flags=re.DOTALL)
    descriptors = [b for b in blocks if '"descriptor_version"' in b]
    assert len(descriptors) == 1, "the README must show exactly one descriptor example"
    assert json.loads(descriptors[0]) == EXAMPLE, (
        "the README's descriptor example and example.descriptor.json diverged — "
        "they are the same document; change both together"
    )


def test_en_only_names_are_rejected():
    broken = json.loads(json.dumps(EXAMPLE))
    broken["names"] = {"en": "Revox A77"}
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate(broken)


def test_full_surface_descriptor_validates():
    """The surfaces the README example doesn't reach — stateful capability with
    feedback/reconcile/state_field, parametric action via param_map, enum field with a
    {wire, canonical, labels} triplet table, range/value control meta — all validate.
    Canonical tokens are real pinned vocabulary (the HVAC fan family)."""
    descriptor = {
        "convention": 1,
        "descriptor_version": 1,
        "profile": "wb-mqtt-v1",
        "device_id": "example_fan_unit",
        "names": {"ru": "Пример вентилятора", "en": "Example fan unit", "de": "Beispiel-Lüfter"},
        "firmware": {"app": "example-fan", "board": "esp32"},
        "timing": {"confirm_latency_ms": 800},
        "controls": {
            "power": {"type": "switch", "title": {"ru": "Питание", "en": "Power"}},
            "fan": {"type": "range", "min": 0, "max": 5},
            "temperature": {"type": "value", "readonly": True, "units": "°C"},
        },
        "capabilities": {
            "power": {
                "kind": "stateful",
                "feedback": True,
                "reconcile": True,
                "state_field": "power",
                "actions": {"on": {"control": "power", "payload": "1"},
                            "off": {"control": "power", "payload": "0"}},
                "fields": [{"name": "power", "type": "boolean",
                            "labels": {"ru": "Питание", "en": "Power"}}],
            },
            "fan": {
                "kind": "stateful",
                "state_field": "fan",
                "actions": {"set": {"control": "fan", "param_map": {"value": "{value}"}}},
                "fields": [{
                    "name": "fan", "type": "enum",
                    "labels": {"ru": "Скорость", "en": "Fan speed"},
                    "values": [
                        {"wire": "0", "canonical": "auto",
                         "labels": {"ru": "авто", "en": "auto"}},
                        {"wire": "2", "canonical": "speed_1",
                         "labels": {"ru": "скорость 1", "en": "speed 1"}},
                    ],
                }],
            },
        },
    }
    Draft202012Validator(SCHEMA).validate(descriptor)
