from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from PySide6 import QtGui
from PySide6.QtCore import QDateTime, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QKeySequence, QShortcut, QTextDocument
try:  # Qt PrintSupport requires platform GL libs; optional at runtime
    from PySide6.QtPrintSupport import QPrinter
except ImportError:  # pragma: no cover - headless environments without GL
    QPrinter = None  # type: ignore[assignment]
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..exceptions import ConflictError, NoShowGuardError, OfflineQueued, PermissionDenied
from ..models import CIStatus, CheckInRecord, Location, PersonnelIdentity, PersonnelStatus, RosterRow
from .. import services


def _monospace_font() -> QFont:
    return QFontDatabase.systemFont(QFontDatabase.FixedFont)


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().isoformat()


class RosterTableModel(QtGui.QStandardItemModel):
    columns = [
        ("colID", "ID"),
        ("colName", "Name"),
        ("colRole", "Role"),
        ("colTeam", "Team"),
        ("colPhone", "Phone"),
        ("colCallsign", "Callsign"),
        ("colCIStatus", "Check-In Status"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, len(self.columns), parent)
        for idx, (_, title) in enumerate(self.columns):
            self.setHeaderData(idx, Qt.Horizontal, title)
        self._rows: List[RosterRow] = []

    def update_rows(self, rows: List[RosterRow]) -> None:
        self.clear()
        for idx, (_, title) in enumerate(self.columns):
            self.setHeaderData(idx, Qt.Horizontal, title)
        self._rows = rows
        self.setRowCount(len(rows))
        self.setColumnCount(len(self.columns))
        palette = QApplication.instance().palette()
        gray = palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text)
        for r_index, row in enumerate(rows):
            values = [
                row.person_id,
                row.name,
                row.role or "",
                row.team or "—",
                row.phone or "",
                row.callsign or "",
                row.ci_status.value,
            ]
            for c_index, value in enumerate(values):
                item = QtGui.QStandardItem(str(value))
                if c_index in (0, 4, 5):
                    item.setFont(_monospace_font())
                if row.ui_flags.grayed:
                    item.setForeground(gray)
                item.setEditable(False)
                item.setData(row.person_id, Qt.UserRole)
                self.setItem(r_index, c_index, item)

    def row_data(self, index: QModelIndex) -> Optional[RosterRow]:
        if not index.isValid():
            return None
        if 0 <= index.row() < len(self._rows):
            return self._rows[index.row()]
        return None

    def find_row(self, person_id: str) -> Optional[int]:
        for idx, row in enumerate(self._rows):
            if row.person_id == person_id:
                return idx
        return None


class RosterPane(QWidget):
    filterChanged = Signal()
    rowActivated = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.search_box = QLineEdit(self)
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("Search name, ID, callsign, phone")
        layout.addWidget(self.search_box)

        filter_row = QGridLayout()
        filter_row.setSpacing(4)
        layout.addLayout(filter_row)

        self.cbo_ci_status = QComboBox(self)
        self.cbo_ci_status.setObjectName("CboFilterCIStatus")
        self.cbo_ci_status.addItem("All", None)
        for status in CIStatus:
            self.cbo_ci_status.addItem(status.value, status.value)
        filter_row.addWidget(self.cbo_ci_status, 0, 0)

        self.cbo_personnel_status = QComboBox(self)
        self.cbo_personnel_status.setObjectName("CboFilterPersStatus")
        self.cbo_personnel_status.addItem("All", None)
        for status in PersonnelStatus:
            self.cbo_personnel_status.addItem(status.value, status.value)
        filter_row.addWidget(self.cbo_personnel_status, 0, 1)

        self.cbo_role = QComboBox(self)
        self.cbo_role.setObjectName("CboFilterRole")
        self.cbo_role.addItem("All", None)
        filter_row.addWidget(self.cbo_role, 1, 0)

        self.cbo_team = QComboBox(self)
        self.cbo_team.setObjectName("CboFilterTeam")
        self.cbo_team.addItem("All", None)
        filter_row.addWidget(self.cbo_team, 1, 1)

        self.chk_show_no_show = QCheckBox("Show No Show", self)
        self.chk_show_no_show.setObjectName("ChkShowNoShow")
        layout.addWidget(self.chk_show_no_show)

        self.table = QTableView(self)
        self.table.setObjectName("TblRoster")
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.model = RosterTableModel(self.table)
        self.table.setModel(self.model)
        layout.addWidget(self.table, 1)

        self.search_box.textChanged.connect(self.filterChanged.emit)
        self.cbo_ci_status.currentIndexChanged.connect(self.filterChanged.emit)
        self.cbo_personnel_status.currentIndexChanged.connect(self.filterChanged.emit)
        self.cbo_role.currentIndexChanged.connect(self.filterChanged.emit)
        self.cbo_team.currentIndexChanged.connect(self.filterChanged.emit)
        self.chk_show_no_show.toggled.connect(self.filterChanged.emit)
        self.table.doubleClicked.connect(self._emit_activation)
        self.table.activated.connect(self._emit_activation)

    def _emit_activation(self, index: QModelIndex) -> None:
        row = self.model.row_data(index)
        if row:
            self.rowActivated.emit(row.person_id)

    # Data helpers ---------------------------------------------------------
    def set_roles(self, roles: List[str]) -> None:
        current = self.cbo_role.currentData()
        self.cbo_role.blockSignals(True)
        self.cbo_role.clear()
        self.cbo_role.addItem("All", None)
        for role in sorted(roles):
            self.cbo_role.addItem(role, role)
        if current:
            idx = self.cbo_role.findData(current)
            if idx >= 0:
                self.cbo_role.setCurrentIndex(idx)
        self.cbo_role.blockSignals(False)

    def set_teams(self, teams: List[tuple[str, str]]) -> None:
        current = self.cbo_team.currentData()
        self.cbo_team.blockSignals(True)
        self.cbo_team.clear()
        self.cbo_team.addItem("All", None)
        self.cbo_team.addItem("—", "—")
        for team_id, name in teams:
            label = f"{name} ({team_id})" if name and name != team_id else team_id
            self.cbo_team.addItem(label, team_id)
        if current is not None:
            idx = self.cbo_team.findData(current)
            if idx >= 0:
                self.cbo_team.setCurrentIndex(idx)
        self.cbo_team.blockSignals(False)

    def update_rows(self, rows: List[RosterRow]) -> None:
        self.model.update_rows(rows)
        self.table.resizeColumnsToContents()

    def filters(self) -> Dict[str, object]:
        return {
            "q": self.search_box.text().strip() or None,
            "ci_status": self.cbo_ci_status.currentData(),
            "personnel_status": self.cbo_personnel_status.currentData(),
            "role": self.cbo_role.currentData(),
            "team": self.cbo_team.currentData(),
            "include_no_show": self.chk_show_no_show.isChecked(),
        }

    def selected_person_id(self) -> Optional[str]:
        indexes = self.table.selectionModel().selectedRows()
        if indexes:
            row = self.model.row_data(indexes[0])
            return row.person_id if row else None
        return None

    def select_person(self, person_id: str) -> None:
        row_index = self.model.find_row(person_id)
        if row_index is None:
            return
        index = self.model.index(row_index, 0)
        self.table.selectRow(row_index)
        self.table.scrollTo(index, QTableView.PositionAtCenter)


class OverrideDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Override Personnel Status")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.cbo_status = QComboBox(self)
        for status in PersonnelStatus:
            self.cbo_status.addItem(status.value, status.value)
        form.addRow("Status", self.cbo_status)
        self.reason_edit = QLineEdit(self)
        form.addRow("Reason", self.reason_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    def get_values(self) -> Optional[tuple[str, str]]:
        if self.exec() == QDialog.Accepted:
            status = self.cbo_status.currentData()
            reason = self.reason_edit.text().strip()
            return status, reason
        return None


class CheckInForm(QWidget):
    saveRequested = Signal(dict, bool)
    cancelRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.person_id: Optional[str] = None
        self.expected_updated_at: Optional[str] = None
        self.override_status: Optional[str] = None
        self.override_reason: Optional[str] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.cbo_status = QComboBox(self)
        self.cbo_status.setObjectName("CboCheckInStatus")
        for status in CIStatus:
            self.cbo_status.addItem(status.value, status.value)
        form.addRow("Check-In Status", self.cbo_status)

        self.lbl_personnel_status = QLabel("Available", self)
        self.lbl_personnel_status.setObjectName("LblPersonnelStatus")
        form.addRow("Personnel Status", self.lbl_personnel_status)

        self.btn_override = QPushButton("Override", self)
        self.btn_override.setObjectName("BtnOverridePersonnelStatus")
        self.btn_override.clicked.connect(self._request_override)
        form.addRow("", self.btn_override)

        self.arrival_edit = QDateTimeEdit(self)
        self.arrival_edit.setObjectName("DtArrivalTime")
        self.arrival_edit.setCalendarPopup(True)
        form.addRow("Arrival Time", self.arrival_edit)

        self.cbo_location = QComboBox(self)
        self.cbo_location.setObjectName("CboLocation")
        for location in Location:
            self.cbo_location.addItem(location.value, location.value)
        form.addRow("Location", self.cbo_location)

        self.location_other = QLineEdit(self)
        self.location_other.setObjectName("TxtLocationOther")
        form.addRow("Location Other", self.location_other)

        self.shift_start = QLineEdit(self)
        self.shift_start.setObjectName("TxtShiftStart")
        self.shift_start.setMaxLength(4)
        form.addRow("Shift Start", self.shift_start)

        self.shift_end = QLineEdit(self)
        self.shift_end.setObjectName("TxtShiftEnd")
        self.shift_end.setMaxLength(4)
        form.addRow("Shift End", self.shift_end)

        preset_row = QHBoxLayout()
        self.btn_preset_day = QPushButton("Day", self)
        self.btn_preset_day.setObjectName("BtnPresetDay")
        self.btn_preset_night = QPushButton("Night", self)
        self.btn_preset_night.setObjectName("BtnPresetNight")
        self.btn_preset_12h = QPushButton("12h", self)
        self.btn_preset_12h.setObjectName("BtnPreset12h")
        preset_row.addWidget(self.btn_preset_day)
        preset_row.addWidget(self.btn_preset_night)
        preset_row.addWidget(self.btn_preset_12h)
        form.addRow("Presets", preset_row)

        self.notes = QPlainTextEdit(self)
        self.notes.setObjectName("TxtNotes")
        self.notes.setPlaceholderText("Notes")
        form.addRow("Notes", self.notes)

        layout.addLayout(form)

        self.status_logic = QListWidget(self)
        self.status_logic.setObjectName("ListStatusLogic")
        self.status_logic.addItems(
            [
                "Checked In + no team → Personnel Available",
                "Demobilized → Personnel Demobilized (row grayed)",
                "No Show → Personnel Unavailable (hidden)",
                '"Enroute to Incident" is normalized to Pending',
            ]
        )
        self.status_logic.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.status_logic)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_save = QPushButton("Save", self)
        self.btn_save.setObjectName("BtnSave")
        self.btn_save_new = QPushButton("Save && New", self)
        self.btn_save_new.setObjectName("BtnSaveAndNew")
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setObjectName("BtnCancel")
        button_row.addWidget(self.btn_save)
        button_row.addWidget(self.btn_save_new)
        button_row.addWidget(self.btn_cancel)
        layout.addLayout(button_row)

        self.btn_save.clicked.connect(lambda: self._emit_save(False))
        self.btn_save_new.clicked.connect(lambda: self._emit_save(True))
        self.btn_cancel.clicked.connect(self.cancelRequested.emit)

        self.cbo_location.currentIndexChanged.connect(self._update_location_other_state)
        self.btn_preset_day.clicked.connect(lambda: self._apply_preset("0800", "1700"))
        self.btn_preset_night.clicked.connect(lambda: self._apply_preset("1800", "0600"))
        self.btn_preset_12h.clicked.connect(lambda: self._apply_preset("0700", "1900"))

    def _apply_preset(self, start: str, end: str) -> None:
        self.shift_start.setText(start)
        self.shift_end.setText(end)

    def _update_location_other_state(self) -> None:
        is_other = self.cbo_location.currentData() == Location.OTHER.value
        self.location_other.setEnabled(is_other)

    def _request_override(self) -> None:
        dialog = OverrideDialog(self)
        result = dialog.get_values()
        if result:
            status, reason = result
            self.override_status = status
            self.override_reason = reason
            if status:
                self.lbl_personnel_status.setText(status)

    def populate(self, person_id: str, record: Optional[CheckInRecord]) -> None:
        self.person_id = person_id
        self.override_status = None
        self.override_reason = None
        now = datetime.now().astimezone()
        dt = now if record is None else datetime.fromisoformat(record.arrival_time)
        self.arrival_edit.setDateTime(QDateTime(dt))
        status = record.ci_status.value if record else CIStatus.CHECKED_IN.value
        idx = self.cbo_status.findData(status)
        self.cbo_status.setCurrentIndex(max(0, idx))
        if record:
            self.lbl_personnel_status.setText(record.personnel_status.value)
        else:
            self.lbl_personnel_status.setText(PersonnelStatus.AVAILABLE.value)
        location = record.location.value if record else Location.ICP.value
        idx = self.cbo_location.findData(location)
        self.cbo_location.setCurrentIndex(max(0, idx))
        self.location_other.setText(record.location_other if record else "")
        self.shift_start.setText(record.shift_start or "")
        self.shift_end.setText(record.shift_end or "")
        self.notes.setPlainText(record.notes or "")
        self.expected_updated_at = record.updated_at if record else None
        self._update_location_other_state()

    def populate_new(self, person_id: str) -> None:
        self.populate(person_id, None)
        self.btn_save_new.show()

    def collect(self) -> Dict[str, object]:
        if not self.person_id:
            raise RuntimeError("Person not loaded")
        dt = self.arrival_edit.dateTime().toPython()
        payload: Dict[str, object] = {
            "person_id": self.person_id,
            "ci_status": self.cbo_status.currentData(),
            "arrival_time": _isoformat(dt),
            "location": self.cbo_location.currentData(),
            "location_other": self.location_other.text().strip() or None,
            "shift_start": self.shift_start.text().strip() or None,
            "shift_end": self.shift_end.text().strip() or None,
            "notes": self.notes.toPlainText().strip() or None,
        }
        if self.expected_updated_at:
            payload["expected_updated_at"] = self.expected_updated_at
        if self.override_status:
            payload["override_personnel_status"] = self.override_status
            payload["override_reason"] = self.override_reason or ""
        return payload

    def _emit_save(self, save_and_new: bool) -> None:
        try:
            payload = self.collect()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Incomplete", str(exc))
            return
        self.saveRequested.emit(payload, save_and_new)


class AssignmentForm(QWidget):
    saveRequested = Signal(dict)
    cancelRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self.cbo_team = QComboBox(self)
        self.cbo_team.setObjectName("CboTeam")
        self.cbo_team.setEditable(True)
        form.addRow("Team", self.cbo_team)

        self.cbo_role_on_team = QComboBox(self)
        self.cbo_role_on_team.setObjectName("CboRoleOnTeam")
        self.cbo_role_on_team.setEditable(True)
        form.addRow("Role on Team", self.cbo_role_on_team)

        self.cbo_op_period = QComboBox(self)
        self.cbo_op_period.setObjectName("CboOperationalPeriod")
        self.cbo_op_period.setEditable(True)
        form.addRow("Operational Period", self.cbo_op_period)

        helper = QLabel("Assigning a team does not auto-flip Personnel Status.", self)
        helper.setWordWrap(True)
        layout.addLayout(form)
        layout.addWidget(helper)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.btn_save = QPushButton("Save", self)
        self.btn_save.setObjectName("BtnAssignSave")
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setObjectName("BtnAssignCancel")
        button_row.addWidget(self.btn_save)
        button_row.addWidget(self.btn_cancel)
        layout.addLayout(button_row)

        self.btn_save.clicked.connect(self._emit_save)
        self.btn_cancel.clicked.connect(self.cancelRequested.emit)

        self.person_id: Optional[str] = None
        self.expected_updated_at: Optional[str] = None

    def set_teams(self, teams: List[tuple[str, str]]) -> None:
        current = self.cbo_team.currentText()
        self.cbo_team.blockSignals(True)
        self.cbo_team.clear()
        self.cbo_team.addItem("—")
        for team_id, name in teams:
            label = f"{name} ({team_id})" if name and name != team_id else team_id
            self.cbo_team.addItem(label, team_id)
        if current:
            idx = self.cbo_team.findText(current)
            if idx >= 0:
                self.cbo_team.setCurrentIndex(idx)
        self.cbo_team.blockSignals(False)

    def populate(self, person_id: str, record: Optional[CheckInRecord]) -> None:
        self.person_id = person_id
        self.expected_updated_at = record.updated_at if record else None
        self.cbo_team.setEditText(record.team_id or "—" if record else "—")
        self.cbo_role_on_team.setEditText(record.role_on_team or "")
        self.cbo_op_period.setEditText(record.operational_period or "")

    def collect(self) -> Dict[str, object]:
        if not self.person_id:
            raise RuntimeError("Person not loaded")
        payload = {
            "person_id": self.person_id,
            "team_id": self.cbo_team.currentData() or self.cbo_team.currentText().strip() or None,
            "role_on_team": self.cbo_role_on_team.currentText().strip() or None,
            "operational_period": self.cbo_op_period.currentText().strip() or None,
        }
        if self.expected_updated_at:
            payload["expected_updated_at"] = self.expected_updated_at
        return payload

    def _emit_save(self) -> None:
        try:
            payload = self.collect()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Assignment", str(exc))
            return
        self.saveRequested.emit(payload)


class IdentityTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        self.lbl_name = QLabel("", self)
        self.lbl_name.setObjectName("LblName")
        layout.addRow("Name", self.lbl_name)
        self.lbl_id = QLabel("", self)
        self.lbl_id.setObjectName("LblID")
        layout.addRow("ID", self.lbl_id)
        self.lbl_role = QLabel("", self)
        self.lbl_role.setObjectName("LblPrimaryRole")
        layout.addRow("Primary Role", self.lbl_role)
        self.lbl_certs = QLabel("", self)
        self.lbl_certs.setObjectName("LblCerts")
        self.lbl_certs.setWordWrap(True)
        layout.addRow("Certifications", self.lbl_certs)
        self.lbl_home = QLabel("", self)
        self.lbl_home.setObjectName("LblHomeUnit")
        layout.addRow("Home Unit", self.lbl_home)
        self.btn_edit = QPushButton("Edit in Personnel", self)
        self.btn_edit.setObjectName("BtnEditInPersonnel")
        self.btn_edit.setEnabled(False)
        layout.addRow("", self.btn_edit)

    def populate(self, identity: PersonnelIdentity) -> None:
        self.lbl_name.setText(identity.name)
        self.lbl_id.setText(identity.person_id)
        self.lbl_role.setText(identity.primary_role or "")
        self.lbl_certs.setText(identity.certifications or "")
        self.lbl_home.setText(identity.home_unit or "")


class HistoryTab(QWidget):
    exportRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("LstTimeline")
        layout.addWidget(self.list_widget)
        self.btn_export = QPushButton("Export 211 Line", self)
        self.btn_export.setObjectName("BtnExport211Line")
        layout.addWidget(self.btn_export)
        self.btn_export.clicked.connect(self.exportRequested.emit)

    def populate(self, history) -> None:
        self.list_widget.clear()
        for item in history:
            label = f"{item.ts} — {item.actor}: {item.event_type}"
            details = json.dumps(item.payload, ensure_ascii=False)
            list_item = QListWidgetItem(f"{label}\n{details}")
            self.list_widget.addItem(list_item)


class ConflictDialog(QDialog):
    def __init__(self, details: Dict[str, Dict], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resolve Conflict")
        layout = QVBoxLayout(self)
        info = QLabel(
            "Another user updated this record. Choose how to proceed.", self
        )
        layout.addWidget(info)
        editors = QHBoxLayout()
        self.mine_edit = QPlainTextEdit(self)
        self.mine_edit.setPlainText(json.dumps(details.get("mine", {}), indent=2))
        self.latest_edit = QPlainTextEdit(self)
        self.latest_edit.setPlainText(json.dumps(details.get("latest", {}), indent=2))
        editors.addWidget(self.mine_edit)
        editors.addWidget(self.latest_edit)
        layout.addLayout(editors)
        buttons = QDialogButtonBox(parent=self)
        self.btn_keep_mine = buttons.addButton("Keep Mine", QDialogButtonBox.AcceptRole)
        self.btn_keep_server = buttons.addButton("Keep Server", QDialogButtonBox.ActionRole)
        self.btn_merge = buttons.addButton("Merge & Apply", QDialogButtonBox.ActionRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        self.choice: Optional[str] = None
        buttons.accepted.connect(self._keep_mine)
        self.btn_keep_server.clicked.connect(self._keep_server)
        self.btn_merge.clicked.connect(self._merge)
        buttons.rejected.connect(self.reject)

    def _keep_mine(self) -> None:
        self.choice = "mine"
        self.accept()

    def _keep_server(self) -> None:
        self.choice = "server"
        self.accept()

    def _merge(self) -> None:
        self.choice = "merge"
        self.accept()

    def result_payload(self) -> Optional[Dict[str, object]]:
        if self.choice == "merge":
            try:
                return json.loads(self.mine_edit.toPlainText())
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Invalid JSON", "Unable to parse merged payload.")
                return None
        return None


class Print211Dialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Print ICS 211")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cbo_scope = QComboBox(self)
        self.cbo_scope.addItems(["CurrentFilteredRoster", "AllCheckedIn"])
        form.addRow("Scope", self.cbo_scope)

        self.chk_phone = QCheckBox("Include Phone", self)
        self.chk_phone.setChecked(True)
        form.addRow("", self.chk_phone)

        self.chk_callsign = QCheckBox("Include Callsign", self)
        self.chk_callsign.setChecked(True)
        form.addRow("", self.chk_callsign)

        self.chk_no_show = QCheckBox("Include No Show", self)
        form.addRow("", self.chk_no_show)

        self.cbo_sort = QComboBox(self)
        self.cbo_sort.addItems(["Name", "ID", "Role", "Team"])
        form.addRow("Sort By", self.cbo_sort)

        self.cbo_group = QComboBox(self)
        self.cbo_group.addItems(["None", "Team", "Role"])
        form.addRow("Group By", self.cbo_group)

        layout.addLayout(form)
        buttons = QDialogButtonBox(self)
        self.btn_print = buttons.addButton("Print", QDialogButtonBox.AcceptRole)
        self.btn_export = buttons.addButton("Export PDF", QDialogButtonBox.ActionRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        if QPrinter is None:
            self.btn_export.setEnabled(False)
            self.btn_export.setToolTip(
                "Qt Print Support is unavailable on this system."
            )
        buttons.accepted.connect(lambda: self.done(1))
        self.btn_export.clicked.connect(lambda: self.done(2))
        buttons.rejected.connect(self.reject)

    def options(self) -> Dict[str, object]:
        return {
            "scope": self.cbo_scope.currentText(),
            "include_phone": self.chk_phone.isChecked(),
            "include_callsign": self.chk_callsign.isChecked(),
            "include_no_show": self.chk_no_show.isChecked(),
            "sort": self.cbo_sort.currentText(),
            "group": self.cbo_group.currentText(),
        }


class NewCheckInDialog(QDialog):
    recordCreated = Signal(CheckInRecord)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Check-In")
        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search personnel")
        search_row.addWidget(self.search_edit)
        self.results_list = QListWidget(self)
        layout.addLayout(search_row)
        layout.addWidget(self.results_list, 1)
        self.form = CheckInForm(self)
        self.form.btn_save_new.setVisible(True)
        layout.addWidget(self.form)

        self.search_edit.textChanged.connect(self._perform_search)
        self.results_list.currentItemChanged.connect(self._select_result)
        self.form.saveRequested.connect(self._save)
        self.form.cancelRequested.connect(self.reject)

        self._service = services.get_service()
        self._current_identity: Optional[PersonnelIdentity] = None

        shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Return), self)
        shortcut.activated.connect(self._save_shortcut)

    def _perform_search(self, term: str) -> None:
        self.results_list.clear()
        if not term.strip():
            return
        results = self._service.search_personnel(term.strip())
        for identity in results:
            item = QListWidgetItem(f"{identity.name} ({identity.person_id})")
            item.setData(Qt.UserRole, identity.person_id)
            self.results_list.addItem(item)

    def _select_result(self, current: QListWidgetItem, _: Optional[QListWidgetItem]) -> None:
        if not current:
            return
        person_id = current.data(Qt.UserRole)
        identity = self._service.get_identity(person_id)
        if identity is None:
            QMessageBox.warning(self, "Not Found", "Selected identity is missing from master DB.")
            return
        self._current_identity = identity
        self.form.populate_new(identity.person_id)

    def _save(self, payload: Dict[str, object], save_and_new: bool) -> None:
        if not self._current_identity:
            QMessageBox.warning(self, "Select Person", "Choose a person to check in.")
            return
        payload["person_id"] = self._current_identity.person_id
        try:
            record = self._service.upsert_checkin(payload)
        except OfflineQueued as exc:
            record = exc.record
            QMessageBox.information(self, "Queued", "Check-in queued while offline.")
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.recordCreated.emit(record)
        if save_and_new:
            self.form.populate_new(self._current_identity.person_id)
            self.form.notes.clear()
            self.search_edit.clear()
            self.results_list.clear()
            self._current_identity = None
        else:
            self.accept()

    def _save_shortcut(self) -> None:
        try:
            payload = self.form.collect()
        except RuntimeError:
            QMessageBox.warning(self, "Select Person", "Choose a person to check in.")
            return
        self._save(payload, True)


class CheckInWindow(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CheckInWindow")
        self.service = services.get_service()
        self.current_identity: Optional[PersonnelIdentity] = None
        self.current_record: Optional[CheckInRecord] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(self._build_top_bar())

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setObjectName("MainSplit")
        layout.addWidget(self.splitter, 1)

        self.roster_pane = RosterPane(self.splitter)
        self.roster_pane.setObjectName("PaneRoster")
        self.splitter.addWidget(self.roster_pane)

        self.detail_pane = QWidget(self.splitter)
        self.detail_pane.setObjectName("PaneDetail")
        detail_layout = QVBoxLayout(self.detail_pane)
        detail_layout.setContentsMargins(6, 6, 6, 6)
        detail_layout.setSpacing(6)
        self.header_label = QLabel("Select a person to view details", self.detail_pane)
        self.header_label.setObjectName("HdrPerson")
        self.header_label.setFrameShape(QFrame.Panel)
        self.header_label.setFrameShadow(QFrame.Sunken)
        self.header_label.setWordWrap(True)
        detail_layout.addWidget(self.header_label)

        self.tab_widget = QTabWidget(self.detail_pane)
        self.tab_widget.setObjectName("TabsDetail")
        detail_layout.addWidget(self.tab_widget, 1)

        self.tab_check_in = CheckInForm(self.tab_widget)
        self.tab_check_in.setObjectName("TabCheckIn")
        self.tab_check_in.saveRequested.connect(self._handle_save)
        self.tab_check_in.cancelRequested.connect(self._reload_current)
        self.tab_widget.addTab(self.tab_check_in, "Check-In")

        self.tab_assignment = AssignmentForm(self.tab_widget)
        self.tab_assignment.setObjectName("TabAssignment")
        self.tab_assignment.saveRequested.connect(self._handle_assignment_save)
        self.tab_assignment.cancelRequested.connect(self._reload_current)
        self.tab_widget.addTab(self.tab_assignment, "Assignment")

        self.tab_identity = IdentityTab(self.tab_widget)
        self.tab_identity.setObjectName("TabIdentity")
        self.tab_widget.addTab(self.tab_identity, "Identity")

        self.tab_history = HistoryTab(self.tab_widget)
        self.tab_history.setObjectName("TabHistory")
        self.tab_history.exportRequested.connect(self._export_211_line)
        self.tab_widget.addTab(self.tab_history, "History")

        self.roster_pane.filterChanged.connect(self.refresh_roster)
        self.roster_pane.rowActivated.connect(self.load_person)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(1000)
        self._autosave_timer.timeout.connect(self._update_autosave_label)
        self._autosave_timer.start()
        self._last_saved: Optional[datetime] = None

        self._register_shortcuts()
        self.refresh_filters()
        self.refresh_roster()

    def _build_top_bar(self) -> QWidget:
        bar = QWidget(self)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(6)
        self.btn_new = QPushButton("New Check-In", bar)
        self.btn_new.setObjectName("BtnNewCheckIn")
        self.btn_import = QPushButton("Batch Import", bar)
        self.btn_import.setObjectName("BtnBatchImport")
        self.btn_print = QPushButton("Print 211", bar)
        self.btn_print.setObjectName("BtnPrint211")
        self.btn_close = QPushButton("Close", bar)
        self.btn_close.setObjectName("BtnClose")
        bar_layout.addWidget(self.btn_new)
        bar_layout.addWidget(self.btn_import)
        bar_layout.addWidget(self.btn_print)
        bar_layout.addStretch(1)
        self.lbl_autosave = QLabel("", bar)
        self.lbl_autosave.setObjectName("LblAutosave")
        bar_layout.addWidget(self.lbl_autosave)
        bar_layout.addWidget(self.btn_close)

        self.btn_new.clicked.connect(self._open_new_dialog)
        self.btn_import.clicked.connect(lambda: QMessageBox.information(self, "Import", "Batch import not implemented in this build."))
        self.btn_print.clicked.connect(self._print_211)
        self.btn_close.clicked.connect(self.close)
        return bar

    def _register_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_N), self, activated=self._open_new_dialog)
        QShortcut(QKeySequence(Qt.CTRL | Qt.Key_S), self, activated=self._shortcut_save)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._clear_selection)

    def _shortcut_save(self) -> None:
        if self.tab_widget.currentWidget() is self.tab_check_in:
            try:
                payload = self.tab_check_in.collect()
            except RuntimeError:
                return
            self._handle_save(payload, False)
        elif self.tab_widget.currentWidget() is self.tab_assignment:
            payload = self.tab_assignment.collect()
            self._handle_assignment_save(payload)

    def _clear_selection(self) -> None:
        self.roster_pane.table.clearSelection()
        self.header_label.setText("Select a person to view details")
        self.current_identity = None
        self.current_record = None

    # Data loading ---------------------------------------------------------
    def refresh_filters(self) -> None:
        self.roster_pane.set_roles(self.service.list_roles())
        teams = self.service.list_teams()
        self.roster_pane.set_teams(teams)
        self.tab_assignment.set_teams(teams)

    def refresh_roster(self) -> None:
        rows = self.service.get_roster(self.roster_pane.filters())
        self.roster_pane.update_rows(rows)

    def load_person(self, person_id: str) -> None:
        identity = self.service.get_identity(person_id)
        record = self.service.get_checkin(person_id)
        if not identity or not record:
            QMessageBox.warning(self, "Missing Record", "Unable to load check-in record.")
            return
        self.current_identity = identity
        self.current_record = record
        self.tab_check_in.populate(person_id, record)
        self.tab_assignment.populate(person_id, record)
        self.tab_identity.populate(identity)
        self.tab_history.populate(self.service.get_history(person_id))
        self._update_header(identity, record)
        self.roster_pane.select_person(person_id)

    def _update_header(self, identity: PersonnelIdentity, record: CheckInRecord) -> None:
        parts = [identity.name, f"{identity.person_id}"]
        role = record.role_on_team or identity.primary_role
        team = record.team_id or "—"
        callsign = record.incident_callsign or identity.callsign or ""
        phone = record.incident_phone or identity.phone or ""
        summary = f"{parts[0]} ({parts[1]}) — Role: {role or '—'} | Team: {team} | Callsign: {callsign or '—'} | Phone: {phone or '—'}"
        self.header_label.setText(summary)

    def _reload_current(self) -> None:
        if self.current_identity:
            self.load_person(self.current_identity.person_id)

    # Saving ---------------------------------------------------------------
    def _handle_save(self, payload: Dict[str, object], save_and_new: bool = False) -> None:
        try:
            record = self.service.upsert_checkin(payload)
        except OfflineQueued as exc:
            record = exc.record
            self.service.set_offline(True)
            QMessageBox.information(self, "Queued", "Operation queued while offline.")
        except ConflictError as exc:
            self._handle_conflict(payload, exc)
            return
        except (PermissionDenied, NoShowGuardError, ValueError) as exc:
            QMessageBox.warning(self, "Unable to Save", str(exc))
            return
        self.current_record = record
        self._last_saved = datetime.now().astimezone()
        self.service.set_offline(False)
        self.refresh_roster()
        if record:
            self.load_person(record.person_id)
        if save_and_new:
            self._open_new_dialog()

    def _handle_assignment_save(self, payload: Dict[str, object]) -> None:
        if not self.current_record:
            return
        payload = {**self.tab_check_in.collect(), **payload}
        # ensure required fields present
        payload.setdefault("ci_status", self.current_record.ci_status.value)
        payload.setdefault("arrival_time", self.current_record.arrival_time)
        payload.setdefault("location", self.current_record.location.value)
        self._handle_save(payload, False)

    def _handle_conflict(self, payload: Dict[str, object], exc: ConflictError) -> None:
        dialog = ConflictDialog({"mine": exc.details.mine, "latest": exc.details.latest}, self)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.choice == "server":
            self.refresh_roster()
            if self.current_identity:
                self.load_person(self.current_identity.person_id)
            return
        if dialog.choice == "merge":
            merged = dialog.result_payload()
            if not merged:
                return
            merged.setdefault("person_id", payload.get("person_id"))
            merged.setdefault("arrival_time", payload.get("arrival_time"))
            merged.setdefault("location", payload.get("location"))
            merged["expected_updated_at"] = exc.details.latest.get("updated_at")
            self._handle_save(merged, False)
            return
        # Keep mine - use latest updated_at
        payload["expected_updated_at"] = exc.details.latest.get("updated_at")
        self._handle_save(payload, False)

    # Printing & Export ----------------------------------------------------
    def _export_211_line(self) -> None:
        if not self.current_identity or not self.current_record:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export 211 Line", str(Path.home() / "checkin.csv"), "CSV Files (*.csv)")
        if not path:
            return
        fields = [
            self.current_identity.person_id,
            self.current_identity.name,
            self.current_record.ci_status.value,
            self.current_record.personnel_status.value,
            self.current_record.team_id or "",
            self.current_record.role_on_team or "",
            self.current_record.arrival_time,
        ]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(",".join(f'"{value}"' for value in fields))
        QMessageBox.information(self, "Exported", f"Exported to {path}")

    def _print_211(self) -> None:
        dialog = Print211Dialog(self)
        result = dialog.exec()
        if result <= 0:
            return
        options = dialog.options()
        rows = self.service.get_roster({"include_no_show": options.get("include_no_show")})
        if options.get("scope") == "CurrentFilteredRoster":
            rows = self.service.get_roster(self.roster_pane.filters())
        if not options.get("include_no_show"):
            rows = [row for row in rows if row.ci_status is not CIStatus.NO_SHOW]
        sort_key = options.get("sort", "Name").lower()
        rows.sort(key=lambda r: getattr(r, sort_key, r.name).lower())
        if result == 1:
            QMessageBox.information(self, "Print", "Send to printer.")
        else:
            if QPrinter is None:
                QMessageBox.warning(
                    self,
                    "Print Support Unavailable",
                    "Qt Print Support is not available; PDF export is disabled.",
                )
                return
            path, _ = QFileDialog.getSaveFileName(self, "Export PDF", str(Path.home() / "ics211.pdf"), "PDF Files (*.pdf)")
            if not path:
                return
            printer = QPrinter()
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            html_rows = []
            for row in rows:
                html_rows.append(
                    "<tr>" + "".join(
                        f"<td>{value}</td>"
                        for value in [
                            row.person_id,
                            row.name,
                            row.role or "",
                            row.team or "",
                            row.phone or "",
                            row.callsign or "",
                            row.ci_status.value,
                        ]
                    ) + "</tr>"
                )
            html = "<table border='1' cellspacing='0' cellpadding='4'>" + "".join(html_rows) + "</table>"
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print(printer)
            QMessageBox.information(self, "Exported", f"Saved to {path}")

    # Offline + autosave ---------------------------------------------------
    def _update_autosave_label(self) -> None:
        pending = self.service.pending_count()
        if pending:
            self.lbl_autosave.setText(f"Working offline — {pending} pending")
            return
        if self._last_saved is None:
            self.lbl_autosave.setText("")
            return
        delta = int((datetime.now().astimezone() - self._last_saved).total_seconds())
        self.lbl_autosave.setText(f"Autosaved {delta}s ago")

    # Dialogs --------------------------------------------------------------
    def _open_new_dialog(self) -> None:
        dialog = NewCheckInDialog(self)
        dialog.recordCreated.connect(self._handle_new_record)
        dialog.exec()

    def _handle_new_record(self, record: CheckInRecord) -> None:
        self._last_saved = datetime.now().astimezone()
        self.refresh_roster()
        if record.pending:
            self.roster_pane.select_person(record.person_id)
        else:
            self.load_person(record.person_id)


__all__ = ["CheckInWindow"]
