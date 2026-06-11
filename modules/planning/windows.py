from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

__all__ = [
    "get_dashboard_panel",
    "get_approvals_panel",
    "get_forecast_panel",
    "get_iap_builder_panel",
    "get_op_manager_panel",
    "get_meetings_panel",
    "get_taskmetrics_panel",
    "get_strategic_objectives_panel",
    "get_sitrep_panel",
]


def _make_panel(title: str, body: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_label)
    layout.addWidget(QLabel(body))
    return widget


def get_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planning Dashboard."""
    return _make_panel(
        "Planning Dashboard",
        f"Placeholder panel - incident: {incident_id}",
    )


def get_approvals_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Pending Approvals."""
    return _make_panel(
        "Pending Approvals",
        f"Approvals queue - incident: {incident_id}",
    )


def get_forecast_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planning Forecast."""
    return _make_panel(
        "Planning Forecast",
        f"Forecast tools - incident: {incident_id}",
    )


def get_op_manager_panel(incident_id: object | None = None) -> QWidget:
    """Return the operational period manager panel."""
    from modules.planning.operational_periods.panel import (
        make_operational_period_manager_panel,
    )

    incident_key = str(incident_id) if incident_id is not None else None
    return make_operational_period_manager_panel(incident_id=incident_key)


def get_meetings_panel(incident_id: object | None = None) -> QWidget:
    """Return the Planning Meetings submodule panel."""
    from modules.planning.meetings.panel import make_meetings_panel

    incident_key = str(incident_id) if incident_id is not None else None
    return make_meetings_panel(incident_id=incident_key)


def get_iap_builder_panel(incident_id: object | None = None) -> QWidget:
    """Return the Qt Widgets based IAP Builder panel."""
    from app.modules.planning.iap.ui.iap_builder_window import IAPBuilderWindow

    incident_key = str(incident_id) if incident_id is not None else "demo-incident"
    return IAPBuilderWindow(incident_id=incident_key)


def get_taskmetrics_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Task Metrics Dashboard."""
    return _make_panel(
        "Task Metrics Dashboard",
        f"Metrics - incident: {incident_id}",
    )


def get_strategic_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget wrapping the QML strategic objectives panel.

    Resolves the current incident's SQLite DB from ``<data_root>/incidents`` (or the
    configured data dir via ``utils.incident_context``) instead of using a
    hard-coded path.
    """
    from pathlib import Path

    from PySide6.QtCore import Property, QUrl, QObject, Signal, Slot
    from PySide6.QtQml import QQmlContext
    from PySide6.QtQuick import QQuickView

    from bridge.objectives_bridge import ObjectiveBridge
    from modules.planning.models.objectives_models import SimpleListModel
    from utils import incident_context

    qml_file = Path(__file__).resolve().parent / "qml" / "ObjectiveList.qml"
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)

    try:
        db_path = incident_context.get_active_incident_db_path()
        bridge = ObjectiveBridge(str(db_path), current_user_id=1)
        try:
            import sys

            print(f"[planning] ObjectiveBridge ready. DB={db_path}", file=sys.stderr)
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - defensive path
        import sys
        import traceback

        print(f"[planning] ObjectiveBridge init failed: {exc}", file=sys.stderr)
        traceback.print_exc()

        class _DummyBridge(QObject):
            objectivesChanged = Signal()
            detailChanged = Signal()
            toast = Signal(str)

            def __init__(self, parent=None):
                super().__init__(parent)
                self._model = SimpleListModel(
                    ["oid", "code", "description", "priority", "status", "customer", "section", "due"],
                    [],
                )
                self._narr = SimpleListModel(["ts", "text", "user", "critical"], [])
                self._log = SimpleListModel(["type", "ts", "user", "text", "details"], [])
                self._next_id = 1

            @Property(QObject, notify=objectivesChanged)
            def objectivesModel(self):  # type: ignore[override]
                return self._model

            @Property(QObject, notify=detailChanged)
            def narrativeModel(self):  # type: ignore[override]
                return self._narr

            @Property(QObject, notify=detailChanged)
            def logModel(self):  # type: ignore[override]
                return self._log

            @Slot(str, str, str)
            def loadObjectives(self, _a: str, _b: str, _c: str) -> None:
                self.objectivesChanged.emit()

            @Slot(str, str, int)
            def createObjective(self, description: str, priority: str, _mission_id: int) -> None:
                objective_id = self._next_id
                self._next_id += 1
                self._model.append(
                    {
                        "oid": objective_id,
                        "code": f"G-{objective_id:02d}",
                        "description": description,
                        "priority": priority or "Normal",
                        "status": "Pending",
                        "customer": "",
                        "section": "",
                        "due": "",
                    }
                )
                self.toast.emit("Objective created (offline)")
                self.objectivesChanged.emit()

            @Slot(str, str)
            def createObjectiveSimple(self, description: str, priority: str) -> None:
                self.createObjective(description, priority, 1)

            @Slot(str, str, str, str)
            def createObjectiveFull(
                self,
                description: str,
                priority: str,
                _customer: str,
                _section: str,
            ) -> None:
                self.createObjective(description, priority, 1)

            @Slot(int)
            def loadObjectiveDetail(self, _objective_id: int) -> None:
                self._narr.replace([])
                self._log.replace([])
                self.detailChanged.emit()

            @Slot(int, str)
            def changeStatus(self, objective_id: int, new_status: str) -> None:
                rows = [self._model._data[i].copy() for i in range(self._model.rowCount())]
                for row in rows:
                    if row.get("oid") == objective_id:
                        row["status"] = new_status
                self._model.replace(rows)
                self.objectivesChanged.emit()
                self.toast.emit(f"Status: {new_status}")

            @Slot(int, str)
            def addComment(self, _objective_id: int, _text: str) -> None:
                self.toast.emit("Comment added (offline)")
                self.detailChanged.emit()

            @Slot(int, str)
            def addNarrative(self, _objective_id: int, _text: str) -> None:
                self.toast.emit("Narrative added (offline)")
                self.detailChanged.emit()

        bridge = _DummyBridge()

    container = QWidget.createWindowContainer(view)
    container._objectiveBridge = bridge  # type: ignore[attr-defined]
    container._quickView = view  # type: ignore[attr-defined]
    context: QQmlContext = view.rootContext()
    context.setContextProperty("objectiveBridge", container._objectiveBridge)
    view.setSource(QUrl.fromLocalFile(qml_file.as_posix()))
    return container


def get_sitrep_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Situation Report."""
    return _make_panel(
        "Situation Report",
        f"SITREP - incident: {incident_id}",
    )
