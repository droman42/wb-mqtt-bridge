"""Regression tests for the state-change callback chokepoint (Invariants A + B).

After the audit in 2026-05-27, the state-change callback chain became the single
chokepoint for BOTH persistence (Invariant A — state.db has new value) AND WB
virtual-device value-topic publishing (Invariant B — /devices/<id>/controls/<name>
reflects the device's actual current state, not the incoming command payload).

These tests lock the invariants in so they can't silently regress:

- The WB-publish chokepoint method publishes the current state for changed fields.
- Explicit `wb_state_mappings` in config override the by-name convention.
- Pushbutton/momentary controls are excluded from the convention map (no state).
- Payload conversion follows WB conventions (bool, None, Enum, str).
- ``handle_wb_message`` no longer echoes the incoming payload back as the value
  (that was wrong whenever the driver's resulting state differed from the request
  — the chokepoint publishes the resulting state instead).
"""

from datetime import datetime
from enum import Enum
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncio
import pytest

from wb_mqtt_bridge.domain.devices.models import LastCommand
from wb_mqtt_bridge.domain.ports import MessageBusPort
from wb_mqtt_bridge.infrastructure.config.models import (
    BaseCommandConfig,
    BaseDeviceConfig,
    CommandParameterDefinition,
)
from wb_mqtt_bridge.infrastructure.devices.base import BaseDevice
from wb_mqtt_bridge.infrastructure.wb_device.service import WBVirtualDeviceService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def message_bus():
    return AsyncMock(spec=MessageBusPort)


@pytest.fixture
def wb_service(message_bus):
    return WBVirtualDeviceService(message_bus)


def _config_dict(commands, *, wb_state_mappings=None):
    """Build a minimal device-config dict (the service accepts both dicts and BaseDeviceConfig
    objects; dict form keeps tests readable)."""
    cfg = {
        "device_id": "test_dev",
        "device_name": "Test Device",
        "device_class": "TestDev",
        "enable_wb_emulation": True,
        "commands": commands,
    }
    if wb_state_mappings is not None:
        cfg["wb_state_mappings"] = wb_state_mappings
    return cfg


# ---------------------------------------------------------------------------
# Test 1 — payload conversion conventions
# ---------------------------------------------------------------------------


class _SampleEnum(Enum):
    ON = "on"
    OFF = "off"


def test_wb_payload_for_value_conventions(wb_service):
    """`_wb_payload_for_value` must mirror the WB MQTT payload conventions used by the
    setup-time initial publish (bool → '0'/'1'; None → '0'; Enum → its value; else str())."""
    assert wb_service._wb_payload_for_value(True) == "1"
    assert wb_service._wb_payload_for_value(False) == "0"
    assert wb_service._wb_payload_for_value(None) == "0"
    assert wb_service._wb_payload_for_value(_SampleEnum.ON) == "on"
    assert wb_service._wb_payload_for_value(_SampleEnum.OFF) == "off"
    assert wb_service._wb_payload_for_value(42) == "42"
    assert wb_service._wb_payload_for_value("hdmi1") == "hdmi1"


# ---------------------------------------------------------------------------
# Test 2 — by-name convention fills the map for stateful controls
# ---------------------------------------------------------------------------


def test_build_state_field_to_control_map_uses_name_convention(wb_service):
    """Every stateful WB control with no explicit mapping → state field of the same name.
    The common case (`power` command ↔ `power` state field ↔ `power` WB control) works
    with zero per-device configuration."""
    config = _config_dict({
        "power": {"action": "power", "params": [
            {"name": "value", "type": "boolean", "required": True, "default": False}
        ]},
        "volume": {"action": "volume", "params": [
            {"name": "level", "type": "range", "required": True, "min": 0, "max": 100, "default": 50}
        ]},
    })

    field_map = wb_service._build_state_field_to_control_map(config)

    assert field_map.get("power") == ["power"]
    assert field_map.get("volume") == ["volume"]


# ---------------------------------------------------------------------------
# Test 3 — explicit `wb_state_mappings` takes precedence over the convention
# ---------------------------------------------------------------------------


def test_build_state_field_to_control_map_explicit_overrides_convention(wb_service):
    """When a state field name doesn't match the WB control name (e.g. driver state field
    is `input_source` but the WB control is `input`), the explicit `wb_state_mappings`
    config field bridges them. Convention still applies to anything not explicitly mapped."""
    config = _config_dict(
        commands={
            "input": {"action": "set_input", "params": [
                {"name": "value", "type": "string", "required": True, "default": "hdmi1"}
            ]},
            "power": {"action": "power", "params": [
                {"name": "value", "type": "boolean", "required": True, "default": False}
            ]},
        },
        wb_state_mappings={"input_source": "input"},
    )

    field_map = wb_service._build_state_field_to_control_map(config)

    # Explicit mapping: state field `input_source` → WB control `input`.
    assert field_map.get("input_source") == ["input"]
    # Convention still applies to `power`.
    assert field_map.get("power") == ["power"]
    # The WB control name `input` is NOT added to the map via convention because an
    # explicit mapping already claims it (otherwise the same control would publish twice
    # for unrelated state changes).
    assert "input" not in field_map


# ---------------------------------------------------------------------------
# Test 4 — pushbutton controls are excluded from the by-name convention
# ---------------------------------------------------------------------------


def test_build_state_field_to_control_map_excludes_pushbutton_controls(wb_service):
    """Pushbutton/momentary controls have no state to track (they're one-shot events).
    The by-name convention must not map them — that would cause spurious WB publishes
    every time a same-named state field changes for an unrelated reason."""
    config = _config_dict({
        "play": {"action": "play"},  # no params → pushbutton
        "stop": {"action": "stop"},  # no params → pushbutton
        "volume": {"action": "volume", "params": [
            {"name": "level", "type": "range", "required": True, "min": 0, "max": 100, "default": 50}
        ]},  # range → stateful
    })

    field_map = wb_service._build_state_field_to_control_map(config)

    # Stateful control: in the map via convention.
    assert "volume" in field_map
    # Pushbuttons: NOT in the map (momentary, no state).
    assert "play" not in field_map
    assert "stop" not in field_map


# ---------------------------------------------------------------------------
# Test 5 — publish_device_state_changes publishes current state for changed fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_device_state_changes_emits_value_topic_with_current_state(
    wb_service, message_bus
):
    """The chokepoint method: given (device_id, [changed_fields]), it reads the device's
    current state via the registered state_provider and publishes each mapped control's
    value to /devices/<wb_device_id>/controls/<control_name> retained.

    This is the test that locks Invariant B in: after a state change anywhere
    (HTTP / MQTT-in / scenario), the WB UI reflects the device's RESULTING state
    (not the incoming command payload, not the config default — the actual state).
    """
    # Setup the WB device with a state-provider closure backed by a mutable namespace.
    state = SimpleNamespace(power="off", volume=42)

    config = _config_dict({
        "power": {"action": "power", "params": [
            {"name": "value", "type": "boolean", "required": True, "default": False}
        ]},
        "volume": {"action": "volume", "params": [
            {"name": "level", "type": "range", "required": True, "min": 0, "max": 100, "default": 50}
        ]},
    })

    await wb_service.setup_wb_device_from_config(
        config=config,
        command_executor=AsyncMock(),
        state_provider=lambda: state,
    )

    # Discard the publishes that fire during setup (meta + initial state). We only assert
    # on what publish_device_state_changes adds AFTER setup.
    message_bus.publish.reset_mock()

    # Simulate the driver having just settled `state.power = "on"`. The chokepoint:
    state.power = "on"
    wb_service.publish_device_state_changes("test_dev", ["power"])

    # publish_device_state_changes is sync entry → schedules async via create_task. Drain.
    await asyncio.sleep(0)
    # Run any pending tasks to completion.
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    # Find the value-topic publish for `power` and assert payload = the RESULTING state ("on"),
    # not the incoming command payload (which the audit found was the wrong thing to publish).
    value_topic = "/devices/test_dev/controls/power"
    matching = [
        call for call in message_bus.publish.call_args_list
        if call.args and call.args[0] == value_topic
    ]
    assert matching, (
        f"Expected a publish to {value_topic} after publish_device_state_changes; "
        f"got: {message_bus.publish.call_args_list}"
    )
    # At least one publish carried the resulting state value.
    payloads = [call.args[1] for call in matching]
    assert "on" in payloads, f"Expected 'on' in published payloads; got {payloads}"
    # And it was published retained — the WB UI requires retained values to render the control.
    retained_calls = [call for call in matching if call.kwargs.get("retain") is True]
    assert retained_calls, f"Expected retain=True publish; got {[c.kwargs for c in matching]}"


# ---------------------------------------------------------------------------
# Test 6 — handle_wb_message no longer echoes the incoming payload back as the value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_wb_message_does_not_echo_incoming_payload(wb_service, message_bus):
    """Regression for the audit's Bug B2 + the chokepoint refactor (2026-05-27).

    Pre-fix: ``handle_wb_message`` republished the INCOMING command payload to the value
    topic immediately after the action — that was redundant in the happy path AND wrong
    whenever the driver settled on a value different from what was requested (toggle,
    normalization, command rejection). Now the chokepoint (driver.update_state → callback
    chain → publish_device_state_changes) publishes the RESULTING state — the right value.

    This test verifies the echo is gone: with an executor that does NOTHING (no
    update_state, no publish), the WB value topic must NOT be published with the incoming
    payload. (A real driver would call update_state, which would publish via the chokepoint
    instead — covered by test 5.)
    """
    config = _config_dict({
        "power": {"action": "power", "params": [
            {"name": "value", "type": "boolean", "required": True, "default": False}
        ]},
    })

    # Executor that does NOTHING — does not call update_state, does not publish.
    noop_executor = AsyncMock()

    await wb_service.setup_wb_device_from_config(
        config=config,
        command_executor=noop_executor,
        state_provider=lambda: SimpleNamespace(power="off"),
    )

    # Reset to exclude setup-time publishes.
    message_bus.publish.reset_mock()

    # Simulate WB UI writing "1" to the power command topic.
    handled = await wb_service.handle_wb_message(
        topic="/devices/test_dev/controls/power/on",
        payload="1",
        wb_device_id="test_dev",
    )
    assert handled is True

    # The executor was called (action dispatched) — but no value-topic publish happened,
    # because the no-op executor didn't trigger the chokepoint and the legacy
    # incoming-payload echo was removed in commit 5d289af.
    noop_executor.assert_awaited_once()

    value_topic = "/devices/test_dev/controls/power"
    value_publishes = [
        call for call in message_bus.publish.call_args_list
        if call.args and call.args[0] == value_topic
    ]
    assert not value_publishes, (
        f"handle_wb_message must NOT echo incoming payload back as the value topic — "
        f"the chokepoint (driver.update_state → publish_device_state_changes) is now the "
        f"single source of truth for value-topic publishes. Got unexpected publishes: "
        f"{value_publishes}"
    )


# ---------------------------------------------------------------------------
# Test 7 — ephemeral-only state changes (last_command) skip the callbacks
# ---------------------------------------------------------------------------


class _ChokepointDevice(BaseDevice):
    """Minimal concrete BaseDevice — only setup/shutdown are abstract."""

    async def setup(self) -> bool:  # pragma: no cover - not exercised
        return True

    async def shutdown(self) -> bool:  # pragma: no cover - not exercised
        return True


def _chokepoint_device():
    cfg = BaseDeviceConfig(
        device_id="cp_dev",
        device_name="Chokepoint Device",
        device_class="TestDev",
        config_class="BaseDeviceConfig",
        commands={},
    )
    return _ChokepointDevice(cfg)


def test_last_command_only_change_skips_persist_and_wb_callbacks():
    """A change to ONLY ephemeral fields (last_command — e.g. every throttled pointer move)
    must NOT run the registered persist/WB-publish callbacks; a change to a real observable
    field must. The in-memory state still updates either way."""
    device = _chokepoint_device()
    spy = Mock()
    device.register_state_change_callback(spy)

    # last_command-only update → callbacks skipped, but state still updates in memory.
    device.update_state(last_command=LastCommand(
        action="move_cursor_relative", source="api", timestamp=datetime.now(), params={"dx": 3, "dy": 1}
    ))
    spy.assert_not_called()
    assert device.state.last_command is not None
    assert device.state.last_command.action == "move_cursor_relative"

    # A real observable field (error) changing → callbacks run, with that field in changed_fields.
    device.update_state(error="boom")
    spy.assert_called_once()
    assert "error" in spy.call_args.args[1]

    # Mixed change (real + ephemeral) → callbacks still run (a meaningful field changed).
    spy.reset_mock()
    device.update_state(error=None, last_command=LastCommand(
        action="select", source="api", timestamp=datetime.now(), params=None
    ))
    spy.assert_called_once()
