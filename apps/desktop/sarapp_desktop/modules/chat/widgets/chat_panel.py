"""Incident chat panel — a simple message log + send box for one channel.

Live updates arrive through `IncidentCache`, the same generic per-incident
change stream every other module uses: the server broadcasts every
`messages` write over `/api/incidents/{incident_id}/ws`, `IncidentCache`
applies it and emits `changed`, and this panel just filters that signal down
to the active channel. History/backfill and sending both go through
`modules/chat/services.py` (HTTP, via `api_client`) — never a direct Mongo
repository, per the UI -> API server -> MongoDB rule in agents.md.

Owned by `ChatWindow`, which swaps the active channel via `set_channel()`
rather than constructing a new panel per channel selection.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.state import AppState

from .. import services

logger = logging.getLogger(__name__)


class ChatPanel(QWidget):
    def __init__(self, incident_id=None, channel_id: str | None = None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._channel_id: str | None = None
        self._seen_ids: set[str] = set()
        self._sender_name: str | None = None
        self._subscribed = False

        self._message_list = QListWidget(self)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Message...")
        self._send_button = QPushButton("Send", self)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(self._send_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._message_list)
        layout.addLayout(input_row)

        self._send_button.clicked.connect(self._on_send)
        self._input.returnPressed.connect(self._on_send)

        self.set_channel(channel_id)

    # ------------------------------------------------------------------
    # Channel switching
    # ------------------------------------------------------------------

    def set_channel(self, channel_id: str | None) -> None:
        self._channel_id = channel_id
        self._seen_ids.clear()
        self._message_list.clear()

        has_channel = bool(self._incident_id and channel_id)
        self._input.setEnabled(has_channel)
        self._send_button.setEnabled(has_channel)

        if has_channel:
            self._load_history()
            self._subscribe_live()

    # ------------------------------------------------------------------
    # History + live updates
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        try:
            messages = services.list_messages(self._incident_id, self._channel_id)
        except Exception:
            logger.exception(
                "Failed to load chat history for incident %s channel %s",
                self._incident_id,
                self._channel_id,
            )
            return
        for message in messages:
            self._append_message(message)

    def _subscribe_live(self) -> None:
        if self._subscribed:
            return
        from utils.incident_cache import incident_cache

        incident_cache.changed.connect(self._on_cache_changed)
        self._subscribed = True

    def _on_cache_changed(self, collection: str, op: str, doc_id: str) -> None:
        if collection != "messages" or op != "created":
            return
        from utils.incident_cache import incident_cache

        doc = incident_cache.get("messages", doc_id)
        if doc is None or doc.get("channel_id") != self._channel_id:
            return
        self._append_message(doc)

    def _append_message(self, message: dict) -> None:
        message_id = message.get("id") or message.get("_id")
        if message_id in self._seen_ids:
            return
        self._seen_ids.add(message_id)

        sender = message.get("sender_name") or message.get("sender_id") or "Unknown"
        text = message.get("text", "")
        item = QListWidgetItem(f"{sender}: {text}")
        self._message_list.addItem(item)
        self._message_list.scrollToBottom()

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or not self._incident_id or not self._channel_id:
            return
        sender_id = AppState.get_active_user_id()
        sender_id_str = str(sender_id) if sender_id else "unknown"
        if self._sender_name is None and sender_id:
            self._sender_name = services.resolve_display_name(sender_id_str)
        try:
            services.send_message(
                self._incident_id,
                self._channel_id,
                sender_id=sender_id_str,
                sender_name=self._sender_name,
                text=text,
            )
        except Exception:
            logger.exception(
                "Failed to send chat message for incident %s channel %s",
                self._incident_id,
                self._channel_id,
            )
            return
        self._input.clear()
        # No optimistic append here — the server's WebSocket broadcast round-trips
        # back to us via IncidentCache within milliseconds, same as every other
        # live-updated panel, so this stays a single source of truth for message order.

    def closeEvent(self, event) -> None:
        if self._subscribed:
            try:
                from utils.incident_cache import incident_cache

                incident_cache.changed.disconnect(self._on_cache_changed)
            except Exception:
                pass
            self._subscribed = False
        super().closeEvent(event)
