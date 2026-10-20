"""Left-pane channel/DM list for the incident chat window.

Loads the channel list (group channels + the current user's DMs) once on
construction, then stays live via `IncidentCache`'s `changed` signal on the
`chat_channels` collection — the same generic per-incident broadcast every
other module subscribes to.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from utils.state import AppState
from utils.styles import get_palette, subscribe_theme

from .. import services
from .presence_roster import status_dot_icon

logger = logging.getLogger(__name__)

_CHANNEL_ROLE = Qt.UserRole + 1
_HEADER_ROLE = Qt.UserRole + 2


class ChatChannelList(QWidget):
    channelSelected = Signal(str, str)
    newChannelRequested = Signal()
    newDmRequested = Signal()

    def __init__(self, incident_id=None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._channels: dict[str, dict] = {}
        self._dm_name_cache: dict[str, str] = {}
        self._presence_statuses: dict[str, str] = {}

        self._list = QListWidget(self)
        self._list.setSpacing(1)
        self._new_channel_button = QPushButton("+ Channel", self)
        self._new_dm_button = QPushButton("+ DM", self)
        self._new_channel_button.setObjectName("chatNewButton")
        self._new_dm_button.setObjectName("chatNewButton")

        button_row = QHBoxLayout()
        button_row.addWidget(self._new_channel_button)
        button_row.addWidget(self._new_dm_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self._list)

        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._new_channel_button.clicked.connect(self.newChannelRequested.emit)
        self._new_dm_button.clicked.connect(self.newDmRequested.emit)

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

        if self._incident_id:
            self._load_channels()
            self._subscribe_live()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _apply_styles(self) -> None:
        pal = get_palette()
        ctrl_focus = pal.get("ctrl_focus", pal["accent"]).name()

        self.setStyleSheet(
            f"""
            QPushButton#chatNewButton {{
                border: 1px solid {ctrl_focus};
                border-radius: 4px;
                padding: 3px 10px;
                font-weight: 600;
            }}
            """
        )

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

    def _dm_other_id(self, channel: dict) -> str | None:
        user_id = self._current_user_id()
        participants = channel.get("participant_ids") or []
        return next((p for p in participants if p != user_id), None)

    def _display_name(self, channel: dict) -> str:
        if channel.get("type") == "group":
            return channel.get("name") or "(unnamed channel)"

        other = self._dm_other_id(channel)
        if other is None:
            return "(direct message)"
        if other not in self._dm_name_cache:
            self._dm_name_cache[other] = services.resolve_display_name(other)
        return self._dm_name_cache[other]

    def set_presence_statuses(self, status_by_user: dict[str, str]) -> None:
        """Update the online/away/unavailable dot shown next to each DM entry."""
        self._presence_statuses = status_by_user
        self._rebuild()

    def _upsert_channel(self, channel: dict) -> None:
        channel_id = channel.get("id") or channel.get("_id")
        if not channel_id:
            return
        self._channels[channel_id] = channel
        self._rebuild()

    def _remove_channel(self, channel_id: str) -> None:
        self._channels.pop(channel_id, None)
        self._rebuild()

    def _rebuild(self) -> None:
        selected_id = self._selected_channel_id()

        groups = sorted(
            (c for c in self._channels.values() if c.get("type") == "group"),
            key=lambda c: (c.get("name") or "").lower(),
        )
        dms = sorted(
            (c for c in self._channels.values() if c.get("type") == "dm"),
            key=lambda c: self._display_name(c).lower(),
        )

        self._list.blockSignals(True)
        self._list.clear()

        if groups:
            self._add_section_header("CHANNELS")
            for channel in groups:
                self._add_channel_item(channel, prefix="#")

        if dms:
            self._add_section_header("DIRECT MESSAGES")
            for channel in dms:
                self._add_channel_item(channel, prefix="@")

        self._list.blockSignals(False)

        if selected_id:
            item = self._find_item(selected_id)
            if item is not None:
                self._list.setCurrentItem(item)

    def _add_section_header(self, text: str) -> None:
        pal = get_palette()
        item = QListWidgetItem(text)
        item.setData(_HEADER_ROLE, True)
        item.setFlags(Qt.NoItemFlags)
        font = item.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize() - 1, 7))
        item.setFont(font)
        item.setForeground(pal.get("fg_muted", pal["muted"]))
        self._list.addItem(item)

    def _add_channel_item(self, channel: dict, *, prefix: str) -> None:
        channel_id = channel.get("id") or channel.get("_id")
        label = f"{prefix} {self._display_name(channel)}"
        item = QListWidgetItem(label)
        item.setData(_CHANNEL_ROLE, channel_id)
        if channel.get("type") == "dm":
            other = self._dm_other_id(channel)
            status = self._presence_statuses.get(other) if other else None
            if status:
                item.setIcon(status_dot_icon(status))
        self._list.addItem(item)

    def _find_item(self, channel_id: str) -> QListWidgetItem | None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(_CHANNEL_ROLE) == channel_id:
                return item
        return None

    def _selected_channel_id(self) -> str | None:
        current = self._list.currentItem()
        return current.data(_CHANNEL_ROLE) if current is not None else None

    def _on_selection_changed(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        if current is None or current.data(_HEADER_ROLE):
            return
        channel_id = current.data(_CHANNEL_ROLE)
        if channel_id:
            channel = self._channels.get(channel_id, {})
            self.channelSelected.emit(channel_id, self._display_name(channel))
