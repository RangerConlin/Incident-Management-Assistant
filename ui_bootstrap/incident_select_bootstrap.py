"""Bootstrap launcher for the Incident selection window.

This module wires up the model, proxy and controller before loading the
``IncidentSelectWindow.qml`` screen. It allows the selector to be executed as
standalone for manual testing or integrated into the wider application.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication
from utils.state import AppState

from models.incidentlist import (
    IncidentController,
    IncidentListModel,
    IncidentProxyModel,
    load_incidents_from_master,
)

from modules.missions.new_incident_dialog import NewIncidentDialog

# Keep strong references to views so they aren't GC'd when called modelessly
_open_views: list[QQuickView] = []


def show_incident_selector():
    """Create and display the incident selection window.

    Loads the root Item QML into a QQuickView so it shows in its own
    window when run standalone, while preserving context properties and
    signal wiring.
    """

    app = QApplication.instance()
    owns_app = False
    if app is None:
        # Create an application if one is not already running
        app = QApplication(sys.argv)
        owns_app = True

    # Base table model loading incidents from the master database
    incident_model = IncidentListModel()
    incident_model.reload(load_incidents_from_master)

    # Proxy model handles sorting/filtering exposed to QML
    proxy = IncidentProxyModel()
    proxy.setSourceModel(incident_model)
    proxy.sort(5, Qt.DescendingOrder)  # Default sort: Start time descending

    # Controller for CRUD-style signals (actual DB writes added later)
    controller = IncidentController()

    # Attach our model and proxy to the controller so its filtering calls affect
    # the same data that the QML is displaying
    controller.model = incident_model
    controller.proxy = proxy
    # Optional: if you ever call controller.loadIncidentByRow, set its private proxy too
    controller._proxy = proxy

    # NEW: when controller announces a selection, set global AppState
    if hasattr(controller, "incidentselected"):
        controller.incidentselected.connect(AppState.set_active_incident)

    # Host the root Item in a QQuickView (creates a window)
    view = QQuickView()
    view.setTitle("Select Incident")
    # Size to content so the root Item's width/height are respected
    try:
        view.setResizeMode(QQuickView.SizeRootObjectToView)
    except Exception:
        pass

    # Expose context properties before loading QML
    ctx = view.rootContext()
    ctx.setContextProperty("incidentModel", incident_model)
    ctx.setContextProperty("proxy", proxy)
    ctx.setContextProperty("controller", controller)

    # Resolve QML file on disk and load it
    qml_file = Path(__file__).resolve().parents[1] / "qml" / "IncidentSelectWindow.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_file)))

    # Verify load success and wire root-level signals
    root_obj = view.rootObject()
    if root_obj is None:
        raise RuntimeError("Failed to load IncidentSelectWindow.qml")

    def _handle_create_requested():
        dialog = NewIncidentDialog()
        dialog.created.connect(lambda *_: incident_model.refresh())
        dialog.exec()

    if hasattr(root_obj, "createRequested"):
        root_obj.createRequested.connect(_handle_create_requested)

    # Show the window and keep a strong reference if we don't own the app loop
    view.show()

    # Persist the model, proxy and controller by attaching them to the view
    view._incident_model = incident_model
    view._proxy = proxy
    view._controller = controller

    if not owns_app:
        _open_views.append(view)

    if owns_app:
        # Execute application event loop if we created the QGuiApplication
        app.exec()


if __name__ == "__main__":
    # Allow manual testing when run directly
    show_incident_selector()

