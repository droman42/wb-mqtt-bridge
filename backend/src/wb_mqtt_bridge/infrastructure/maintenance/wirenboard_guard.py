# wirenboard_guard.py
import time
from abc import ABC, abstractmethod
from typing import List


class SystemMaintenanceGuard(ABC):
    """
    Abstract base for "maintenance mode" detectors.

    The guard never subscribes on its own – it just tells the caller
    **which** topics to listen to and, for every incoming publish,
    **whether that publish falls inside a maintenance window** (and
    should therefore be dropped instead of dispatched to handlers).
    """

    @abstractmethod
    def subscription_topics(self) -> List[str]:
        """
        Return the list of MQTT topics the caller MUST subscribe to.
        """
        raise NotImplementedError

    @abstractmethod
    def maintenance_started(self, topic: str, retain: bool) -> bool:
        """
        Inspect an incoming MQTT message.

        Args:
            topic: The topic the message arrived on.
            retain: The message's RETAIN flag as delivered. Per MQTT 3.1.1
                [MQTT-3.3.1-9], a broker sets RETAIN=1 only when replaying a
                stored message to a *new* subscription; a publish forwarded to
                an established subscription always arrives with RETAIN=0. The
                flag therefore distinguishes "subscribe-time replay" from
                "this just happened live".

        Return **True** if the message falls inside a maintenance / restart
        window (the caller should drop it), otherwise **False**.
        """
        raise NotImplementedError


class WirenboardMaintenanceGuard(SystemMaintenanceGuard):
    """
    A concrete guard for Wiren Board controllers.

    When the `wb-rules` engine (re)starts — e.g. a nightly
    `systemctl restart wb-rules` cron — it republishes every virtual
    device it owns: metas first, then control values as each rule file
    loads, with rule-startup side-effect publishes trailing behind. All
    of that arrives live (RETAIN=0), so the client's retained-skip cannot
    filter it; this guard is the only defense against re-processing the
    burst as if it were real device activity.

    Logic
    -----
    * We watch the trigger topic (default ``/devices/wbrules/meta/driver``),
      which wbgong republishes early in every engine start.
    * Only a **live** (RETAIN=0) publish on the trigger topic opens a
      window. The retained copy the broker replays when *we* subscribe is
      ignored — that's our own startup, not a controller restart.
    * The window is **sliding**: it opens for `duration` seconds and every
      message that arrives while it is open extends it by another
      `duration` seconds (the restart burst is bursty and its total length
      varies with the number of rule files). The window closes after
      `duration` seconds of silence.
    * ``MAX_WINDOW_S`` hard-caps the total window so a periodic publisher
      on a subscribed topic (a sensor mirror, a poller) can never hold the
      window open forever.
    """

    # Absolute ceiling on one maintenance window, seconds. The measured
    # wb-rules restart burst is ~10-15 s on a full controller; 60 s leaves
    # generous headroom while bounding how long real traffic can be dropped.
    MAX_WINDOW_S: float = 60.0

    def __init__(
        self,
        duration: int = 3,
        topic: str = "/devices/wbrules/meta/driver",  # change to "wb-rules" on older FW
    ) -> None:
        self._duration = float(duration)
        self._watch_topic = topic
        self._window_opened: float | None = None  # monotonic seconds
        self._last_activity: float = 0.0  # monotonic seconds

    def subscription_topics(self) -> List[str]:
        return [self._watch_topic]

    def maintenance_started(self, topic: str, retain: bool) -> bool:
        now = time.monotonic()

        # 1. A LIVE publish on the trigger topic (re)starts the window.
        #    A retained delivery is the broker replaying stored state at our
        #    own subscribe time — never a restart signal; fall through to the
        #    ordinary window check without touching the timestamps.
        if topic == self._watch_topic and not retain:
            self._window_opened = now
            self._last_activity = now
            return True

        # 2. While the window is open, every message is inside it — and
        #    extends it (sliding window), up to the hard cap.
        if self._window_opened is not None:
            if (now - self._window_opened) >= self.MAX_WINDOW_S:
                self._window_opened = None  # hard cap reached
            elif (now - self._last_activity) < self._duration:
                self._last_activity = now
                return True
            else:
                self._window_opened = None  # quiet long enough — window closed

        return False
