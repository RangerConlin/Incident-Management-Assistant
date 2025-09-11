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


class AircraftEditor(BaseEditDialog):
    """Placeholder QtWidgets editor for aircraft records."""

    def __init__(self, db_conn=None, parent=None):
        super().__init__("Aircraft", "Manage aircraft catalog", parent)
        self.set_columns([
            ("tail_number", "Tail Number"),
            ("callsign", "Callsign"),
            ("type", "Type"),
        ])
        self.set_adapter(_StubAdapter())
        self.form_layout.addRow(QLabel("Not yet implemented"))
