from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

__all__ = [
    "get_dashboard_panel",
    "get_approvals_panel",
    "get_forecast_panel",
    "get_op_manager_panel",
    "get_taskmetrics_panel",
    "get_strategic_objectives_panel",
    "get_sitrep_panel",
]

def _make_panel(title: str, body: str) -> QWidget:
    w = QWidget()
    layout = QVBoxLayout(w)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title_lbl)
    layout.addWidget(QLabel(body))
    return w

def get_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planning Dashboard."""
    return _make_panel(
        "Planning Dashboard",
        f"Placeholder panel — incident: {incident_id}",
    )

def get_approvals_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Pending Approvals."""
    return _make_panel(
        "Pending Approvals",
        f"Approvals queue — incident: {incident_id}",
    )

def get_forecast_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Planning Forecast."""
    return _make_panel(
        "Planning Forecast",
        f"Forecast tools — incident: {incident_id}",
    )

def get_op_manager_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Operational Period Manager."""
    return _make_panel(
        "Operational Period Manager",
        f"OP builder — incident: {incident_id}",
    )

def get_taskmetrics_panel(incident_id: object | None = None) -> QWidget:
    """Return placeholder QWidget for Task Metrics Dashboard."""
    return _make_panel(
        "Task Metrics Dashboard",
        f"Metrics — incident: {incident_id}",
    )

def get_strategic_objectives_panel(incident_id: object | None = None) -> QWidget:
    """Return QWidget wrapping the QML strategic objectives panel.

    Resolves the current incident's SQLite DB from ``data/incidents`` (or the
    configured data dir via ``utils.incident_context``) instead of using a
    hard-coded path.
    """
    from pathlib import Path
    from PySide6.QtCore import QUrl
    from PySide6.QtQuick import QQuickView
    from PySide6.QtQml import QQmlContext

    from bridge.objectives_bridge import ObjectiveBridge
    from utils import incident_context

    qml_file = Path(__file__).resolve().parent / "qml" / "ObjectiveList.qml"
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)

    # Instantiate the bridge; fall back to a safe dummy on error so QML doesn't get a null
    try:
        # Resolve from the globally active incident to keep a single source of truth
        db_path = incident_context.get_active_incident_db_path()
        bridge = ObjectiveBridge(str(db_path), current_user_id=1)
        try:
            import sys
            print(f"[planning] ObjectiveBridge ready. DB={db_path}", file=sys.stderr)
        except Exception:
            pass
    except Exception as e:  # pragma: no cover - defensive path
        import sys, traceback
        print(f"[planning] ObjectiveBridge init failed: {e}", file=sys.stderr)
        traceback.print_exc()
        from PySide6.QtCore import QObject, Slot, Signal, Property
        from modules.planning.models.objectives_models import SimpleListModel

        class _DummyBridge(QObject):
            objectivesChanged = Signal()
            detailChanged = Signal()
            toast = Signal(str)

            def __init__(self, parent=None):
                super().__init__(parent)
                # Provide the expected roles so delegates bind cleanly
                self._model = SimpleListModel(["oid","code","description","priority","status","customer","section","due"], [])
                self._narr = SimpleListModel(["ts","text","user","critical"], [])
                self._log = SimpleListModel(["type","ts","user","text","details"], [])
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
            def loadObjectives(self, a: str, b: str, c: str) -> None:
                # no-op; keeps QML happy when in fallback
                self.objectivesChanged.emit()

            @Slot(str, str, int)
            def createObjective(self, description: str, priority: str, mission_id: int) -> None:
                oid = self._next_id
                self._next_id += 1
                self._model.append({
                    "oid": oid,
                    "code": "G-%02d" % oid,
                    "description": description,
                    "priority": priority or "Normal",
                    "status": "Pending",
                    "customer": "",
                    "section": "",
                    "due": "",
                })
                self.toast.emit("Objective created (offline)")
                self.objectivesChanged.emit()

            @Slot(str, str)
            def createObjectiveSimple(self, description: str, priority: str) -> None:
                self.createObjective(description, priority, 1)

            @Slot(str, str, str, str)
            def createObjectiveFull(self, description: str, priority: str, customer: str, section: str) -> None:
                self.createObjective(description, priority, 1)

            @Slot(int)
            def loadObjectiveDetail(self, oid: int) -> None:
                self._narr.replace([])
                self._log.replace([])
                self.detailChanged.emit()

            @Slot(int, str)
            def changeStatus(self, oid: int, new_status: str) -> None:
                # Replace list with updated status (simple fallback)
                rows = []
                for i in range(self._model.rowCount()):
                    # Access internal data
                    # This is a simple fallback; in real model we'd have update API
                    rows.append(self._model._data[i].copy())
                for r in rows:
                    if r.get("oid") == oid:
                        r["status"] = new_status
                self._model.replace(rows)
                self.objectivesChanged.emit()
                self.toast.emit(f"Status: {new_status}")

            @Slot(int, str)
            def addComment(self, oid: int, text: str) -> None:
                self.toast.emit("Comment added (offline)")
                self.detailChanged.emit()

            @Slot(int, str)
            def addNarrative(self, oid: int, text: str) -> None:
                self.toast.emit("Narrative added (offline)")
                self.detailChanged.emit()

        bridge = _DummyBridge()
    # Keep a Python reference to prevent garbage collection of the QObject
    # held only by the QML context property.
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
        f"SITREP — incident: {incident_id}",
    )
