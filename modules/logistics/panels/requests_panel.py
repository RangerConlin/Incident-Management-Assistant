from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.panels.request_detail_dialog import RequestDetailDialog


class RequestsPanel(QWidget):
    """Simple table panel for listing resource requests."""

    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Resource Requests")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Legacy QML resource-request board has been removed."))
        self.table = QTableWidget()
        layout.addWidget(self.table)

        bar = QWidget(self)
        hb = QHBoxLayout(bar)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(6)
        self.new_btn = QPushButton("New Request")
        self.new_btn.setFixedSize(120, 28)
        self.new_btn.clicked.connect(self.open_detail)
        hb.addWidget(self.new_btn)
        hb.addStretch(1)
        layout.addWidget(bar)

    def open_detail(self) -> None:
        dialog = RequestDetailDialog(self.incident_id, request_id=-1)
        dialog.show()
