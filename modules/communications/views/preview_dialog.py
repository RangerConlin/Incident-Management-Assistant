from __future__ import annotations

"""Read‑only preview of ICS‑205 rows."""

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
)


class PreviewDialog(QDialog):
    def __init__(self, rows: List[Dict[str, object]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("ICS‑205 Preview")
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Function", "Channel", "Assignment", "RX", "TX", "Tone/NAC", "Mode", "Encryption",
        ])
        layout.addWidget(self.table, 1)

        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [
                r.get("Function", ""),
                r.get("Channel", ""),
                r.get("Assignment", ""),
                r.get("RX", ""),
                r.get("TX", ""),
                r.get("ToneNAC", ""),
                r.get("Mode", ""),
                r.get("Encryption", ""),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v or ""))
                if c in (3, 4):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, c, item)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Close, parent=self
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

