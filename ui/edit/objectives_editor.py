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


class ObjectivesEditor(BaseEditDialog):
    """Placeholder QtWidgets editor for objective templates."""

    def __init__(self, db_conn=None, parent=None):
        super().__init__("Objectives", "Manage objective templates", parent)
        self.set_columns([
            ("description", "Description"),
            ("priority", "Priority"),
        ])
        self.set_adapter(_StubAdapter())
        self.form_layout.addRow(QLabel("Not yet implemented"))
