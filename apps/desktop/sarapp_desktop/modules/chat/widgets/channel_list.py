"""Left-pane channel/DM list for the incident chat window.

Loads the channel list (group channels + the current user's DMs) once on
construction, then stays live via `IncidentCache`'s `changed` signal on the
`chat_channels` collection — the same generic per-incident broadcast every
other module subscribes to.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from utils.state import AppState

from .. import services

logger = logging.getLogger(__name__)


class ChatChannelList(QWidget):
    channelSelected = Signal(str)
    newChannelRequested = Signal()
    newDmRequested = Signal()

    def __init__(self, incident_id=None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._channels: dict[str, dict] = {}
        self._dm_name_cache: dict[str, str] = {}

        self._list = QListWidget(self)
        self._new_channel_button = QPushButton("New Channel", self)
        self._new_dm_button = QPushButton("New DM", self)

        button_row = QHBoxLayout()
        button_row.addWidget(self._new_channel_button)
        button_row.addWidget(self._new_dm_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self._list)

        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._new_channel_button.clicked.connect(self.newChannelRequested.emit)
        self._new_dm_button.clicked.connect(self.newDmRequested.emit)

        if self._incident_id:
            self._load_channels()
            self._subscribe_live()

    # ------------------------------------------------------------------
    # Loading + live updates
    # ------------------------------------------------------------------

    def _current_user_id(self) -> str | None:
        user_id = AppState.get_active_user_id()
        return str(user_id) if user_id else None

    def _load_channels(self) -> None:
        user_id = self._current_user_id()
        if not user_id:
            return
        try:
            channels = services.list_channels(self._incident_id, user_id=user_id)
        except Exception:
            logger.exception("Failed to load chat channels for incident %s", self._incident_id)
            return
        for channel in channels:
            self._upsert_channel(channel)

    def _subscribe_live(self) -> None:
        from utils.incident_cache import incident_cache

        incident_cache.changed.connect(self._on_cache_changed)

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection != "chat_channels":
            return
        from utils.incident_cache import incident_cache

        if op == "deleted":
            self._remove_channel(doc_id)
            return
        doc = incident_cache.get("chat_channels", doc_id)
        if doc is None:
            return
        if doc.get("deleted"):
            self._remove_channel(doc_id)
            return
        user_id = self._current_user_id()
        if doc.get("type") == "dm" and user_id not in (doc.get("participant_ids") or []):
            return
        self._upsert_channel(doc)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _display_name(self, channel: dict) -> str:
        if channel.get("type") == "group":
            return channel.get("name") or "(unnamed channel)"

        user_id = self._current_user_id()
        participants = channel.get("participant_ids") or []
        other = next((p for p in participants if p != user_id), None)
        if other is None:
            return "(direct message)"
        if other not in self._dm_name_cache:
            self._dm_name_cache[other] = services.resolve_display_name(other)
        return self._dm_name_cache[other]

    def _upsert_channel(self, channel: dict) -> None:
        channel_id = channel.get("id") or channel.get("_id")
        if not channel_id:
            return
        self._channels[channel_id] = channel

        label = self._display_name(channel)
        existing_item = self._find_item(channel_id)
        if existing_item is not None:
            existing_item.setText(label)
            return

        item = QListWidgetItem(label)
        item.setData(1000, channel_id)
        self._list.addItem(item)

    def _remove_channel(self, channel_id: str) -> None:
        self._channels.pop(channel_id, None)
        item = self._find_item(channel_id)
        if item is not None:
            self._list.takeItem(self._list.row(item))

    def _find_item(self, channel_id: str) -> QListWidgetItem | None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(1000) == channel_id:
                return item
        return None

    def _on_selection_changed(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        if current is None:
            return
        channel_id = current.data(1000)
        if channel_id:
            self.channelSelected.emit(channel_id)
