from __future__ import annotations

"""Qt controller and data models for the ICS-205 module."""

from typing import Any, Dict, List

from PySide6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
    Slot,
    QByteArray,
)

from utils.state import AppState

from .models.master_repo import MasterRepository
from .models.incident_repo import IncidentRepository
from .models import db


# ---------------------------------------------------------------------------
# List model helpers
# ---------------------------------------------------------------------------

class MasterListModel(QAbstractListModel):
    """List model exposing channels from the master database."""

    roles = ["id", "display_name", "function", "rx_freq", "tx_freq", "mode", "band"]

    def __init__(self, rows: List[Dict[str, Any]] | None = None, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = rows or []

    # Qt model implementation ----------------------------------------------
    def rowCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(self._rows)

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self.roles[role - Qt.UserRole]
        return row.get(key)

    def roleNames(self):  # type: ignore[override]
        return {Qt.UserRole + i: QByteArray(r.encode()) for i, r in enumerate(self.roles)}

    # Helpers ---------------------------------------------------------------
    def replace(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def get(self, row: int) -> Dict[str, Any]:
        return self._rows[row] if 0 <= row < len(self._rows) else {}


PLAN_COLUMNS = [
    ("channel", "Channel"),
    ("function", "Function"),
    ("assignment_division", "Division"),
    ("assignment_team", "Team"),
    ("rx_freq", "RX"),
    ("tx_freq", "TX"),
    ("mode", "Mode"),
    ("band", "Band"),
    ("priority", "Priority"),
    ("include_on_205", "205"),
    ("remarks", "Remarks"),
]


class PlanModel(QAbstractTableModel):
    """Editable table model for the incident plan."""

    def __init__(self, repo: IncidentRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._rows: List[Dict[str, Any]] = []

    # Basic model API ------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(PLAN_COLUMNS)

    def roleNames(self):  # type: ignore[override]
        roles = {Qt.UserRole + i: QByteArray(col[0].encode()) for i, col in enumerate(PLAN_COLUMNS)}
        return roles

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role >= Qt.UserRole:
            key = PLAN_COLUMNS[role - Qt.UserRole][0]
            return row.get(key)
        if role == Qt.DisplayRole:
            key = PLAN_COLUMNS[index.column()][0]
            return row.get(key)
        return None

    def setData(self, index, value, role=Qt.EditRole):  # type: ignore[override]
        if not index.isValid():
            return False
        key = PLAN_COLUMNS[index.column()][0]
        row = self._rows[index.row()]
        self.repo.update_row(row["id"], {key: value})
        row[key] = value
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    # Helpers ---------------------------------------------------------------
    def replace(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_dict(self, row: int) -> Dict[str, Any]:
        return self._rows[row] if 0 <= row < len(self._rows) else {}


class ValidationModel(QAbstractListModel):
    roles = ["level", "text"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(self._rows)

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        key = self.roles[role - Qt.UserRole]
        return self._rows[index.row()].get(key)

    def roleNames(self):  # type: ignore[override]
        return {Qt.UserRole + i: QByteArray(r.encode()) for i, r in enumerate(self.roles)}

    def replace(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class ICS205Controller(QObject):
    filtersChanged = Signal()
    statusLineChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters: Dict[str, Any] = {}
        self._status = ""

        incident = AppState.get_active_incident()
        if incident is None:
            raise RuntimeError("Active incident not set")
        db.ensure_incident_schema(incident)
        self.master_repo = MasterRepository()
        self.incident_repo = IncidentRepository(incident)

        self._masterModel = MasterListModel([])
        self._planModel = PlanModel(self.incident_repo)
        self._validationModel = ValidationModel()

        self.refreshMaster()
        self.refreshPlan()

    # Properties -----------------------------------------------------------
    @Property("QVariantMap", notify=filtersChanged)
    def filters(self):  # type: ignore[override]
        return self._filters

    @Property(str, notify=statusLineChanged)
    def statusLine(self):  # type: ignore[override]
        return self._status

    @Property(QObject, constant=True)
    def masterModel(self):  # type: ignore[override]
        return self._masterModel

    @Property(QObject, constant=True)
    def planModel(self):  # type: ignore[override]
        return self._planModel

    @Property(QObject, constant=True)
    def validationModel(self):  # type: ignore[override]
        return self._validationModel

    # Slots ----------------------------------------------------------------
    @Slot()
    def refreshMaster(self):
        rows = self.master_repo.list_channels(self._filters)
        self._masterModel.replace(rows)

    @Slot()
    def refreshPlan(self):
        rows = self.incident_repo.list_plan()
        self._planModel.replace(rows)

    @Slot(str, "QVariant")
    def setFilter(self, key: str, value: Any):
        self._filters[key] = value
        self.filtersChanged.emit()
        self.refreshMaster()

    @Slot(int)
    def addMasterIdToPlan(self, master_id: int):
        row = self.master_repo.get_channel(master_id)
        if row:
            self.incident_repo.add_from_master(row, {})
            self.refreshPlan()

    @Slot(int, str, "QVariant")
    def updatePlanCell(self, row: int, column: str, value: Any):
        rows = self._planModel._rows
        if 0 <= row < len(rows):
            row_id = rows[row]["id"]
            self.incident_repo.update_row(row_id, {column: value})
            self.refreshPlan()

    @Slot(int)
    def deletePlanRow(self, row: int):
        rows = self._planModel._rows
        if 0 <= row < len(rows):
            row_id = rows[row]["id"]
            self.incident_repo.delete_row(row_id)
            self.refreshPlan()

    @Slot(int, str)
    def moveRow(self, row: int, direction: str):
        rows = self._planModel._rows
        if 0 <= row < len(rows):
            row_id = rows[row]["id"]
            self.incident_repo.reorder(row_id, direction)
            self.refreshPlan()

    @Slot()
    def runValidation(self):
        report = self.incident_repo.validate_plan()
        self._validationModel.replace(report["messages"])
        self._status = f"{report['conflicts']} conflicts • {report['warnings']} warnings"
        self.statusLineChanged.emit()

    @Slot(result="QVariantList")
    def getPreviewRows(self):
        return self.incident_repo.preview_rows()

    @Slot(int, result="QVariantMap")
    def getPlanRow(self, row: int):
        return self._planModel.row_dict(row)
