"""Desktop resource status board for the Logistics module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, Signal

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.facilities import FacilityPicker
from modules.logistics.facilities.service import FacilitiesService
from styles.styles import resource_status_colors, subscribe_theme
from utils.table_view_styles import apply_statusboard_table_behavior

from modules.logistics.resource_status import RESOURCE_STATUSES, ResourceBoardFilters
from modules.logistics.resource_status.models import ResourceItem, format_display_datetime, parse_datetime
from modules.logistics.resource_status.service import ResourceStatusService, get_service
from modules.logistics.checkin.services import get_service as get_checkin_service
from modules.logistics.checkin.services import ENTITY_CONFIG
from modules.statusboards.resource_status_desk import get_resource_status_desk
from modules.operations.teams.windows import open_team_detail_window
from modules.logistics.vehicle.panels.vehicle_edit_window import VehicleEditDialog, VehicleRepository
from modules.logistics.aircraft.panels.aircraft_inventory_window import AircraftInventoryWindow, AircraftRepository
from ui.personnel import PersonnelDetailDialog
from utils import incident_context



@dataclass(slots=True)
class _Column:
    key: str
    title: str


COLUMNS: tuple[_Column, ...] = (
    _Column("resource_id", "Resource ID"),
    _Column("resource_name", "Resource Name"),
    _Column("resource_type", "Resource Type"),
    _Column("status", "Status"),
    _Column("eta_utc", "ETA"),
    _Column("assigned_to", "Assigned To"),
    _Column("location", "Location"),
    _Column("checked_in_time", "Checked-In Time"),
    _Column("last_updated", "Last Updated"),
    _Column("notes", "Notes"),
)


class ResourceStatusTableModel(QAbstractTableModel):
    """Qt table model exposing tracked incident resources."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._items: list[ResourceItem] = []

    def set_items(self, items: list[ResourceItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(COLUMNS):
            return COLUMNS[section].title
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        column = COLUMNS[index.column()].key
        value = getattr(item, column)

        if role == Qt.DisplayRole:
            if column in {"eta_utc", "checked_in_time", "last_updated"}:
                return format_display_datetime(value)
            return "" if value is None else str(value)

        if role == Qt.ToolTipRole:
            if column == "eta_utc" and item.eta_overdue:
                return "ETA is past due while the resource is still pending or enroute."
            if value is None:
                return None
            return str(value)

        if role == Qt.BackgroundRole:
            entry = resource_status_colors().get(item.status)
            return entry["bg"] if entry else None

        if role == Qt.ForegroundRole:
            entry = resource_status_colors().get(item.status)
            return entry["fg"] if entry else None

        if role == Qt.TextAlignmentRole and column in {"eta_utc", "checked_in_time", "last_updated"}:
            return int(Qt.AlignCenter | Qt.AlignVCenter)

        if role == Qt.UserRole:
            return item.id

        if role == Qt.UserRole + 1:
            return item

        if role == Qt.UserRole + 2:
            return parse_datetime(value).timestamp() if column in {"eta_utc", "checked_in_time", "last_updated"} and parse_datetime(value) else 0

        if role == Qt.UserRole + 3:
            return item.eta_overdue

        return None

    def item_at(self, row: int) -> Optional[ResourceItem]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None


class ResourceStatusFilterProxyModel(QSortFilterProxyModel):
    """Combines text and structured filters for the resource board."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._filters = ResourceBoardFilters()
        self.setDynamicSortFilter(True)

    def set_filters(self, filters: ResourceBoardFilters) -> None:
        self._filters = filters
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return True
        item = model.item_at(source_row)
        if item is None:
            return False

        if self._filters.status and self._filters.status != "All" and item.status != self._filters.status:
            return False
        if self._filters.resource_type and self._filters.resource_type != "All" and item.resource_type != self._filters.resource_type:
            return False
        if self._filters.assignment == "Assigned" and not item.assigned_to:
            return False
        if self._filters.assignment == "Unassigned" and item.assigned_to:
            return False
        if self._filters.eta_presence == "ETA Present" and not item.eta_utc:
            return False
        if self._filters.eta_presence == "ETA Missing" and item.eta_utc:
            return False

        search = (self._filters.text_search or "").strip().lower()
        if search:
            haystack = "|".join(
                filter(
                    None,
                    [
                        item.resource_id,
                        item.resource_name,
                        item.resource_type,
                        item.status,
                        item.assigned_to,
                        item.location,
                        item.notes,
                    ],
                )
            ).lower()
            if search not in haystack:
                return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return False
        column = COLUMNS[left.column()].key
        left_item = model.item_at(left.row())
        right_item = model.item_at(right.row())
        if left_item is None or right_item is None:
            return super().lessThan(left, right)

        if column in {"eta_utc", "checked_in_time", "last_updated"}:
            left_dt = parse_datetime(getattr(left_item, column))
            right_dt = parse_datetime(getattr(right_item, column))
            left_key = left_dt.timestamp() if left_dt else float("inf")
            right_key = right_dt.timestamp() if right_dt else float("inf")
            return left_key < right_key

        left_value = str(getattr(left_item, column) or "").lower()
        right_value = str(getattr(right_item, column) or "").lower()
        return left_value < right_value


class ResourceEditDialog(QDialog):
    """Create/edit workflow for a tracked incident resource."""

    def __init__(self, parent: Optional[QWidget] = None, item: Optional[ResourceItem] = None, source_entity_type: Optional[str] = None, source_record_id: Optional[str] = None) -> None:
        self._source_entity_type = source_entity_type
        self._source_record_id = source_record_id
        self._facility_service = FacilitiesService()
        super().__init__(parent)
        self.setWindowTitle("Resource Details")
        self._item = item
        self._build_ui()
        self._load_item(item)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.resource_id_edit = QLineEdit()
        self.resource_name_edit = QLineEdit()
        self.resource_type_edit = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(RESOURCE_STATUSES)
        self.assigned_to_edit = QLineEdit()
        self.assignment_reference_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.facility_picker = FacilityPicker(service=self._facility_service)
        self.eta_unknown_check = QCheckBox("ETA unknown")
        self.eta_edit = QDateTimeEdit(self)
        self.eta_edit.setCalendarPopup(True)
        self.eta_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.eta_edit.setDateTime(datetime.now())
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(90)

        eta_box = QWidget(self)
        eta_layout = QHBoxLayout(eta_box)
        eta_layout.setContentsMargins(0, 0, 0, 0)
        eta_layout.addWidget(self.eta_edit, 1)
        eta_layout.addWidget(self.eta_unknown_check)

        form.addRow("Resource ID", self.resource_id_edit)
        form.addRow("Resource Name", self.resource_name_edit)
        form.addRow("Resource Type", self.resource_type_edit)
        form.addRow("Status", self.status_combo)
        form.addRow("ETA", eta_box)
        form.addRow("Assigned To", self.assigned_to_edit)
        form.addRow("Assignment Ref", self.assignment_reference_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Facility", self.facility_picker)
        form.addRow("Notes", self.notes_edit)

        layout.addLayout(form)

        self.eta_unknown_check.toggled.connect(self.eta_edit.setDisabled)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_item(self, item: Optional[ResourceItem]) -> None:
        if item is None:
            self.eta_unknown_check.setChecked(True)
            return
        self.resource_id_edit.setText(item.resource_id)
        self.resource_name_edit.setText(item.resource_name)
        self.resource_type_edit.setText(item.resource_type)
        self.status_combo.setCurrentText(item.status)
        self.assigned_to_edit.setText(item.assigned_to or "")
        self.assignment_reference_edit.setText(item.assignment_reference or "")
        self.location_edit.setText(item.location or "")
        facility_id = item.checkin_facility_id or item.destination_facility_id or ""
        self.facility_picker.set_value(facility_id, item.location or "")
        self.notes_edit.setPlainText(item.notes or "")
        eta_dt = parse_datetime(item.eta_utc)
        if eta_dt is None:
            self.eta_unknown_check.setChecked(True)
        else:
            self.eta_unknown_check.setChecked(False)
            self.eta_edit.setDateTime(eta_dt.replace(tzinfo=None))

    def payload(self) -> dict[str, Any]:
        eta_value: Optional[str]
        if self.eta_unknown_check.isChecked():
            eta_value = None
        else:
            eta_value = self.eta_edit.dateTime().toPython().astimezone().isoformat()
        facility_id = self.facility_picker.facility_id or None
        status = self.status_combo.currentText()
        payload = {
            "resource_id": self.resource_id_edit.text().strip(),
            "resource_name": self.resource_name_edit.text().strip(),
            "resource_type": self.resource_type_edit.text().strip(),
            "status": status,
            "eta_utc": eta_value,
            "assigned_to": self.assigned_to_edit.text().strip() or None,
            "assignment_reference": self.assignment_reference_edit.text().strip() or None,
            "location": self.facility_picker.facility_text or self.location_edit.text().strip() or None,
            "destination_facility_id": facility_id if status in {"Pending", "Enroute", "Assigned"} else None,
            "checkin_facility_id": facility_id if status == "Checked In" else None,
            "notes": self.notes_edit.toPlainText().strip() or None,
        }
        if getattr(self, "_source_entity_type", None):
            payload["source_entity_type"] = self._source_entity_type
        if getattr(self, "_source_record_id", None):
            payload["source_record_id"] = self._source_record_id
        return payload


class ResourceStatusBoard(QWidget):
    """Filterable and sortable status board for all tracked incident resources."""

    dataChangedForWorkflow = Signal(str)

    def __init__(
        self,
        service: Optional[ResourceStatusService] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service or get_service()
        self._model = ResourceStatusTableModel(self)
        self._proxy = ResourceStatusFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        self.setWindowTitle("Logistics — Resource Status Board")
        self._build_ui()
        try:
            subscribe_theme(self, lambda *_: self._model.layoutChanged.emit())
        except Exception:
            pass
        self._desk = get_resource_status_desk()
        self._desk.resource_rows_changed.connect(self._render_rows)
        self._render_rows(self._desk.resource_rows())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Checked-In Resources / Resource Status Board")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        subtitle = QLabel(
            "Tracks all resources tied to the active incident, including pending and enroute arrivals."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filters_box = QGroupBox("Filters")
        filters_layout = QGridLayout(filters_box)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All")
        self.status_filter.addItems(RESOURCE_STATUSES)
        self.resource_type_filter = QComboBox()
        self.resource_type_filter.addItems(["All", "Personnel", "Vehicle", "Aircraft", "Equipment"])
        self.assignment_filter = QComboBox()
        self.assignment_filter.addItems(["All", "Assigned", "Unassigned"])
        self.eta_filter = QComboBox()
        self.eta_filter.addItems(["All", "ETA Present", "ETA Missing"])
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search resource ID, name, assignment, location, or notes")

        filters_layout.addWidget(QLabel("Status"), 0, 0)
        filters_layout.addWidget(self.status_filter, 0, 1)
        filters_layout.addWidget(QLabel("Resource Type"), 0, 2)
        filters_layout.addWidget(self.resource_type_filter, 0, 3)
        filters_layout.addWidget(QLabel("Assigned"), 1, 0)
        filters_layout.addWidget(self.assignment_filter, 1, 1)
        filters_layout.addWidget(QLabel("ETA"), 1, 2)
        filters_layout.addWidget(self.eta_filter, 1, 3)
        filters_layout.addWidget(QLabel("Search"), 2, 0)
        filters_layout.addWidget(self.search_edit, 2, 1, 1, 3)
        layout.addWidget(filters_box)

        action_bar = QHBoxLayout()
        self.add_button = QPushButton("Add Resource")
        self.edit_button = QPushButton("Edit Selected")
        self.refresh_button = QPushButton("Refresh")
        self.audit_label = QLabel("Audit logging enabled for status, ETA, and assignment changes.")
        action_bar.addWidget(self.add_button)
        action_bar.addWidget(self.edit_button)
        action_bar.addWidget(self.refresh_button)
        action_bar.addStretch(1)
        action_bar.addWidget(self.audit_label)
        layout.addLayout(action_bar)

        self._table = QTableView(self)
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(1, Qt.AscendingOrder)
        self._table.setAlternatingRowColors(False)
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        self._table.doubleClicked.connect(lambda *_: self._edit_selected())
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_table_context_menu)
        header = self._table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        for column in range(len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        layout.addWidget(self._table, 1)

        self.status_filter.currentTextChanged.connect(self._apply_filters)
        self.resource_type_filter.currentTextChanged.connect(self._apply_filters)
        self.assignment_filter.currentTextChanged.connect(self._apply_filters)
        self.eta_filter.currentTextChanged.connect(self._apply_filters)
        self.search_edit.textChanged.connect(self._apply_filters)
        self.add_button.clicked.connect(self._add_resource)
        self.edit_button.clicked.connect(self._edit_selected)
        self.refresh_button.clicked.connect(self.refresh)
        self._source_windows: list[QWidget] = []

    def refresh(self) -> None:
        self._render_rows(self._desk.resource_rows())

    def _render_rows(self, rows: list[dict]) -> None:
        items = []
        for row in rows:
            try:
                items.append(ResourceItem.from_row(row))
            except Exception:
                pass
        self._model.set_items(items)
        self._apply_filters()
        self._table.resizeRowsToContents()

    def _apply_filters(self) -> None:
        self._proxy.set_filters(
            ResourceBoardFilters(
                status=self.status_filter.currentText(),
                resource_type=self.resource_type_filter.currentText(),
                assignment=self.assignment_filter.currentText(),
                eta_presence=self.eta_filter.currentText(),
                text_search=self.search_edit.text(),
            )
        )

    def _selected_item(self) -> Optional[ResourceItem]:
        index = self._table.currentIndex()
        if not index.isValid():
            return None
        source_index = self._proxy.mapToSource(index)
        return self._model.item_at(source_index.row())

    def _show_table_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        self._table.setCurrentIndex(index)
        item = self._selected_item()
        if item is None:
            return

        menu = QMenu(self)
        act_edit = menu.addAction("Edit Resource")
        act_open_team = None
        if item.assigned_to:
            act_open_team = menu.addAction("Open Team")
        menu.addSeparator()
        status_actions: dict[Any, str] = {}
        for status in ("Requested", "Ordered", "Enroute", "Available", "Assigned", "Cancelled", "Pending"):
            action = menu.addAction(status)
            action.setEnabled(status != item.status)
            status_actions[action] = status
        act_refresh = menu.addAction("Refresh")
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))

        if chosen in status_actions:
            self._set_status_for_item(item, status_actions[chosen])
        elif act_open_team is not None and chosen == act_open_team:
            self._open_team_for_item(item)
        elif chosen == act_edit:
            self._open_source_record(item)
        elif chosen == act_refresh:
            self.refresh()

    def _set_status_for_item(self, item: ResourceItem, status: str) -> None:
        try:
            self._service.update_resource(item.id, {"status": status}, actor_name="Desktop Logistics")
        except Exception as exc:
            QMessageBox.critical(self, "Unable to Update Status", str(exc))
            return
        self.refresh()
        self.dataChangedForWorkflow.emit(item.id)

    def _open_team_for_item(self, item: ResourceItem) -> None:
        team_name = (item.assigned_to or item.assignment_reference or "").strip()
        if not team_name:
            QMessageBox.information(self, "Open Team", "This resource is not assigned to a team.")
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.information(self, "Open Team", "No active incident is selected.")
            return
        try:
            from modules.operations.taskings.repository import list_all_teams as _list_all_teams
            teams = _list_all_teams()
        except Exception as exc:
            QMessageBox.warning(self, "Open Team", str(exc))
            return

        match = next(
            (
                team for team in teams
                if str(team.get("team_id")) == team_name
                or str(team.get("team_name") or "").strip().lower() == team_name.lower()
            ),
            None,
        )
        if not match:
            QMessageBox.information(self, "Open Team", f"Could not resolve team '{team_name}'.")
            return
        team_id = match.get("team_id")
        if team_id is None:
            QMessageBox.information(self, "Open Team", "That team record does not have an ID.")
            return
        open_team_detail_window(int(team_id))

    def _open_source_record(self, item: ResourceItem) -> None:
        entity_type = (item.source_entity_type or "").strip()
        source_id = (item.source_record_id or "").strip()
        if not entity_type or not source_id:
            QMessageBox.information(self, "Open Source Record", "This row does not have source metadata.")
            return
        try:
            if entity_type == "personnel":
                dialog = PersonnelDetailDialog(None, person_record=int(source_id))
            elif entity_type == "vehicle":
                dialog = VehicleEditDialog(vehicle_id=source_id, repository=VehicleRepository(), parent=self)
            elif entity_type == "aircraft":
                dialog = AircraftInventoryWindow(repository=AircraftRepository(), parent=self)
            else:
                QMessageBox.information(
                    self,
                    "Open Source Record",
                    f"No opener is available for {entity_type} records yet.",
                )
                return
            self._source_windows.append(dialog)
            try:
                dialog.destroyed.connect(lambda *_: self._cleanup_source_window(dialog))
            except Exception:
                pass
            if hasattr(dialog, "open") and callable(getattr(dialog, "open")):
                dialog.open()
            elif hasattr(dialog, "exec") and callable(getattr(dialog, "exec")):
                dialog.exec()
            else:
                dialog.show()
        except Exception as exc:
            QMessageBox.warning(self, "Open Source Record", str(exc))

    def _cleanup_source_window(self, window: QWidget) -> None:
        try:
            self._source_windows.remove(window)
        except ValueError:
            pass


    def _edit_selected(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, "Select a Resource", "Choose a resource row to edit.")
            return
        dialog = ResourceEditDialog(self, item=item)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self._service.update_resource(item.id, dialog.payload(), actor_name="Desktop Logistics")
        except Exception as exc:
            QMessageBox.critical(self, "Unable to Update Resource", str(exc))
            return
        self.refresh()
        self.dataChangedForWorkflow.emit(item.id)

    def _add_resource(self) -> None:
        dialog = ResourceEditDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            created = self._service.create_resource(dialog.payload(), actor_name="Desktop Logistics")
        except Exception as exc:
            QMessageBox.critical(self, "Unable to Add Resource", str(exc))
            return
        self.refresh()
        try:
            self.dataChangedForWorkflow.emit(created.id)
        except Exception:
            pass
