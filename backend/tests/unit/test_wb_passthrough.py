"""Tests for the generic WB-passthrough driver (§P3.7 #13).

Real driver, real config, mocked MQTT client. Exercises:

- handler auto-registration from `config.commands` (one publish per command).
- publish path: static `value` and param-derived value.
- mirror path: a value-topic echo flows through `update_state` into `state.mirrored`.
- error path: a per-control `meta/error` `r` flag flips `reachable` False and records the
  flag in `state.error_flags`; clearing the flag flips it back.
- loop guard: `enable_wb_emulation` defaults to False so the BaseDevice flow skips the
  WB virtual-device callback registration (no feedback loop with the real device).
- single-room schema works end-to-end (config carries `room: "cabinet"`; cross-room
  actions like "выключи свет везде" are Irene's job, resolved from the catalog).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from wb_mqtt_bridge.infrastructure.config.models import (
    CommandParameterDefinition,
    StateTopicSpec,
    WbPassthroughCommandConfig,
    WbPassthroughDeviceConfig,
)
from wb_mqtt_bridge.infrastructure.devices.wb_passthrough.driver import (
    WbPassthroughDevice,
    _parse_template,
)


def _slice_config() -> WbPassthroughDeviceConfig:
    """The cabinet_spots slice config from §P3.7 A1, in code."""
    return WbPassthroughDeviceConfig(
        device_id="cabinet_spots",
        names={"ru": "Споты", "en": "Spots"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="cabinet",
        commands={
            "power_on":  WbPassthroughCommandConfig(action="power_on",  topic="/devices/wb-mr6c_51/controls/K4/on", value="1"),
            "power_off": WbPassthroughCommandConfig(action="power_off", topic="/devices/wb-mr6c_51/controls/K4/on", value="0"),
        },
        state_topics={"power": "/devices/wb-mr6c_51/controls/K4"},
    )


def _dimmer_config() -> WbPassthroughDeviceConfig:
    """A param-carrying command (slider) to exercise the param-derived payload path."""
    return WbPassthroughDeviceConfig(
        device_id="cabinet_spots_dim",
        names={"ru": "Споты", "en": "Spots"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="cabinet",
        commands={
            "set_brightness": WbPassthroughCommandConfig(
                action="set_brightness",
                topic="/devices/wb-mdm3_83/controls/Channel 1/on",
                params=[CommandParameterDefinition(name="level", type="range", min=0, max=100, required=True)],
            ),
        },
        state_topics={"brightness": "/devices/wb-mdm3_83/controls/Channel 1"},
    )


@pytest.fixture
def mqtt() -> MagicMock:
    m = MagicMock()
    m.subscribe = AsyncMock()
    m.publish = AsyncMock()
    return m


@pytest.fixture
def device(mqtt) -> WbPassthroughDevice:
    return WbPassthroughDevice(_slice_config(), mqtt_client=mqtt)


# --- Schema + construction ------------------------------------------------


def test_passthrough_config_defaults_disable_wb_emulation():
    """enable_wb_emulation MUST default to False on the passthrough config so the BaseDevice
    flow skips _setup_wb_virtual_device — the structural loop guard."""
    cfg = _slice_config()
    assert cfg.enable_wb_emulation is False


def test_bilingual_names_and_single_room_carry_through(device):
    assert device.config.names.ru == "Споты"
    assert device.config.names.en == "Spots"
    assert device.config.room == "cabinet"
    # BaseDevice's flat compat field projects ru, matching the UI/state surfaces.
    assert device.device_name == "Споты"


def test_handlers_registered_one_per_command(device):
    assert "power_on" in device._action_handlers
    assert "power_off" in device._action_handlers


# --- Setup: subscriptions go out for value + meta/error ------------------


@pytest.mark.asyncio
async def test_setup_subscribes_to_value_and_error_topic_per_state_field(device, mqtt):
    ok = await device.setup()
    assert ok is True
    subs = [c.args[0] for c in mqtt.subscribe.await_args_list]
    assert "/devices/wb-mr6c_51/controls/K4" in subs
    assert "/devices/wb-mr6c_51/controls/K4/meta/error" in subs
    # Two state_topics fields would be two subscribe calls each; slice has one field.
    assert len(subs) == 2


@pytest.mark.asyncio
async def test_setup_opts_into_retained_message_processing(device, mqtt):
    """Both the value-topic mirror AND the meta/error subscription must pass
    `process_retained=True` so the broker's retained "current state" payload is
    actually dispatched on connect. Otherwise the FIRST request after a bridge restart
    that targets the device's already-current value (`power_off` when it's already off)
    hits the canonical endpoint's 500 ms wait with an empty mirrored state, no echo
    arrives (the device doesn't republish unchanged values), and we 503. See §P3.7 #18
    cold-start fix."""
    await device.setup()
    for call in mqtt.subscribe.await_args_list:
        assert call.kwargs.get("process_retained") is True, (
            f"subscribe to {call.args[0]!r} did not opt into retained-message processing"
        )


@pytest.mark.asyncio
async def test_setup_returns_false_without_mqtt_client():
    dev = WbPassthroughDevice(_slice_config(), mqtt_client=None)
    assert await dev.setup() is False


# --- Write path: static value -----------------------------------------------


@pytest.mark.asyncio
async def test_power_on_publishes_static_value(device, mqtt):
    result = await device.execute_action("power_on", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "1")


@pytest.mark.asyncio
async def test_power_off_publishes_static_value(device, mqtt):
    result = await device.execute_action("power_off", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "0")


# --- Write path: param-derived value ----------------------------------------


@pytest.mark.asyncio
async def test_set_brightness_publishes_param_value(mqtt):
    dev = WbPassthroughDevice(_dimmer_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_brightness", {"level": 75}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mdm3_83/controls/Channel 1/on", "75")


@pytest.mark.asyncio
async def test_set_brightness_without_param_fails_cleanly(mqtt):
    """Missing required param → graceful failure, no publish."""
    dev = WbPassthroughDevice(_dimmer_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_brightness", {}, source="api")
    assert result["success"] is False
    mqtt.publish.assert_not_called()


# --- Mirror path: value topic flows into state.mirrored ---------------------


@pytest.mark.asyncio
async def test_value_topic_echo_mirrors_into_state(device):
    await device._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert device.state.mirrored == {"power": "1"}
    assert device.state.reachable is True


@pytest.mark.asyncio
async def test_value_topic_echo_clears_previous_error_flag(device):
    # Seed: a previous read error
    device.state.error_flags = {"power": "r"}
    device.state.reachable = False
    await device._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert "power" not in device.state.error_flags
    assert device.state.reachable is True


# --- Error path: meta/error flag flips reachable ----------------------------


@pytest.mark.asyncio
async def test_meta_error_r_flag_flips_reachable_false(device):
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "r")
    assert device.state.error_flags == {"power": "r"}
    assert device.state.reachable is False


@pytest.mark.asyncio
async def test_meta_error_empty_payload_clears_flag(device):
    device.state.error_flags = {"power": "r"}
    device.state.reachable = False
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "")
    assert device.state.error_flags == {}
    assert device.state.reachable is True


@pytest.mark.asyncio
async def test_meta_error_compound_rw_still_marks_unreachable(device):
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "rw")
    assert device.state.error_flags == {"power": "rw"}
    assert device.state.reachable is False


@pytest.mark.asyncio
async def test_publish_flags_no_op_when_mirror_already_matches(device, mqtt):
    """Idempotency: when state.mirrored already shows the target value, the publish goes
    out (we keep the WB layer informed; cheap) but the result is flagged `no_op: True` so
    the canonical endpoint can short-circuit its echo wait. Otherwise voice would get a
    500 ms timeout + 503 on a routine "включи свет" when the light is already on."""
    device.state.mirrored = {"power": "1"}  # echo from a previous successful power_on
    result = await device.execute_action("power_on", {}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "1")


@pytest.mark.asyncio
async def test_publish_no_op_false_on_real_change(device, mqtt):
    """The flag must be False (not just missing) when the publish IS a real change so
    the endpoint knows to wait for the echo."""
    device.state.mirrored = {"power": "0"}
    result = await device.execute_action("power_on", {}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is False


@pytest.mark.asyncio
async def test_publish_no_op_false_when_mirror_unseen_yet(device, mqtt):
    """Cold start (no echo yet): mirrored is empty, so we can't know whether it's already
    at the target. Treat as a real change (no_op=False) so the endpoint waits for the
    echo. (Limitation: if the device really is already at the target it won't echo and
    the wait will 503 -- documented as a known cold-start edge case until retained-message
    handling lands.)"""
    assert device.state.mirrored == {}
    result = await device.execute_action("power_on", {}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is False


@pytest.mark.asyncio
async def test_w_only_error_does_not_flip_reachable(device):
    """Per the convention, `w` is a write-side failure; the device may still be readable.
    We model `reachable` against read failures (`r`) only."""
    await device._on_error_message("power", "/devices/wb-mr6c_51/controls/K4/meta/error", "w")
    assert device.state.error_flags == {"power": "w"}
    assert device.state.reachable is True


# --- §P3.7 #19 -- typed state_topics + payload_template + type coercion -----


def _rgb_config() -> WbPassthroughDeviceConfig:
    """A composite-payload device: `color.set(r,g,b)` is one WB publish with `"R;G;B"`,
    one mirrored field of typed RGB. Exercises payload_template + rgb encoding round-trip."""
    return WbPassthroughDeviceConfig(
        device_id="livingroom_rgb",
        names={"ru": "Подсветка", "en": "Mood Light"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="livingroom",
        commands={
            "set_color": WbPassthroughCommandConfig(
                action="set_color",
                topic="/devices/wb-mrgbw-d-fw3_10/controls/RGB Strip/on",
                params=[
                    CommandParameterDefinition(name="r", type="integer", min=0, max=255, required=True),
                    CommandParameterDefinition(name="g", type="integer", min=0, max=255, required=True),
                    CommandParameterDefinition(name="b", type="integer", min=0, max=255, required=True),
                ],
                payload_template="{r};{g};{b}",
            ),
        },
        state_topics={
            "color": {
                "topic": "/devices/wb-mrgbw-d-fw3_10/controls/RGB Strip",
                "type": "rgb",
                "encoding": "{r};{g};{b}",
            },
        },
    )


def _sensor_config() -> WbPassthroughDeviceConfig:
    """A pure-sensor (no commands) device that uses typed state_topics for all the
    wb-msw-v3 fields. Exercises the type coercion paths for scalar reads."""
    return WbPassthroughDeviceConfig(
        device_id="livingroom_sensors",
        names={"ru": "Сенсоры гостиной", "en": "Living Room Sensors"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        capability_profile="sensor_room",
        room="livingroom",
        state_topics={
            "temperature": {"topic": "/devices/wb-msw-v3_207/controls/Temperature", "type": "float", "unit": "°C"},
            "humidity":    {"topic": "/devices/wb-msw-v3_207/controls/Humidity",    "type": "float", "unit": "%"},
            "co2":         {"topic": "/devices/wb-msw-v3_207/controls/CO2",         "type": "int",   "unit": "ppm"},
            "illuminance": {"topic": "/devices/wb-msw-v3_207/controls/Illuminance", "type": "float", "unit": "lux"},
            "sound_level": {"topic": "/devices/wb-msw-v3_207/controls/Sound Level", "type": "float", "unit": "dB"},
        },
    )


def test_parse_template_inverse_round_trip():
    """`"{r};{g};{b}"` + `"255;128;0"` → `{r:255, g:128, b:0}` (with int coerce). Used by
    `_parse_value` for the `rgb` type and any future composite encoding."""
    result = _parse_template("{r};{g};{b}", "255;128;0", coerce=int)
    assert result == {"r": 255, "g": 128, "b": 0}


def test_parse_template_rejects_payload_mismatching_separators():
    with pytest.raises(ValueError, match="does not match template"):
        _parse_template("{r};{g};{b}", "255,128,0", coerce=int)


def test_parse_template_rejects_template_with_no_placeholders():
    with pytest.raises(ValueError, match="no `{name}` placeholders"):
        _parse_template("fixed_value", "anything")


@pytest.mark.asyncio
async def test_rgb_publish_uses_payload_template(mqtt):
    """`color.set(r,g,b)` must compose `"R;G;B"` and publish once — the v1 way to drive
    a composite WB control without a separate adapter layer."""
    dev = WbPassthroughDevice(_rgb_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_color", {"r": 255, "g": 128, "b": 0}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/wb-mrgbw-d-fw3_10/controls/RGB Strip/on", "255;128;0"
    )


@pytest.mark.asyncio
async def test_rgb_publish_with_missing_template_param_fails_cleanly(mqtt):
    dev = WbPassthroughDevice(_rgb_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_color", {"r": 255, "g": 128}, source="api")
    assert result["success"] is False
    mqtt.publish.assert_not_called()


@pytest.mark.asyncio
async def test_rgb_mirror_inverse_parses_into_typed_dict(mqtt):
    """The incoming value-topic echo `"255;128;0"` must coerce into the typed
    `{r:255,g:128,b:0}` dict via the `encoding` template (state_topics → rgb)."""
    dev = WbPassthroughDevice(_rgb_config(), mqtt_client=mqtt)
    await dev._on_value_message("color", "/devices/wb-mrgbw-d-fw3_10/controls/RGB Strip", "255;128;0")
    assert dev.state.mirrored == {"color": {"r": 255, "g": 128, "b": 0}}
    assert dev.state.reachable is True


@pytest.mark.asyncio
async def test_sensor_float_payloads_coerce_to_typed_state(mqtt):
    """Temperature/humidity/illuminance/sound_level all `type=float`; the raw `"21.5"` wire
    string must land in state.mirrored as the float 21.5 (catalog/Irene get typed values
    without consumer-side parsing)."""
    dev = WbPassthroughDevice(_sensor_config(), mqtt_client=mqtt)
    await dev._on_value_message("temperature", "/devices/wb-msw-v3_207/controls/Temperature", "21.5")
    await dev._on_value_message("co2", "/devices/wb-msw-v3_207/controls/CO2", "650")
    assert dev.state.mirrored["temperature"] == 21.5
    assert isinstance(dev.state.mirrored["temperature"], float)
    assert dev.state.mirrored["co2"] == 650
    assert isinstance(dev.state.mirrored["co2"], int)


@pytest.mark.asyncio
async def test_malformed_typed_payload_logs_and_mirrors_raw_without_changing_reachable(mqtt, caplog):
    """If a payload doesn't parse against its declared type, the driver logs a warning and
    mirrors the raw string instead -- it does NOT touch `state.error_flags` (which is
    WB-protocol-only: `r`/`w`/`p`) and `reachable` stays True (the device IS talking; WE
    just can't decode this one message)."""
    dev = WbPassthroughDevice(_sensor_config(), mqtt_client=mqtt)
    import logging
    caplog.set_level(logging.WARNING)
    await dev._on_value_message("co2", "/devices/wb-msw-v3_207/controls/CO2", "not-a-number")
    # Raw string preserved (lets downstream code see what arrived; no `None` surprise).
    assert dev.state.mirrored["co2"] == "not-a-number"
    # No WB-protocol flag fabricated.
    assert "co2" not in dev.state.error_flags
    assert dev.state.reachable is True
    # Operator visibility lives in the log, not the state.
    assert any("failed to parse 'co2'" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_slice_bare_string_state_topic_still_mirrors_as_string(device):
    """Back-compat regression: the slice's `state_topics={"power": "/topic"}` form must
    keep mirroring `"1"` / `"0"` as raw strings (StateTopicSpec normalises with type=str).
    Tests against the existing slice fixture so the cabinet_spots install doesn't change."""
    await device._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert device.state.mirrored == {"power": "1"}
    assert isinstance(device.state.mirrored["power"], str)


def test_state_topic_spec_normalises_bare_string_form():
    """Bare-string `state_topics` config still parses -- key invariant for the slice's
    existing cabinet_spots.json (no migration required)."""
    cfg = _slice_config()
    spec = cfg.state_topics["power"]
    assert isinstance(spec, StateTopicSpec)
    assert spec.topic == "/devices/wb-mr6c_51/controls/K4"
    assert spec.type == "str"
