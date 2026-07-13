"""Tests for MqttClient's per-topic retained-message opt-in (§P3.7 #18 cold-start fix).

Background: WB MQTT convention publishes the current value of every control as a
retained message on `/devices/<dev>/controls/<ctrl>`. By default MqttClient skips
retained messages in its receive loop -- that's safe behaviour (a retained `/on`
command payload could otherwise replay a stale action on startup). State-mirroring
subscriptions opt in via `subscribe(..., process_retained=True)` so the retained
"current value" payload IS dispatched and seeds `state.mirrored`. Without that seed
the canonical endpoint's no_op short-circuit can't detect "already at target" on the
first request after a bridge restart, and idempotent voice commands ("выключи свет"
when the light is already off) 503-timeout.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from locveil_bridge.infrastructure.mqtt.client import MQTTClient


def _client() -> MQTTClient:
    """Build an MqttClient without touching the network. The receive loop never runs
    here -- we only assert the data structures `subscribe()` populates."""
    return MQTTClient({
        "host": "localhost", "port": 1883, "client_id": "test", "keepalive": 60,
        "auth": {},
    })


@pytest.mark.asyncio
async def test_subscribe_does_not_opt_into_retained_by_default():
    c = _client()
    await c.subscribe("/some/topic", lambda t, p: None)
    assert "/some/topic" not in c._retained_allowed_topics


@pytest.mark.asyncio
async def test_subscribe_opt_in_adds_topic_to_allowed_set():
    c = _client()
    await c.subscribe(
        "/devices/wb-mr6c_51/controls/K4", lambda t, p: None, process_retained=True,
    )
    assert "/devices/wb-mr6c_51/controls/K4" in c._retained_allowed_topics


@pytest.mark.asyncio
async def test_opt_in_and_default_topics_coexist():
    """Mixing opted-in state-mirror subscribes with default WB-MQTT-in subscribes (the
    /on command path) on the same client must keep them isolated -- only the opted-in
    topic dispatches retained messages."""
    c = _client()
    await c.subscribe(
        "/devices/wb-mr6c_51/controls/K4", lambda t, p: None, process_retained=True,
    )
    await c.subscribe("/devices/cabinet_spots/controls/power_on/on", lambda t, p: None)
    assert c._retained_allowed_topics == {"/devices/wb-mr6c_51/controls/K4"}


def test_default_initial_state_has_no_retained_allowed_topics():
    c = _client()
    assert c._retained_allowed_topics == set()
