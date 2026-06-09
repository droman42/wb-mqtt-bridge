"""Generic Wirenboard passthrough device driver.

The bridge is **not** the owner of the underlying WB control — wb-mqtt-serial (and any
wb-rules acting through it) is. This driver:

- **Writes** by publishing to a config-declared `/devices/<wb-device>/controls/<ctrl>/on`
  topic when a canonical action lands. One command = one publish.
- **Mirrors** state by subscribing to each `state_topic` and to its per-control
  `<state_topic>/meta/error` companion (Wirenboard MQTT convention — `r`/`w`/`p` codes
  combine; see §P3.7 A3 for the verified shape). Every incoming value flows through
  `update_state` (the state-sync chokepoint) so persistence + SSE callbacks fire normally.
- **Skips WB virtual-device registration entirely** (`enable_wb_emulation = False` on the
  config). That's the structural **loop guard**: without
  `WBVirtualDeviceService.publish_device_state_changes` in the callback chain, an incoming
  value-topic update can't trigger a republish back to the same value topic — we'd
  otherwise feedback-loop with the real device.

Adding a new WB device is a config file, not code. The driver is data-driven; composite
payload shapes (RGB `"r;g;b"`, multi-cell HVAC) are handled INSIDE this driver via typed
`state_topics` specs (§P3.7 #19) + per-command `payload_template`, not in a separate
adapter layer.
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

import re

from wb_mqtt_bridge.infrastructure.config.models import (
    StateTopicSpec,
    WbPassthroughCommandConfig,
    WbPassthroughDeviceConfig,
)
from wb_mqtt_bridge.domain.devices.models import (
    BaseDeviceState,
    LastCommand,
    WbPassthroughState,
)
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService
from wb_mqtt_bridge.utils.types import CommandResult

logger = logging.getLogger(__name__)


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _toggle_bool_wire_form(payload: str) -> str:
    """Flip a boolean-on-the-wire payload, preserving the surface form so the result
    matches adjacent commands' static values byte-for-byte. WB controls publish `"0"`/
    `"1"` overwhelmingly, but the WB-passthrough config schema doesn't FORCE that --
    if someone writes a bool command with `value: "on"`, the inverted form should be
    `"off"`, not `"1"`. Unknown forms (numeric strings outside 0/1, arbitrary text)
    pass through unchanged -- safer than guessing."""
    s = payload.strip()
    pairs = (("0", "1"), ("false", "true"), ("off", "on"))
    for low, high in pairs:
        if s.lower() == low:
            return high if s.islower() or not s.isalpha() else high.capitalize()
        if s.lower() == high:
            return low if s.islower() or not s.isalpha() else low.capitalize()
    return payload


def _parse_template(template: str, raw: str, coerce: Any = str) -> Dict[str, Any]:
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


class WbPassthroughDevice(BaseDevice[WbPassthroughState]):
    """Data-driven device whose actions publish to WB control topics + whose state mirrors
    those same controls' value-topic echoes."""

    # Narrow self.config so pyright sees WbPassthroughDeviceConfig-shaped fields.
    config: WbPassthroughDeviceConfig

    def __init__(
        self,
        config: WbPassthroughDeviceConfig,
        mqtt_client: Optional[MQTTClient] = None,
        wb_service: Optional[WBVirtualDeviceService] = None,
    ) -> None:
        super().__init__(config, mqtt_client=mqtt_client, wb_service=wb_service)
        # Concrete state class for this driver; preserves the bilingual-friendly flat
        # device_name plumbing from BaseDevice and adds the mirrored/reachable fields.
        self.state = WbPassthroughState(
            device_id=self.device_id,
            device_name=self.device_name,
        )
        # Reverse map: MQTT value topic -> state-field name (for fast handler dispatch).
        self._state_topic_to_field: Dict[str, str] = {
            spec.topic: field for field, spec in self.config.state_topics.items()
        }
        # Track which topics we actually subscribed to so shutdown is symmetric.
        self._subscribed_topics: List[str] = []

    # -- handler registration ------------------------------------------------

    def _register_handlers(self) -> None:
        """Auto-register one publishing handler per command in the config. All handlers
        route through `_publish_command`; per-command shape lives in the config, not code."""
        for cmd_name in self.config.commands:
            self._action_handlers[cmd_name] = partial(self._publish_command, cmd_name)
            logger.debug(f"[{self.device_name}] registered passthrough handler: {cmd_name}")

    # -- setup / shutdown ----------------------------------------------------

    async def setup(self) -> bool:
        """Subscribe to every value topic + its per-control meta/error companion.

        Both subscriptions opt into retained-message processing via
        ``process_retained=True`` -- the retained payload on a value topic IS the current
        value of the control, so seeding state.mirrored from it lets the canonical
        endpoint's no_op short-circuit detect "already at target" on the FIRST request
        after a bridge restart (e.g. fire `power_off` when the relay is already off and
        get a clean 200 instead of a 503 timeout). The meta/error topic opts in for the
        same reason -- if a control was sick when the bridge died, the retained flag
        tells us on restart.
        """
        if not self.mqtt_client:
            logger.warning(f"[{self.device_name}] no mqtt_client; cannot subscribe — state will not mirror.")
            return False
        for field, spec in self.config.state_topics.items():
            await self.mqtt_client.subscribe(
                spec.topic, partial(self._on_value_message, field), process_retained=True,
            )
            self._subscribed_topics.append(spec.topic)
            error_topic = f"{spec.topic}/meta/error"
            await self.mqtt_client.subscribe(
                error_topic, partial(self._on_error_message, field), process_retained=True,
            )
            self._subscribed_topics.append(error_topic)
            logger.info(
                f"[{self.device_name}] mirroring {field!r} ({spec.type}) from {spec.topic} (+ meta/error)"
            )
        return True

    async def shutdown(self) -> bool:
        # Subscriptions live on the shared MqttClient and are dropped when it disconnects;
        # nothing per-device to tear down here. The last mirrored snapshot is preserved as
        # the device's final state for assumed-state continuity (state.db persistence).
        return True

    # -- write path ----------------------------------------------------------

    async def _publish_command(
        self,
        cmd_name: str,
        cmd_config: WbPassthroughCommandConfig,
        params: Dict[str, Any],
    ) -> CommandResult:
        """Resolve the payload for `cmd_name` and publish it to the configured topic.

        Resolution: a static `value` takes precedence; otherwise the first declared param's
        value (stringified) is the payload. This matches the WB convention (one slider →
        one publish; one switch → one publish).

        Sets `data.no_op = True` when our mirrored snapshot already shows the device at the
        target value. The canonical endpoint short-circuits its echo wait when it sees that
        flag — wb-mqtt-serial doesn't republish unchanged values, so the wait would 503
        out otherwise on idempotent calls ("включи свет" when the light is already on).
        """
        if not self.mqtt_client:
            return self.create_command_result(success=False, error="mqtt_client not available")

        natural_payload = self._resolve_payload(cmd_config, params)
        if natural_payload is None:
            return self.create_command_result(
                success=False,
                error=f"could not resolve payload for {cmd_name!r} "
                      f"(no static value AND no param value provided)",
            )

        # The payload from _resolve_payload is in natural sense (configs are always
        # authored in natural sense — set_position(25) means "25% open"). For idempotency
        # comparison we stay in natural sense throughout, since state.mirrored is also
        # natural-sense (the mirror path inverts incoming wire echoes via _coerce_mirror).
        # We only convert to wire sense at the very last moment, just before publishing.
        state_field = self._state_field_for_command(cmd_config)
        target_spec = (
            self.config.state_topics.get(state_field) if state_field else None
        )

        # Idempotency check BEFORE publishing. If we already see the device at the target
        # value via the mirror, the publish is a no-op as far as state is concerned -- the
        # device won't echo, and even if it did, update_state would filter the no-change.
        # We still publish so the WB layer sees the command (cheap; harmless on relays);
        # the canonical endpoint reads `no_op` to skip its echo wait.
        # Compare in the field's TYPED space so a bool mirror (`True`) matches a config-
        # side `"1"` and an int mirror (25) matches a config-side `"25"`. Falls back to
        # plain string compare when no spec is available (side-channel command, or first
        # echo before mirror seeded).
        current = self.state.mirrored.get(state_field) if state_field else None
        if current is None:
            no_op = False
        elif target_spec is not None:
            try:
                target_typed = self._parse_value(natural_payload, target_spec)
                no_op = current == target_typed
            except (ValueError, TypeError):
                no_op = str(current) == natural_payload
        else:
            no_op = str(current) == natural_payload

        # Final outbound transform: wire-format inversion if the target field has it.
        wire_payload = (
            self._invert_wire_payload(natural_payload, target_spec)
            if target_spec is not None and target_spec.invert
            else natural_payload
        )

        try:
            await self.mqtt_client.publish(cmd_config.topic, wire_payload)
        except Exception as e:
            logger.error(f"[{self.device_name}] publish to {cmd_config.topic} failed: {e}")
            return self.create_command_result(success=False, error=str(e))

        # Record what we just did. The value-topic echo (mirrored back via _on_value_message)
        # is what proves the device acted; the canonical endpoint (slice #15) waits for it.
        self.update_state(last_command=LastCommand(
            action=cmd_name,
            source="api",
            timestamp=datetime.now(),
            params=dict(params) if params else None,
        ))
        msg = f"published {wire_payload!r} to {cmd_config.topic}"
        if no_op:
            msg += " (no-op: target already reached)"
        return self.create_command_result(
            success=True,
            message=msg,
            data={"topic": cmd_config.topic, "payload": wire_payload, "no_op": no_op},
        )

    def _state_field_for_command(
        self, cmd_config: WbPassthroughCommandConfig
    ) -> Optional[str]:
        """The state_topics key whose value-topic this command writes to. WB convention:
        commands publish to `<value_topic>/on`, so we strip the suffix and look up which
        state field mirrors that topic. Returns None if the command writes to anything
        other than a known value topic (e.g. a side-channel command with no echo)."""
        topic = cmd_config.topic
        if not topic.endswith("/on"):
            return None
        base = topic[:-3]
        for field, spec in self.config.state_topics.items():
            if spec.topic == base:
                return field
        return None

    @staticmethod
    def _resolve_payload(
        cmd_config: WbPassthroughCommandConfig, params: Dict[str, Any]
    ) -> Optional[str]:
        """Resolve the wire payload for a command, in precedence order:

        1. **Static `value`** wins (e.g. `power_on` → `"1"`).
        2. **`payload_template`** (multi-param composite, §P3.7 #19): format the template
           with all provided params. Raises ValueError via `format()` if a placeholder is
           missing — `_compose_payload` is called via `_publish_command` which catches it.
        3. **Single-param** fallback: render the first declared param's value using WB
           conventions — int-shaped floats lose their decimal (the WB UI sends "75" not
           "75.0" for a 0-100 slider); booleans render as "1"/"0"; everything else `str()`.
        """
        if cmd_config.value is not None:
            return cmd_config.value
        if cmd_config.payload_template is not None:
            try:
                return cmd_config.payload_template.format(**params)
            except KeyError as e:
                logger.error(
                    f"payload_template {cmd_config.payload_template!r} references missing param: {e}"
                )
                return None
        if cmd_config.params:
            for p in cmd_config.params:
                if p.name in params and params[p.name] is not None:
                    v = params[p.name]
                    if isinstance(v, bool):
                        return "1" if v else "0"
                    if isinstance(v, float) and v.is_integer():
                        return str(int(v))
                    return str(v)
        return None

    # -- mirror path (incoming MQTT) -----------------------------------------

    @staticmethod
    def _parse_value(raw: str, spec: StateTopicSpec) -> Any:
        """Coerce a raw wire payload into its declared type. Raises ValueError on a
        malformed payload — caller is `_coerce_mirror`, which records a `parse` error
        flag instead of dropping the value silently."""
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
            if spec.values is not None and raw not in spec.values:
                raise ValueError(f"{raw!r} not in allowed values {spec.values}")
            return raw
        if t == "rgb":
            return _parse_template(spec.encoding or "{r};{g};{b}", raw, coerce=int)
        raise ValueError(f"unknown StateTopicSpec.type {t!r}")

    @staticmethod
    def _apply_inversion(value: Any, spec: StateTopicSpec) -> Any:
        """If `spec.invert` is True, apply the wire-orientation flip on the INBOUND
        mirror path (after _parse_value) so `state.mirrored` always carries the natural-
        sense value regardless of device-family orientation. Symmetric counterpart for
        outbound writes is `_invert_wire_payload`.

        Inversion semantics per type:
          - int/float: `100 - value` (percentage-like fields; e.g. cabinet rollers'
            inverted position).
          - bool: `not value` (toggle; e.g. inverted-valve heating actuators where
            wire 0=heating-on, 1=heating-off).
          - str/enum/rgb: no-op (inversion has no obvious meaning).
        """
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

    @staticmethod
    def _invert_wire_payload(payload: str, spec: StateTopicSpec) -> str:
        """OUTBOUND counterpart of `_apply_inversion`: parse the natural-sense payload
        string, apply the type-appropriate flip, render back to string. Called by
        `_publish_command` just before the MQTT publish so the wire format respects the
        device-family quirk (cabinet rollers' 0=open / 100=closed; inverted heating
        actuators' 0=on / 1=off) while configs + voice + state stay in natural sense.

        Type handling matches `_apply_inversion`:
          - int: `str(100 - int(payload))`
          - float: `str(100.0 - float(payload))` (integer-valued rendered without `.0`
            to match WB UI convention; see `_resolve_payload`)
          - bool: toggle the canonical wire form -- `"1"`↔`"0"`, `"true"`↔`"false"`,
            `"on"`↔`"off"` (preserves the input's surface form so the wire bytes look
            consistent with adjacent commands' static values)
          - str/enum/rgb or parse failure: pass through unchanged
        """
        if not spec.invert:
            return payload
        if spec.type == "bool":
            return _toggle_bool_wire_form(payload)
        if spec.type in ("int", "float"):
            try:
                if spec.type == "int":
                    return str(100 - int(payload))
                v = 100.0 - float(payload)
                return str(int(v)) if v.is_integer() else str(v)
            except (TypeError, ValueError):
                return payload
        return payload

    def _coerce_mirror(self, field: str, raw: str) -> Any:
        """Look up `field`'s StateTopicSpec, parse the raw payload to its typed form, apply
        the `invert` transform if set, and return the typed value. On parse failure: log a
        warning and return the raw string unchanged. We deliberately do NOT touch
        `state.error_flags` -- that's reserved for WB-protocol per-control flags
        (`r`/`w`/`p`) and conflating it with internal parse errors would mis-fire the
        `reachable` check (the device IS talking; WE just can't decode this one payload)."""
        spec = self.config.state_topics.get(field)
        if spec is None:
            return raw
        try:
            typed = self._parse_value(raw, spec)
            return self._apply_inversion(typed, spec)
        except (ValueError, TypeError) as e:
            logger.warning(
                f"[{self.device_name}] failed to parse {field!r} payload {raw!r} as {spec.type}: {e}"
            )
            return raw

    async def _on_value_message(self, field: str, topic: str, payload: str) -> None:
        """A value-topic echo arrived. Coerce per the field's spec, mirror the typed value
        into state, and clear the field's error flag on a successful read."""
        typed = self._coerce_mirror(field, payload)
        new_mirrored = {**self.state.mirrored, field: typed}
        # Clear the per-field error flag on a successful read (per the convention spec the
        # broker would do the same; this keeps our snapshot consistent without a re-subscribe).
        new_errors = {k: v for k, v in self.state.error_flags.items() if k != field}
        new_reachable = not any("r" in v for v in new_errors.values())
        self.update_state(
            mirrored=new_mirrored,
            error_flags=new_errors,
            reachable=new_reachable,
        )

    async def _on_error_message(self, field: str, topic: str, payload: str) -> None:
        """A `<value_topic>/meta/error` update arrived. payload is empty / `r` / `w` / `rw` / etc.

        Per Wirenboard MQTT conventions: any non-empty payload means there's a problem on this
        control. We mirror the raw flag string into `error_flags[field]` and flip `reachable`
        based on whether ANY tracked field has a read-error flag (`r`).
        """
        if payload == "":
            new_errors = {k: v for k, v in self.state.error_flags.items() if k != field}
        else:
            new_errors = {**self.state.error_flags, field: payload}
        new_reachable = not any("r" in v for v in new_errors.values())
        self.update_state(error_flags=new_errors, reachable=new_reachable)
