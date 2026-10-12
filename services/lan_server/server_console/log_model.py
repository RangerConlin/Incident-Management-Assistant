"""Small log buffer used by the SARApp Server Console UI."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Callable


class QtLogHandler(logging.Handler):
    """Forwards stdlib ``logging`` records to a callback for display in the console.

    The server engine (uvicorn, sarapp_db, the cloud tunnel client) logs
    through the standard ``logging`` module on its own worker threads, but
    the console UI had no handler attached, so those records went nowhere
    visible. ``emit`` is called from whatever thread produced the log record;
    the callback must itself be thread-safe (the console wires this to a Qt
    signal, which safely marshals the call onto the UI thread).
    """

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback
        self.setFormatter(
            logging.Formatter("[%(asctime)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:  # noqa: BLE001 - never let logging break the app
            pass


class ConsoleLogBuffer:
    """Stores timestamped runtime messages without depending on Qt widgets."""

    def __init__(self, *, max_entries: int = 500) -> None:
        self._entries: deque[str] = deque(maxlen=max_entries)

    def add(self, message: str) -> str:
        """Append a message with a local timestamp and return the formatted line."""

        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self._entries.append(line)
        return line

    def lines(self) -> list[str]:
        """Return a copy of buffered log lines for display or tests."""

        return list(self._entries)
