"""In-memory sliding-window rate limiter.

Best-effort, single-process protection for ``/tunnel/register`` — not a
distributed limiter. Fine for the router's stateless, single-instance
deployment; would need shared state if the router is ever horizontally
scaled (see ``Design Documents/Instructions/cloud_router_architecture.md``).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > self._window_seconds:
            events.popleft()
        if len(events) >= self._max_events:
            return False
        events.append(now)
        return True
