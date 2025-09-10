from __future__ import annotations

"""PySide6 widget embedding the ICS-205 QML view."""

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQml import QQmlContext

from utils.state import AppState

from ..controller import ICS205Controller
from ..models import db


class ICS205Panel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        incident = AppState.get_active_incident()
        if incident is None or not db.verify_master_access():
            layout.addWidget(
                QLabel("Select or create an incident to edit ICS-205."), alignment=Qt.AlignCenter
            )
            self.setEnabled(False)
            return

        # Ensure schema exists
        db.ensure_incident_schema(incident)

        controller = ICS205Controller(self)

        qml_path = Path(__file__).resolve().parent.parent / "qml" / "ICS205View.qml"
        view = QQuickWidget(self)
        view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        context: QQmlContext = view.rootContext()
        context.setContextProperty("ics205", controller)
        view.setSource(QUrl.fromLocalFile(str(qml_path)))
        layout.addWidget(view)

        self._controller = controller
