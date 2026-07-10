"""Shared wire↔typed↔canonical value translation for config-driven MQTT drivers.

Extracted from the WB-passthrough driver (DRV-28) so that sibling drivers — the
generic passthrough and `MitsubishiHvac` — can share one implementation without
importing each other (the import-linter `independence` contract forbids
driver-package cross-imports; this module lives OUTSIDE the listed packages).

The semantics are the §P3.7 #19/#26 stack, unchanged:

- :func:`parse_value` — raw wire payload → typed value per ``StateTopicSpec.type``.
- :func:`apply_inversion` / :func:`invert_wire_payload` — the symmetric ``invert``
  transforms (inbound typed flip / outbound wire flip).
- :func:`translate_inbound` / :func:`translate_outbound` — the symmetric enum
  value-label translation (wire → canonical / canonical → wire) via the spec's
  ``{wire, canonical, labels}`` table.
"""

import logging
import re
from typing import Any, Dict

from wb_mqtt_bridge.infrastructure.config.models import StateTopicSpec

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def toggle_bool_wire_form(payload: str) -> str:
    """Flip a boolean-on-the-wire payload, preserving the surface form so the result
    matches adjacent commands' static values byte-for-byte. WB controls publish `"0"`/
    `"1"` overwhelmingly, but the config schemas don't FORCE that -- if someone writes
    a bool command with `value: "on"`, the inverted form should be `"off"`, not `"1"`.
    Unknown forms (numeric strings outside 0/1, arbitrary text) pass through unchanged
    -- safer than guessing."""
    s = payload.strip()
    pairs = (("0", "1"), ("false", "true"), ("off", "on"))
    for low, high in pairs:
        if s.lower() == low:
            return high if s.islower() or not s.isalpha() else high.capitalize()
        if s.lower() == high:
            return low if s.islower() or not s.isalpha() else low.capitalize()
    return payload


def parse_template(template: str, raw: str, coerce: Any = str) -> Dict[str, Any]:
    """Invert a `"{a};{b};{c}"`-style template against a concrete payload, producing the
    dict `{a: ..., b: ..., c: ...}`. Used for composite encodings like RGB
    (`"{r};{g};{b}"` + `"255;128;0"` → `{r: 255, g: 128, b: 0}`).

    Raises ValueError on a payload that doesn't match the template's literal separators
    or whose parts can't be coerced.
    """
    names = _PLACEHOLDER_RE.findall(template)
    if not names:
        raise ValueError(f"template {template!r} has no `{{name}}` placeholders")
    # Build a regex from the template: literal separators escaped, placeholders -> capture groups.
    pattern = re.escape(template)
    for n in names:
        pattern = pattern.replace(re.escape("{" + n + "}"), "([^;,/\\s]+)", 1)
    m = re.fullmatch(pattern, raw)
    if not m:
        raise ValueError(f"{raw!r} does not match template {template!r}")
    parts = m.groups()
    if len(parts) != len(names):
        raise ValueError(f"template {template!r} expects {len(names)} groups, got {len(parts)}")
    return {n: coerce(p) for n, p in zip(names, parts)}


def parse_value(raw: str, spec: StateTopicSpec) -> Any:
    """Coerce a raw wire payload into its declared type. Raises ValueError on a
    malformed payload. For ``enum``, the payload is accepted if it matches EITHER
    ``wire`` OR ``canonical`` of any ValueLabel entry: inbound echoes arrive in wire
    space (``"2"``), outbound idempotency callers come through in canonical space
    (``"cool"``). Translation to canonical happens in :func:`translate_inbound`;
    this function only validates + returns ``raw``."""
    t = spec.type
    if t == "str":
        return raw
    if t == "int":
        return int(raw)
    if t == "float":
        return float(raw)
    if t == "bool":
        return raw.strip().lower() in ("1", "true", "on")
    if t == "enum":
        if spec.values is not None:
            allowed = {v.wire for v in spec.values} | {v.canonical for v in spec.values}
            if raw not in allowed:
                raise ValueError(
                    f"{raw!r} not in enum values (wire/canonical: {sorted(allowed)})"
                )
        return raw
    if t == "rgb":
        return parse_template(spec.encoding or "{r};{g};{b}", raw, coerce=int)
    raise ValueError(f"unknown StateTopicSpec.type {t!r}")


def apply_inversion(value: Any, spec: StateTopicSpec) -> Any:
    """If ``spec.invert``, apply the wire-orientation flip on the INBOUND path (after
    :func:`parse_value`) so state always carries the natural-sense value. int/float:
    ``100 - value``; bool: ``not value``; str/enum/rgb: no-op."""
    if not spec.invert:
        return value
    if spec.type == "bool":
        return not value if isinstance(value, bool) else value
    if spec.type in ("int", "float"):
        try:
            return type(value)(100 - value)
        except (TypeError, ValueError):
            return value
    return value


def translate_outbound(payload: str, spec: StateTopicSpec) -> str:
    """OUTBOUND value-label translation (canonical → wire) for enum fields with a
    value table. Non-enum / no table: identity. Canonical match → its wire; wire
    match → identity; no match: warn + pass through (the WB layer rejects bogus
    payloads with its own semantics)."""
    if spec.type != "enum" or not spec.values:
        return payload
    for v in spec.values:
        if v.canonical == payload:
            return v.wire
    for v in spec.values:
        if v.wire == payload:
            return payload
    logger.warning(
        f"value {payload!r} not in canonical or wire list for enum spec; "
        f"passing through unchanged"
    )
    return payload


def translate_inbound(value: Any, spec: StateTopicSpec) -> Any:
    """INBOUND value-label translation (wire → canonical) for enum fields with a value
    table. Called after :func:`parse_value` + :func:`apply_inversion` so state always
    holds the canonical identifier. Wire match → canonical; else identity."""
    if spec.type != "enum" or not spec.values or not isinstance(value, str):
        return value
    for v in spec.values:
        if v.wire == value:
            return v.canonical
    return value


def invert_wire_payload(payload: str, spec: StateTopicSpec) -> str:
    """OUTBOUND counterpart of :func:`apply_inversion`: flip the natural-sense payload
    string just before publish. int: ``100 - int``; float: ``100.0 - float`` (integer-
    valued rendered without ``.0``); bool: :func:`toggle_bool_wire_form`; other types
    or parse failure: pass through."""
    if not spec.invert:
        return payload
    if spec.type == "bool":
        return toggle_bool_wire_form(payload)
    if spec.type in ("int", "float"):
        try:
            if spec.type == "int":
                return str(100 - int(payload))
            v = 100.0 - float(payload)
            return str(int(v)) if v.is_integer() else str(v)
        except (TypeError, ValueError):
            return payload
    return payload


def coerce_state_value(field: str, raw: str, spec: StateTopicSpec, device_name: str) -> Any:
    """The full inbound stack: parse → invert → translate to canonical. On parse
    failure: warn and return the raw string unchanged (the device IS talking; we just
    can't decode this one payload — don't drop it silently)."""
    try:
        typed = parse_value(raw, spec)
        inverted = apply_inversion(typed, spec)
        return translate_inbound(inverted, spec)
    except (ValueError, TypeError) as e:
        logger.warning(
            f"[{device_name}] failed to parse {field!r} payload {raw!r} as {spec.type}: {e}"
        )
        return raw
