"""Small timing helpers for lightweight UI performance instrumentation."""

from __future__ import annotations

import time
from typing import Protocol


class _LoggerLike(Protocol):
    def debug(self, msg: str, *args) -> None: ...


class PerfTimer:
    """Measure elapsed wall time and log readable checkpoints."""

    def __init__(self, logger: _LoggerLike, label: str) -> None:
        self._logger = logger
        self._label = label
        self._start = time.perf_counter()
        self._last = self._start

    def checkpoint(self, step: str) -> float:
        now = time.perf_counter()
        delta_ms = (now - self._last) * 1000.0
        total_ms = (now - self._start) * 1000.0
        self._last = now
        self._logger.debug("%s: %s in %.1f ms (total %.1f ms)", self._label, step, delta_ms, total_ms)
        return delta_ms

    def finish(self, outcome: str = "complete") -> float:
        total_ms = (time.perf_counter() - self._start) * 1000.0
        self._logger.debug("%s: %s in %.1f ms", self._label, outcome, total_ms)
        return total_ms
