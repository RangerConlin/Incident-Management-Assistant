"""Widget implementation of the Aircraft Inventory window."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..repository import AircraftRecord, AircraftRepository


@dataclass(slots=True)
class FilterState:
    """Current filter selections for the inventory table."""

    search: str = ""
    type: str = "All"
    status: str = "All"
    base: str = "All"
    sort_key: str = "tail_number"
    sort_order: str = "asc"
    fuels: set[str] = field(default_factory=set)
    capabilities: set[str] = field(default_factory=set)
    night_ops: bool = False
    ifr: bool = False
    hoist: bool = False
    flir: bool = False

    def to_repository_filters(self) -> dict[str, Any]:
        return {
            "search": self.search,
            "type": self.type,
            "status": self.status,
            "base": self.base,
            "fuels": list(self.fuels),
            "capabilities": list(self.capabilities),
            "night_ops": self.night_ops,
            "ifr": self.ifr,
            "hoist": self.hoist,
            "flir": self.flir,
        }


class AircraftTableModel(QAbstractTableModel):
    """Table model presenting aircraft inventory rows."""

    headers: list[str] = [
        "",
        "Tail #",
        "Callsign",
        "Type",
        "Make/Model",
        "Status",
        "Base",
        "Assigned To",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[AircraftRecord] = []
        self._checked_ids: set[int] = set()

    # Qt model interface -------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        return len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        record = self._rows[index.row()]
        column = index.column()

        if column == 0:
            if role == Qt.CheckStateRole:
                if record.id is None:
                    return Qt.Unchecked
                return Qt.Checked if record.id in self._checked_ids else Qt.Unchecked
            if role in (Qt.DisplayRole, Qt.EditRole):
                return ""
            return None

        if role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter | Qt.AlignLeft

        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None

        mapping = {
            1: record.tail_number,
            2: record.callsign or "",
            3: record.type,
            4: record.make_model_display or "",
            5: record.status,
            6: record.base or "",
            7: record.assigned_team_name or ("(none)" if not record.assigned_team_name else record.assigned_team_name),
        }
        return mapping.get(column, "")

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:  # type: ignore[override]
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore[override]
        base = super().flags(index)
        if not index.isValid():
            return base
        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
        return base | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    # Data utilities -----------------------------------------------------
    def set_rows(self, rows: Sequence[AircraftRecord]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        valid_ids = {r.id for r in self._rows if r.id is not None}
        self._checked_ids &= {int(v) for v in valid_ids if isinstance(v, int)}
        self.endResetModel()

    def toggle_checked(self, row: int) -> None:
        if not (0 <= row < len(self._rows)):
            return
        record = self._rows[row]
        if record.id is None:
            return
        if record.id in self._checked_ids:
            self._checked_ids.remove(record.id)
        else:
            self._checked_ids.add(record.id)
        top_left = self.index(row, 0)
        self.dataChanged.emit(top_left, top_left, [Qt.CheckStateRole])

    def set_all_checked(self, checked: bool) -> None:
        if checked:
            self._checked_ids = {int(r.id) for r in self._rows if r.id is not None}
        else:
            self._checked_ids.clear()
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.CheckStateRole])

    def checked_ids(self) -> list[int]:
        return [int(i) for i in self._checked_ids]

    def row_record(self, row: int) -> AircraftRecord | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def index_of(self, record_id: int | None) -> int:
        if record_id is None:
            return -1
        for idx, record in enumerate(self._rows):
            if record.id == record_id:
                return idx
        return -1


class SetStatusDialog(QDialog):
    """Simple dialog to change aircraft status for bulk operations."""

    def __init__(self, statuses: Sequence[str], count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Status")
        self._status_combo = QComboBox()
        self._status_combo.addItems(list(statuses))
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Reason or notes (optional)")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Apply to {count} selected aircraft."))

        form = QFormLayout()
        form.addRow("New Status:", self._status_combo)
        form.addRow("Reason/Notes:", self._notes_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def status(self) -> str:
        return str(self._status_combo.currentText())

    @property
    def notes(self) -> str:
        return self._notes_edit.toPlainText().strip()


class AssignTeamDialog(QDialog):
    """Dialog to capture team assignment details."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign to Team")
        self._team_edit = QLineEdit()
        self._team_edit.setPlaceholderText("Team name or identifier")
        self._notify_check = QCheckBox("Auto-notify Ops lead")
        self._notify_check.setChecked(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Team:"))
        layout.addWidget(self._team_edit)
        layout.addWidget(self._notify_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def team_name(self) -> str:
        return self._team_edit.text().strip()

    @property
    def notify(self) -> bool:
        return self._notify_check.isChecked()


class AircraftInventoryWindow(QDialog):
    """Main widget housing the aircraft inventory workspace."""

    PAGE_SIZE = 50

    def __init__(self, repository: AircraftRepository | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aircraft Inventory")
        self.resize(1360, 820)

        self._repository = repository or AircraftRepository()
        try:
            self._repository.ensure_seed_data()
        except Exception:  # pragma: no cover - seed data optional
            pass

        self._filters = FilterState()
        self._table_model = AircraftTableModel()
        self._current_page = 0
        self._total_rows = 0
        self._selected_record: AircraftRecord | None = None

        self._notes_timer = QTimer(self)
        self._notes_timer.setInterval(600)
        self._notes_timer.setSingleShot(True)

        self._build_ui()
        self._register_shortcuts()
        self._refresh_table()

    # UI construction ----------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_filter_band())

        splitter = QSplitter(self)
        splitter.setOrientation(Qt.Horizontal)
        splitter.addWidget(self._build_table_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        legend = QLabel("Status Legend: Available ▮  Assigned ▮  Out of Service ▮  Standby ▮  In Transit ▮")
        legend.setObjectName("statusLegend")
        layout.addWidget(legend)

    # Placeholder methods (implemented later) ---------------------------
    def _build_toolbar(self) -> QWidget:
        widget = QWidget(self)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Aircraft Inventory Management", widget)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addStretch(1)

        self.add_button = QPushButton("Add", widget)
        self.add_button.clicked.connect(self._open_add_dialog)
        layout.addWidget(self.add_button)

        self.import_button = QPushButton("Import", widget)
        self.import_button.clicked.connect(self._open_import_dialog)
        layout.addWidget(self.import_button)

        self.export_button = QPushButton("Export", widget)
        self.export_button.clicked.connect(self._export_current_view)
        layout.addWidget(self.export_button)

        self.bulk_button = QToolButton(widget)
        self.bulk_button.setText("Bulk Actions ▾")
        self.bulk_button.setPopupMode(QToolButton.InstantPopup)
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Set Status…", self._bulk_set_status)
        self.bulk_menu.addAction("Assign to Team…", self._bulk_assign_team)
        self.bulk_menu.addAction("Clear Assignment", self._bulk_clear_assignment)
        self.bulk_menu.addAction("Delete", self._bulk_delete)
        self.bulk_button.setMenu(self.bulk_menu)
        layout.addWidget(self.bulk_button)

        return widget

    def _build_filter_band(self) -> QWidget:
        container = QWidget(self)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        row_a = QHBoxLayout()
        row_a.setSpacing(6)

        row_a.addWidget(QLabel("Search:", container))
        self.search_edit = QLineEdit(container)
        self.search_edit.setPlaceholderText("Search tail #, callsign, model, ADS-B, base")
        self.search_edit.textChanged.connect(self._on_search_changed)
        row_a.addWidget(self.search_edit, 1)

        row_a.addWidget(QLabel("Type:", container))
        self.type_combo = QComboBox(container)
        self.type_combo.addItems(["All", "Helicopter", "Fixed-Wing", "UAS", "Gyroplane", "Other"])
        self.type_combo.currentTextChanged.connect(self._on_filter_changed)
        row_a.addWidget(self.type_combo)

        row_a.addWidget(QLabel("Status:", container))
        self.status_combo = QComboBox(container)
        self.status_combo.addItems(["All", "Available", "Assigned", "Out of Service", "Standby", "In Transit"])
        self.status_combo.currentTextChanged.connect(self._on_filter_changed)
        row_a.addWidget(self.status_combo)

        row_a.addWidget(QLabel("Base:", container))
        self.base_combo = QComboBox(container)
        self.base_combo.addItems(["All"])
        self.base_combo.currentTextChanged.connect(self._on_filter_changed)
        row_a.addWidget(self.base_combo)

        row_a.addWidget(QLabel("Sort:", container))
        self.sort_combo = QComboBox(container)
        self.sort_combo.addItems(
            [
                "Name ↑",
                "Name ↓",
                "Tail # ↑",
                "Tail # ↓",
                "Type ↑",
                "Type ↓",
                "Status ↑",
                "Status ↓",
                "Base ↑",
                "Base ↓",
                "Fuel ↑",
                "Fuel ↓",
                "Endurance ↑",
                "Endurance ↓",
                "Updated ↑",
                "Updated ↓",
            ]
        )
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        row_a.addWidget(self.sort_combo)

        outer.addLayout(row_a)

        row_b = QHBoxLayout()
        row_b.setSpacing(6)

        self.capabilities_button = QPushButton("Capabilities", container)
        self.capabilities_button.clicked.connect(self._toggle_capabilities_filter)
        row_b.addWidget(self.capabilities_button)

        self.fuel_button = QPushButton("Fuel", container)
        self.fuel_button.clicked.connect(self._toggle_fuel_filter)
        row_b.addWidget(self.fuel_button)

        self.night_ops_chip = self._create_chip("Night Ops", self._on_chip_toggled)
        row_b.addWidget(self.night_ops_chip)
        self.ifr_chip = self._create_chip("IFR", self._on_chip_toggled)
        row_b.addWidget(self.ifr_chip)
        self.hoist_chip = self._create_chip("Hoist", self._on_chip_toggled)
        row_b.addWidget(self.hoist_chip)
        self.flir_chip = self._create_chip("FLIR", self._on_chip_toggled)
        row_b.addWidget(self.flir_chip)

        reset_btn = QPushButton("Reset Filters", container)
        reset_btn.clicked.connect(self._reset_filters)
        row_b.addWidget(reset_btn)
        row_b.addStretch(1)

        outer.addLayout(row_b)
        return container

    def _build_table_panel(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.table_view = QTableView(widget)
        self.table_view.setModel(self._table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(0, QTableView.ResizeToContents)
        self.table_view.clicked.connect(self._on_table_clicked)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table_view, 1)

        if self.table_view.selectionModel() is not None:
            self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.pagination_label = QLabel("Rows: 0–0 of 0", widget)
        footer.addWidget(self.pagination_label)

        self.first_button = QPushButton("<<", widget)
        self.first_button.clicked.connect(self._go_first_page)
        footer.addWidget(self.first_button)

        self.prev_button = QPushButton("<", widget)
        self.prev_button.clicked.connect(self._go_prev_page)
        footer.addWidget(self.prev_button)

        self.page_display = QLabel("Page 1/1", widget)
        footer.addWidget(self.page_display)

        self.next_button = QPushButton(">", widget)
        self.next_button.clicked.connect(self._go_next_page)
        footer.addWidget(self.next_button)

        self.last_button = QPushButton(">>", widget)
        self.last_button.clicked.connect(self._go_last_page)
        footer.addWidget(self.last_button)

        footer.addStretch(1)

        select_all = QPushButton("Select All", widget)
        select_all.clicked.connect(lambda: self._table_model.set_all_checked(True))
        footer.addWidget(select_all)

        clear_btn = QPushButton("Clear", widget)
        clear_btn.clicked.connect(lambda: self._table_model.set_all_checked(False))
        footer.addWidget(clear_btn)

        layout.addLayout(footer)
        return widget

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(8)

        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(6)

        self.assign_button = QPushButton("Assign to Team…", panel)
        self.assign_button.clicked.connect(lambda: self._assign_team([self._current_record_id()]))
        quick_actions.addWidget(self.assign_button)

        self.status_button = QPushButton("Set Status…", panel)
        self.status_button.clicked.connect(lambda: self._set_status([self._current_record_id()]))
        quick_actions.addWidget(self.status_button)

        self.clear_assign_button = QPushButton("Clear Assignment", panel)
        self.clear_assign_button.clicked.connect(lambda: self._clear_assignment([self._current_record_id()]))
        quick_actions.addWidget(self.clear_assign_button)

        self.print_button = QPushButton("Print Summary", panel)
        self.print_button.clicked.connect(self._print_summary)
        quick_actions.addWidget(self.print_button)

        self.log_button = QPushButton("Open Log", panel)
        self.log_button.clicked.connect(self._open_log)
        quick_actions.addWidget(self.log_button)

        self.delete_button = QPushButton("Delete Aircraft", panel)
        self.delete_button.clicked.connect(lambda: self._bulk_delete(single=True))
        quick_actions.addWidget(self.delete_button)

        quick_actions.addStretch(1)
        layout.addLayout(quick_actions)

        core_group = QGroupBox("Core Details", panel)
        core_layout = QFormLayout(core_group)
        core_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.tail_edit = QLineEdit(core_group)
        self.tail_edit.setPlaceholderText("Required")
        self.tail_edit.editingFinished.connect(lambda: self._save_field("tail_number", self.tail_edit.text().strip()))
        core_layout.addRow("Tail Number:", self.tail_edit)

        self.callsign_edit = QLineEdit(core_group)
        self.callsign_edit.editingFinished.connect(lambda: self._save_field("callsign", self.callsign_edit.text().strip() or None))
        core_layout.addRow("Callsign:", self.callsign_edit)

        self.type_detail = QComboBox(core_group)
        self.type_detail.addItems(["Helicopter", "Fixed-Wing", "UAS", "Gyroplane", "Other"])
        self.type_detail.currentTextChanged.connect(lambda text: self._save_field("type", text))
        core_layout.addRow("Type:", self.type_detail)

        self.make_model_edit = QLineEdit(core_group)
        self.make_model_edit.editingFinished.connect(self._save_make_model)
        core_layout.addRow("Make/Model:", self.make_model_edit)

        self.base_detail = QLineEdit(core_group)
        self.base_detail.editingFinished.connect(lambda: self._save_field("base", self.base_detail.text().strip() or None))
        core_layout.addRow("Base (Home):", self.base_detail)

        self.current_location_edit = QLineEdit(core_group)
        self.current_location_edit.editingFinished.connect(lambda: self._save_field("current_location", self.current_location_edit.text().strip() or None))
        core_layout.addRow("Current Location:", self.current_location_edit)

        self.status_detail = QComboBox(core_group)
        self.status_detail.addItems(["Available", "Assigned", "Out of Service", "Standby", "In Transit"])
        self.status_detail.currentTextChanged.connect(lambda text: self._save_field("status", text))
        core_layout.addRow("Status:", self.status_detail)

        self.assigned_combo = QLineEdit(core_group)
        self.assigned_combo.editingFinished.connect(lambda: self._save_field("assigned_team_name", self.assigned_combo.text().strip() or None))
        core_layout.addRow("Assigned To (Team):", self.assigned_combo)

        layout.addWidget(core_group)

        perf_group = QGroupBox("Performance & Avionics", panel)
        perf_layout = QFormLayout(perf_group)
        perf_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.fuel_combo = QComboBox(perf_group)
        self.fuel_combo.addItems(["Jet A", "Avgas", "Electric", "Other"])
        self.fuel_combo.currentTextChanged.connect(lambda text: self._save_field("fuel_type", text))
        perf_layout.addRow("Fuel Type:", self.fuel_combo)

        self.range_spin = QSpinBox(perf_group)
        self.range_spin.setRange(0, 5000)
        self.range_spin.valueChanged.connect(lambda value: self._save_field("range_nm", int(value)))
        perf_layout.addRow("Range (nm):", self.range_spin)

        self.endurance_spin = QDoubleSpinBox(perf_group)
        self.endurance_spin.setDecimals(1)
        self.endurance_spin.setRange(0.0, 50.0)
        self.endurance_spin.valueChanged.connect(lambda value: self._save_field("endurance_hr", float(value)))
        perf_layout.addRow("Endurance (hr):", self.endurance_spin)

        self.cruise_spin = QSpinBox(perf_group)
        self.cruise_spin.setRange(0, 600)
        self.cruise_spin.valueChanged.connect(lambda value: self._save_field("cruise_kt", int(value)))
        perf_layout.addRow("Cruise Speed (kt):", self.cruise_spin)

        crew_widget = QWidget(perf_group)
        crew_layout = QHBoxLayout(crew_widget)
        crew_layout.setContentsMargins(0, 0, 0, 0)
        crew_layout.setSpacing(6)
        self.crew_min_spin = QSpinBox(crew_widget)
        self.crew_min_spin.setRange(0, 20)
        self.crew_min_spin.valueChanged.connect(lambda value: self._save_field("crew_min", int(value)))
        crew_layout.addWidget(self.crew_min_spin)
        crew_layout.addWidget(QLabel("/", crew_widget))
        self.crew_max_spin = QSpinBox(crew_widget)
        self.crew_max_spin.setRange(0, 20)
        self.crew_max_spin.valueChanged.connect(lambda value: self._save_field("crew_max", int(value)))
        crew_layout.addWidget(self.crew_max_spin)
        perf_layout.addRow("Crew Min/Max:", crew_widget)

        self.adsb_edit = QLineEdit(perf_group)
        self.adsb_edit.setMaxLength(6)
        self.adsb_edit.editingFinished.connect(lambda: self._save_field("adsb_hex", self.adsb_edit.text().strip().upper() or None))
        perf_layout.addRow("ADS-B Hex:", self.adsb_edit)

        radio_widget = QWidget(perf_group)
        radio_layout = QHBoxLayout(radio_widget)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(6)
        self.radio_vhf_air = QCheckBox("VHF Air", radio_widget)
        self.radio_vhf_air.toggled.connect(lambda checked: self._save_field("radio_vhf_air", bool(checked)))
        radio_layout.addWidget(self.radio_vhf_air)
        self.radio_vhf_sar = QCheckBox("VHF SAR", radio_widget)
        self.radio_vhf_sar.toggled.connect(lambda checked: self._save_field("radio_vhf_sar", bool(checked)))
        radio_layout.addWidget(self.radio_vhf_sar)
        self.radio_uhf = QCheckBox("UHF", radio_widget)
        self.radio_uhf.toggled.connect(lambda checked: self._save_field("radio_uhf", bool(checked)))
        radio_layout.addWidget(self.radio_uhf)
        perf_layout.addRow("Radio Fits:", radio_widget)

        cap_widget = QWidget(perf_group)
        cap_layout = QHBoxLayout(cap_widget)
        cap_layout.setContentsMargins(0, 0, 0, 0)
        cap_layout.setSpacing(6)
        self.cap_hoist = QCheckBox("Hoist", cap_widget)
        self.cap_hoist.toggled.connect(lambda checked: self._save_field("cap_hoist", bool(checked)))
        cap_layout.addWidget(self.cap_hoist)
        self.cap_nvg = QCheckBox("NVG", cap_widget)
        self.cap_nvg.toggled.connect(lambda checked: self._save_field("cap_nvg", bool(checked)))
        cap_layout.addWidget(self.cap_nvg)
        self.cap_flir = QCheckBox("FLIR", cap_widget)
        self.cap_flir.toggled.connect(lambda checked: self._save_field("cap_flir", bool(checked)))
        cap_layout.addWidget(self.cap_flir)
        self.cap_ifr = QCheckBox("IFR", cap_widget)
        self.cap_ifr.toggled.connect(lambda checked: self._save_field("cap_ifr", bool(checked)))
        cap_layout.addWidget(self.cap_ifr)
        perf_layout.addRow("Capabilities:", cap_widget)

        self.payload_spin = QSpinBox(perf_group)
        self.payload_spin.setRange(0, 10_000)
        self.payload_spin.valueChanged.connect(lambda value: self._save_field("payload_kg", int(value)))
        perf_layout.addRow("Payload/Winch (kg):", self.payload_spin)

        self.med_combo = QComboBox(perf_group)
        self.med_combo.addItems(["None", "Basic", "Advanced"])
        self.med_combo.currentTextChanged.connect(lambda text: self._save_field("med_config", text))
        perf_layout.addRow("Med Config:", self.med_combo)

        layout.addWidget(perf_group)

        layout.addWidget(QLabel("Notes", panel))
        self.notes_edit = QPlainTextEdit(panel)
        self.notes_edit.setPlaceholderText("Enter notes (supports @mentions and #tags)")
        self.notes_edit.textChanged.connect(self._schedule_notes_save)
        layout.addWidget(self.notes_edit, 1)

        self.tabs = QTabWidget(panel)
        self.tabs.addTab(self._build_details_tab(), "Details")
        self.tabs.addTab(self._build_capabilities_tab(), "Capabilities")
        self.tabs.addTab(self._build_maintenance_tab(), "Maintenance")
        self.tabs.addTab(self._build_attachments_tab(), "Attachments")
        self.tabs.addTab(self._build_history_tab(), "History")
        layout.addWidget(self.tabs, 1)

        return panel

    def _register_shortcuts(self) -> None:
        action_add = QAction("Add", self)
        action_add.setShortcut(QKeySequence.StandardKey.New)
        action_add.triggered.connect(self._open_add_dialog)
        self.addAction(action_add)

        action_import = QAction("Import", self)
        action_import.setShortcut(QKeySequence("Ctrl+I"))
        action_import.triggered.connect(self._open_import_dialog)
        self.addAction(action_import)

        action_export = QAction("Export", self)
        action_export.setShortcut(QKeySequence("Ctrl+E"))
        action_export.triggered.connect(self._export_current_view)
        self.addAction(action_export)

        action_search = QAction("Search", self)
        action_search.setShortcut(QKeySequence("Ctrl+F"))
        action_search.triggered.connect(self.search_edit.setFocus)
        self.addAction(action_search)

    def _refresh_table(self, *, reset_page: bool = False) -> None:
        if reset_page:
            self._current_page = 0

        filters = self._filters.to_repository_filters()
        rows, total = self._repository.list_aircraft(
            filters,
            sort_key=self._filters.sort_key,
            sort_order=self._filters.sort_order,
            limit=self.PAGE_SIZE,
            offset=self._current_page * self.PAGE_SIZE,
        )
        self._total_rows = total
        self._table_model.set_rows(rows)
        self._update_pagination()
        self._populate_base_filter()

        if rows:
            self.table_view.selectRow(0)
            self._load_record(rows[0])
        else:
            self._load_record(None)

    # Table interactions -------------------------------------------------
    def _on_table_clicked(self, index: QModelIndex) -> None:
        if index.column() == 0:
            self._table_model.toggle_checked(index.row())

    def _on_row_double_clicked(self, index: QModelIndex) -> None:
        if index.column() == 0:
            self._table_model.toggle_checked(index.row())
            return
        record = self._table_model.row_record(index.row())
        if record is not None:
            self._load_record(record)

    def _on_selection_changed(self, *_: Any) -> None:
        selection = self.table_view.selectionModel()
        if selection is None:
            self._load_record(None)
            return
        rows = selection.selectedRows()
        if not rows:
            self._load_record(None)
            return
        record = self._table_model.row_record(rows[0].row())
        self._load_record(record)

    def _go_first_page(self) -> None:
        if self._current_page != 0:
            self._current_page = 0
            self._refresh_table()

    def _go_prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_table()

    def _go_next_page(self) -> None:
        total_pages = max(1, (self._total_rows + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._refresh_table()

    def _go_last_page(self) -> None:
        total_pages = max(1, (self._total_rows + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._current_page != total_pages - 1:
            self._current_page = total_pages - 1
            self._refresh_table()

    def _update_pagination(self) -> None:
        if self._total_rows == 0:
            self.pagination_label.setText("Rows: 0–0 of 0")
            self.page_display.setText("Page 1/1")
            self.first_button.setEnabled(False)
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.last_button.setEnabled(False)
            return

        start = self._current_page * self.PAGE_SIZE + 1
        end = min((self._current_page + 1) * self.PAGE_SIZE, self._total_rows)
        self.pagination_label.setText(f"Rows: {start}–{end} of {self._total_rows}")
        total_pages = max(1, (self._total_rows + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.page_display.setText(f"Page {self._current_page + 1}/{total_pages}")
        self.first_button.setEnabled(self._current_page > 0)
        self.prev_button.setEnabled(self._current_page > 0)
        self.next_button.setEnabled(self._current_page < total_pages - 1)
        self.last_button.setEnabled(self._current_page < total_pages - 1)

    def _populate_base_filter(self) -> None:
        current = self.base_combo.currentText()
        bases = sorted({row.base or "" for row in self._table_model._rows if row.base})
        items = ["All", *bases]
        existing = [self.base_combo.itemText(i) for i in range(self.base_combo.count())]
        if items != existing:
            self.base_combo.blockSignals(True)
            self.base_combo.clear()
            self.base_combo.addItems(items)
            if current in items:
                self.base_combo.setCurrentText(current)
            else:
                self.base_combo.setCurrentIndex(0)
            self.base_combo.blockSignals(False)

    # Filter management --------------------------------------------------
    def _create_chip(self, label: str, slot: Any) -> QPushButton:
        button = QPushButton(label, self)
        button.setCheckable(True)
        button.setStyleSheet("QPushButton:checked { background-color: #1976d2; color: white; }")
        button.toggled.connect(slot)
        return button

    def _on_search_changed(self, text: str) -> None:
        self._filters.search = text
        self._refresh_table(reset_page=True)

    def _on_filter_changed(self, *_: Any) -> None:
        self._filters.type = self.type_combo.currentText()
        self._filters.status = self.status_combo.currentText()
        self._filters.base = self.base_combo.currentText()
        self._refresh_table(reset_page=True)

    def _on_sort_changed(self, text: str) -> None:
        key_map = {
            "Name": "name",
            "Tail": "tail_number",
            "Type": "type",
            "Status": "status",
            "Base": "base",
            "Fuel": "fuel",
            "Endurance": "endurance",
            "Updated": "updated",
        }
        parts = text.split()
        key = key_map.get(parts[0], "tail_number")
        order = "desc" if "↓" in text or (len(parts) > 1 and parts[1] == "↓") else "asc"
        self._filters.sort_key = key
        self._filters.sort_order = order
        self._refresh_table()

    def _on_chip_toggled(self, _: bool) -> None:
        self._filters.night_ops = self.night_ops_chip.isChecked()
        self._filters.ifr = self.ifr_chip.isChecked()
        self._filters.hoist = self.hoist_chip.isChecked()
        self._filters.flir = self.flir_chip.isChecked()
        self._refresh_table(reset_page=True)

    def _reset_filters(self) -> None:
        self.search_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.base_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)
        for chip in (self.night_ops_chip, self.ifr_chip, self.hoist_chip, self.flir_chip):
            chip.setChecked(False)
        self._filters = FilterState()
        self._refresh_table(reset_page=True)

    def _toggle_capabilities_filter(self) -> None:
        menu = QMenu(self)
        options = ["Hoist", "NVG", "FLIR", "IFR"]
        for option in options:
            action = menu.addAction(option)
            action.setCheckable(True)
            action.setChecked(option in self._filters.capabilities)
            action.toggled.connect(lambda checked, opt=option: self._on_capability_toggled(opt, checked))
        menu.exec(self.capabilities_button.mapToGlobal(self.capabilities_button.rect().bottomLeft()))

    def _toggle_fuel_filter(self) -> None:
        menu = QMenu(self)
        for fuel in ["Jet A", "Avgas", "Electric", "Other"]:
            action = menu.addAction(fuel)
            action.setCheckable(True)
            action.setChecked(fuel in self._filters.fuels)
            action.toggled.connect(lambda checked, opt=fuel: self._on_fuel_toggled(opt, checked))
        menu.exec(self.fuel_button.mapToGlobal(self.fuel_button.rect().bottomLeft()))

    def _on_capability_toggled(self, capability: str, checked: bool) -> None:
        if checked:
            self._filters.capabilities.add(capability)
        else:
            self._filters.capabilities.discard(capability)
        self._refresh_table(reset_page=True)

    def _on_fuel_toggled(self, fuel: str, checked: bool) -> None:
        if checked:
            self._filters.fuels.add(fuel)
        else:
            self._filters.fuels.discard(fuel)
        self._refresh_table(reset_page=True)

    # Detail loading ----------------------------------------------------
    def _current_record_id(self) -> int | None:
        return self._selected_record.id if self._selected_record else None

    def _load_record(self, record: AircraftRecord | None) -> None:
        self._selected_record = record
        widgets: list[QWidget] = [
            self.assign_button,
            self.status_button,
            self.clear_assign_button,
            self.print_button,
            self.log_button,
            self.delete_button,
            self.tail_edit,
            self.callsign_edit,
            self.type_detail,
            self.make_model_edit,
            self.base_detail,
            self.current_location_edit,
            self.status_detail,
            self.assigned_combo,
            self.fuel_combo,
            self.range_spin,
            self.endurance_spin,
            self.cruise_spin,
            self.crew_min_spin,
            self.crew_max_spin,
            self.adsb_edit,
            self.radio_vhf_air,
            self.radio_vhf_sar,
            self.radio_uhf,
            self.cap_hoist,
            self.cap_nvg,
            self.cap_flir,
            self.cap_ifr,
            self.payload_spin,
            self.med_combo,
            self.notes_edit,
            self.serial_edit,
            self.year_spin,
            self.owner_edit,
            self.registration_edit,
            self.inspection_edit,
            self.last100_edit,
            self.next100_edit,
        ]

        enabled = record is not None
        for widget in widgets:
            widget.setEnabled(enabled)

        if record is None:
            for widget in widgets:
                if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
                    widget.blockSignals(True)
                    widget.clear()
                    widget.blockSignals(False)
                elif isinstance(widget, QComboBox):
                    widget.blockSignals(True)
                    if widget.count():
                        widget.setCurrentIndex(0)
                    widget.blockSignals(False)
                elif isinstance(widget, QSpinBox | QDoubleSpinBox):
                    widget.blockSignals(True)
                    widget.setValue(0)
                    widget.blockSignals(False)
                elif isinstance(widget, QCheckBox):
                    widget.blockSignals(True)
                    widget.setChecked(False)
                    widget.blockSignals(False)
            self._populate_secondary_tables(None)
            return

        # Block signals while populating
        blockers = [
            self.tail_edit,
            self.callsign_edit,
            self.type_detail,
            self.make_model_edit,
            self.base_detail,
            self.current_location_edit,
            self.status_detail,
            self.assigned_combo,
            self.fuel_combo,
            self.range_spin,
            self.endurance_spin,
            self.cruise_spin,
            self.crew_min_spin,
            self.crew_max_spin,
            self.adsb_edit,
            self.radio_vhf_air,
            self.radio_vhf_sar,
            self.radio_uhf,
            self.cap_hoist,
            self.cap_nvg,
            self.cap_flir,
            self.cap_ifr,
            self.payload_spin,
            self.med_combo,
            self.notes_edit,
            self.serial_edit,
            self.year_spin,
            self.owner_edit,
            self.registration_edit,
            self.inspection_edit,
            self.last100_edit,
            self.next100_edit,
        ]
        for widget in blockers:
            widget.blockSignals(True)

        self.tail_edit.setText(record.tail_number)
        self.callsign_edit.setText(record.callsign or "")
        self.type_detail.setCurrentText(record.type)
        self.make_model_edit.setText(record.make_model_display or "")
        self.base_detail.setText(record.base or "")
        self.current_location_edit.setText(record.current_location or "")
        self.status_detail.setCurrentText(record.status)
        self.assigned_combo.setText(record.assigned_team_name or "")
        self.fuel_combo.setCurrentText(record.fuel_type or "Jet A")
        self.range_spin.setValue(record.range_nm or 0)
        self.endurance_spin.setValue(float(record.endurance_hr or 0.0))
        self.cruise_spin.setValue(record.cruise_kt or 0)
        self.crew_min_spin.setValue(record.crew_min or 0)
        self.crew_max_spin.setValue(record.crew_max or 0)
        self.adsb_edit.setText(record.adsb_hex or "")
        self.radio_vhf_air.setChecked(record.radio_vhf_air)
        self.radio_vhf_sar.setChecked(record.radio_vhf_sar)
        self.radio_uhf.setChecked(record.radio_uhf)
        self.cap_hoist.setChecked(record.cap_hoist)
        self.cap_nvg.setChecked(record.cap_nvg)
        self.cap_flir.setChecked(record.cap_flir)
        self.cap_ifr.setChecked(record.cap_ifr)
        self.payload_spin.setValue(record.payload_kg or 0)
        self.med_combo.setCurrentText(record.med_config or "None")
        self.notes_edit.setPlainText(record.notes or "")
        self.serial_edit.setText(record.serial_number or "")
        self.year_spin.setValue(record.year or 0)
        self.owner_edit.setText(record.owner_operator or "")
        self.registration_edit.setText(record.registration_exp or "")
        self.inspection_edit.setText(record.inspection_due or "")
        self.last100_edit.setText(record.last_100hr or "")
        self.next100_edit.setText(record.next_100hr or "")

        for widget in blockers:
            widget.blockSignals(False)

        self._populate_secondary_tables(record)

    def _populate_secondary_tables(self, record: AircraftRecord | None) -> None:
        self.maintenance_table.setRowCount(0)
        self.attachments_table.setRowCount(0)
        self.history_table.setRowCount(0)
        if record is None:
            self.custom_capability_list.setPlainText("")
            return

        # Attachments
        for attachment in record.attachments:
            row = self.attachments_table.rowCount()
            self.attachments_table.insertRow(row)
            self.attachments_table.setItem(row, 0, QTableWidgetItem(str(attachment.get("name", ""))))
            self.attachments_table.setItem(row, 1, QTableWidgetItem(str(attachment.get("type", ""))))
            size = attachment.get("size")
            size_display = f"{int(size)} B" if isinstance(size, (int, float)) else ""
            self.attachments_table.setItem(row, 2, QTableWidgetItem(size_display))
            self.attachments_table.setItem(row, 3, QTableWidgetItem(str(attachment.get("uploaded", ""))))

        # History
        for entry in record.history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row, 0, QTableWidgetItem(str(entry.get("ts", ""))))
            self.history_table.setItem(row, 1, QTableWidgetItem(str(entry.get("actor", ""))))
            self.history_table.setItem(row, 2, QTableWidgetItem(str(entry.get("details", ""))))

        self.custom_capability_list.setPlainText(
            "\n".join(
                sorted({entry.get("details", "") for entry in record.history if entry.get("action") == "Capability"})
            )
        )

    # Saving -------------------------------------------------------------
    def _save_field(self, field: str, value: Any) -> None:
        record_id = self._current_record_id()
        if record_id is None:
            return
        try:
            updated = self._repository.update_aircraft(record_id, {field: value})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save Failed", str(exc))
            return
        self._selected_record = updated
        self._refresh_table()

    def _save_make_model(self) -> None:
        record_id = self._current_record_id()
        if record_id is None:
            return
        text = self.make_model_edit.text().strip()
        payload: dict[str, Any] = {"make_model_display": text}
        if " " in text:
            make, model = text.split(" ", 1)
            payload["make"] = make
            payload["model"] = model
        try:
            updated = self._repository.update_aircraft(record_id, payload)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save Failed", str(exc))
            return
        self._selected_record = updated
        self._refresh_table()

    def _schedule_notes_save(self) -> None:
        self._notes_timer.stop()
        self._notes_timer.timeout.connect(self._save_notes_once, Qt.UniqueConnection)
        self._notes_timer.start()

    def _save_notes_once(self) -> None:
        record_id = self._current_record_id()
        if record_id is None:
            return
        notes = self.notes_edit.toPlainText()
        try:
            updated = self._repository.update_aircraft(record_id, {"notes": notes})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save Failed", str(exc))
            return
        self._selected_record = updated
        self._refresh_table()

    # Quick actions -----------------------------------------------------
    def _set_status(self, ids: Sequence[int | None]) -> None:
        valid_ids = [i for i in ids if i is not None]
        if not valid_ids:
            return
        dialog = SetStatusDialog(self._repository.DEFAULT_STATUSES, len(valid_ids), parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self._repository.set_status(valid_ids, dialog.status, dialog.notes)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Status Update Failed", str(exc))
        self._refresh_table()

    def _assign_team(self, ids: Sequence[int | None]) -> None:
        valid_ids = [i for i in ids if i is not None]
        if not valid_ids:
            return
        dialog = AssignTeamDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        team_name = dialog.team_name or None
        try:
            self._repository.assign_team(valid_ids, team_name, team_name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Assignment Failed", str(exc))
        self._refresh_table()

    def _clear_assignment(self, ids: Sequence[int | None]) -> None:
        valid_ids = [i for i in ids if i is not None]
        if not valid_ids:
            return
        try:
            self._repository.clear_assignment(valid_ids)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Clear Assignment Failed", str(exc))
        self._refresh_table()

    def _collect_selected_ids(self) -> list[int]:
        ids = set(self._table_model.checked_ids())
        selection = self.table_view.selectionModel()
        if selection is not None:
            for index in selection.selectedRows():
                record = self._table_model.row_record(index.row())
                if record and record.id is not None:
                    ids.add(int(record.id))
        return sorted(ids)

    def _bulk_set_status(self) -> None:
        ids = self._collect_selected_ids()
        if not ids:
            QMessageBox.information(self, "No Selection", "Select one or more aircraft to change status.")
            return
        self._set_status(ids)

    def _bulk_assign_team(self) -> None:
        ids = self._collect_selected_ids()
        if not ids:
            QMessageBox.information(self, "No Selection", "Select one or more aircraft to assign.")
            return
        self._assign_team(ids)

    def _bulk_clear_assignment(self) -> None:
        ids = self._collect_selected_ids()
        if not ids:
            QMessageBox.information(self, "No Selection", "Select aircraft to clear assignment.")
            return
        self._clear_assignment(ids)

    def _bulk_delete(self, single: bool = False) -> None:
        if single:
            record_id = self._current_record_id()
            ids = [record_id] if record_id is not None else []
        else:
            ids = self._collect_selected_ids()
        if not ids:
            QMessageBox.information(self, "No Selection", "Select aircraft to delete.")
            return
        if len(ids) == 1:
            record = self._repository.fetch_aircraft(ids[0])
            tail = record.tail_number if record else "this aircraft"
            confirm = QMessageBox.question(
                self,
                "Delete Aircraft",
                f"Delete aircraft {tail}? This action cannot be undone.",
            )
            if confirm != QMessageBox.Yes:
                return
        else:
            confirm = QMessageBox.question(
                self,
                "Delete Aircraft",
                f"Delete {len(ids)} aircraft? This action cannot be undone.",
            )
            if confirm != QMessageBox.Yes:
                return
        try:
            self._repository.delete_aircraft(ids)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Delete Failed", str(exc))
        self._refresh_table(reset_page=True)

    def _print_summary(self) -> None:
        record = self._selected_record
        if record is None:
            QMessageBox.information(self, "No Aircraft Selected", "Select an aircraft to print a summary.")
            return
        QMessageBox.information(
            self,
            "Print Summary",
            f"Summary for {record.tail_number} would be generated as a PDF in the production build.",
        )

    def _open_log(self) -> None:
        record = self._selected_record
        if record is None:
            QMessageBox.information(self, "No Aircraft Selected", "Select an aircraft to open its log.")
            return
        QMessageBox.information(
            self,
            "Open Log",
            f"History tab shows the latest entries for {record.tail_number}.",
        )

    # Tab builders -------------------------------------------------------
    def _build_details_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.serial_edit = QLineEdit(widget)
        self.serial_edit.editingFinished.connect(lambda: self._save_field("serial_number", self.serial_edit.text().strip() or None))
        layout.addRow("Serial #:", self.serial_edit)

        self.year_spin = QSpinBox(widget)
        self.year_spin.setRange(1900, 2100)
        self.year_spin.valueChanged.connect(lambda value: self._save_field("year", int(value)))
        layout.addRow("Year:", self.year_spin)

        self.owner_edit = QLineEdit(widget)
        self.owner_edit.editingFinished.connect(lambda: self._save_field("owner_operator", self.owner_edit.text().strip() or None))
        layout.addRow("Owner/Operator:", self.owner_edit)

        self.registration_edit = QLineEdit(widget)
        self.registration_edit.setPlaceholderText("YYYY-MM-DD")
        self.registration_edit.editingFinished.connect(lambda: self._save_field("registration_exp", self.registration_edit.text().strip() or None))
        layout.addRow("Reg. Exp:", self.registration_edit)

        self.inspection_edit = QLineEdit(widget)
        self.inspection_edit.setPlaceholderText("YYYY-MM-DD")
        self.inspection_edit.editingFinished.connect(lambda: self._save_field("inspection_due", self.inspection_edit.text().strip() or None))
        layout.addRow("Inspection Due:", self.inspection_edit)

        self.last100_edit = QLineEdit(widget)
        self.last100_edit.setPlaceholderText("YYYY-MM-DD")
        self.last100_edit.editingFinished.connect(lambda: self._save_field("last_100hr", self.last100_edit.text().strip() or None))
        layout.addRow("Last 100-hr:", self.last100_edit)

        self.next100_edit = QLineEdit(widget)
        self.next100_edit.setPlaceholderText("YYYY-MM-DD")
        self.next100_edit.editingFinished.connect(lambda: self._save_field("next_100hr", self.next100_edit.text().strip() or None))
        layout.addRow("Next 100-hr:", self.next100_edit)

        return widget

    def _build_capabilities_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(QLabel("Custom capability tags", widget))

        entry_row = QHBoxLayout()
        self.custom_capability_edit = QLineEdit(widget)
        self.custom_capability_edit.setPlaceholderText("Enter capability (e.g. Water Bucket)")
        entry_row.addWidget(self.custom_capability_edit)
        add_btn = QPushButton("Add", widget)
        add_btn.clicked.connect(self._add_custom_capability)
        entry_row.addWidget(add_btn)
        layout.addLayout(entry_row)

        self.custom_capability_list = QTextEdit(widget)
        self.custom_capability_list.setReadOnly(True)
        layout.addWidget(self.custom_capability_list, 1)
        return widget

    def _build_maintenance_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.maintenance_table = QTableWidget(0, 5, widget)
        self.maintenance_table.setHorizontalHeaderLabels(["Date", "Type", "Notes", "OOS", "Entered By"])
        self.maintenance_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.maintenance_table, 1)

        add_btn = QPushButton("Add Entry", widget)
        add_btn.clicked.connect(self._add_maintenance_entry)
        layout.addWidget(add_btn)
        return widget

    def _build_attachments_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.attachments_table = QTableWidget(0, 4, widget)
        self.attachments_table.setHorizontalHeaderLabels(["Name", "Type", "Size", "Uploaded"])
        self.attachments_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.attachments_table, 1)

        add_btn = QPushButton("Add Attachment…", widget)
        add_btn.clicked.connect(self._add_attachment)
        layout.addWidget(add_btn)
        return widget

    def _build_history_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.history_table = QTableWidget(0, 3, widget)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "Actor", "Details"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.history_table, 1)

        export_btn = QPushButton("Export History", widget)
        export_btn.clicked.connect(self._export_history)
        layout.addWidget(export_btn)
        return widget

    # Tab helpers --------------------------------------------------------
    def _add_custom_capability(self) -> None:
        text = self.custom_capability_edit.text().strip()
        record = self._selected_record
        if not text or record is None or record.id is None:
            return
        entry = {
            "ts": self._timestamp(),
            "actor": "user",
            "action": "Capability",
            "details": text,
        }
        history = list(record.history) + [entry]
        try:
            updated = self._repository.update_aircraft(record.id, {"history": history})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Capability Add Failed", str(exc))
            return
        self.custom_capability_edit.clear()
        self._selected_record = updated
        self._refresh_table()

    def _add_maintenance_entry(self) -> None:
        record = self._selected_record
        if record is None or record.id is None:
            QMessageBox.information(self, "No Aircraft Selected", "Select an aircraft to log maintenance.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Maintenance Entry")
        form = QFormLayout(dialog)

        date_edit = QLineEdit(dialog)
        date_edit.setPlaceholderText("YYYY-MM-DD")
        type_edit = QLineEdit(dialog)
        notes_edit = QLineEdit(dialog)
        oos_check = QCheckBox("Out of Service", dialog)
        by_edit = QLineEdit(dialog)

        form.addRow("Date:", date_edit)
        form.addRow("Type:", type_edit)
        form.addRow("Notes:", notes_edit)
        form.addRow("OOS:", oos_check)
        form.addRow("Entered By:", by_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, dialog)
        form.addRow(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.Accepted:
            return

        entry = {
            "ts": date_edit.text().strip() or self._timestamp(),
            "actor": by_edit.text().strip() or "user",
            "action": "Maintenance",
            "details": f"{type_edit.text().strip()} — {notes_edit.text().strip()}",
            "oos": bool(oos_check.isChecked()),
        }
        history = list(record.history) + [entry]
        payload: dict[str, Any] = {"history": history}
        if entry["oos"]:
            payload["status"] = "Out of Service"
        try:
            updated = self._repository.update_aircraft(record.id, payload)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Maintenance Entry Failed", str(exc))
            return
        self._selected_record = updated
        self._refresh_table()

    def _add_attachment(self) -> None:
        record = self._selected_record
        if record is None or record.id is None:
            QMessageBox.information(self, "No Aircraft Selected", "Select an aircraft to attach files.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select Attachment")
        if not path:
            return
        file_path = Path(path)
        attachment = {
            "name": file_path.name,
            "type": file_path.suffix.lstrip(".") or "file",
            "size": file_path.stat().st_size if file_path.exists() else None,
            "uploaded": self._timestamp(),
        }
        attachments = list(record.attachments) + [attachment]
        try:
            updated = self._repository.update_aircraft(record.id, {"attachments": attachments})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Attachment Failed", str(exc))
            return
        self._selected_record = updated
        self._refresh_table()

    def _export_history(self) -> None:
        record = self._selected_record
        if record is None:
            QMessageBox.information(self, "No Aircraft Selected", "Select an aircraft to export history.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export History", f"{record.tail_number}_history.csv")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Timestamp", "Actor", "Action", "Details"])
                for entry in record.history:
                    writer.writerow([
                        entry.get("ts", ""),
                        entry.get("actor", ""),
                        entry.get("action", ""),
                        entry.get("details", ""),
                    ])
        except OSError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", str(exc))

    # Dialog entry points -----------------------------------------------
    def _open_add_dialog(self) -> None:
        dialog = NewAircraftDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.payload()
        try:
            created = self._repository.create_aircraft(payload)
        except ValueError as exc:
            QMessageBox.warning(self, "Create Failed", str(exc))
            return
        self._selected_record = created
        self._refresh_table(reset_page=True)

    def _open_import_dialog(self) -> None:
        dialog = ImportAircraftDialog(self._repository, self)
        dialog.exec()
        self._refresh_table(reset_page=True)

    def _export_current_view(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Aircraft", "aircraft_inventory.csv")
        if not path:
            return
        rows = self._repository.export_rows(
            self._filters.to_repository_filters(),
            sort_key=self._filters.sort_key,
            sort_order=self._filters.sort_order,
        )
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                if rows:
                    writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow([row.get(key, "") for key in rows[0].keys()])
        except OSError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _timestamp(self) -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat(timespec="seconds") + "Z"


class NewAircraftDialog(QDialog):
    """Dialog used to capture required data for new aircraft records."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Aircraft")
        self.setModal(True)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.tail_edit = QLineEdit(self)
        self.tail_edit.setPlaceholderText("Tail number (unique)")
        form.addRow("Tail #:", self.tail_edit)

        self.callsign_edit = QLineEdit(self)
        form.addRow("Callsign:", self.callsign_edit)

        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["Helicopter", "Fixed-Wing", "UAS", "Gyroplane", "Other"])
        form.addRow("Type:", self.type_combo)

        self.make_edit = QLineEdit(self)
        form.addRow("Make/Model:", self.make_edit)

        self.base_edit = QLineEdit(self)
        form.addRow("Base:", self.base_edit)

        self.status_combo = QComboBox(self)
        self.status_combo.addItems(["Available", "Assigned", "Out of Service", "Standby", "In Transit"])
        form.addRow("Status:", self.status_combo)

        self.assigned_edit = QLineEdit(self)
        form.addRow("Assigned Team:", self.assigned_edit)

        self.current_loc_edit = QLineEdit(self)
        form.addRow("Current Loc:", self.current_loc_edit)

        self.fuel_combo = QComboBox(self)
        self.fuel_combo.addItems(["Jet A", "Avgas", "Electric", "Other"])
        form.addRow("Fuel:", self.fuel_combo)

        self.range_spin = QSpinBox(self)
        self.range_spin.setRange(0, 5000)
        form.addRow("Range (nm):", self.range_spin)

        self.endurance_spin = QDoubleSpinBox(self)
        self.endurance_spin.setRange(0.0, 50.0)
        self.endurance_spin.setDecimals(1)
        form.addRow("Endurance (hr):", self.endurance_spin)

        self.cruise_spin = QSpinBox(self)
        self.cruise_spin.setRange(0, 600)
        form.addRow("Cruise (kt):", self.cruise_spin)

        crew_widget = QWidget(self)
        crew_layout = QHBoxLayout(crew_widget)
        crew_layout.setContentsMargins(0, 0, 0, 0)
        crew_layout.setSpacing(6)
        self.crew_min_spin = QSpinBox(crew_widget)
        self.crew_min_spin.setRange(0, 20)
        self.crew_max_spin = QSpinBox(crew_widget)
        self.crew_max_spin.setRange(0, 20)
        crew_layout.addWidget(self.crew_min_spin)
        crew_layout.addWidget(QLabel("/", crew_widget))
        crew_layout.addWidget(self.crew_max_spin)
        form.addRow("Crew Min/Max:", crew_widget)

        self.adsb_edit = QLineEdit(self)
        form.addRow("ADS-B Hex:", self.adsb_edit)

        radio_widget = QWidget(self)
        radio_layout = QHBoxLayout(radio_widget)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(6)
        self.radio_air = QCheckBox("VHF Air", radio_widget)
        self.radio_sar = QCheckBox("VHF SAR", radio_widget)
        self.radio_uhf = QCheckBox("UHF", radio_widget)
        radio_layout.addWidget(self.radio_air)
        radio_layout.addWidget(self.radio_sar)
        radio_layout.addWidget(self.radio_uhf)
        form.addRow("Radio Fits:", radio_widget)

        cap_widget = QWidget(self)
        cap_layout = QHBoxLayout(cap_widget)
        cap_layout.setContentsMargins(0, 0, 0, 0)
        cap_layout.setSpacing(6)
        self.cap_hoist = QCheckBox("Hoist", cap_widget)
        self.cap_nvg = QCheckBox("NVG", cap_widget)
        self.cap_flir = QCheckBox("FLIR", cap_widget)
        self.cap_ifr = QCheckBox("IFR", cap_widget)
        cap_layout.addWidget(self.cap_hoist)
        cap_layout.addWidget(self.cap_nvg)
        cap_layout.addWidget(self.cap_flir)
        cap_layout.addWidget(self.cap_ifr)
        form.addRow("Capabilities:", cap_widget)

        self.payload_spin = QSpinBox(self)
        self.payload_spin.setRange(0, 10_000)
        form.addRow("Payload/Winch:", self.payload_spin)

        self.med_combo = QComboBox(self)
        self.med_combo.addItems(["None", "Basic", "Advanced"])
        form.addRow("Med Config:", self.med_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save, self)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.tail_edit.text().strip():
            QMessageBox.warning(self, "Missing Tail #", "Tail number is required.")
            return
        self.accept()

    def payload(self) -> dict[str, Any]:
        return {
            "tail_number": self.tail_edit.text().strip(),
            "callsign": self.callsign_edit.text().strip() or None,
            "type": self.type_combo.currentText(),
            "make_model_display": self.make_edit.text().strip() or None,
            "base": self.base_edit.text().strip() or None,
            "status": self.status_combo.currentText(),
            "assigned_team_name": self.assigned_edit.text().strip() or None,
            "current_location": self.current_loc_edit.text().strip() or None,
            "fuel_type": self.fuel_combo.currentText(),
            "range_nm": self.range_spin.value(),
            "endurance_hr": float(self.endurance_spin.value()),
            "cruise_kt": self.cruise_spin.value(),
            "crew_min": self.crew_min_spin.value(),
            "crew_max": self.crew_max_spin.value(),
            "adsb_hex": self.adsb_edit.text().strip() or None,
            "radio_vhf_air": self.radio_air.isChecked(),
            "radio_vhf_sar": self.radio_sar.isChecked(),
            "radio_uhf": self.radio_uhf.isChecked(),
            "cap_hoist": self.cap_hoist.isChecked(),
            "cap_nvg": self.cap_nvg.isChecked(),
            "cap_flir": self.cap_flir.isChecked(),
            "cap_ifr": self.cap_ifr.isChecked(),
            "payload_kg": self.payload_spin.value(),
            "med_config": self.med_combo.currentText(),
        }


class ImportAircraftDialog(QDialog):
    """Simple importer supporting CSV or JSON payloads."""

    def __init__(self, repository: AircraftRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Aircraft")
        self.setModal(True)
        self._repository = repository
        self._rows: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit(self)
        browse_btn = QPushButton("Browse…", self)
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        self.preview = QTableWidget(0, 0, self)
        self.preview.setMinimumHeight(220)
        layout.addWidget(self.preview, 1)

        options = QHBoxLayout()
        self.update_check = QCheckBox("Update existing by Tail #", self)
        self.update_check.setChecked(True)
        options.addWidget(self.update_check)
        options.addWidget(QLabel("On conflict:", self))
        self.conflict_combo = QComboBox(self)
        self.conflict_combo.addItems(["Skip", "Overwrite", "Merge"])
        options.addWidget(self.conflict_combo)
        options.addStretch(1)
        layout.addLayout(options)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, self)
        buttons.button(QDialogButtonBox.Ok).setText("Import")
        buttons.accepted.connect(self._do_import)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Aircraft File", filter="CSV or JSON (*.csv *.json)")
        if not path:
            return
        self.file_edit.setText(path)
        self._load_file(Path(path))

    def _load_file(self, path: Path) -> None:
        try:
            if path.suffix.lower() == ".json":
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    self._rows = [dict(row) for row in data if isinstance(row, dict)]
                else:
                    self._rows = []
            else:
                with path.open("r", encoding="utf-8-sig") as handle:
                    reader = csv.DictReader(handle)
                    self._rows = [dict(row) for row in reader]
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            self._rows = []
            return

        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self.preview.clear()
        self.preview.setRowCount(0)
        self.preview.setColumnCount(0)
        if not self._rows:
            return
        headers = list(self._rows[0].keys())
        self.preview.setColumnCount(len(headers))
        self.preview.setHorizontalHeaderLabels(headers)
        for row_idx, row in enumerate(self._rows[:25]):
            self.preview.insertRow(row_idx)
            for col_idx, header in enumerate(headers):
                value = row.get(header, "")
                self.preview.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

    def _do_import(self) -> None:
        if not self._rows:
            QMessageBox.information(self, "No Data", "Select a CSV or JSON file first.")
            return
        result = self._repository.import_rows(
            self._rows,
            update_existing=self.update_check.isChecked(),
            conflict_mode=self.conflict_combo.currentText().lower(),
        )
        QMessageBox.information(
            self,
            "Import Complete",
            f"Inserted {result.get('inserted', 0)} records, updated {result.get('updated', 0)} records.",
        )
        self.accept()
