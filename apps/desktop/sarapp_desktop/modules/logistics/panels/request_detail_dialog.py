from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class RequestDetailDialog(QDialog):
    def __init__(self, incident_id: str, request_id: int):
        super().__init__()
        self.incident_id = incident_id
        self.request_id = request_id
        self.setWindowTitle("Request Detail")
        layout = QVBoxLayout(self)
        title = QLabel("Request Detail")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Legacy QML request-detail dialog has been removed. "
                f"Request id: {request_id}"
            )
        )
