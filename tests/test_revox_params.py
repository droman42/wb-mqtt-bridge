import pytest
import asyncio
from unittest.mock import MagicMock, patch

from wb_mqtt_bridge.infrastructure.devices.revox_a77_reel_to_reel.driver import RevoxA77ReelToReel
from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient
from wb_mqtt_bridge.infrastructure.config.models import (
    RevoxA77ReelToReelConfig,
    RevoxA77ReelToReelParams,
    IRCommandConfig,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def revox_config():
    """Typed Pydantic config matching the current production schema."""
    def _ir_cmd(action: str, topic: str, rom_position: str) -> IRCommandConfig:
        return IRCommandConfig(
            action=action,
            topic=topic,
            location="revox_ir",
            rom_position=rom_position,
        )

    return RevoxA77ReelToReelConfig(
        device_id="test_revox",
        device_name="Test Revox A77",
        device_class="RevoxA77ReelToReel",
        config_class="RevoxA77ReelToReelConfig",
        reel_to_reel=RevoxA77ReelToReelParams(sequence_delay=3),
        commands={
            "play": _ir_cmd("play", "/devices/test_revox/controls/play", "1"),
            "stop": _ir_cmd("stop", "/devices/test_revox/controls/stop", "2"),
            "rewind_forward": _ir_cmd("rewind_forward", "/devices/test_revox/controls/rewind_forward", "3"),
            "rewind_backward": _ir_cmd("rewind_backward", "/devices/test_revox/controls/rewind_backward", "4"),
        },
    )


@pytest.fixture
def mock_mqtt_client():
    mqtt_client = MagicMock(spec=MQTTClient)
    mqtt_client.publish = MagicMock(return_value=asyncio.Future())
    mqtt_client.publish.return_value.set_result(None)
    return mqtt_client


@pytest.fixture
def revox_device(revox_config, mock_mqtt_client):
    device = RevoxA77ReelToReel(revox_config, mock_mqtt_client)
    return device


@pytest.mark.asyncio
async def test_parameter_pattern(revox_device):
    """handle_stop forwards to _send_ir_command with (cfg, name, params).

    The current _send_ir_command signature is (cmd_config, command_name, params).
    handle_stop passes params through. The semantic intent (handler delegates
    to _send_ir_command with the correct command name) is preserved.
    """
    stop_config = revox_device.get_available_commands()["stop"]

    with patch.object(revox_device, '_send_ir_command') as mock_send:
        # Match CommandResult shape (TypedDict with success/mqtt_command).
        mock_send.return_value = {
            "success": True,
            "mqtt_command": {
                "topic": "/devices/revox_ir/controls/Play from ROM2/on",
                "payload": "1",
            },
        }

        result = await revox_device.handle_stop(cmd_config=stop_config, params={"value": "1"})

        # New signature has params as a 3rd positional arg.
        mock_send.assert_called_once_with(stop_config, "stop", {"value": "1"})

        assert isinstance(result, dict)
        assert result.get("success") is True
        assert "mqtt_command" in result


@pytest.mark.asyncio
async def test_sequence_execution(revox_device):
    """_execute_sequence sends stop first, then the requested command, with a delay between."""
    with patch.object(revox_device, '_send_ir_command') as mock_send, \
         patch.object(asyncio, 'sleep') as mock_sleep:

        mock_send.side_effect = [
            {"success": True, "mqtt_command": {"topic": "/devices/revox_ir/controls/Play from ROM2/on", "payload": "1"}},
            {"success": True, "mqtt_command": {"topic": "/devices/revox_ir/controls/Play from ROM1/on", "payload": "1"}},
        ]

        play_config = revox_device.get_available_commands()["play"]
        await revox_device._execute_sequence(play_config, "play")

        # Two _send_ir_command calls (stop then the requested command).
        assert mock_send.call_count == 2
        # Sequence delay from the typed config (sequence_delay=3 in the fixture).
        mock_sleep.assert_called_once_with(3)


@pytest.mark.asyncio
async def test_mqtt_message_handling(revox_device):
    """An auto-generated MQTT control topic routes to the matching handler."""
    play_handler_called = []

    async def fake_handle_play(cmd_config=None, params=None):
        play_handler_called.append({"cmd_config": cmd_config, "params": params})
        return {"success": True, "mqtt_command": {"topic": "/test/topic", "payload": "1"}}

    # Patch handle_play and propagate the patch into the handler registry too.
    with patch.object(revox_device, 'handle_play', side_effect=fake_handle_play) as mock_handle:
        original_handler = revox_device._action_handlers["play"]
        revox_device._action_handlers["play"] = mock_handle
        try:
            # handle_message matches against auto-generated topics (/devices/<id>/controls/<cmd>).
            auto_topic = f"/devices/{revox_device.device_id}/controls/play"
            await revox_device.handle_message(auto_topic, "1")

            assert mock_handle.call_count == 1
            assert play_handler_called[0]["cmd_config"] is not None
        finally:
            revox_device._action_handlers["play"] = original_handler
