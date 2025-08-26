"""Bootstrap launcher for the Mission selection window.

This module wires up the model, proxy and controller before loading the
``MissionSelectWindow.qml`` screen. It allows the selector to be executed as
standalone for manual testing or integrated into the wider application.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from models.missionlist import (
    MissionController,
    MissionListModel,
    MissionProxyModel,
    load_missions_from_master,
)


def show_mission_selector():
    """Create and display the mission selection window."""

    app = QGuiApplication.instance()
    owns_app = False
    if app is None:
        # Create an application if one is not already running
        app = QGuiApplication(sys.argv)
        owns_app = True

    # Base table model loading missions from the master database
    mission_model = MissionListModel()
    mission_model.reload(load_missions_from_master)

    # Proxy model handles sorting/filtering exposed to QML
    proxy = MissionProxyModel()
    proxy.setSourceModel(mission_model)
    proxy.sort(5, Qt.DescendingOrder)  # Default sort: Start time descending

    # Controller for CRUD-style signals (actual DB writes added later)
    controller = MissionController(mission_model)

    # Prepare QML engine and expose context properties
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("missionModel", mission_model)
    ctx.setContextProperty("proxy", proxy)
    ctx.setContextProperty("controller", controller)

    # Resolve QML file on disk and load it
    qml_file = Path(__file__).resolve().parents[1] / "qml" / "MissionSelectWindow.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        raise RuntimeError("Failed to load MissionSelectWindow.qml")

    if owns_app:
        # Execute application event loop if we created the QGuiApplication
        app.exec()


if __name__ == "__main__":
    # Allow manual testing when run directly
    show_mission_selector()

