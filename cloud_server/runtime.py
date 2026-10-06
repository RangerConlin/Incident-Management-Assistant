"""Runtime state for the hosted SARApp cloud server."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RequestLog:
    limit: int = 500
    _items: deque[dict[str, Any]] = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)

    def append(self, item: dict[str, Any]) -> None:
        with self._lock:
            self._items.appendleft(dict(item))
            while len(self._items) > self.limit:
                self._items.pop()

    def latest(self, count: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items)[:count]


@dataclass
class ServerRuntime:
    server_id: str
    server_name: str
    connect_code: str
    started_at: str = field(default_factory=utc_now)
    requests: RequestLog = field(default_factory=RequestLog)

    def server_info(self) -> dict[str, Any]:
        return {
            "server_id": self.server_id,
            "server_name": self.server_name,
            "version": "0.1.0",
            "status": "available",
            "host": "0.0.0.0",
            "port": 8000,
            "started_at": self.started_at,
            "last_heartbeat": utc_now(),
            "connect_code": self.connect_code,
            "mode": "cloud-hosted",
        }

