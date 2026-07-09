"""CORE-9 — the MQTT reconnect budget must be per-disconnect-episode, not per-process.

Before the fix, `_run_mqtt_client`'s `retry_count` accumulated across the whole
process lifetime: five *separate* transient drops over a long-running controller's
life (broker restarts, Wi-Fi blips — each self-healing) exhausted `max_retries` and
the loop permanently gave up on MQTT, leaving the house uncontrollable until a manual
restart. A successful connection now resets the budget, so `max_retries` only bounds
retries within a single failed-to-connect episode.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from aiomqtt import MqttError

from wb_mqtt_bridge.infrastructure.mqtt.client import MQTTClient


def _client() -> MQTTClient:
    return MQTTClient({
        "host": "localhost", "port": 1883, "client_id": "test", "keepalive": 60,
        "auth": {},
    })


class _ConnectThenDrop:
    """Async ctx manager that models one connect episode: the connection succeeds
    (entered cleanly), then the message stream raises — an `MqttError` for the first
    `drops` episodes (a transient disconnect), and `CancelledError` afterwards to end
    the loop the way a real shutdown would."""

    def __init__(self, episodes: dict, drops: int):
        self._episodes = episodes
        self._drops = drops

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def subscribe(self, *_a, **_k):
        return None

    @property
    def messages(self):
        return self._gen()

    async def _gen(self):
        # Reaching the message loop == a successful connection for this episode.
        self._episodes["n"] += 1
        if self._episodes["n"] > self._drops:
            raise asyncio.CancelledError()
        raise MqttError("simulated transient drop")
        yield  # noqa: unreachable — makes this an async generator


@pytest.mark.asyncio
async def test_reconnect_survives_more_than_max_retries_lifetime_drops():
    c = _client()
    episodes = {"n": 0}
    DROPS = 8  # deliberately > the loop's max_retries (5)

    with patch(
        "wb_mqtt_bridge.infrastructure.mqtt.client.Client",
        side_effect=lambda *a, **k: _ConnectThenDrop(episodes, DROPS),
    ), patch(
        "wb_mqtt_bridge.infrastructure.mqtt.client.asyncio.sleep", new=AsyncMock()
    ):
        await c._run_mqtt_client({"hostname": "h", "port": 1883}, [])

    # Each successful connect resets the budget, so the loop keeps reconnecting past
    # max_retries and only stops on the injected CancelledError at episode DROPS+1.
    # Without the reset it would give up after exactly max_retries (5) episodes.
    assert episodes["n"] == DROPS + 1
