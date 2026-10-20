"""Sends this client's own online/away/unavailable heartbeat to the active
incident's presence roster (`modules/chat/services.py` ->
`POST /incidents/{incident_id}/presence/heartbeat`).

Started/stopped by `incident_cache_loader.activate_incident()`/`shutdown()`
— the same place that drives the IncidentCache/WebSocket lifecycle — so
presence always tracks whichever incident is currently open. A heartbeat
that stops arriving is what tells the server the client went offline (see
`PRESENCE_STALE_AFTER_SECONDS` in `chat.py`); there is no explicit
"I'm leaving" call.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_MS = 20_000
PRESENCE_STATUSES = ("online", "away", "unavailable")


class PresenceController(QObject):
    """App-wide singleton — see `presence` below."""

    statusChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._incident_id: Optional[str] = None
        self._status = "online"
        self._timer = QTimer(self)
        self._timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._timer.timeout.connect(self._send_heartbeat)

    @property
    def status(self) -> str:
        return self._status

    def set_status(self, status: str) -> None:
        """User-initiated status change (e.g. from the roster panel's picker)."""
        if status not in PRESENCE_STATUSES or status == self._status:
            return
        self._status = status
        self.statusChanged.emit(status)
        self._send_heartbeat()

    def start(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._status = "online"
        self._send_heartbeat()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._incident_id = None

    def _send_heartbeat(self) -> None:
        if not self._incident_id:
            return
        from utils.state import AppState

        user_id = AppState.get_active_user_id()
        if not user_id:
            return
        try:
            from modules.chat import services

            services.send_presence_heartbeat(
                self._incident_id, user_id=str(user_id), status=self._status
            )
        except Exception:
            logger.exception("Presence heartbeat failed for incident %s", self._incident_id)


presence = PresenceController()

__all__ = ["presence", "PresenceController", "PRESENCE_STATUSES"]
