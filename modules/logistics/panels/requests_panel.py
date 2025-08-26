# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""Resource request status board panel."""

from pathlib import Path

from PySide6.QtWidgets import QPushButton, QTableWidget, QVBoxLayout, QWidget
from PySide6.QtQml import QQmlApplicationEngine


class RequestsPanel(QWidget):
    """Simple table panel for listing resource requests."""

    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Resource Requests")

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        layout.addWidget(self.table)

        self.new_btn = QPushButton("New Request")
        layout.addWidget(self.new_btn)
        self.new_btn.clicked.connect(self.open_detail)

    def open_detail(self) -> None:
        """Open the detail dialog using QML."""
        engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "RequestDetail.qml"
        engine.load(str(qml_path))
