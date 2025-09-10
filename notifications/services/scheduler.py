from __future__ import annotations

import threading
from typing import Callable, List


class NotificationScheduler:
    """Simple scheduler for delayed notifications."""

    def __init__(self, notifier) -> None:
        self.notifier = notifier
        self._timers: List[threading.Timer] = []

    def schedule(self, seconds: float, func: Callable, *args, **kwargs) -> threading.Timer:
        timer = threading.Timer(seconds, func, args=args, kwargs=kwargs)
        timer.start()
        self._timers.append(timer)
        return timer

    def cancel_all(self) -> None:
        for t in self._timers:
            t.cancel()
        self._timers.clear()
