from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQml import QQmlContext
from PySide6.QtCore import QUrl
import os

from models.incident_handler import IncidentHandler
from models.incidentlist import IncidentListModel
from models.database import get_incident_by_number
from utils.state import AppState


class QmlWindow(QDialog):
    def __init__(self, qml_path, title, context_data=None):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.qml_widget = QQuickWidget()

        #Inject any context data (like models) into QML
        if context_data:
            context: QQmlContext = self.qml_widget.rootContext()
            for key, value in context_data.items():
                context.setContextProperty(key, value)

        self.qml_widget.setSource(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

        layout.addWidget(self.qml_widget)


def new_incident_form():
    path = os.path.abspath("qml/newincidentform.qml")
    win = QmlWindow(path, "Create New Incident", {
        "incidentHandler": IncidentHandler()
    })
    win.exec()

def open_incident_list(main_window=None):
        model = IncidentListModel()
        model.refresh()

        handler = IncidentHandler()

        def handle_selection(incident_number):
            AppState.set_active_incident(incident_number)
            incident = get_incident_by_number(incident_number)
            if incident:
                print(f"Selected incident: {incident['number']} - {incident['name']}")
                if main_window:
                    main_window.update_title_with_active_incident()

        handler.incident_selected.connect(handle_selection)

        path = os.path.abspath("qml/incidentlist.qml")
        win = QmlWindow(path, "Select Active Incident", {
            "incidentModel": model,
            "incidentHandler": handler
        })
        root = win.qml_widget.rootObject()
        root.incidentSelected.connect(handler.select_incident)
        win.exec()
