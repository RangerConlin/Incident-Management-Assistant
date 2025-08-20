from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQml import QQmlContext
from PySide6.QtCore import QUrl
import os

from models.mission_handler import MissionHandler
from models.missionlist import MissionListModel
from models.database import get_all_active_missions, get_mission_by_number
from utils.state import AppState


class QmlWindow(QDialog):
    def __init__(self, qml_path, title, context_data=None):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.qml_widget = QQuickWidget()

        # ✅ Inject any context data (like models) into QML
        if context_data:
            context: QQmlContext = self.qml_widget.rootContext()
            for key, value in context_data.items():
                context.setContextProperty(key, value)

        self.qml_widget.setSource(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

        layout.addWidget(self.qml_widget)


def new_mission_form():
    path = os.path.abspath("qml/newmissionform.qml")
    win = QmlWindow(path, "Create New Mission", {
        "missionHandler": MissionHandler()
    })
    win.exec()

def open_mission_list(main_window=None):
        missions = get_all_active_missions()
        model = MissionListModel(missions)

        handler = MissionHandler()

        def handle_selection(mission_number):
            AppState.set_active_mission(mission_number)
            mission = get_mission_by_number(mission_number)
            if mission:
                print(f"Selected mission: {mission['number']} - {mission['name']}")
                if main_window:
                    main_window.update_title_with_active_mission()

        handler.mission_selected.connect(handle_selection)

        path = os.path.abspath("qml/missionlist.qml")
        win = QmlWindow(path, "Select Active Mission", {
            "missionModel": model,
            "missionHandler": handler
        })
        root = win.qml_widget.rootObject()
        root.missionSelected.connect(handler.select_mission)
        win.exec()
