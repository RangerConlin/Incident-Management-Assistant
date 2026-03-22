"""Alert management helpers."""

from __future__ import annotations

import logging
from typing import Callable, List

from PySide6.QtCore import QObject, Signal

LOGGER = logging.getLogger(__name__)


class AlertCenter(QObject):
    """Central dispatch for weather alerts."""

    alertRaised = Signal(object)
    alertAcknowledged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._listeners: List[Callable[[object], None]] = []

    def register_listener(self, callback: Callable[[object], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def emit_alert(self, payload: object) -> None:
        LOGGER.info("Dispatching weather alert payload: %s", payload)
        self.alertRaised.emit(payload)
        for callback in self._listeners:
            callback(payload)

    def acknowledge(self, payload: object) -> None:
        LOGGER.info("Alert acknowledged: %s", payload)
        self.alertAcknowledged.emit(payload)


_alert_center: AlertCenter | None = None


def alert_center() -> AlertCenter:
    """Return the shared alert center instance."""

    global _alert_center
    if _alert_center is None:
        _alert_center = AlertCenter()
    return _alert_center


__all__ = ["alert_center", "AlertCenter"]
