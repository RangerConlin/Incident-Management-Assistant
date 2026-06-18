from __future__ import annotations

import dataclasses
import time
from typing import List, Dict, Any

from PySide6.QtCore import QObject, Signal

from notifications.models.notification import Notification
from .sound_player import SoundPlayer
from .rules_engine import RulesEngine
from .scheduler import NotificationScheduler

_DEFAULT_TOAST_MODE = "auto"
_DEFAULT_DURATION_MS = 4500
_THROTTLE_WINDOW_S = 2
_RECENT_CAP = 500


class Notifier(QObject):
    """Central service for emitting and tracking notifications."""

    notificationCreated = Signal(dict)
    showToast = Signal(dict)
    showBanner = Signal(dict)
    badgeCountChanged = Signal(int)

    _instance: "Notifier | None" = None

    def __init__(self) -> None:
        super().__init__()
        self._recent: List[Dict[str, Any]] = []
        self._badge = 0
        self._throttle: Dict[tuple[str, str], float] = {}
        self.rules = RulesEngine(self)
        self.scheduler = NotificationScheduler(self)

    @classmethod
    def instance(cls) -> "Notifier":
        if cls._instance is None:
            cls._instance = Notifier()
        return cls._instance

    def notify(self, note: Notification) -> None:
        payload = dataclasses.asdict(note)
        if payload.get("toast_mode") is None:
            payload["toast_mode"] = _DEFAULT_TOAST_MODE
        if payload.get("toast_duration_ms") is None:
            payload["toast_duration_ms"] = _DEFAULT_DURATION_MS
        payload["ts"] = int(time.time())

        key = (payload["title"], payload["message"])
        now = time.time()
        if key in self._throttle and now - self._throttle[key] < _THROTTLE_WINDOW_S:
            return
        self._throttle[key] = now

        self._recent.append(payload)
        if len(self._recent) > _RECENT_CAP:
            self._recent = self._recent[-_RECENT_CAP:]

        self._badge += 1
        self.notificationCreated.emit(payload)
        self.showToast.emit(payload)
        self.badgeCountChanged.emit(self._badge)

        try:
            SoundPlayer.instance().play()
        except Exception:
            pass

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._recent[-limit:]))

    def clear_badge(self) -> None:
        self._badge = 0
        self.badgeCountChanged.emit(0)


get_notifier = Notifier.instance
