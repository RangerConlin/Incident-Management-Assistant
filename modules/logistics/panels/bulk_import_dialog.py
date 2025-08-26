# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).
"""Bulk import wizard dialog."""

from pathlib import Path

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QDialog


class BulkImportDialog(QDialog):
    def __init__(self, incident_id: str):
        super().__init__()
        self.incident_id = incident_id
        self.setWindowTitle("Bulk Import")
        engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "qml" / "BulkImportWizard.qml"
        engine.load(str(qml_path))
