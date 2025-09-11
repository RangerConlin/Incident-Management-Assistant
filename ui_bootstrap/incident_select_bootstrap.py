"""Widget-based incident selector replacing the former QML implementation."""

from __future__ import annotations

import sys
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QListWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)

from utils.state import AppState
from models.database import get_all_incidents
from modules.incidents.new_incident_dialog import NewIncidentDialog


def show_incident_selector(on_select: Optional[Callable[[int], None]] = None) -> None:
    """Display a simple dialog to choose an incident."""
    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication(sys.argv)
        owns_app = True

    dlg = QDialog()
    dlg.setWindowTitle("Select Incident")
    layout = QVBoxLayout(dlg)
    list_widget = QListWidget()
    layout.addWidget(list_widget)

    def load_incidents():
        list_widget.clear()
        incidents = get_all_incidents() or []
        for inc in incidents:
            number = inc[1] if not isinstance(inc, dict) else inc.get("number")
            name = inc[2] if not isinstance(inc, dict) else inc.get("name")
            list_widget.addItem(f"{number} - {name}")
        return incidents

    incidents = load_incidents()

    btn_layout = QHBoxLayout()
    new_btn = QPushButton("New")
    open_btn = QPushButton("Open")
    cancel_btn = QPushButton("Cancel")
    btn_layout.addWidget(new_btn)
    btn_layout.addStretch()
    btn_layout.addWidget(open_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)

    def handle_open():
        idx = list_widget.currentRow()
        if idx < 0:
            QMessageBox.warning(dlg, "Select Incident", "Please select an incident.")
            return
        inc = incidents[idx]
        number = inc[1] if not isinstance(inc, dict) else inc.get("number")
        AppState.set_active_incident(number)
        if on_select:
            on_select(number)
        dlg.accept()

    def handle_new():
        dialog = NewIncidentDialog(dlg)

        def _on_created(meta, db_path: str) -> None:
            try:
                from models.database import insert_new_incident, get_incident_by_number
                if not get_incident_by_number(meta.number):
                    insert_new_incident(
                        number=meta.number,
                        name=meta.name,
                        type=meta.type,
                        description=meta.description,
                        icp_location=meta.location,
                        is_training=meta.is_training,
                    )
            except Exception:
                pass
            nonlocal incidents
            incidents = load_incidents()

        dialog.created.connect(_on_created)
        dialog.exec()

    new_btn.clicked.connect(handle_new)
    open_btn.clicked.connect(handle_open)
    cancel_btn.clicked.connect(dlg.reject)
    list_widget.itemDoubleClicked.connect(lambda *_: handle_open())

    if owns_app:
        dlg.show()
        app.exec()
    else:
        dlg.exec()


if __name__ == "__main__":
    show_incident_selector()
