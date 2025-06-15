# maintenance_guard.py
import time
from abc import ABC, abstractmethod
from typing import List


class SystemMaintenanceGuard(ABC):
    """
    Abstract base for “maintenance mode” detectors.

    The guard never subscribes on its own – it just tells the caller
    **which** topics to listen to and, for every incoming publish,
    **whether that publish places the system in its maintenance window**.
    """

    # ────────────────────── interface you requested ────────────────────── #

    @abstractmethod
    def subscription_topics(self) -> List[str]:
        """
        Return the list of MQTT topics the caller MUST subscribe to.
        """
        raise NotImplementedError

    @abstractmethod
    def maintenance_started(self, topic: str) -> bool:
        """
        Inspect the *topic* of an incoming MQTT message.

        Return **True** if that topic means the system has JUST ENTERED
        or is CURRENTLY WITHIN a maintenance / restart window,
        otherwise **False**.
        """
        raise NotImplementedError


class WirenboardMaintenanceGuard(SystemMaintenanceGuard):
    """
    A concrete guard for Wiren Board controllers.

    Logic
    -----
    * We watch `/devices/<device_id>/meta/online`.
    * **Any** publish on that topic marks the *start* of the restart burst.
    * The guard stays “active” for `warmup_s` seconds after that publish,
      then goes back to normal.
    """

    def __init__(
        self,
        duration: int = 3,
        topic: str = "/devices/wbrules/meta/online",  # change to "wb-rules" on older FW
    ) -> None:
        self._duration = float(duration)
        self._watch_topic = topic
        self._maintenance_trigger: float | None = None  # monotonic seconds

    # ───────────────────────── interface methods ───────────────────────── #

    def subscription_topics(self) -> List[str]:
        return [self._watch_topic]

    def maintenance_started(self, topic: str) -> bool:
        now = time.monotonic()

        # 1. The trigger topic always **starts** a maintenance window
        if topic == self._watch_topic:
            self._maintenance_trigger = now
            return True

        # 2. While the window is still open, return True for *every* topic
        if self._maintenance_trigger is not None:
            if (now - self._maintenance_trigger) < self._duration:
                return True
            # window closed – forget the timestamp
            self._maintenance_trigger = None

        return False
