"""In-memory evidence rings (problem_reports_bridge.md B-2/B-9).

Always-on, bounded, dumped only into report bundles. Pure data structures — the
hooks live in the infrastructure adapters (BaseDevice.execute_action feeds the
dispatch ring; the MQTT client's traffic observer feeds the window), pointing
inward at these per the hexagonal rule.
"""

import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional


class DispatchRing:
    """Last N executed device actions — the "what did the system just do" narrative."""

    def __init__(self, depth: int = 50):
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=depth)

    def record(
        self,
        *,
        source: str,
        device_id: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        self._entries.append({
            "ts": time.time(),
            "source": source,
            "device_id": device_id,
            "action": action,
            "params": dict(params or {}),
            "success": success,
            "error": error,
        })

    def snapshot(self) -> List[Dict[str, Any]]:
        return list(self._entries)


class MqttWindow:
    """Recent broker traffic, topic-filtered with per-topic last-value dedup.

    Bounded two ways (B-9): entries older than ``max_age_s`` are pruned, and the
    window never holds more than ``max_entries``. Dedup keeps only the LATEST
    message per (direction, topic) — sensor value churn collapses to one row.
    """

    def __init__(self, max_age_s: int = 60, max_entries: int = 500,
                 topic_prefix: str = "/devices/"):
        self._max_age_s = max_age_s
        self._max_entries = max_entries
        self._prefix = topic_prefix
        self._entries: Deque[Dict[str, Any]] = deque()

    def record(self, direction: str, topic: str, payload: str) -> None:
        if not topic.startswith(self._prefix):
            return
        # per-topic dedup: drop the older entry for the same (direction, topic)
        for i, e in enumerate(self._entries):
            if e["topic"] == topic and e["direction"] == direction:
                del self._entries[i]
                break
        self._entries.append({
            "ts": time.time(),
            "direction": direction,  # "in" | "out"
            "topic": topic,
            "payload": payload if len(payload) <= 512 else payload[:512] + "…",
        })
        self._prune()

    def _prune(self) -> None:
        cutoff = time.time() - self._max_age_s
        while self._entries and self._entries[0]["ts"] < cutoff:
            self._entries.popleft()
        while len(self._entries) > self._max_entries:
            self._entries.popleft()

    def snapshot(self) -> List[Dict[str, Any]]:
        self._prune()
        return list(self._entries)
