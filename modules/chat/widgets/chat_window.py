"""Master-detail incident chat window: channel/DM list on the left, the
active channel's messages on the right. Modeled on the list+content
QSplitter layout used by `modules/communications/panels/ics205_window.py`.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGroupBox, QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from utils.state import AppState

from .. import services
from .chat_panel import ChatPanel
from .channel_list import ChatChannelList
from .new_channel_dialog import NewChannelDialog
from .new_dm_dialog import NewDmDialog

logger = logging.getLogger(__name__)


class ChatWindow(QWidget):
    def __init__(self, incident_id=None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id

        self._channel_list = ChatChannelList(incident_id=incident_id, parent=self)
        self._chat_panel = ChatPanel(incident_id=incident_id, channel_id=None, parent=self)

        left_box = QGroupBox("Channels", self)
        left_layout = QVBoxLayout(left_box)
        left_layout.addWidget(self._channel_list)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(left_box)
        splitter.addWidget(self._chat_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(self)
        layout.addWidget(splitter)

        self._channel_list.channelSelected.connect(self._chat_panel.set_channel)
        self._channel_list.newChannelRequested.connect(self._on_new_channel)
        self._channel_list.newDmRequested.connect(self._on_new_dm)

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
        if not other_id:
            return
        user_id = AppState.get_active_user_id()
        if not user_id:
            return
        try:
            services.find_or_create_dm(
                self._incident_id, user_a=str(user_id), user_b=other_id
            )
        except Exception:
            logger.exception("Failed to start DM for incident %s", self._incident_id)


__all__ = ["ChatWindow"]
