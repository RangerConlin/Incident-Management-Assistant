"""Incident chat panel — a message thread + send box for one channel.

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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from utils.state import AppState
from utils.styles import chat_bubble_colors, get_palette, subscribe_theme
from utils.timefmt import format_local_hhmm

from .. import services

logger = logging.getLogger(__name__)

_AVATAR_COLOR_KEYS = ("accent", "accent_alt", "info", "warning", "success")


def _avatar_colors(key: str) -> tuple[str, str]:
    """Background/foreground hex pair for a sender's avatar, from the active palette."""
    palette = get_palette()
    bubbles = chat_bubble_colors()
    color_key = _AVATAR_COLOR_KEYS[hash(key) % len(_AVATAR_COLOR_KEYS)]
    bg = palette.get(color_key, palette["accent"]).name()
    fg = bubbles.get("own", {}).get("fg", palette["fg_primary"]).name()
    return bg, fg


def _initial(name: str) -> str:
    name = (name or "").strip()
    return name[0].upper() if name else "?"


class _MessageBubble(QFrame):
    """One message row: an avatar + name/time header and a wrapped text bubble."""

    def __init__(self, message: dict, *, is_own: bool, show_sender: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("messageBubble")

        sender = message.get("sender_name") or message.get("sender_id") or "Unknown"
        text = message.get("text", "")
        time_label = format_local_hhmm(message.get("created_at"))

        bubble = QFrame(self)
        bubble.setObjectName("bubbleOwn" if is_own else "bubbleOther")
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 6, 10, 6)
        bubble_layout.setSpacing(2)

        if show_sender and not is_own:
            header = QLabel(sender, bubble)
            header.setObjectName("bubbleSender")
            bubble_layout.addWidget(header)

        text_label = QLabel(text, bubble)
        text_label.setWordWrap(True)
        text_label.setObjectName("bubbleText")
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble_layout.addWidget(text_label)

        time_widget = QLabel(time_label, bubble)
        time_widget.setObjectName("bubbleTime")
        time_widget.setAlignment(Qt.AlignRight if is_own else Qt.AlignLeft)
        bubble_layout.addWidget(time_widget)

        bubble.setMaximumWidth(420)
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(6)

        if not is_own:
            avatar = QLabel(_initial(sender), self)
            avatar.setObjectName("bubbleAvatar")
            avatar.setFixedSize(26, 26)
            avatar.setAlignment(Qt.AlignCenter)
            avatar_bg, avatar_fg = _avatar_colors(sender)
            avatar.setStyleSheet(
                f"background: {avatar_bg}; border-radius: 13px;"
                f" color: {avatar_fg}; font-weight: 600;"
            )
            if not show_sender:
                avatar.setVisible(False)
            row.addWidget(avatar, 0, Qt.AlignTop)
            row.addWidget(bubble, 0, Qt.AlignLeft)
            row.addStretch(1)
        else:
            row.addStretch(1)
            row.addWidget(bubble, 0, Qt.AlignRight)


class ChatPanel(QWidget):
    def __init__(self, incident_id=None, channel_id: str | None = None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        self._channel_id: str | None = None
        self._seen_ids: set[str] = set()
        self._messages: list[dict] = []
        self._sender_name: str | None = None
        self._subscribed = False

        self._header = QLabel(self)
        self._header.setObjectName("chatHeader")

        self._empty_state = QLabel(
            "Select a channel or direct message to start chatting.", self
        )
        self._empty_state.setObjectName("chatEmptyState")
        self._empty_state.setAlignment(Qt.AlignCenter)

        self._message_container = QWidget(self)
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(8, 8, 8, 8)
        self._message_layout.setSpacing(6)
        self._message_layout.addItem(
            QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._message_container)
        self._scroll_area.setFrameShape(QFrame.NoFrame)

        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Message...")
        self._send_button = QPushButton("Send", self)
        self._send_button.setObjectName("chatSendButton")
        self._send_button.setEnabled(False)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(self._send_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._empty_state)
        layout.addWidget(self._scroll_area, 1)
        layout.addLayout(input_row)

        self._send_button.clicked.connect(self._on_send)
        self._input.returnPressed.connect(self._on_send)
        self._input.textChanged.connect(self._on_input_changed)

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._on_theme_changed())

        self.set_channel(channel_id)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _apply_styles(self) -> None:
        pal = get_palette()
        bubbles = chat_bubble_colors()
        bg_panel = pal.get("bg_panel", pal["bg"]).name()
        bg_raised = pal.get("bg_raised", pal["bg_panel"]).name()
        ctrl_focus = pal.get("ctrl_focus", pal["accent"]).name()
        fg_muted = pal.get("fg_muted", pal["muted"]).name()
        divider = pal.get("divider", pal["ctrl_border"]).name()

        own = bubbles.get("own", {})
        other = bubbles.get("other", {})
        own_bg = own.get("bg", pal["ctrl_focus"]).name()
        own_fg = own.get("fg", pal["fg_primary"]).name()
        own_time_fg = own.get("time_fg", pal["fg_muted"]).name()
        other_bg = other.get("bg", pal["bg_raised"]).name()
        other_fg = other.get("fg", pal["fg_primary"]).name()
        other_time_fg = other.get("time_fg", pal["fg_muted"]).name()

        self.setStyleSheet(
            f"""
            QLabel#chatHeader {{
                font-size: 13px;
                font-weight: 600;
                color: {pal.get("fg_primary", pal["fg"]).name()};
                padding: 8px 12px;
                border-bottom: 1px solid {divider};
                background: {bg_panel};
            }}
            QLabel#chatEmptyState {{
                color: {fg_muted};
                font-size: 12px;
                padding: 24px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QFrame#bubbleOwn {{
                background: {own_bg};
                border-radius: 10px;
            }}
            QFrame#bubbleOwn QLabel#bubbleText {{
                color: {own_fg};
            }}
            QFrame#bubbleOwn QLabel#bubbleTime {{
                color: {own_time_fg};
                font-size: 10px;
            }}
            QFrame#bubbleOther {{
                background: {other_bg};
                border-radius: 10px;
            }}
            QFrame#bubbleOther QLabel#bubbleText {{
                color: {other_fg};
            }}
            QLabel#bubbleSender {{
                color: {ctrl_focus};
                font-weight: 600;
                font-size: 11px;
            }}
            QLabel#bubbleTime {{
                color: {other_time_fg};
                font-size: 10px;
            }}
            QPushButton#chatSendButton {{
                background: {ctrl_focus};
                color: {own_fg};
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-weight: 600;
            }}
            QPushButton#chatSendButton:disabled {{
                background: {bg_raised};
                color: {fg_muted};
            }}
            """
        )

    def _on_theme_changed(self) -> None:
        self._apply_styles()
        self._rebuild_messages()

    def _on_input_changed(self, text: str) -> None:
        has_channel = bool(self._incident_id and self._channel_id)
        self._send_button.setEnabled(has_channel and bool(text.strip()))

    # ------------------------------------------------------------------
    # Channel switching
    # ------------------------------------------------------------------

    def set_channel(self, channel_id: str | None, label: str | None = None) -> None:
        self._channel_id = channel_id
        self._seen_ids.clear()
        self._messages.clear()
        self._clear_messages()

        has_channel = bool(self._incident_id and channel_id)
        self._input.setEnabled(has_channel)
        self._on_input_changed(self._input.text())
        self._empty_state.setVisible(not has_channel)
        self._scroll_area.setVisible(has_channel)
        self._header.setText(label or "")
        self._header.setVisible(has_channel)

        if has_channel:
            self._load_history()
            self._subscribe_live()
            self._mark_read()

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
        self._mark_read()

    def _mark_read(self) -> None:
        if not self._incident_id or not self._channel_id:
            return
        user_id = AppState.get_active_user_id()
        if not user_id:
            return
        try:
            services.mark_channel_read(self._incident_id, self._channel_id, user_id=str(user_id))
        except Exception:
            logger.exception(
                "Failed to mark chat channel read for incident %s channel %s",
                self._incident_id,
                self._channel_id,
            )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _clear_messages(self) -> None:
        while self._message_layout.count() > 1:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_messages(self) -> None:
        self._clear_messages()
        previous: dict | None = None
        for message in self._messages:
            self._add_bubble(message, previous)
            previous = message

    def _append_message(self, message: dict) -> None:
        message_id = message.get("id") or message.get("_id")
        if message_id in self._seen_ids:
            return
        self._seen_ids.add(message_id)
        previous = self._messages[-1] if self._messages else None
        self._messages.append(message)
        self._add_bubble(message, previous)

    def _add_bubble(self, message: dict, previous: dict | None) -> None:
        sender_id = str(message.get("sender_id") or "")
        current_user = AppState.get_active_user_id()
        is_own = bool(current_user) and sender_id == str(current_user)
        show_sender = previous is None or previous.get("sender_id") != message.get("sender_id")

        bubble_row = _MessageBubble(message, is_own=is_own, show_sender=show_sender, parent=self._message_container)
        insert_at = self._message_layout.count() - 1
        self._message_layout.insertWidget(insert_at, bubble_row)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

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
