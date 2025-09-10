from __future__ import annotations

from typing import List, Dict

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QDialogButtonBox


class PreviewDialog(QDialog):
    def __init__(self, rows: List[Dict[str, object]], parent=None):
        super().__init__(parent)
        self.setWindowTitle('ICS-205 Preview')
        layout = QVBoxLayout(self)
        table = QTableWidget()
        headers = ['Function', 'Channel', 'Assignment', 'RX', 'TX', 'ToneNAC', 'Mode', 'Encryption', 'Notes']
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(headers):
                table.setItem(r, c, QTableWidgetItem(str(row.get(key, ''))))
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
