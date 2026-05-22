"""Fresh tests for RevoxA77ReelToReel, written against the post-hexagonal-refactor driver.

The Revox A77 is a tape deck controlled via IR codes (through a Wirenboard IR
blaster). Its driver wraps each command in a "send stop first, wait, then send
the actual command" sequence — required by the physical mechanism. The four
handlers are:
  - handle_play       -> _execute_sequence(cmd, "play",  params)
  - handle_stop       -> _send_ir_command(cmd, "stop", params)  (direct, no stop-first)
  - handle_rewind_*   -> _execute_sequence(cmd, "rewind_*", params)
The IR command itself is emitted by publishing to a Wirenboard topic:
  /devices/<location>/controls/Play from ROM<rom_position>/on

These tests verify each handler dispatches the right IR command via MQTT
publish, and that _execute_sequence performs the stop-then-wait-then-action
dance with the configured delay.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from wb_mqtt_bridge.infrastructure.devices.revox_a77_reel_to_reel.driver import RevoxA77ReelToReel
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.config.models import (
    RevoxA77ReelToReelConfig,
    RevoxA77ReelToReelParams,
    IRCommandConfig,
)


pytestmark = pytest.mark.integration


def _ir(action: str, topic: str, rom: str) -> IRCommandConfig:
    return IRCommandConfig(
        action=action,
        topic=topic,
        location="revox_ir",
        rom_position=rom,
    )


def _make_config(sequence_delay: int = 3) -> RevoxA77ReelToReelConfig:
    return RevoxA77ReelToReelConfig(
        device_id="test_revox",
        device_name="Test Revox A77",
        device_class="RevoxA77ReelToReel",
        config_class="RevoxA77ReelToReelConfig",
        reel_to_reel=RevoxA77ReelToReelParams(sequence_delay=sequence_delay),
        commands={
            "play":             _ir("play",             "/devices/test_revox/controls/play",             "1"),
            "stop":             _ir("stop",             "/devices/test_revox/controls/stop",             "2"),
            "rewind_forward":   _ir("rewind_forward",   "/devices/test_revox/controls/rewind_forward",   "3"),
            "rewind_backward":  _ir("rewind_backward",  "/devices/test_revox/controls/rewind_backward",  "4"),
        },
    )


@pytest.fixture
def mqtt_client():
    m = MagicMock(spec=MQTTClient)
    fut = asyncio.Future()
    fut.set_result(None)
    m.publish = MagicMock(return_value=fut)
    return m


@pytest.fixture
def device(mqtt_client):
    return RevoxA77ReelToReel(_make_config(), mqtt_client)


# --- handle_stop: direct dispatch (no sequence) -----------------------------


@pytest.mark.asyncio
async def test_handle_stop_publishes_stop_ir_directly(device, mqtt_client):
    """handle_stop sends the stop IR code directly (no preceding stop-then-wait dance)."""
    stop_cfg = device.get_available_commands()["stop"]

    result = await device.handle_stop(cmd_config=stop_cfg, params={})

    assert result.get("success") is True
    mqtt_client.publish.assert_called_once()
    topic_arg, _payload = mqtt_client.publish.call_args[0][:2]
    # The IR-blaster topic for ROM2 (stop).
    assert topic_arg == "/devices/revox_ir/controls/Play from ROM2/on"


# --- _execute_sequence: stop -> wait -> action ------------------------------


@pytest.mark.asyncio
async def test_execute_sequence_sends_stop_then_target(device, mqtt_client):
    """_execute_sequence emits two publishes: stop (ROM2) then the requested command's ROM."""
    play_cfg = device.get_available_commands()["play"]

    with patch.object(asyncio, "sleep", new=AsyncMock()) as mock_sleep:
        result = await device._execute_sequence(play_cfg, "play")

    assert result.get("success") is True
    assert mqtt_client.publish.call_count == 2
    topics = [call.args[0] for call in mqtt_client.publish.call_args_list]
    # Order: stop (ROM2) first, then play (ROM1).
    assert "ROM2" in topics[0]
    assert "ROM1" in topics[1]
    # Sleep was called with the configured sequence_delay (3 seconds).
    mock_sleep.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_execute_sequence_respects_custom_delay():
    """The configured reel_to_reel.sequence_delay is what _execute_sequence sleeps for."""
    mqtt = MagicMock(spec=MQTTClient)
    fut = asyncio.Future(); fut.set_result(None)
    mqtt.publish = MagicMock(return_value=fut)

    cfg = _make_config(sequence_delay=7)
    d = RevoxA77ReelToReel(cfg, mqtt)

    play_cfg = d.get_available_commands()["play"]
    with patch.object(asyncio, "sleep", new=AsyncMock()) as mock_sleep:
        await d._execute_sequence(play_cfg, "play")

    mock_sleep.assert_awaited_once_with(7)


# --- handle_play / handle_rewind_*: delegate to _execute_sequence ----------


@pytest.mark.asyncio
async def test_handle_play_uses_execute_sequence(device, mqtt_client):
    play_cfg = device.get_available_commands()["play"]
    with patch.object(asyncio, "sleep", new=AsyncMock()):
        result = await device.handle_play(cmd_config=play_cfg, params={})
    assert result.get("success") is True
    # Two publishes (stop then play) — same dance as test_execute_sequence_sends_stop_then_target.
    assert mqtt_client.publish.call_count == 2


@pytest.mark.asyncio
async def test_handle_rewind_forward_uses_execute_sequence(device, mqtt_client):
    cfg = device.get_available_commands()["rewind_forward"]
    with patch.object(asyncio, "sleep", new=AsyncMock()):
        result = await device.handle_rewind_forward(cmd_config=cfg, params={})
    assert result.get("success") is True
    topics = [call.args[0] for call in mqtt_client.publish.call_args_list]
    assert any("ROM3" in t for t in topics)


@pytest.mark.asyncio
async def test_handle_rewind_backward_uses_execute_sequence(device, mqtt_client):
    cfg = device.get_available_commands()["rewind_backward"]
    with patch.object(asyncio, "sleep", new=AsyncMock()):
        result = await device.handle_rewind_backward(cmd_config=cfg, params={})
    assert result.get("success") is True
    topics = [call.args[0] for call in mqtt_client.publish.call_args_list]
    assert any("ROM4" in t for t in topics)


# --- handle_message: routing to action handlers -----------------------------


@pytest.mark.asyncio
async def test_handle_message_routes_to_handler(device, mqtt_client):
    """An auto-generated MQTT control topic (/devices/<id>/controls/play) dispatches handle_play."""
    captured = []

    async def fake_play(cmd_config=None, params=None):
        captured.append({"cmd_config": cmd_config, "params": params})
        return device.create_command_result(success=True)

    original = device._action_handlers["play"]
    device._action_handlers["play"] = fake_play
    try:
        topic = f"/devices/{device.device_id}/controls/play"
        await device.handle_message(topic, "1")
        assert len(captured) == 1
        assert captured[0]["cmd_config"] is not None
    finally:
        device._action_handlers["play"] = original


@pytest.mark.asyncio
async def test_handle_message_unknown_topic_is_noop(device):
    """A topic that doesn't match any auto-generated control returns None."""
    result = await device.handle_message("/devices/test_revox/controls/nonexistent", "1")
    assert result is None


# --- typed config sanity ----------------------------------------------------


def test_commands_are_typed_ir_command_configs(device):
    cmds = device.get_available_commands()
    for name in ("play", "stop", "rewind_forward", "rewind_backward"):
        cfg = cmds[name]
        assert isinstance(cfg, IRCommandConfig)
        assert cfg.location == "revox_ir"
        assert cfg.rom_position
