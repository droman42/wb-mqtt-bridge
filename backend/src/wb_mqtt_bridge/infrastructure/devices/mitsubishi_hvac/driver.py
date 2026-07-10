"""MitsubishiHvac — dedicated driver for mitsubishi2wb-firmware HVAC units (DRV-28).

The actual contract this driver speaks is the **mitsubishi2wb firmware's MQTT dialect**
(https://github.com/mavlyutov/mitsubishi2wb — `mitsubishi2wb.ino`
`hpSettingsChanged()`/`mqttCallback()`/`mqttConnect()`, verified 2026-07-09), NOT a
chip's: the modules happen to be ESP8266 Wemos D1 Minis. Design:
`docs/design/mitsubishi_hvac_driver.md` (rev. 2). The dialect, in short:

- Values are retained numeric index strings, published **on change only**; commands go
  to `…/{control}/on` and anything non-numeric is **silently ignored** by the firmware.
- The wire↔canonical tables live in the `MitsubishiHvac` class capability map ONLY
  (design D3); the loader enrichment merges them into this config's bare
  ``state_topics`` before MQTT echoes arrive, and translation runs through the shared
  ``value_translation`` stack (never a cross-import from the passthrough package — the
  import-linter ``independence`` contract).
- The firmware has **no LWT and no per-control meta/error** — but it publishes
  ``room_temperature`` every 45 s unconditionally. That heartbeat drives
  ``state.reachable`` (design D5): ~3 silent intervals ⇒ unreachable.
- Typed declared state (``MitsubishiHvacState``) rides the standard restore-at-boot
  (VWB-18), which is what survives the WB7's persistence-less broker across reboots.

Commands honor the reserved ``force``/``assume_state`` params via the standard
``idempotence_skip`` chokepoint (DRV-5); availability guards never use it.

**This driver NEVER creates WB virtual devices** — the firmware owns and publishes its
own WB card (``/devices/hvac_*``); the bridge never writes into that namespace (design
D7). Structurally enforced twice: ``MitsubishiHvacConfig`` inherits
``enable_wb_emulation = False`` (the passthrough loop-guard default), and ``setup()``
never calls ``setup_wb_emulation_if_enabled()``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional, cast

from wb_mqtt_bridge.domain.devices.models import LastCommand, MitsubishiHvacState
from wb_mqtt_bridge.domain.devices.types import ActionHandler, CommandResult
from wb_mqtt_bridge.infrastructure.config.models import (
    MitsubishiHvacConfig,
    WbPassthroughCommandConfig,
)
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.infrastructure.devices.value_translation import (
    coerce_state_value,
    parse_value,
    translate_inbound,
    translate_outbound,
)
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService

logger = logging.getLogger(__name__)

# The firmware publishes room_temperature every SEND_ROOM_TEMP_INTERVAL_MS (45 s,
# observed live + read in source). Three silent intervals = the unit is gone.
HEARTBEAT_INTERVAL_S = 45.0
HEARTBEAT_TIMEOUT_S = HEARTBEAT_INTERVAL_S * 3

# Native command -> the state field it drives (and whose enriched StateTopicSpec
# carries the type/value table used for translation + idempotence comparison).
_COMMAND_STATE_FIELD: Dict[str, str] = {
    "power_on": "power",
    "power_off": "power",
    "set_mode": "mode",
    "set_fan": "fan",
    "set_vane": "vane",
    "set_widevane": "widevane",
    "set_setpoint": "setpoint",
}


class MitsubishiHvac(BaseDevice[MitsubishiHvacState]):
    """Typed, restorable, heartbeat-monitored driver for the mitsubishi2wb units."""

    # Narrow self.config so pyright sees the HVAC-shaped fields.
    config: MitsubishiHvacConfig

    def __init__(
        self,
        config: MitsubishiHvacConfig,
        mqtt_client: Optional[MQTTClient] = None,
        wb_service: Optional[WBVirtualDeviceService] = None,
    ) -> None:
        super().__init__(config, mqtt_client=mqtt_client, wb_service=wb_service)
        self.state = MitsubishiHvacState(
            device_id=self.device_id,
            device_name=self.device_name,
        )
        self._subscribed_topics: List[str] = []
        self._last_heartbeat: Optional[float] = None
        self._watchdog_task: Optional[asyncio.Task] = None

    # -- handler registration --------------------------------------------------

    def _register_handlers(self) -> None:
        """One handler per config command; the firmware contract is fixed, so the
        config validator already guaranteed the full set is present."""
        for cmd_name in self.config.commands:
            self._action_handlers[cmd_name] = cast(
                ActionHandler, partial(self._execute_command, cmd_name)
            )

    # -- setup / shutdown --------------------------------------------------------

    async def setup(self) -> bool:
        """Subscribe to every state topic (retained payloads seed the typed state on
        boot — live values win over the restored snapshot) and start the heartbeat
        watchdog. The firmware publishes no per-control meta/error, so unlike the
        passthrough there is nothing else to subscribe to."""
        if not self.mqtt_client:
            logger.warning(
                f"[{self.device_name}] no mqtt_client; cannot subscribe — state will not sync."
            )
            return False
        for field, spec in self.config.state_topics.items():
            await self.mqtt_client.subscribe(
                spec.topic, partial(self._on_value_message, field), process_retained=True,
            )
            self._subscribed_topics.append(spec.topic)
            logger.info(
                f"[{self.device_name}] syncing {field!r} ({spec.type}) from {spec.topic}"
            )
        self._watchdog_task = asyncio.create_task(self._heartbeat_watchdog())
        return True

    async def shutdown(self) -> bool:
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            self._watchdog_task = None
        return True

    # -- inbound state -----------------------------------------------------------

    async def _on_value_message(self, field: str, topic: str, payload: str) -> None:
        """A value echo arrived: coerce per the (class-map-enriched) spec into the
        canonical typed form and set the TOP-LEVEL state field. room_temperature
        doubles as the liveness heartbeat."""
        spec = self.config.state_topics.get(field)
        typed = coerce_state_value(field, payload, spec, self.device_name) if spec else payload
        updates: Dict[str, Any] = {field: typed}
        if field == "room_temperature":
            self._last_heartbeat = time.monotonic()
            if not self.state.reachable:
                updates["reachable"] = True
                logger.info(f"[{self.device_name}] heartbeat back — unit reachable again")
        self.update_state(**updates)

    async def _heartbeat_watchdog(self) -> None:
        """Flip `reachable` False after ~3 silent heartbeat intervals. The firmware has
        no LWT, so this is the only honest offline detection. Never raises out (a dead
        watchdog would silently disable the feature)."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                if self._last_heartbeat is None:
                    continue  # nothing heard yet (fresh boot, retained not delivered)
                silent_for = time.monotonic() - self._last_heartbeat
                if silent_for > HEARTBEAT_TIMEOUT_S and self.state.reachable:
                    logger.warning(
                        f"[{self.device_name}] no room_temperature heartbeat for "
                        f"{silent_for:.0f}s — marking unreachable"
                    )
                    self.update_state(reachable=False)
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 — keep the watchdog alive semantics honest
            logger.exception(f"[{self.device_name}] heartbeat watchdog died")

    # -- write path ----------------------------------------------------------------

    async def _execute_command(
        self,
        cmd_name: str,
        cmd_config: WbPassthroughCommandConfig,
        params: Dict[str, Any],
    ) -> CommandResult:
        """Translate the canonical target to the firmware's numeric wire and publish.

        The firmware silently drops any payload that is not the exact numeric string
        (`mqttCallback()`'s `else return`), so the outbound translation here is
        load-bearing, not cosmetic. Idempotence rides the standard chokepoint:
        already-at-target skips (unless `force`), flagged `no_op` for the canonical
        endpoint's echo-wait short-circuit — the firmware won't echo an unchanged value.
        """
        if not self.mqtt_client:
            return self.create_command_result(success=False, error="mqtt_client not available")

        field = _COMMAND_STATE_FIELD.get(cmd_name)
        spec = self.config.state_topics.get(field) if field else None

        # Resolve the canonical-space target: static value (power '1'/'0') or the first
        # declared param's value (mode/fan/vane/widevane canonical id; setpoint float).
        if cmd_config.value is not None:
            natural = str(cmd_config.value)
        else:
            declared = cmd_config.params or []
            if not declared:
                return self.create_command_result(
                    success=False,
                    error=f"could not resolve payload for {cmd_name!r} (no value, no params)",
                )
            pname = declared[0].name
            if pname not in params or params[pname] is None:
                return self.create_command_result(
                    success=False,
                    error=f"missing required parameter {pname!r} for {cmd_name!r}",
                )
            natural = str(params[pname])

        # Idempotence in canonical space (state fields hold canonical / typed values).
        if field is not None and spec is not None:
            current = getattr(self.state, field, None)
            try:
                target_typed = parse_value(natural, spec)
                target_canonical = translate_inbound(target_typed, spec)
            except (ValueError, TypeError):
                target_canonical = natural
            skip = self.idempotence_skip(
                params,
                current is not None and current == target_canonical,
                f"{field} already {target_canonical!r} — publish skipped",
            )
            if skip is not None:
                return skip

        # Canonical -> numeric wire. Load-bearing for enum fields (see docstring);
        # identity for power (static '1'/'0') and setpoint (float string).
        wire = translate_outbound(natural, spec) if spec is not None else natural

        try:
            await self.mqtt_client.publish(cmd_config.topic, wire)
        except Exception as e:
            logger.error(f"[{self.device_name}] publish to {cmd_config.topic} failed: {e}")
            return self.create_command_result(success=False, error=str(e))

        self.update_state(last_command=LastCommand(
            action=cmd_name,
            source="api",
            timestamp=datetime.now(),
            params=dict(params) if params else None,
        ))
        return self.create_command_result(
            success=True,
            message=f"published {wire!r} to {cmd_config.topic}",
            data={"topic": cmd_config.topic, "payload": wire, "no_op": False},
        )
