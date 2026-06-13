"""Small log buffer used by the SARApp Server Console UI."""

from __future__ import annotations

from collections import deque
from datetime import datetime


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
