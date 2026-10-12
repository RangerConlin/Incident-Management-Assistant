"""Runtime state for the hosted SARApp cloud server."""

from __future__ import annotations

import logging
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
class ServerLog:
    limit: int = 1000
    _items: deque[str] = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)

    def append(self, line: str) -> None:
        with self._lock:
            self._items.appendleft(line)
            while len(self._items) > self.limit:
                self._items.pop()

    def latest(self, count: int = 250) -> list[str]:
        with self._lock:
            return list(self._items)[:count]


class RuntimeLogHandler(logging.Handler):
    def __init__(self, server_log: ServerLog) -> None:
        super().__init__()
        self.server_log = server_log
        self.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.server_log.append(self.format(record))
        except Exception:  # noqa: BLE001 - logging must never break the server
            pass


@dataclass
class ServerRuntime:
    server_id: str
    server_name: str
    connect_code: str
    started_at: str = field(default_factory=utc_now)
    requests: RequestLog = field(default_factory=RequestLog)
    logs: ServerLog = field(default_factory=ServerLog)

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

