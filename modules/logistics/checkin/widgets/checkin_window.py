"""Unified Logistics Resource Check-In and Status Board (Qt Widgets).

This module replaces the older tab + bottom editor workflow with a board-first
experience that is optimized for high-volume incident intake.  The design keeps
single-click row selection lightweight and uses double-click or explicit actions
for full editing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from utils.state import AppState
from utils.org_combo import make_org_combo

from modules.logistics.checkin.services import (
    ENTITY_CONFIG,
    CheckInService,
    EntityConfig,
    get_service as get_checkin_service,
)
from modules.logistics.resource_status.models import RESOURCE_STATUSES, ResourceItem, format_display_datetime
from modules.logistics.resource_status.service import ResourceStatusService, get_service as get_resource_status_service


STATUS_COLORS: dict[str, tuple[str, str]] = {
    "Pending": ("#fff8e1", "#5d4037"),
    "Enroute": ("#e3f2fd", "#0d47a1"),
    "Checked In": ("#e8f5e9", "#1b5e20"),
    "Assigned": ("#ede7f6", "#4527a0"),
    "Available": ("#e0f2f1", "#004d40"),
    "Out of Service": ("#fbe9e7", "#bf360c"),
    "Demobilized": ("#eceff1", "#37474f"),
}

RESOURCE_TYPE_OPTIONS = ["All", "Personnel", "Vehicle", "Equipment", "Aircraft"]
ENTITY_FROM_LABEL = {
    "Personnel": "personnel",
    "Vehicle": "vehicle",
    "Equipment": "equipment",
    "Aircraft": "aircraft",
}
LABEL_FROM_ENTITY = {v: k for k, v in ENTITY_FROM_LABEL.items()}


@dataclass(slots=True)
class BoardRow:
    """Flattened row shown in the table.

    Each row blends incident-specific tracking data (status, assignment, ETA,
    check-in time) with optional master/source details (callsign, role, plate,
    tail number, etc.) so that one table can serve all resource types.
    """

    status_item: ResourceItem
    name_identifier: str
    organization: str
    assigned_to: str
    location: str
    notes_flag: str
    role: str = ""
    team: str = ""
    callsign: str = ""
    vehicle_unit: str = ""
    vehicle_kind: str = ""
    plate: str = ""
    equipment_tag: str = ""
    equipment_type: str = ""
    holder: str = ""
    tail_number: str = ""
    aircraft_type: str = ""
    crew_lead: str = ""
    base_airport: str = ""


class ResourceBoardTableModel(QAbstractTableModel):
    """Table model for the unified incident resource board."""

    COLUMNS = [
        "Resource ID",
        "Resource Type",
        "Name / Identifier",
        "Organization",
        "Assigned To",
        "Status",
        "ETA",
        "Arrival / Check-In Time",
        "Location",
        "Notes",
        "Role",
        "Team",
        "Callsign",
        "Vehicle ID / Unit",
        "Vehicle Type",
        "Plate",
        "Asset Tag",
        "Equipment Type",
        "Current Holder",
        "Tail Number",
        "Aircraft Type",
        "Crew Lead",
        "Base / Airport",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._all_rows: list[BoardRow] = []
        self._visible_rows: list[BoardRow] = []

    def set_rows(self, rows: list[BoardRow]) -> None:
        self.beginResetModel()
        self._all_rows = list(rows)
        self._visible_rows = list(rows)
        self.endResetModel()

    def apply_filters(
        self,
        text: str,
        resource_type: str,
        status: str,
        waiting_only: bool,
        current_section_only: bool,
    ) -> None:
        """Apply all user-selected filters in one pass for speed."""

        text_norm = text.strip().lower()
        active_section = (AppState.get_active_user_role() or "").strip().lower()

        def _matches(row: BoardRow) -> bool:
            item = row.status_item
            if resource_type != "All" and item.resource_type != resource_type:
                return False
            if status != "All" and item.status != status:
                return False
            if waiting_only and item.status not in {"Pending", "Enroute"}:
                return False
            if current_section_only and active_section:
                assigned = (row.assigned_to or "").lower()
                if active_section not in assigned:
                    return False
            if text_norm:
                haystack = "|".join(
                    [
                        item.resource_id,
                        row.name_identifier,
                        row.organization,
                        row.assigned_to,
                        item.status,
                        row.location,
                        row.callsign,
                        row.tail_number,
                        row.equipment_tag,
                        row.vehicle_unit,
                    ]
                ).lower()
                return text_norm in haystack
            return True

        self.beginResetModel()
        self._visible_rows = [row for row in self._all_rows if _matches(row)]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._visible_rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # noqa: N802
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._visible_rows)):
            return None
        row = self._visible_rows[index.row()]
        item = row.status_item

        value_map = {
            0: item.resource_id,
            1: item.resource_type,
            2: row.name_identifier,
            3: row.organization,
            4: row.assigned_to,
            5: item.status,
            6: format_display_datetime(item.eta_utc),
            7: format_display_datetime(item.checked_in_time),
            8: row.location,
            9: row.notes_flag,
            10: row.role,
            11: row.team,
            12: row.callsign,
            13: row.vehicle_unit,
            14: row.vehicle_kind,
            15: row.plate,
            16: row.equipment_tag,
            17: row.equipment_type,
            18: row.holder,
            19: row.tail_number,
            20: row.aircraft_type,
            21: row.crew_lead,
            22: row.base_airport,
        }

        if role == Qt.DisplayRole:
            return value_map.get(index.column(), "")

        if role == Qt.BackgroundRole:
            if item.status == "Demobilized":
                return QBrush(QColor("#d6d8db"))
            bg, _ = STATUS_COLORS.get(item.status, ("#ffffff", "#202020"))
            return QBrush(QColor(bg))

        if role == Qt.ForegroundRole:
            _, fg = STATUS_COLORS.get(item.status, ("#ffffff", "#202020"))
            return QBrush(QColor(fg))

        if role == Qt.UserRole:
            return row
        return None

    def row_at(self, model_row: int) -> Optional[BoardRow]:
        if 0 <= model_row < len(self._visible_rows):
            return self._visible_rows[model_row]
        return None


class ResourceDetailDialog(QDialog):
    """Full resource detail editor opened from double-click or toolbar action."""

    def __init__(self, row: BoardRow, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resource Details")
        self._row = row
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.resource_id = QLineEdit(self._row.status_item.resource_id)
        self.resource_type = QLineEdit(self._row.status_item.resource_type)
        self.name = QLineEdit(self._row.name_identifier)
        self.organization = make_org_combo(self._row.organization)
        self.status = QComboBox()
        self.status.addItems(RESOURCE_STATUSES)
        self.status.setCurrentText(self._row.status_item.status)
        self.assigned_to = QLineEdit(self._row.assigned_to)
        self.location = QLineEdit(self._row.location)
        self.eta = QLineEdit(self._row.status_item.eta_utc or "")
        self.notes = QTextEdit(self._row.status_item.notes or "")

        form.addRow("Resource ID", self.resource_id)
        form.addRow("Resource Type", self.resource_type)
        form.addRow("Name / Identifier", self.name)
        form.addRow("Organization", self.organization)
        form.addRow("Status", self.status)
        form.addRow("Assigned To", self.assigned_to)
        form.addRow("Location", self.location)
        form.addRow("ETA", self.eta)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)

        self.audit_preview = QTextEdit()
        self.audit_preview.setReadOnly(True)
        self.audit_preview.setPlaceholderText("Audit history appears here when available.")
        layout.addWidget(QLabel("Status History / Audit"))
        layout.addWidget(self.audit_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def payload(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id.text().strip(),
            "resource_type": self.resource_type.text().strip(),
            "resource_name": self.name.text().strip(),
            "status": self.status.currentText(),
            "assigned_to": self.assigned_to.text().strip() or None,
            "location": self.location.text().strip() or None,
            "eta_utc": self.eta.text().strip() or None,
            "notes": self.notes.toPlainText().strip() or None,
        }


class QuickCheckInDialog(QDialog):
    """Fast keyboard/scanner modal for repetitive intake."""

    processed = Signal()

    def __init__(self, board: "CheckInWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Check-In")
        self.setModal(True)
        self._board = board
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top = QGridLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Personnel", "Vehicle", "Equipment", "Aircraft"])
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Scan or type ID, callsign, tag, tail number, then press Enter")
        self.id_input.setMinimumHeight(40)
        self.status_combo = QComboBox()
        self.status_combo.addItems(list(RESOURCE_STATUSES))
        self.status_combo.setCurrentText("Checked In")

        top.addWidget(QLabel("Resource Type"), 0, 0)
        top.addWidget(self.type_combo, 0, 1)
        top.addWidget(QLabel("ID / Tag Input"), 1, 0)
        top.addWidget(self.id_input, 1, 1)
        top.addWidget(QLabel("Status"), 2, 0)
        top.addWidget(self.status_combo, 2, 1)

        self.eta_input = QLineEdit()
        self.eta_input.setPlaceholderText("ETA (optional)")
        self.assignment_input = QLineEdit()
        self.assignment_input.setPlaceholderText("Team / section / location")
        self.oos_reason = QLineEdit()
        self.oos_reason.setPlaceholderText("Out of service reason (optional)")
        top.addWidget(self.eta_input, 3, 1)
        top.addWidget(self.assignment_input, 4, 1)
        top.addWidget(self.oos_reason, 5, 1)

        layout.addLayout(top)

        self.result_strip = QLabel("Ready")
        self.result_strip.setFrameShape(QFrame.StyledPanel)
        self.result_strip.setMinimumHeight(32)
        layout.addWidget(self.result_strip)

        layout.addWidget(QLabel("Create New (shown when not found)"))
        self.create_stack = QStackedWidget(self)
        self.create_stack.addWidget(self._build_personnel_create_form())
        self.create_stack.addWidget(self._build_vehicle_create_form())
        self.create_stack.addWidget(self._build_equipment_create_form())
        self.create_stack.addWidget(self._build_aircraft_create_form())
        layout.addWidget(self.create_stack)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_create = QPushButton("Create New")
        self.btn_open = QPushButton("Open Full Record")
        self.btn_close = QPushButton("Close")
        buttons.addWidget(self.btn_add)
        buttons.addWidget(self.btn_create)
        buttons.addWidget(self.btn_open)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

        self.type_combo.currentIndexChanged.connect(self._sync_create_stack)
        self.status_combo.currentTextChanged.connect(self._sync_status_fields)
        self.id_input.returnPressed.connect(self._on_add)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_create.clicked.connect(self._on_create_new)
        self.btn_open.clicked.connect(self._on_open_record)
        self.btn_close.clicked.connect(self.reject)

        self._sync_create_stack()
        self._sync_status_fields()

    def _build_personnel_create_form(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        self.new_personnel_id = QLineEdit()
        self.new_personnel_name = QLineEdit()
        self.new_personnel_callsign = QLineEdit()
        self.new_personnel_role = QLineEdit()
        self.new_personnel_org = make_org_combo()
        form.addRow("ID", self.new_personnel_id)
        form.addRow("Name", self.new_personnel_name)
        form.addRow("Callsign", self.new_personnel_callsign)
        form.addRow("Role", self.new_personnel_role)
        form.addRow("Organization", self.new_personnel_org)
        return w

    def _build_vehicle_create_form(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        self.new_vehicle_id = QLineEdit()
        self.new_vehicle_type = QLineEdit()
        self.new_vehicle_org = make_org_combo()
        self.new_vehicle_plate = QLineEdit()
        form.addRow("Vehicle ID", self.new_vehicle_id)
        form.addRow("Type", self.new_vehicle_type)
        form.addRow("Organization", self.new_vehicle_org)
        form.addRow("Plate", self.new_vehicle_plate)
        return w

    def _build_equipment_create_form(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        self.new_equipment_tag = QLineEdit()
        self.new_equipment_name = QLineEdit()
        self.new_equipment_type = QLineEdit()
        self.new_equipment_org = make_org_combo()
        form.addRow("Asset Tag / ID", self.new_equipment_tag)
        form.addRow("Name", self.new_equipment_name)
        form.addRow("Type", self.new_equipment_type)
        form.addRow("Organization", self.new_equipment_org)
        return w

    def _build_aircraft_create_form(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        self.new_air_tail = QLineEdit()
        self.new_air_callsign = QLineEdit()
        self.new_air_type = QLineEdit()
        self.new_air_org = make_org_combo()
        self.new_air_base = QLineEdit()
        form.addRow("Tail Number", self.new_air_tail)
        form.addRow("Callsign", self.new_air_callsign)
        form.addRow("Type", self.new_air_type)
        form.addRow("Organization", self.new_air_org)
        form.addRow("Base / Airport", self.new_air_base)
        return w

    def _sync_create_stack(self) -> None:
        self.create_stack.setCurrentIndex(self.type_combo.currentIndex())

    def _sync_status_fields(self) -> None:
        status = self.status_combo.currentText()
        self.eta_input.setVisible(status in {"Pending", "Enroute"})
        self.assignment_input.setVisible(status == "Assigned")
        self.oos_reason.setVisible(status == "Out of Service")

    def _status_patch(self) -> dict[str, Any]:
        status = self.status_combo.currentText()
        patch: dict[str, Any] = {"status": status}
        if status in {"Pending", "Enroute"}:
            patch["eta_utc"] = self.eta_input.text().strip() or None
        if status == "Checked In":
            patch["checked_in_time"] = datetime.now().astimezone().isoformat(timespec="seconds")
        if status == "Assigned":
            patch["assigned_to"] = self.assignment_input.text().strip() or None
        if status == "Out of Service":
            patch["notes"] = self.oos_reason.text().strip() or None
        return patch

    def _on_add(self) -> None:
        typed = self.id_input.text().strip()
        if not typed:
            self.result_strip.setText("Enter or scan an ID first.")
            return
        entity_key = ENTITY_FROM_LABEL[self.type_combo.currentText()]
        result = self._board.quick_check_in(entity_key, typed, self._status_patch())
        self.result_strip.setText(result)
        self.id_input.clear()
        self.id_input.setFocus()
        self.processed.emit()

    def _on_create_new(self) -> None:
        entity_key = ENTITY_FROM_LABEL[self.type_combo.currentText()]
        try:
            created = self._board.create_inline_resource(entity_key, self._collect_create_payload(entity_key), self._status_patch())
        except Exception as exc:  # noqa: BLE001
            self.result_strip.setText(f"Create failed: {exc}")
            return
        self.result_strip.setText(f"Created and checked in: {created}")
        self.id_input.clear()
        self.id_input.setFocus()
        self.processed.emit()

    def _collect_create_payload(self, entity_key: str) -> dict[str, Any]:
        if entity_key == "personnel":
            return {
                "id": self.new_personnel_id.text().strip() or None,
                "name": self.new_personnel_name.text().strip(),
                "callsign": self.new_personnel_callsign.text().strip(),
                "role": self.new_personnel_role.text().strip(),
                "unit": self.new_personnel_org.currentText().strip(),
            }
        if entity_key == "vehicle":
            return {
                "id": self.new_vehicle_id.text().strip(),
                "type_id": self.new_vehicle_type.text().strip(),
                "organization": self.new_vehicle_org.currentText().strip(),
                "license_plate": self.new_vehicle_plate.text().strip(),
            }
        if entity_key == "equipment":
            return {
                "id": self.new_equipment_tag.text().strip() or None,
                "name": self.new_equipment_name.text().strip(),
                "type": self.new_equipment_type.text().strip(),
                "notes": self.new_equipment_org.currentText().strip(),
            }
        return {
            "tail_number": self.new_air_tail.text().strip(),
            "callsign": self.new_air_callsign.text().strip(),
            "type": self.new_air_type.text().strip(),
            "organization": self.new_air_org.currentText().strip(),
            "base_location": self.new_air_base.text().strip(),
        }

    def _on_open_record(self) -> None:
        self._board.open_selected_details()


class CheckInWindow(QWidget):
    """Unified Resource Check-In / Status Board main window."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        checkin_service: Optional[CheckInService] = None,
        resource_status_service: Optional[ResourceStatusService] = None,
    ) -> None:
        super().__init__(parent)
        self._checkin_service = checkin_service or get_checkin_service()
        self._status_service = resource_status_service or get_resource_status_service()
        self._model = ResourceBoardTableModel(self)
        self._build_ui()
        self.refresh_board()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Resource Check-In / Status Board")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search ID, name, callsign, tail number, asset tag, vehicle ID")
        self.type_filter = QComboBox()
        self.type_filter.addItems(RESOURCE_TYPE_OPTIONS)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All")
        self.status_filter.addItems(list(RESOURCE_STATUSES))
        self.waiting_only = QCheckBox("Waiting arrivals only")
        self.section_only = QCheckBox("Current section only")
        filter_row.addWidget(self.search_input, 2)
        filter_row.addWidget(self.type_filter)
        filter_row.addWidget(self.status_filter)
        filter_row.addWidget(self.waiting_only)
        filter_row.addWidget(self.section_only)
        layout.addLayout(filter_row)

        self.toolbar = QToolBar("Resource Actions", self)
        for label, handler in [
            ("New Resource", self._open_quick_checkin),
            ("Quick Check-In", self._open_quick_checkin),
            ("Mark Pending", lambda: self._apply_status_bulk("Pending")),
            ("Mark Enroute", lambda: self._apply_status_bulk("Enroute")),
            ("Mark Checked In", lambda: self._apply_status_bulk("Checked In")),
            ("Mark Assigned", lambda: self._apply_status_bulk("Assigned")),
            ("Mark Available", lambda: self._apply_status_bulk("Available")),
            ("Mark Out of Service", lambda: self._apply_status_bulk("Out of Service")),
            ("Mark Demobilized", lambda: self._apply_status_bulk("Demobilized")),
            ("Assign", self._assign_selected),
            ("Open Details", self.open_selected_details),
            ("View Audit Log", self._view_selected_audit),
            ("Refresh", self.refresh_board),
        ]:
            action = QAction(label, self)
            action.triggered.connect(handler)
            self.toolbar.addAction(action)
        layout.addWidget(self.toolbar)

        self.table = QTableView(self)
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.doubleClicked.connect(self._open_details_from_index)
        self.table.customContextMenuRequested.connect(self._open_context_menu)
        layout.addWidget(self.table, 1)

        self.quick_button = QPushButton("Open Quick Check-In")
        self.quick_button.clicked.connect(self._open_quick_checkin)
        layout.addWidget(self.quick_button)

        self.search_input.textChanged.connect(self._apply_filters)
        self.type_filter.currentTextChanged.connect(self._apply_filters)
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        self.waiting_only.toggled.connect(self._apply_filters)
        self.section_only.toggled.connect(self._apply_filters)

    def _open_context_menu(self, point: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("Open Details", self.open_selected_details)
        menu.addSeparator()
        for status in RESOURCE_STATUSES:
            menu.addAction(f"Mark {status}", lambda s=status: self._apply_status_bulk(s))
        menu.exec(self.table.viewport().mapToGlobal(point))

    def _selected_rows(self) -> list[BoardRow]:
        rows: list[BoardRow] = []
        for index in self.table.selectionModel().selectedRows():
            row = self._model.row_at(index.row())
            if row:
                rows.append(row)
        return rows

    def _open_quick_checkin(self) -> None:
        dlg = QuickCheckInDialog(self, self)
        dlg.processed.connect(self.refresh_board)
        dlg.exec()

    def _open_details_from_index(self, index: QModelIndex) -> None:
        row = self._model.row_at(index.row())
        if not row:
            return
        self._open_details_for_row(row)

    def open_selected_details(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Open Details", "Select a resource row first.")
            return
        self._open_details_for_row(rows[0])

    def _open_details_for_row(self, row: BoardRow) -> None:
        dialog = ResourceDetailDialog(row, self)
        for entry in self._status_service.list_audit_entries(row.status_item.id, limit=30):
            dialog.audit_preview.append(
                f"{entry.get('changed_at')} | {entry.get('field_name')} | {entry.get('old_value')} -> {entry.get('new_value')}"
            )
        if dialog.exec() == QDialog.Accepted:
            self._status_service.update_resource(row.status_item.id, dialog.payload(), actor_name="Logistics Detail Editor")
            self.refresh_board()

    def _apply_status_bulk(self, status: str) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        for row in rows:
            patch: dict[str, Any] = {"status": status}
            if status == "Checked In":
                patch["checked_in_time"] = datetime.now().astimezone().isoformat(timespec="seconds")
            if status == "Out of Service" and row.status_item.resource_type in {"Vehicle", "Equipment", "Aircraft"}:
                patch["assigned_to"] = None
            self._status_service.update_resource(row.status_item.id, patch, actor_name="Bulk Status Update")
        self.refresh_board()

    def _assign_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        target, ok = QInputDialogCompat.get_text(self, "Assign", "Assign selected rows to team/location/section:")
        if not ok:
            return
        for row in rows:
            self._status_service.update_resource(
                row.status_item.id,
                {"status": "Assigned", "assigned_to": target},
                actor_name="Bulk Assignment",
            )
        self.refresh_board()

    def _view_selected_audit(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        entries = self._status_service.list_audit_entries(rows[0].status_item.id, limit=100)
        text = "\n".join(
            f"{entry.get('changed_at')} | {entry.get('field_name')} | {entry.get('old_value')} -> {entry.get('new_value')}"
            for entry in entries
        ) or "No audit entries found."
        QMessageBox.information(self, "Audit Log", text)

    def refresh_board(self) -> None:
        items = self._status_service.list_resources()
        enriched = self._enrich_rows(items)
        self._model.set_rows(enriched)
        self._apply_filters()
        self.table.resizeColumnsToContents()

    def _apply_filters(self) -> None:
        self._model.apply_filters(
            self.search_input.text(),
            self.type_filter.currentText(),
            self.status_filter.currentText(),
            self.waiting_only.isChecked(),
            self.section_only.isChecked(),
        )

    def _enrich_rows(self, items: list[ResourceItem]) -> list[BoardRow]:
        details = self._source_detail_map(items)
        rows: list[BoardRow] = []
        for item in items:
            key = (item.source_entity_type or "", item.source_record_id or "")
            source = details.get(key, {})
            name_identifier = item.resource_name or str(source.get("name") or source.get("callsign") or item.resource_id)
            organization = str(source.get("organization") or source.get("unit") or "")
            rows.append(
                BoardRow(
                    status_item=item,
                    name_identifier=name_identifier,
                    organization=organization,
                    assigned_to=item.assigned_to or "",
                    location=item.location or "",
                    notes_flag="ÃƒÂ¢Ã…Â¡Ã¢â‚¬Ëœ" if (item.notes or "").strip() else "",
                    role=str(source.get("role") or ""),
                    team=str(source.get("team_id") or ""),
                    callsign=str(source.get("callsign") or ""),
                    vehicle_unit=str(source.get("id") if item.resource_type == "Vehicle" else ""),
                    vehicle_kind=str(source.get("type_id") or ""),
                    plate=str(source.get("license_plate") or ""),
                    equipment_tag=str(source.get("id") if item.resource_type == "Equipment" else ""),
                    equipment_type=str(source.get("type") or ""),
                    holder=str(source.get("current_holder_id") or ""),
                    tail_number=str(source.get("tail_number") or ""),
                    aircraft_type=str(source.get("type") if item.resource_type == "Aircraft" else ""),
                    crew_lead=str(source.get("crew_lead") or ""),
                    base_airport=str(source.get("base_location") or ""),
                )
            )
        return rows

    def _source_detail_map(self, items: list[ResourceItem]) -> dict[tuple[str, str], dict[str, Any]]:
        """Read incident checked-in resources and map them for type-aware columns."""

        from utils import incident_context
        from utils.api_client import api_client

        incident_id = incident_context.get_active_incident_id()
        map_out: dict[tuple[str, str], dict[str, Any]] = {}
        if not incident_id:
            return map_out

        by_entity: dict[str, set[str]] = {}
        for item in items:
            if item.source_entity_type and item.source_record_id:
                by_entity.setdefault(item.source_entity_type, set()).add(item.source_record_id)

        for entity, ids in by_entity.items():
            if not ids:
                continue
            try:
                docs = api_client.get(
                    f"/api/incidents/{incident_id}/resources",
                    params={"resource_type": entity},
                ) or []
            except Exception:
                continue
            for doc in docs:
                rid = str(doc.get("resource_id") or doc.get("id") or doc.get("int_id") or "")
                if rid in ids:
                    map_out[(entity, rid)] = doc

        return map_out

    def quick_check_in(self, entity_key: str, typed_value: str, status_patch: dict[str, Any]) -> str:
        """Quick intake path used by scanner/keyboard workflows."""

        matched = self._find_existing_record(entity_key, typed_value)
        if not matched:
            return f"Not found: {typed_value}. Use Create New to add it inline."

        record_id = matched.get(ENTITY_CONFIG[entity_key].id_column)
        checked = self._checkin_service.check_in(entity_key, record_id)
        self._upsert_status_row(entity_key, checked, status_patch)
        return f"Updated {typed_value} as {status_patch.get('status')}"

    def create_inline_resource(self, entity_key: str, create_payload: dict[str, Any], status_patch: dict[str, Any]) -> str:
        """Create a missing master record from the Quick Check-In modal and apply status."""

        payload = {k: v for k, v in create_payload.items() if v not in (None, "")}
        if not payload:
            raise ValueError("Enter required fields before creating a new resource.")
        created = self._checkin_service.create_master_record(entity_key, payload)
        record_id = created.get(ENTITY_CONFIG[entity_key].id_column)
        checked = self._checkin_service.check_in(entity_key, record_id)
        self._upsert_status_row(entity_key, checked, status_patch)
        return str(record_id)

    def _find_existing_record(self, entity_key: str, typed_value: str) -> Optional[dict[str, Any]]:
        config: EntityConfig = ENTITY_CONFIG[entity_key]
        results = self._checkin_service.search_master_records(entity_key, typed_value, limit=30)
        for row in results:
            exact_values = [
                str(row.get(config.id_column) or "").strip().lower(),
                str(row.get("callsign") or "").strip().lower(),
                str(row.get("tail_number") or "").strip().lower(),
                str(row.get("serial_number") or "").strip().lower(),
                str(row.get("license_plate") or "").strip().lower(),
            ]
            if typed_value.strip().lower() in exact_values:
                return row
        return results[0] if results else None

    def _upsert_status_row(self, entity_key: str, checked_record: dict[str, Any], status_patch: dict[str, Any]) -> None:
        source_id = str(checked_record.get(ENTITY_CONFIG[entity_key].id_column) or "")
        existing = self._status_service.repository.get_by_source(entity_key, source_id)

        resource_name = str(
            checked_record.get("name")
            or checked_record.get("callsign")
            or checked_record.get("tail_number")
            or checked_record.get("id")
            or source_id
        )
        resource_type = LABEL_FROM_ENTITY.get(entity_key, entity_key.title())

        if existing is None:
            payload = {
                "resource_id": source_id,
                "resource_name": resource_name,
                "resource_type": resource_type,
                "status": status_patch.get("status", "Checked In"),
                "eta_utc": status_patch.get("eta_utc"),
                "assigned_to": status_patch.get("assigned_to"),
                "checked_in_time": status_patch.get("checked_in_time"),
                "notes": status_patch.get("notes"),
                "source_entity_type": entity_key,
                "source_record_id": source_id,
            }
            self._status_service.create_resource(payload, actor_name="Quick Check-In")
            return

        patch = dict(status_patch)
        if patch.get("status") == "Out of Service" and resource_type in {"Vehicle", "Equipment", "Aircraft"}:
            patch["assigned_to"] = None
        self._status_service.update_resource(existing.id, patch, actor_name="Quick Check-In")


class QInputDialogCompat:
    """Small helper so this module does not depend on static dialog APIs in tests."""

    @staticmethod
    def get_text(parent: QWidget, title: str, prompt: str) -> tuple[str, bool]:
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        v = QVBoxLayout(dialog)
        v.addWidget(QLabel(prompt))
        edit = QLineEdit(dialog)
        v.addWidget(edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        ok = dialog.exec() == QDialog.Accepted
        return edit.text().strip(), ok


__all__ = ["CheckInWindow"]
