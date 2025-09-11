from __future__ import annotations

from PySide6.QtWidgets import QLabel

from .base_dialog import BaseEditDialog


class _StubAdapter:
    def list(self):
        return []
    def create(self, payload):
        return 0
    def update(self, id, payload):
        pass
    def delete(self, id):
        pass


class CommsChannelEditor(BaseEditDialog):
    """Placeholder editor for communications channels."""

    def __init__(self, db_conn=None, parent=None):
        super().__init__("Communications Channels", "Manage master comms channel list", parent)
        self.set_columns([("channel_name", "Channel"), ("band", "Band")])
        self.set_adapter(_StubAdapter())
        self.form_layout.addRow(QLabel("Not yet implemented"))
