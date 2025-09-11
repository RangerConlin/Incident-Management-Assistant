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


class PersonnelEditor(BaseEditDialog):
    """Placeholder QtWidgets editor for personnel records."""

    def __init__(self, db_conn=None, parent=None):
        super().__init__("Personnel", "Manage personnel records", parent)
        self.set_columns([("last_name", "Last Name"), ("first_name", "First Name")])
        self.set_adapter(_StubAdapter())
        self.form_layout.addRow(QLabel("Not yet implemented"))
