from __future__ import annotations

"""Qt controller and data models for the ICS‑205 module (Widgets)."""

from typing import Any, Dict, List

from PySide6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
    QByteArray,
)

from utils.state import AppState
from .models.master_repo import MasterRepository
from .models.incident_repo import IncidentRepository
from .models import db


class MasterListModel(QAbstractListModel):
    """List model exposing channels from the master database."""

    roles = ["id", "display_name", "function", "rx_freq", "tx_freq", "mode", "band"]

    def __init__(self, rows: List[Dict[str, Any]] | None = None, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = rows or []

    def rowCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(self._rows)

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role == Qt.DisplayRole:
            return row.get("display_name")
        base = Qt.UserRole + 1
        if role >= base:
            i = role - base
            if 0 <= i < len(self.roles):
                key = self.roles[i]
                return row.get(key)
        return None

    def roleNames(self):  # type: ignore[override]
        base = Qt.UserRole + 1
        return {base + i: QByteArray(r.encode()) for i, r in enumerate(self.roles)}

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

    def rowCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):  # type: ignore[override]
        return len(PLAN_COLUMNS)

    def roleNames(self):  # type: ignore[override]
        base = Qt.UserRole + 1
        roles = {base + i: QByteArray(col[0].encode()) for i, col in enumerate(PLAN_COLUMNS)}
        return roles

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        base = Qt.UserRole + 1
        if role >= base:
            i = role - base
            if 0 <= i < len(PLAN_COLUMNS):
                key = PLAN_COLUMNS[i][0]
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
        row_id = row.get("id")
        self.repo.update_row(int(row_id), {key: value})
        row[key] = value
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):  # type: ignore[override]
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return PLAN_COLUMNS[section][1]
            except Exception:
                return None
        if orientation == Qt.Vertical:
            return section + 1
        return None

    def replace(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


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
        if role == Qt.DisplayRole:
            r = self._rows[index.row()]
            return f"{r.get('level')}: {r.get('text')}"
        base = Qt.UserRole + 1
        if role >= base:
            i = role - base
            if 0 <= i < len(self.roles):
                key = self.roles[i]
                return self._rows[index.row()].get(key)
        return None

    def roleNames(self):  # type: ignore[override]
        base = Qt.UserRole + 1
        return {base + i: QByteArray(r.encode()) for i, r in enumerate(self.roles)}

    def replace(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


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

        self.masterModel = MasterListModel([])
        self.planModel = PlanModel(self.incident_repo)
        self.validationModel = ValidationModel()

        self.refreshMaster()
        self.refreshPlan()

    # Properties -----------------------------------------------------------
    @Property("QVariantMap", notify=filtersChanged)
    def filters(self):  # type: ignore[override]
        return self._filters

    @Property(str, notify=statusLineChanged)
    def statusLine(self):  # type: ignore[override]
        return self._status

    # Slots (callable methods from widgets) --------------------------------
    def refreshMaster(self):
        rows = self.master_repo.list_channels(self._filters)
        self.masterModel.replace(rows)

    def refreshPlan(self):
        rows = self.incident_repo.list_plan()
        self.planModel.replace(rows)

    def setFilter(self, key: str, value: Any):
        self._filters[key] = value
        self.filtersChanged.emit()
        self.refreshMaster()

    def addMasterIdToPlan(self, master_id: int):
        row = self.master_repo.get_channel(master_id)
        if row:
            self.incident_repo.add_from_master(row, {})
            self.refreshPlan()

    def updatePlanCell(self, row_index: int, column: str, value: Any):
        rows = self.planModel._rows
        if 0 <= row_index < len(rows):
            row_id = rows[row_index]["id"]
            self.incident_repo.update_row(int(row_id), {column: value})
            self.refreshPlan()

    def deletePlanRow(self, row_index: int):
        rows = self.planModel._rows
        if 0 <= row_index < len(rows):
            row_id = rows[row_index]["id"]
            self.incident_repo.delete_row(int(row_id))
            self.refreshPlan()

    def moveRow(self, row_index: int, direction: str):
        rows = self.planModel._rows
        if 0 <= row_index < len(rows):
            row_id = rows[row_index]["id"]
            self.incident_repo.reorder(int(row_id), direction)
            self.refreshPlan()

    def runValidation(self):
        report = self.incident_repo.validate_plan()
        self.validationModel.replace(report["messages"])  # type: ignore[index]
        self._status = f"{report.get('conflicts', 0)} conflicts • {report.get('warnings', 0)} warnings"
        self.statusLineChanged.emit()

    def getPreviewRows(self) -> List[Dict[str, Any]]:
        return self.incident_repo.preview_rows()


__all__ = [
    "ICS205Controller",
    "MasterListModel",
    "PlanModel",
    "ValidationModel",
]
