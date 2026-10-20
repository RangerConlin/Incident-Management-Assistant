"""Master-detail incident chat window: channel/DM list on the left, the
active channel's messages on the right. Modeled on the list+content
QSplitter layout used by `modules/communications/panels/ics205_window.py`.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QGroupBox, QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from utils.state import AppState

from .. import services
from .chat_panel import ChatPanel
from .channel_list import ChatChannelList
from .new_channel_dialog import NewChannelDialog
from .new_dm_dialog import NewDmDialog
from .presence_roster import PresenceRoster

logger = logging.getLogger(__name__)

# How often to re-poll who's online. Presence is a staleness computation the
# server can only do at request time (see PRESENCE_STALE_AFTER_SECONDS in
# chat.py) — there's no live "went offline" event to listen for instead.
PRESENCE_POLL_INTERVAL_MS = 15_000


class ChatWindow(QWidget):
    def __init__(self, incident_id=None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._presence_name_cache: dict[str, str] = {}

        self._channel_list = ChatChannelList(incident_id=incident_id, parent=self)
        self._chat_panel = ChatPanel(incident_id=incident_id, channel_id=None, parent=self)
        self._presence_roster = PresenceRoster(self)

        left_box = QGroupBox("Channels", self)
        left_box.setMinimumWidth(200)
        left_box.setMaximumWidth(320)
        left_layout = QVBoxLayout(left_box)
        left_layout.addWidget(self._channel_list)

        right_box = QGroupBox("People", self)
        right_box.setMinimumWidth(160)
        right_box.setMaximumWidth(260)
        right_layout = QVBoxLayout(right_box)
        right_layout.addWidget(self._presence_roster)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(left_box)
        splitter.addWidget(self._chat_panel)
        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 560, 180])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._channel_list.channelSelected.connect(
            lambda channel_id, label: self._chat_panel.set_channel(channel_id, label)
        )
        self._channel_list.newChannelRequested.connect(self._on_new_channel)
        self._channel_list.newDmRequested.connect(self._on_new_dm)
        self._presence_roster.userActivated.connect(self._start_dm)

        self._presence_timer = QTimer(self)
        self._presence_timer.setInterval(PRESENCE_POLL_INTERVAL_MS)
        self._presence_timer.timeout.connect(self._refresh_presence)
        if incident_id:
            self._refresh_presence()
            self._presence_timer.start()

    def _on_new_channel(self) -> None:
        dialog = NewChannelDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        name = dialog.channel_name
        if not name:
            return
        user_id = AppState.get_active_user_id()
        try:
            services.create_channel(
                self._incident_id,
                name=name,
                created_by=str(user_id) if user_id else "unknown",
                participant_ids=dialog.participant_ids,
            )
        except Exception:
            logger.exception("Failed to create chat channel for incident %s", self._incident_id)

    def _on_new_dm(self) -> None:
        dialog = NewDmDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        other_id = dialog.selected_person_id
        if other_id:
            self._start_dm(other_id)

    def _start_dm(self, other_id: str) -> None:
        user_id = AppState.get_active_user_id()
        if not user_id:
            return
        try:
            services.find_or_create_dm(
                self._incident_id, user_a=str(user_id), user_b=other_id
            )
        except Exception:
            logger.exception("Failed to start DM for incident %s", self._incident_id)

    # ------------------------------------------------------------------
    # Presence roster
    # ------------------------------------------------------------------

    def _refresh_presence(self) -> None:
        current_user = AppState.get_active_user_id()
        current_user_str = str(current_user) if current_user else None
        try:
            items = services.list_presence(self._incident_id)
        except Exception:
            logger.exception("Failed to load presence roster for incident %s", self._incident_id)
            return

        status_by_user: dict[str, str] = {}
        roster: list[tuple[str, str, str]] = []
        for item in items:
            user_id = item.get("user_id")
            if not user_id or user_id == current_user_str:
                continue
            status = item.get("status", "online")
            status_by_user[user_id] = status
            if user_id not in self._presence_name_cache:
                self._presence_name_cache[user_id] = services.resolve_display_name(user_id)
            roster.append((user_id, self._presence_name_cache[user_id], status))

        roster.sort(key=lambda entry: entry[1].lower())
        self._presence_roster.set_online_users(roster)
        self._channel_list.set_presence_statuses(status_by_user)


__all__ = ["ChatWindow"]
