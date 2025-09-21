"""Stub table configuration dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class TableEditorDialog(QDialog):
    """Placeholder dialog that will evolve in future iterations."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Table Field Editor")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Table/repeater configuration is planned for a future release.\n"
                "You can still place the field on the canvas to reserve space."
            )
        )
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
