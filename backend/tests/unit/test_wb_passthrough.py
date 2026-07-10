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


def _sensor_config() -> WbPassthroughDeviceConfig:
    """A device whose catalog-advertised readable field (a float sensor) lands in mirrored —
    the DRV-23 shape: voice reads top-level `state.room_temperature`, not `mirrored`."""
    return WbPassthroughDeviceConfig(
        device_id="cabinet_floor",
        names={"ru": "Пол", "en": "Floor"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="cabinet",
        commands={
            "mode_on": WbPassthroughCommandConfig(
                action="mode_on", topic="/devices/wb-mr6cu_31/controls/K5/on", value="1"),
        },
        state_topics={
            "room_temperature": StateTopicSpec(
                topic="/devices/wb-m1w2_56/controls/External Sensor 1", type="float"),
        },
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
    assert getattr(device.state, "power") == "1"
    assert device.state.reachable is True


@pytest.mark.asyncio
async def test_readable_field_lands_at_top_level(mqtt):
    """DRV-23/DRV-25: a catalog-advertised readable field appears at top-level `state.<field>`
    — voice reads the top level. DRV-25: it IS a top-level field (no `mirrored` bucket)."""
    dev = WbPassthroughDevice(_sensor_config(), mqtt_client=mqtt)
    assert "room_temperature" not in dev.state.model_dump()  # nothing echoed yet
    await dev._on_value_message(
        "room_temperature", "/devices/wb-m1w2_56/controls/External Sensor 1", "24.125")
    d = dev.state.model_dump()
    assert "room_temperature" in d                # top-level — what voice reads
    assert float(d["room_temperature"]) == 24.125
    assert "mirrored" not in d                    # DRV-25: no bucket


@pytest.mark.asyncio
async def test_power_echo_sets_declared_top_level_field(device):
    """DRV-25: a `power` echo sets the declared top-level `state.power` directly (no bucket).
    (This un-enriched slice config carries no value table, so the raw wire value lands;
    production configs enrich `power` to canonical `on`/`off`.)"""
    await device._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    d = device.state.model_dump()
    assert d["power"] == "1"        # top-level, from the echo
    assert "mirrored" not in d      # no bucket


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
    setattr(device.state, "power", "1")  # echo from a previous successful power_on
    result = await device.execute_action("power_on", {}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "1")


@pytest.mark.asyncio
async def test_publish_no_op_false_on_real_change(device, mqtt):
    """The flag must be False (not just missing) when the publish IS a real change so
    the endpoint knows to wait for the echo."""
    setattr(device.state, "power", "0")
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
    assert device.state.power == "off"  # default, no echo seeded yet
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
    assert getattr(dev.state, "color") == {"r": 255, "g": 128, "b": 0}
    assert dev.state.reachable is True


@pytest.mark.asyncio
async def test_sensor_float_payloads_coerce_to_typed_state(mqtt):
    """Temperature/humidity/illuminance/sound_level all `type=float`; the raw `"21.5"` wire
    string must land in state.mirrored as the float 21.5 (catalog/Irene get typed values
    without consumer-side parsing)."""
    dev = WbPassthroughDevice(_sensor_config(), mqtt_client=mqtt)
    await dev._on_value_message("temperature", "/devices/wb-msw-v3_207/controls/Temperature", "21.5")
    await dev._on_value_message("co2", "/devices/wb-msw-v3_207/controls/CO2", "650")
    assert getattr(dev.state, "temperature") == 21.5
    assert isinstance(getattr(dev.state, "temperature"), float)
    assert getattr(dev.state, "co2") == 650
    assert isinstance(getattr(dev.state, "co2"), int)


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
    assert getattr(dev.state, "co2") == "not-a-number"
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
    assert getattr(device.state, "power") == "1"
    assert isinstance(getattr(device.state, "power"), str)


def test_state_topic_spec_normalises_bare_string_form():
    """Bare-string `state_topics` config still parses -- key invariant for the slice's
    existing cabinet_spots.json (no migration required)."""
    cfg = _slice_config()
    spec = cfg.state_topics["power"]
    assert isinstance(spec, StateTopicSpec)
    assert spec.topic == "/devices/wb-mr6c_51/controls/K4"
    assert spec.type == "str"


def test_state_topic_spec_values_accept_bare_string_list_back_compat():
    """§P3.7 #26 back-compat: enum `values: ["a", "b"]` keeps parsing — each entry
    widens to `ValueLabel(wire="a", canonical="a", labels=None)`."""
    spec = StateTopicSpec.model_validate({
        "topic": "/devices/x/controls/Mode",
        "type": "enum",
        "values": ["heat", "cool", "auto"],
    })
    assert spec.values is not None and len(spec.values) == 3
    assert spec.values[0].wire == "heat" and spec.values[0].canonical == "heat"
    assert spec.values[0].labels is None


def test_state_topic_spec_values_accept_full_value_label_with_labels():
    """§P3.7 #26 full form on StateTopicSpec: same triplet as CapabilityField."""
    spec = StateTopicSpec.model_validate({
        "topic": "/devices/x/controls/Mode",
        "type": "enum",
        "values": [
            {"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat", "de": "Heizen"}},
            {"wire": "2", "canonical": "cool", "labels": {"ru": "Охлаждение", "en": "Cool", "de": "Kühlen"}},
        ],
    })
    assert spec.values is not None
    assert spec.values[0].wire == "1" and spec.values[0].canonical == "heat"
    assert spec.values[0].labels is not None
    assert spec.values[0].labels.ru == "Обогрев"
    assert getattr(spec.values[0].labels, "de") == "Heizen"


# --- invert flag (cabinet rollers / inverted-percentage devices) -------------


def _inverted_cover_config() -> WbPassthroughDeviceConfig:
    """A cover device with `invert: true` on the position state topic -- mimics the
    cabinet rollers (dooya_dm35eq_x_*), where wire 0=open and 100=closed instead of the
    natural sense. The configs are authored in NATURAL sense (open writes 100, close
    writes 0, set_position takes natural pct); the driver flips at the wire boundary."""
    return WbPassthroughDeviceConfig(
        device_id="cabinet_roller_test",
        names={"ru": "Ролл", "en": "Roller", "de": "Rollo"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        capability_profile="cover",
        room="cabinet",
        commands={
            "open":  WbPassthroughCommandConfig(
                action="open",
                topic="/devices/dooya_dm35eq_x_test/controls/Position/on",
                value="100",
            ),
            "close": WbPassthroughCommandConfig(
                action="close",
                topic="/devices/dooya_dm35eq_x_test/controls/Position/on",
                value="0",
            ),
            "set_position": WbPassthroughCommandConfig(
                action="set_position",
                topic="/devices/dooya_dm35eq_x_test/controls/Position/on",
                params=[CommandParameterDefinition(name="pct", type="range", min=0, max=100, required=True)],
            ),
        },
        state_topics={
            "position": {
                "topic": "/devices/dooya_dm35eq_x_test/controls/Position",
                "type": "int",
                "unit": "%",
                "invert": True,
            },
        },
    )


def test_state_topic_spec_invert_flag_defaults_false():
    cfg = _slice_config()
    assert cfg.state_topics["power"].invert is False


def test_state_topic_spec_invert_flag_parses_true():
    cfg = _inverted_cover_config()
    assert cfg.state_topics["position"].invert is True


@pytest.mark.asyncio
async def test_invert_outbound_static_open_publishes_inverted_zero(mqtt):
    """`open` config has value="100" (natural sense). For an inverted cover the driver
    must publish "0" on the wire (motor's 0% travel position = fully open)."""
    dev = WbPassthroughDevice(_inverted_cover_config(), mqtt_client=mqtt)
    result = await dev.execute_action("open", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/dooya_dm35eq_x_test/controls/Position/on", "0"
    )


@pytest.mark.asyncio
async def test_invert_outbound_static_close_publishes_inverted_hundred(mqtt):
    dev = WbPassthroughDevice(_inverted_cover_config(), mqtt_client=mqtt)
    result = await dev.execute_action("close", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/dooya_dm35eq_x_test/controls/Position/on", "100"
    )


@pytest.mark.asyncio
async def test_invert_outbound_set_position_25_publishes_75_wire_sense(mqtt):
    """The core voice-ergonomics fix: user/voice says "25% open"; the driver publishes
    "75" (25% open = 75% motor travel for an inverted cover). Without the invert flag
    we'd publish "25" which would actually be 75% open."""
    dev = WbPassthroughDevice(_inverted_cover_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_position", {"pct": 25}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/dooya_dm35eq_x_test/controls/Position/on", "75"
    )


@pytest.mark.asyncio
async def test_invert_outbound_set_position_midpoint_unchanged(mqtt):
    """50% is the same in either sense; demonstrates the invariant that mid-position
    looks the same regardless of wire orientation."""
    dev = WbPassthroughDevice(_inverted_cover_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_position", {"pct": 50}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/dooya_dm35eq_x_test/controls/Position/on", "50"
    )


@pytest.mark.asyncio
async def test_invert_inbound_mirror_stores_natural_sense(mqtt):
    """Wire echo arrives as `"75"` (motor at 75% travel); the mirror inverts to natural
    sense `25` (= 25% open) before storing in state.mirrored. Voice consumers reading
    the state endpoint always see natural sense regardless of device family."""
    dev = WbPassthroughDevice(_inverted_cover_config(), mqtt_client=mqtt)
    await dev._on_value_message(
        "position", "/devices/dooya_dm35eq_x_test/controls/Position", "75"
    )
    assert getattr(dev.state, "position") == 25
    assert dev.state.reachable is True


@pytest.mark.asyncio
async def test_invert_roundtrip_set_then_mirror_consistent(mqtt):
    """End-to-end: set_position(25) publishes 75; the device echoes 75; mirror inverts
    back to 25; state.mirrored shows the natural target. The next set_position(25) call
    then short-circuits as no_op."""
    dev = WbPassthroughDevice(_inverted_cover_config(), mqtt_client=mqtt)
    # 1) publish
    await dev.execute_action("set_position", {"pct": 25}, source="api")
    # 2) device echoes the wire value
    await dev._on_value_message(
        "position", "/devices/dooya_dm35eq_x_test/controls/Position", "75"
    )
    assert getattr(dev.state, "position") == 25
    # 3) repeat the same call -> no_op
    mqtt.publish.reset_mock()
    result = await dev.execute_action("set_position", {"pct": 25}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is True
    # We still publish (cheap; keeps WB informed) but the wait can short-circuit.
    mqtt.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_invert_does_not_affect_non_inverted_field(mqtt):
    """The slice's cabinet_spots is uninverted. Sanity: its publish + mirror behave
    unchanged regardless of the new flag plumbing."""
    dev = WbPassthroughDevice(_slice_config(), mqtt_client=mqtt)
    await dev.execute_action("power_on", {}, source="api")
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr6c_51/controls/K4/on", "1")
    await dev._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    # power state_topic is bare-string (type=str), so mirror keeps the raw "1".
    assert getattr(dev.state, "power") == "1"


# --- invert flag: bool type (inverted heating actuators) ---------------------


def _inverted_heating_config() -> WbPassthroughDeviceConfig:
    """A heating loop with `invert: true` on a bool mode state_topic -- mimics the
    living_room / children_room / bedroom heating actuators on `wb-gpio/EXT3_R3A2-4`
    which are normally-closed valves: wire `"0"` = valve open (heating ON), wire
    `"1"` = valve closed (heating OFF). With the flag, configs author in natural
    sense (mode_on="1") and the driver flips at the wire."""
    return WbPassthroughDeviceConfig(
        device_id="livingroom_heating_test",
        names={"ru": "Обогрев", "en": "Heating", "de": "Heizung"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        capability_profile="heating_loop",
        room="living_room",
        commands={
            "mode_on":  WbPassthroughCommandConfig(
                action="mode_on",
                topic="/devices/wb-gpio/controls/EXT3_TEST/on",
                value="1",
            ),
            "mode_off": WbPassthroughCommandConfig(
                action="mode_off",
                topic="/devices/wb-gpio/controls/EXT3_TEST/on",
                value="0",
            ),
        },
        state_topics={
            "mode": {
                "topic": "/devices/wb-gpio/controls/EXT3_TEST",
                "type": "bool",
                "invert": True,
            },
        },
    )


@pytest.mark.asyncio
async def test_invert_bool_outbound_mode_on_publishes_zero(mqtt):
    """mode_on config has value="1" (natural sense: ON). With invert on a bool wire,
    the driver toggles to publish "0" -- the wire form for "valve open"."""
    dev = WbPassthroughDevice(_inverted_heating_config(), mqtt_client=mqtt)
    result = await dev.execute_action("mode_on", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/wb-gpio/controls/EXT3_TEST/on", "0"
    )


@pytest.mark.asyncio
async def test_invert_bool_outbound_mode_off_publishes_one(mqtt):
    dev = WbPassthroughDevice(_inverted_heating_config(), mqtt_client=mqtt)
    result = await dev.execute_action("mode_off", {}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with(
        "/devices/wb-gpio/controls/EXT3_TEST/on", "1"
    )


@pytest.mark.asyncio
async def test_invert_bool_inbound_wire_zero_stores_true_natural_sense(mqtt):
    """Wire echo "0" (valve open) → parsed as bool False → inverted to True (natural
    sense: heating IS on). State.mirrored shows the user-facing truth."""
    dev = WbPassthroughDevice(_inverted_heating_config(), mqtt_client=mqtt)
    await dev._on_value_message(
        "mode", "/devices/wb-gpio/controls/EXT3_TEST", "0"
    )
    assert getattr(dev.state, "mode") == True


@pytest.mark.asyncio
async def test_invert_bool_inbound_wire_one_stores_false_natural_sense(mqtt):
    dev = WbPassthroughDevice(_inverted_heating_config(), mqtt_client=mqtt)
    await dev._on_value_message(
        "mode", "/devices/wb-gpio/controls/EXT3_TEST", "1"
    )
    assert getattr(dev.state, "mode") == False


@pytest.mark.asyncio
async def test_invert_bool_roundtrip_mode_on_then_echo_then_no_op(mqtt):
    """End-to-end: mode_on publishes "0" → device echoes "0" → mirror inverts to True
    (natural sense: heating on) → next mode_on call short-circuits as no_op."""
    dev = WbPassthroughDevice(_inverted_heating_config(), mqtt_client=mqtt)
    # 1) publish mode_on -> wire "0"
    await dev.execute_action("mode_on", {}, source="api")
    # 2) device echoes wire "0"
    await dev._on_value_message("mode", "/devices/wb-gpio/controls/EXT3_TEST", "0")
    assert getattr(dev.state, "mode") is True
    # 3) repeat -> no_op (mirror already True, target also "on")
    mqtt.publish.reset_mock()
    result = await dev.execute_action("mode_on", {}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is True
    mqtt.publish.assert_awaited_once()


def test_invert_bool_static_passthrough_for_non_zero_one_forms():
    """If someone authored a bool command with `value: "on"`/`"off"`, the toggle
    should preserve the surface form (returning `"off"`/`"on"`, not `"1"`/`"0"`).
    Unknown forms pass through unchanged."""
    from wb_mqtt_bridge.infrastructure.devices.wb_passthrough.driver import (
        _toggle_bool_wire_form,
    )
    assert _toggle_bool_wire_form("0") == "1"
    assert _toggle_bool_wire_form("1") == "0"
    assert _toggle_bool_wire_form("on") == "off"
    assert _toggle_bool_wire_form("off") == "on"
    assert _toggle_bool_wire_form("On") == "Off"
    assert _toggle_bool_wire_form("true") == "false"
    # Unknown forms pass through (safer than guessing).
    assert _toggle_bool_wire_form("garbage") == "garbage"


@pytest.mark.asyncio
async def test_invert_bool_does_not_apply_to_non_inverted_str_field(mqtt):
    """Regression: cabinet_spots's `power` state_topic is bare-string (no invert flag,
    type defaults to str). The bool-toggle path must not catch it. Mirror keeps the
    raw "1"."""
    dev = WbPassthroughDevice(_slice_config(), mqtt_client=mqtt)
    await dev._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert getattr(dev.state, "power") == "1"  # still raw string, not toggled


# --- §P3.7 #26: value-label translation (canonical ↔ wire for enum fields) -----


def _hvac_mode_config() -> WbPassthroughDeviceConfig:
    """HVAC-style device with a value-table enum: wire integers, canonical English
    names, ru/en/de labels. Mirrors the Mitsubishi HVAC mode shape we'll roll out in
    Phase 2."""
    return WbPassthroughDeviceConfig(
        device_id="livingroom_hvac_test",
        names={"ru": "Кондиционер", "en": "AC", "de": "Klimaanlage"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        capability_profile="hvac",
        room="living_room",
        commands={
            "set_mode": WbPassthroughCommandConfig(
                action="set_mode",
                topic="/devices/wb-mr3lv12_x/controls/Mode/on",
                params=[CommandParameterDefinition(name="mode", type="string", required=True)],
            ),
        },
        state_topics={
            "mode": {
                "topic": "/devices/wb-mr3lv12_x/controls/Mode",
                "type": "enum",
                "values": [
                    {"wire": "0", "canonical": "auto", "labels": {"ru": "Авто", "en": "Auto", "de": "Auto"}},
                    {"wire": "1", "canonical": "heat", "labels": {"ru": "Обогрев", "en": "Heat", "de": "Heizen"}},
                    {"wire": "2", "canonical": "cool", "labels": {"ru": "Охлаждение", "en": "Cool", "de": "Kühlen"}},
                    {"wire": "3", "canonical": "dry", "labels": {"ru": "Осушение", "en": "Dry", "de": "Trocken"}},
                ],
            },
        },
    )


@pytest.mark.asyncio
async def test_value_label_outbound_canonical_set_mode_publishes_wire(mqtt):
    """Voice/UI calls `set_mode(mode="cool")` (canonical). The driver looks up the
    matching ValueLabel and publishes wire `"2"` to the MQTT topic. This is the core
    voice-ergonomics fix: catalog declares canonical, bus speaks wire."""
    dev = WbPassthroughDevice(_hvac_mode_config(), mqtt_client=mqtt)
    result = await dev.execute_action("set_mode", {"mode": "cool"}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr3lv12_x/controls/Mode/on", "2")
    assert result["data"]["payload"] == "2"


@pytest.mark.asyncio
async def test_value_label_inbound_wire_echo_stores_canonical_in_state(mqtt):
    """A wire echo `"2"` arrives on the mode value topic. The driver translates to
    canonical `"cool"` before storing in state.mirrored — so state always speaks the
    same identifier the catalog declared + that voice sends back."""
    dev = WbPassthroughDevice(_hvac_mode_config(), mqtt_client=mqtt)
    await dev._on_value_message("mode", "/devices/wb-mr3lv12_x/controls/Mode", "2")
    assert getattr(dev.state, "mode") == "cool"


@pytest.mark.asyncio
async def test_value_label_roundtrip_canonical_set_then_wire_echo_then_no_op(mqtt):
    """End-to-end: set_mode("cool") publishes wire `"2"`; device echoes `"2"`; mirror
    translates back to canonical `"cool"`; next set_mode("cool") short-circuits as
    no_op (idempotency comparison is canonical-vs-canonical)."""
    dev = WbPassthroughDevice(_hvac_mode_config(), mqtt_client=mqtt)
    # 1) publish canonical -> wire "2"
    await dev.execute_action("set_mode", {"mode": "cool"}, source="api")
    # 2) device echoes wire "2"
    await dev._on_value_message("mode", "/devices/wb-mr3lv12_x/controls/Mode", "2")
    assert getattr(dev.state, "mode") == "cool"
    # 3) repeat -> no_op
    mqtt.publish.reset_mock()
    result = await dev.execute_action("set_mode", {"mode": "cool"}, source="api")
    assert result["success"] is True
    assert result["data"]["no_op"] is True
    mqtt.publish.assert_awaited_once()  # cheap re-publish, but no_op flag set


@pytest.mark.asyncio
async def test_value_label_outbound_unknown_canonical_passes_through_with_warning(mqtt, caplog):
    """An unknown canonical (typo, stale voice grammar, malicious payload) passes
    through unchanged rather than 500-ing the canonical endpoint. The bus will reject
    it via WB's own error semantics; we log the bridge-side observation for ops."""
    dev = WbPassthroughDevice(_hvac_mode_config(), mqtt_client=mqtt)
    with caplog.at_level("WARNING"):
        await dev.execute_action("set_mode", {"mode": "nonsense"}, source="api")
    # Pass-through: the bogus canonical lands on the bus as-is for WB to reject.
    mqtt.publish.assert_awaited_once_with(
        "/devices/wb-mr3lv12_x/controls/Mode/on", "nonsense"
    )
    assert any("not in canonical or wire list" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_value_label_outbound_accepts_wire_pass_through(mqtt):
    """An internal caller posting `set_mode(mode="2")` (wire form) is accepted: a
    wire-match short-circuits the canonical lookup and publishes the same wire byte
    unchanged. Lets bridge-internal callers stay flexible without going through
    canonical translation twice."""
    dev = WbPassthroughDevice(_hvac_mode_config(), mqtt_client=mqtt)
    await dev.execute_action("set_mode", {"mode": "2"}, source="api")
    mqtt.publish.assert_awaited_once_with("/devices/wb-mr3lv12_x/controls/Mode/on", "2")


@pytest.mark.asyncio
async def test_value_label_inbound_unknown_wire_falls_back_to_raw(mqtt, caplog):
    """An unknown wire value (e.g. firmware revision adds a new mode mid-runtime)
    fails parse_value's allowed-set check, logs the parse warning, and lands as the
    raw payload in state.mirrored — the catalog hash will bump when the profile is
    extended, prompting a re-fetch."""
    dev = WbPassthroughDevice(_hvac_mode_config(), mqtt_client=mqtt)
    with caplog.at_level("WARNING"):
        await dev._on_value_message("mode", "/devices/wb-mr3lv12_x/controls/Mode", "9")
    assert getattr(dev.state, "mode") == "9"
    assert any("failed to parse 'mode'" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_value_label_bare_string_back_compat_acts_as_identity(mqtt):
    """A `values: ["a", "b"]` config widens each entry to wire==canonical; the
    translation pass becomes a no-op (wire and canonical strings are equal). State
    stores the same raw string regardless of which direction the data flows."""
    cfg = WbPassthroughDeviceConfig(
        device_id="x",
        names={"ru": "X", "en": "X"},
        device_class="WbPassthroughDevice",
        config_class="WbPassthroughDeviceConfig",
        room="cabinet",
        commands={
            "set_mode": WbPassthroughCommandConfig(
                action="set_mode",
                topic="/devices/wb-x/controls/Mode/on",
                params=[CommandParameterDefinition(name="mode", type="string", required=True)],
            ),
        },
        state_topics={
            "mode": {
                "topic": "/devices/wb-x/controls/Mode",
                "type": "enum",
                "values": ["heat", "cool"],
            },
        },
    )
    dev = WbPassthroughDevice(cfg, mqtt_client=mqtt)
    await dev.execute_action("set_mode", {"mode": "cool"}, source="api")
    mqtt.publish.assert_awaited_once_with("/devices/wb-x/controls/Mode/on", "cool")
    await dev._on_value_message("mode", "/devices/wb-x/controls/Mode", "heat")
    assert getattr(dev.state, "mode") == "heat"


@pytest.mark.asyncio
async def test_value_label_no_table_acts_as_identity_for_str_field(mqtt):
    """The slice's bare-string `power` field has no value table; the translation
    helpers must be a pure identity so existing devices keep mirroring raw strings."""
    dev = WbPassthroughDevice(_slice_config(), mqtt_client=mqtt)
    await dev._on_value_message("power", "/devices/wb-mr6c_51/controls/K4", "1")
    assert getattr(dev.state, "power") == "1"


# --- DRV-26: the real HVAC config speaks the firmware's numeric wire ---------
# mitsubishi2wb publishes numeric indices and its command callback silently ignores
# anything else (mitsubishi2wb.ino hpSettingsChanged()/mqttCallback()). Before DRV-26 the
# tables carried label strings ("COOL"): inbound echoes failed enum-parse (raw "2" in
# /state) and outbound set_mode published "COOL", which the firmware DROPPED — HVAC
# mode/fan/vane/widevane control was silently dead. These tests drive the REAL config.


def _real_hvac_device(mqtt) -> WbPassthroughDevice:
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "config"
    cfg = WbPassthroughDeviceConfig.model_validate(
        json.loads((root / "devices/wb-devices/children_room/children_room_hvac.json").read_text())
    )
    return WbPassthroughDevice(cfg, mqtt_client=mqtt)


@pytest.mark.asyncio
async def test_drv26_hvac_inbound_numeric_wire_translates_to_canonical(mqtt):
    """Wire echo `mode=2` (the firmware's COOL index) lands as canonical `cool`."""
    dev = _real_hvac_device(mqtt)
    await dev._on_value_message("mode", "/devices/hvac_children/controls/mode", "2")
    assert getattr(dev.state, "mode") == "cool"
    await dev._on_value_message("widevane", "/devices/hvac_children/controls/widevane", "3")
    assert getattr(dev.state, "widevane") == "center"
    await dev._on_value_message("fan", "/devices/hvac_children/controls/fan", "0")
    assert getattr(dev.state, "fan") == "auto"


@pytest.mark.asyncio
async def test_drv26_hvac_outbound_canonical_translates_to_numeric_wire(mqtt):
    """set_mode(cool) publishes the numeric wire `2` — the ONLY payload the firmware
    accepts (it silently ignores non-numeric strings like the old "COOL")."""
    dev = _real_hvac_device(mqtt)
    result = await dev.execute_action("set_mode", {"mode": "cool"}, source="api")
    assert result["success"] is True
    mqtt.publish.assert_awaited_once_with("/devices/hvac_children/controls/mode/on", "2")
