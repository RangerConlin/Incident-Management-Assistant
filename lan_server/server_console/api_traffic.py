"""Thread-safe ring buffer of API request entries for the console traffic tab.

The FastAPI request-logging middleware (``create_app(request_log_fn=...)``)
calls :meth:`ApiTrafficLog.record` from the server's asyncio thread; the Qt
window drains new entries from the UI thread on a timer.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any


class ApiTrafficLog:
    """Bounded, sequence-numbered request log shared between threads."""

    def __init__(self, *, max_entries: int = 1000) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = Lock()
        self._next_seq = 0

    def record(self, entry: dict[str, Any]) -> None:
        """Store one request entry; called from the API server thread."""

        with self._lock:
            stored = dict(entry)
            stored["seq"] = self._next_seq
            self._next_seq += 1
            self._entries.append(stored)

    def entries_since(self, seq: int) -> list[dict[str, Any]]:
        """Return entries newer than ``seq`` (use -1 for everything buffered)."""

        with self._lock:
            return [dict(item) for item in self._entries if item["seq"] > seq]

    def clear(self) -> None:
        """Drop buffered entries; sequence numbers keep increasing."""

        with self._lock:
            self._entries.clear()

    @property
    def total_recorded(self) -> int:
        """Total requests ever recorded, including ones the buffer dropped."""

        with self._lock:
            return self._next_seq
