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


class SafetyTemplatesEditor(BaseEditDialog):
    """Placeholder editor for safety templates."""

    def __init__(self, db_conn=None, parent=None):
        super().__init__("Safety Templates", "Manage ICS-215A templates", parent)
        self.set_columns([
            ("name", "Name"),
            ("hazard", "Hazard"),
        ])
        self.set_adapter(_StubAdapter())
        self.form_layout.addRow(QLabel("Not yet implemented"))
