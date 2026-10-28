from __future__ import annotations

import dataclasses
import logging
import time
import uuid
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal

from notifications.models.notification import (
    Notification,
    CATEGORY_DEFAULTS,
    CATEGORY_TOAST_THRESHOLDS,
    SEVERITY_OVERRIDES,
    SEVERITY_RANK,
)
from .sound_player import SoundPlayer
from .rules_engine import RulesEngine
from .scheduler import NotificationScheduler

_DEFAULT_TOAST_MODE = "auto"
_DEFAULT_DURATION_MS = 4500
_THROTTLE_WINDOW_S = 2
_RECENT_CAP = 500
logger = logging.getLogger(__name__)


class Notifier(QObject):
    """Central service for emitting and tracking notifications."""

    notificationCreated = Signal(dict)
    notificationUpdated = Signal(dict)  # emitted when read state changes
    showToast = Signal(dict)
    showBanner = Signal(dict)
    badgeCountChanged = Signal(int)

    _instance: "Notifier | None" = None

    def __init__(self) -> None:
        super().__init__()
        self._recent: List[Dict[str, Any]] = []
        self._throttle: Dict[tuple[str, str], float] = {}
        # Per-category toast threshold, settable at runtime from settings
        self._thresholds: Dict[str, str] = dict(CATEGORY_TOAST_THRESHOLDS)
        self.rules = RulesEngine(self)
        self.scheduler = NotificationScheduler(self)
        try:
            from utils.app_signals import app_signals
            app_signals.incidentChanged.connect(lambda _: self.clear())
        except Exception:
            logger.exception("Notifier failed to wire incidentChanged clear")

    @classmethod
    def instance(cls) -> "Notifier":
        if cls._instance is None:
            cls._instance = Notifier()
        return cls._instance

    def clear(self) -> None:
        """Drop all tracked notifications and throttle state.

        Called on active-incident switch: this history is not scoped by
        incident, so without clearing it, the previous incident's
        notifications (and unread badge count) would bleed into the newly
        active one.
        """
        self._recent = []
        self._throttle = {}
        self._emit_badge()

    def set_threshold(self, category: str, severity: str) -> None:
        """Set the minimum severity that will produce a toast for a category."""
        self._thresholds[category] = severity

    def notify(self, note: Notification) -> None:
        payload = dataclasses.asdict(note)
        payload["id"] = uuid.uuid4().hex
        payload["ts"] = int(time.time())
        payload["read"] = False

        category = payload.get("category", "operations")
        severity = payload.get("severity", "routine")

        # Resolve toast behavior: category defaults → severity overrides
        cat_defaults = CATEGORY_DEFAULTS.get(category, {})
        sev_overrides = SEVERITY_OVERRIDES.get(severity, {})
        merged = {**cat_defaults, **sev_overrides}

        # Apply per-category threshold — suppress toast if severity is below it
        threshold = self._thresholds.get(category, "routine")
        below_threshold = SEVERITY_RANK.get(severity, 0) < SEVERITY_RANK.get(threshold, 0)
        show_toast = not below_threshold and merged.get("show_toast", True)
        play_sound = show_toast and merged.get("sound", cat_defaults.get("sound", True))
        logger.info(
            "Notifier received title=%r source=%s category=%s severity=%s threshold=%s show_toast=%s play_sound=%s",
            payload.get("title"), payload.get("source"), category, severity,
            threshold, show_toast, play_sound,
        )

        if payload.get("toast_mode") is None:
            payload["toast_mode"] = merged.get("toast_mode", _DEFAULT_TOAST_MODE)
        if payload.get("toast_duration_ms") is None:
            payload["toast_duration_ms"] = merged.get("toast_duration_ms", _DEFAULT_DURATION_MS)

        key = (payload["title"], payload["message"])
        now = time.time()
        if key in self._throttle and now - self._throttle[key] < _THROTTLE_WINDOW_S:
            logger.warning(
                "Notifier throttled duplicate title=%r age_seconds=%.3f",
                payload.get("title"), now - self._throttle[key],
            )
            return
        self._throttle[key] = now

        self._recent.append(payload)
        if len(self._recent) > _RECENT_CAP:
            self._recent = self._recent[-_RECENT_CAP:]

        logger.debug("Notifier emitting notificationCreated id=%s", payload["id"])
        self.notificationCreated.emit(payload)
        if show_toast:
            logger.debug("Notifier emitting showToast id=%s", payload["id"])
            self.showToast.emit(payload)
            logger.debug("Notifier showToast emit returned id=%s", payload["id"])
        else:
            logger.info(
                "Notifier stored notification without toast id=%s below_threshold=%s",
                payload["id"], below_threshold,
            )
        self._emit_badge()

        if play_sound:
            try:
                SoundPlayer.instance().play(category, severity)
            except Exception:
                logger.exception(
                    "Notifier sound playback failed id=%s category=%s severity=%s",
                    payload["id"], category, severity,
                )

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._recent[-limit:]))

    def unread_count(self) -> int:
        return sum(1 for n in self._recent if not n.get("read", False))

    def mark_read(self, notification_id: str) -> None:
        for n in self._recent:
            if n.get("id") == notification_id and not n.get("read", False):
                n["read"] = True
                self.notificationUpdated.emit(n)
                self._emit_badge()
                return

    def mark_all_read(self) -> None:
        changed = False
        for n in self._recent:
            if not n.get("read", False):
                n["read"] = True
                changed = True
        if changed:
            self._emit_badge()

    def _emit_badge(self) -> None:
        self.badgeCountChanged.emit(self.unread_count())

get_notifier = Notifier.instance
