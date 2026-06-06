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

Adding a new WB device is a config file, not code. The driver is data-driven; complex
shapes (RGB strings, HVAC multi-cell, paired switch+brightness lights) are handled by the
capability-adapter layer above (§P3.7 #20), not in here.
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

from wb_mqtt_bridge.infrastructure.config.models import (
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


class WbPassthroughDevice(BaseDevice[WbPassthroughState]):
    """Data-driven device whose actions publish to WB control topics + whose state mirrors
    those same controls' value-topic echoes."""

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
            topic: field for field, topic in self.config.state_topics.items()
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
        for field, topic in self.config.state_topics.items():
            await self.mqtt_client.subscribe(
                topic, partial(self._on_value_message, field), process_retained=True,
            )
            self._subscribed_topics.append(topic)
            error_topic = f"{topic}/meta/error"
            await self.mqtt_client.subscribe(
                error_topic, partial(self._on_error_message, field), process_retained=True,
            )
            self._subscribed_topics.append(error_topic)
            logger.info(f"[{self.device_name}] mirroring {field!r} from {topic} (+ meta/error)")
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

        payload = self._resolve_payload(cmd_config, params)
        if payload is None:
            return self.create_command_result(
                success=False,
                error=f"could not resolve payload for {cmd_name!r} "
                      f"(no static value AND no param value provided)",
            )

        # Idempotency check BEFORE publishing. If we already see the device at the target
        # value via the mirror, the publish is a no-op as far as state is concerned -- the
        # device won't echo, and even if it did, update_state would filter the no-change.
        # We still publish so the WB layer sees the command (cheap; harmless on relays);
        # the canonical endpoint reads `no_op` to skip its echo wait.
        state_field = self._state_field_for_command(cmd_config)
        current = self.state.mirrored.get(state_field) if state_field else None
        no_op = current is not None and current == payload

        try:
            await self.mqtt_client.publish(cmd_config.topic, payload)
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
        msg = f"published {payload!r} to {cmd_config.topic}"
        if no_op:
            msg += " (no-op: target already reached)"
        return self.create_command_result(
            success=True,
            message=msg,
            data={"topic": cmd_config.topic, "payload": payload, "no_op": no_op},
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
        for field, st in self.config.state_topics.items():
            if st == base:
                return field
        return None

    @staticmethod
    def _resolve_payload(
        cmd_config: WbPassthroughCommandConfig, params: Dict[str, Any]
    ) -> Optional[str]:
        """Static `value` wins. Otherwise render the first declared param's value to the
        wire payload using WB conventions: int-shaped floats lose their decimal (the WB
        UI sends "75" not "75.0" for a 0-100 slider); booleans render as "1"/"0";
        everything else falls back to str()."""
        if cmd_config.value is not None:
            return cmd_config.value
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

    async def _on_value_message(self, field: str, topic: str, payload: str) -> None:
        """A value-topic echo arrived. Mirror it into state and reset the field's error."""
        new_mirrored = {**self.state.mirrored, field: payload}
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
