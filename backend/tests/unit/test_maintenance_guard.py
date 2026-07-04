"""Tests for WirenboardMaintenanceGuard — the wb-rules restart-burst filter.

The guard's contract (diagnosed against a live midnight `systemctl restart
wb-rules` burst, 2026-07-05):

* only a LIVE (retain=0) publish of the trigger topic opens a window — the
  retained copy the broker replays at our own subscribe time must NOT;
* the window is sliding: in-window traffic extends it, `duration` seconds of
  silence closes it;
* MAX_WINDOW_S hard-caps the total window so a periodic publisher on a
  subscribed topic can't hold it open forever.

Time is driven through a fake `time.monotonic` so every boundary is exact.
"""

import pytest

from wb_mqtt_bridge.infrastructure.maintenance import wirenboard_guard
from wb_mqtt_bridge.infrastructure.maintenance.wirenboard_guard import (
    WirenboardMaintenanceGuard,
)

TRIGGER = "/devices/wbrules/meta/driver"
OTHER = "/devices/wb-mr6c-nc_25/controls/K2"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(wirenboard_guard.time, "monotonic", fake)
    return fake


@pytest.fixture
def guard() -> WirenboardMaintenanceGuard:
    return WirenboardMaintenanceGuard(duration=5, topic=TRIGGER)


def test_retained_trigger_does_not_open_window(guard, clock):
    """The subscribe-time replay of the retained trigger is our own startup,
    not a controller restart — nothing may be dropped because of it."""
    assert guard.maintenance_started(TRIGGER, retain=True) is False
    clock.advance(0.001)
    assert guard.maintenance_started(OTHER, retain=False) is False


def test_live_trigger_opens_window(guard, clock):
    assert guard.maintenance_started(TRIGGER, retain=False) is True
    clock.advance(1)
    assert guard.maintenance_started(OTHER, retain=False) is True


def test_window_closes_after_quiet_time(guard, clock):
    guard.maintenance_started(TRIGGER, retain=False)
    clock.advance(5)  # exactly `duration` of silence — window closed
    assert guard.maintenance_started(OTHER, retain=False) is False
    # and stays closed
    clock.advance(1)
    assert guard.maintenance_started(OTHER, retain=False) is False


def test_in_window_traffic_extends_the_window(guard, clock):
    """The restart burst outlives any fixed window (measured: meta/driver at
    ~t+3s, rule files still republishing at t+8s and beyond) — each skipped
    message must push the closing horizon out."""
    guard.maintenance_started(TRIGGER, retain=False)
    for _ in range(4):
        clock.advance(4)  # inside the 5s quiet-time each step
        assert guard.maintenance_started(OTHER, retain=False) is True
    # 16s after the trigger — far past the original 5s — still guarded,
    # because activity kept extending. Now go quiet:
    clock.advance(5)
    assert guard.maintenance_started(OTHER, retain=False) is False


def test_hard_cap_bounds_total_window(guard, clock):
    """A periodic publisher (sensor mirror, poller) on a subscribed topic must
    not be able to hold the window open forever."""
    guard.maintenance_started(TRIGGER, retain=False)
    elapsed = 0.0
    while elapsed < WirenboardMaintenanceGuard.MAX_WINDOW_S:
        clock.advance(2)
        elapsed += 2
        if elapsed >= WirenboardMaintenanceGuard.MAX_WINDOW_S:
            break
        assert guard.maintenance_started(OTHER, retain=False) is True
    # past the cap: window force-closed despite continuous traffic
    assert guard.maintenance_started(OTHER, retain=False) is False


def test_live_trigger_rearms_open_window(guard, clock):
    """A second restart mid-window (double restart) restarts the clock,
    including the hard cap."""
    guard.maintenance_started(TRIGGER, retain=False)
    clock.advance(40)
    # quiet 40s > duration: window would be closed, but a fresh live trigger...
    assert guard.maintenance_started(TRIGGER, retain=False) is True
    clock.advance(4)
    assert guard.maintenance_started(OTHER, retain=False) is True


def test_retained_trigger_inside_open_window_is_skipped_but_does_not_extend(guard, clock):
    guard.maintenance_started(TRIGGER, retain=False)
    clock.advance(3)
    # retained trigger delivery mid-window: inside the window (skip = True via
    # the ordinary window check) but it must not reset the trigger timestamps
    assert guard.maintenance_started(TRIGGER, retain=True) is True
    clock.advance(4.5)
    # 4.5s after the retained delivery extended last_activity — still open
    assert guard.maintenance_started(OTHER, retain=False) is True


def test_no_window_no_skip(guard, clock):
    assert guard.maintenance_started(OTHER, retain=False) is False
    assert guard.maintenance_started(OTHER, retain=True) is False


def test_subscription_topics(guard):
    assert guard.subscription_topics() == [TRIGGER]
