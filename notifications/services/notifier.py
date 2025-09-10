from __future__ import annotations

import dataclasses
import time
from typing import List, Dict, Any

from PySide6.QtCore import QObject, Signal

from notifications.models.notification import Notification
from notifications.models.schema_sql import ensure_master_schema, ensure_mission_schema
from utils.context import master_db, require_incident_db
from .sound_player import SoundPlayer
from .rules_engine import RulesEngine
from .scheduler import NotificationScheduler


class Notifier(QObject):
    """Central service for emitting notifications toasts/banners/feed."""

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
        self._load_preferences()
        self.rules = RulesEngine(self)
        self.scheduler = NotificationScheduler(self)

        try:
            from utils.app_signals import app_signals

            app_signals.incidentChanged.connect(self._on_incident_changed)
        except Exception:
            pass

    # ---- Singleton helpers -------------------------------------------------
    @classmethod
    def instance(cls) -> "Notifier":
        if cls._instance is None:
            cls._instance = Notifier()
        return cls._instance

    # ---- Preferences -------------------------------------------------------
    def _load_preferences(self) -> None:
        try:
            conn = master_db()
            ensure_master_schema(conn)
            row = conn.execute(
                "SELECT toast_mode, toast_duration_ms FROM notification_preferences LIMIT 1"
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO notification_preferences (toast_mode, toast_duration_ms) VALUES ('auto', 4500)"
                )
                conn.commit()
                row = conn.execute(
                    "SELECT toast_mode, toast_duration_ms FROM notification_preferences LIMIT 1"
                ).fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        self._default_mode = row[0] if row and row[0] else "auto"
        self._default_duration = row[1] if row and row[1] else 4500
        self._play_sound = True

    # ---- Incident change ---------------------------------------------------
    def _on_incident_changed(self, *_: object) -> None:
        # rebind or preload mission schema
        try:
            conn = require_incident_db()
            ensure_mission_schema(conn)
            conn.close()
        except Exception:
            pass

    # ---- Public API --------------------------------------------------------
    def notify(self, note: Notification) -> None:
        payload = dataclasses.asdict(note)
        if payload.get("toast_mode") is None:
            payload["toast_mode"] = self._default_mode
        if payload.get("toast_duration_ms") is None:
            payload["toast_duration_ms"] = self._default_duration

        key = (payload["title"], payload["message"])
        now = time.time()
        if key in self._throttle and now - self._throttle[key] < 2:
            return
        self._throttle[key] = now

        self._recent.append(payload)
        self._badge += 1
        self.notificationCreated.emit(payload)
        self.showToast.emit(payload)
        self.badgeCountChanged.emit(self._badge)

        if self._play_sound:
            try:
                SoundPlayer.instance().play()
            except Exception:
                pass

        try:
            self._persist(payload)
        except Exception:
            pass

    def _persist(self, payload: Dict[str, Any]) -> None:
        conn = require_incident_db()
        ensure_mission_schema(conn)
        conn.execute(
            "INSERT INTO notifications (ts, title, message, severity, source, entity_type, entity_id, toast_mode, toast_duration_ms)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(time.time()),
                payload.get("title"),
                payload.get("message"),
                payload.get("severity"),
                payload.get("source"),
                payload.get("entity_type"),
                payload.get("entity_id"),
                payload.get("toast_mode"),
                payload.get("toast_duration_ms"),
            ),
        )
        conn.commit()
        conn.close()

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            conn = require_incident_db()
            ensure_mission_schema(conn)
            cur = conn.execute(
                "SELECT ts, title, message, severity, source, entity_type, entity_id, toast_mode, toast_duration_ms"
                " FROM notifications ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return self._recent[-limit:]

    def clear_badge(self) -> None:
        self._badge = 0
        self.badgeCountChanged.emit(0)


# convenient alias
get_notifier = Notifier.instance
