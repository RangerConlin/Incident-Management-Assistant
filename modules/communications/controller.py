from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import (QAbstractListModel, QAbstractTableModel, QModelIndex,
                             QObject, Qt, Signal)

from utils.state import AppState

from .models.master_repo import MasterRepository
from .models.incident_repo import IncidentRepository, ValidationMessage


# ---------------------------------------------------------------------------
# Qt Models
# ---------------------------------------------------------------------------

class MasterListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.rows: List[Dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return row.get('display_name')
        if role == Qt.UserRole:
            return row
        return None

    def setRows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


PLAN_COLUMNS = [
    ('channel', 'Channel'),
    ('function', 'Function'),
    ('band', 'Band'),
    ('rx_freq', 'RX'),
    ('tx_freq', 'TX'),
    ('mode', 'Mode'),
    ('assignment_division', 'Division'),
    ('assignment_team', 'Team'),
    ('priority', 'Priority'),
    ('include_on_205', 'Include'),
]


class PlanTableModel(QAbstractTableModel):
    rowEdited = Signal(int, dict)

    def __init__(self, repo: IncidentRepository | None):
        super().__init__()
        self.repo = repo
        self.rows: List[Dict[str, Any]] = []

    # basic impl
    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(PLAN_COLUMNS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        key = PLAN_COLUMNS[index.column()][0]
        if role in (Qt.DisplayRole, Qt.EditRole):
            return row.get(key)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return PLAN_COLUMNS[section][1]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def setRows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False
        row = self.rows[index.row()]
        key = PLAN_COLUMNS[index.column()][0]
        row[key] = value
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        if self.repo:
            self.repo.update_row(row['id'], {key: value})
            self.rowEdited.emit(row['id'], {key: value})
        return True


class ValidationListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.messages: List[ValidationMessage] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.messages)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        msg = self.messages[index.row()]
        if role == Qt.DisplayRole:
            return f"{msg.level}: {msg.text}"
        return None

    def setMessages(self, msgs: List[ValidationMessage]):
        self.beginResetModel()
        self.messages = msgs
        self.endResetModel()


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class ICS205Controller(QObject):
    statusLineChanged = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.filters: Dict[str, Any] = {}
        self.master_repo = MasterRepository()
        incident = AppState.get_active_incident()
        self.repo: IncidentRepository | None = None
        if incident is not None:
            self.repo = IncidentRepository(incident)
        self.masterModel = MasterListModel()
        self.planModel = PlanTableModel(self.repo)
        self.validationModel = ValidationListModel()
        self.statusLine = ''
        if incident is not None:
            self.refreshMaster()
            self.refreshPlan()

    # --------------------------------------------------------------
    def refreshMaster(self):
        rows = self.master_repo.list_channels(self.filters)
        self.masterModel.setRows(rows)

    def refreshPlan(self):
        if not self.repo:
            self.planModel.setRows([])
            return
        rows = self.repo.list_plan()
        self.planModel.setRows(rows)

    # --------------------------------------------------------------
    def setFilter(self, key: str, value: Any):
        if value:
            self.filters[key] = value
        else:
            self.filters.pop(key, None)
        self.refreshMaster()

    # --------------------------------------------------------------
    def addMasterIdToPlan(self, master_id: int):
        if not self.repo:
            return
        master_row = self.master_repo.get_channel(master_id)
        if not master_row:
            return
        self.repo.add_from_master(master_row, {})
        self.refreshPlan()

    # --------------------------------------------------------------
    def updatePlanCell(self, row: int, column: int, value: Any):
        index = self.planModel.index(row, column)
        self.planModel.setData(index, value, Qt.EditRole)

    # --------------------------------------------------------------
    def deletePlanRow(self, row: int):
        if not self.repo:
            return
        data = self.planModel.rows[row]
        self.repo.delete_row(data['id'])
        self.refreshPlan()

    # --------------------------------------------------------------
    def moveRow(self, row: int, direction: str):
        if not self.repo:
            return
        data = self.planModel.rows[row]
        self.repo.reorder(data['id'], direction)
        self.refreshPlan()

    # --------------------------------------------------------------
    def runValidation(self):
        if not self.repo:
            return
        report = self.repo.validate_plan()
        self.validationModel.setMessages(report.messages)
        self.statusLine = f"{report.conflicts} conflicts, {report.warnings} warnings"
        self.statusLineChanged.emit(self.statusLine)

    # --------------------------------------------------------------
    def getPreviewRows(self) -> List[Dict[str, Any]]:
        if not self.repo:
            return []
        return self.repo.preview_rows()
