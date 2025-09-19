"""Qt Widgets implementation of the Aircraft Inventory window."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..repository import AircraftRepository

STATUS_OPTIONS = ["Available", "Assigned", "Out of Service", "Standby", "In Transit"]
TYPE_OPTIONS = ["Helicopter", "Fixed-Wing", "UAS", "Gyroplane", "Other"]
FUEL_OPTIONS = ["Jet A", "Avgas", "Electric", "Other"]
MED_CONFIG_OPTIONS = ["None", "Basic", "Advanced"]
CAPABILITY_KEYS = ["Hoist", "Night Ops", "FLIR", "IFR"]
RADIO_KEYS = ["VHF Air", "VHF SAR", "UHF"]
PAGE_SIZE = 50


@dataclass
class AircraftFilterState:
    search: str = ""
    type_filter: str = "All"
    status_filter: str = "All"
    base_filter: str = "All"
    sort_key: str = "tail_number"
    sort_desc: bool = False
    capabilities: set[str] = field(default_factory=set)
    fuels: set[str] = field(default_factory=set)
    night_ops: bool = False
    ifr: bool = False
    hoist: bool = False
    flir: bool = False

    def active_filter_count(self) -> int:
        count = 0
        if self.type_filter != "All":
            count += 1
        if self.status_filter != "All":
            count += 1
        if self.base_filter != "All":
            count += 1
        count += len(self.capabilities)
        count += len(self.fuels)
        count += int(self.night_ops)
        count += int(self.ifr)
        count += int(self.hoist)
        count += int(self.flir)
        return count


class AircraftTableModel(QAbstractTableModel):
    """Table model presenting aircraft rows with checkbox selection."""

    selectionChanged = Signal(int, bool)
    headers = ["", "Tail #", "Callsign", "Type", "Make/Model", "Status", "Base", "Assigned To"]

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._records: List[Dict[str, Any]] = []
        self._selected_ids: set[int] = set()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.headers[section]
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        record = self._records[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            if column == 1:
                return record.get("tail_number", "")
            if column == 2:
                return record.get("callsign", "")
            if column == 3:
                return record.get("type", "")
            if column == 4:
                return record.get("make_model", "")
            if column == 5:
                return record.get("status", "")
            if column == 6:
                return record.get("base", "")
            if column == 7:
                return record.get("assigned_team_name") or "(none)"
        if role == Qt.CheckStateRole and column == 0:
            rid = record.get("id")
            if rid is None:
                return Qt.Unchecked
            return Qt.Checked if rid in self._selected_ids else Qt.Unchecked
        if role == Qt.TextAlignmentRole and column == 1:
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def flags(self, index: QModelIndex):  # type: ignore[override]
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() == 0:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole):  # type: ignore[override]
        if not index.isValid() or index.column() != 0 or role != Qt.CheckStateRole:
            return False
        record = self._records[index.row()]
        rid = record.get("id")
        if rid is None:
            return False
        checked = value == Qt.Checked
        changed = False
        if checked and rid not in self._selected_ids:
            self._selected_ids.add(int(rid))
            changed = True
        elif not checked and rid in self._selected_ids:
            self._selected_ids.remove(int(rid))
            changed = True
        if changed:
            self.selectionChanged.emit(int(rid), checked)
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
        return changed

    def set_records(self, records: Sequence[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def set_selected_ids(self, selected: Iterable[int]) -> None:
        self._selected_ids = {int(v) for v in selected}
        if self._records:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._records) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [Qt.CheckStateRole])

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None


class DebouncedUpdater(QObject):
    """Collects key/value updates and emits them after a short delay."""

    patchReady = Signal(dict)

    def __init__(self, parent: Optional[QObject] = None, interval_ms: int = 400) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)
        self._pending: Dict[str, Any] = {}
        self._record_id: Optional[int] = None

    def set_record_id(self, record_id: Optional[int]) -> None:
        self._record_id = record_id
        self._pending.clear()
        self._timer.stop()

    def add_update(self, key: str, value: Any) -> None:
        if self._record_id is None:
            return
        self._pending[key] = value
        self._timer.start()

    def _flush(self) -> None:
        if self._record_id is None or not self._pending:
            return
        payload = {"id": self._record_id, **self._pending}
        self._pending = {}
        self.patchReady.emit(payload)

class AircraftDetailPane(QWidget):
    """Right-hand detail pane with autosave form."""

    patchReady = Signal(dict)
    requestAssign = Signal()
    requestStatus = Signal()
    requestClearAssignment = Signal()
    requestPrint = Signal()
    requestOpenLog = Signal()
    requestDelete = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._record: Optional[Dict[str, Any]] = None
        self._bases: List[str] = []
        self._updating = False
        self._debouncer = DebouncedUpdater(self)
        self._debouncer.patchReady.connect(self.patchReady)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        actions_row = QHBoxLayout()
        self.assign_btn = QPushButton("Assign to Team…")
        self.assign_btn.clicked.connect(self.requestAssign)
        self.status_btn = QPushButton("Set Status…")
        self.status_btn.clicked.connect(self.requestStatus)
        self.clear_assign_btn = QPushButton("Clear Assignment")
        self.clear_assign_btn.clicked.connect(self.requestClearAssignment)
        self.print_btn = QPushButton("Print Summary")
        self.print_btn.clicked.connect(self.requestPrint)
        self.log_btn = QPushButton("Open Log")
        self.log_btn.clicked.connect(self.requestOpenLog)
        self.delete_btn = QPushButton("Delete Aircraft")
        self.delete_btn.clicked.connect(self.requestDelete)
        for btn in (
            self.assign_btn,
            self.status_btn,
            self.clear_assign_btn,
            self.print_btn,
            self.log_btn,
            self.delete_btn,
        ):
            btn.setCursor(Qt.PointingHandCursor)
            actions_row.addWidget(btn)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        form_layout = QVBoxLayout(content)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(8, 8, 8, 8)

        identity_group = QGroupBox("Core Information")
        identity_form = QFormLayout(identity_group)
        identity_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.tail_display = QLabel("—")
        identity_form.addRow("Tail Number:", self.tail_display)

        self.callsign_edit = QLineEdit()
        self._bind_line_edit(self.callsign_edit, "callsign")
        identity_form.addRow("Callsign:", self.callsign_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(TYPE_OPTIONS)
        self.type_combo.currentTextChanged.connect(lambda text: self._emit_combo("type", text))
        identity_form.addRow("Type:", self.type_combo)

        make_model_widget = QWidget()
        mm_layout = QHBoxLayout(make_model_widget)
        mm_layout.setContentsMargins(0, 0, 0, 0)
        mm_layout.setSpacing(6)
        self.make_edit = QLineEdit()
        self._bind_line_edit(self.make_edit, "make")
        self.model_edit = QLineEdit()
        self._bind_line_edit(self.model_edit, "model")
        mm_layout.addWidget(self.make_edit)
        mm_layout.addWidget(self.model_edit)
        identity_form.addRow("Make / Model:", make_model_widget)

        self.base_combo = QComboBox()
        self.base_combo.setEditable(True)
        self.base_combo.currentTextChanged.connect(lambda text: self._emit_combo("base", text))
        identity_form.addRow("Base (Home):", self.base_combo)

        self.location_edit = QLineEdit()
        self._bind_line_edit(self.location_edit, "current_location")
        identity_form.addRow("Current Location:", self.location_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_OPTIONS)
        self.status_combo.currentTextChanged.connect(lambda text: self._emit_combo("status", text))
        identity_form.addRow("Status:", self.status_combo)

        self.assigned_display = QLabel("(none)")
        identity_form.addRow("Assigned Team:", self.assigned_display)

        form_layout.addWidget(identity_group)

        perf_group = QGroupBox("Performance & Avionics")
        perf_grid = QGridLayout(perf_group)
        perf_grid.setContentsMargins(12, 8, 12, 8)
        perf_grid.setHorizontalSpacing(8)

        self.fuel_combo = QComboBox()
        self.fuel_combo.addItems(FUEL_OPTIONS)
        self.fuel_combo.currentTextChanged.connect(lambda text: self._emit_combo("fuel_type", text))
        perf_grid.addWidget(QLabel("Fuel Type"), 0, 0)
        perf_grid.addWidget(self.fuel_combo, 0, 1)

        self.range_spin = QSpinBox()
        self.range_spin.setRange(0, 10000)
        self.range_spin.valueChanged.connect(lambda value: self._emit_spin("range_nm", value))
        perf_grid.addWidget(QLabel("Range (nm)"), 0, 2)
        perf_grid.addWidget(self.range_spin, 0, 3)

        self.endurance_spin = QDoubleSpinBox()
        self.endurance_spin.setRange(0.0, 48.0)
        self.endurance_spin.setDecimals(1)
        self.endurance_spin.valueChanged.connect(lambda value: self._emit_spin("endurance_hr", value))
        perf_grid.addWidget(QLabel("Endurance (hr)"), 0, 4)
        perf_grid.addWidget(self.endurance_spin, 0, 5)

        self.cruise_spin = QSpinBox()
        self.cruise_spin.setRange(0, 600)
        self.cruise_spin.valueChanged.connect(lambda value: self._emit_spin("cruise_kt", value))
        perf_grid.addWidget(QLabel("Cruise Speed (kt)"), 1, 0)
        perf_grid.addWidget(self.cruise_spin, 1, 1)

        crew_widget = QWidget()
        crew_layout = QHBoxLayout(crew_widget)
        crew_layout.setContentsMargins(0, 0, 0, 0)
        crew_layout.setSpacing(6)
        self.crew_min_spin = QSpinBox()
        self.crew_min_spin.setRange(0, 20)
        self.crew_min_spin.valueChanged.connect(lambda value: self._on_crew_changed(value, True))
        self.crew_max_spin = QSpinBox()
        self.crew_max_spin.setRange(0, 20)
        self.crew_max_spin.valueChanged.connect(lambda value: self._on_crew_changed(value, False))
        crew_layout.addWidget(self.crew_min_spin)
        crew_layout.addWidget(QLabel("/"))
        crew_layout.addWidget(self.crew_max_spin)
        perf_grid.addWidget(QLabel("Crew Min / Max"), 1, 2)
        perf_grid.addWidget(crew_widget, 1, 3)

        self.adsb_edit = QLineEdit()
        self._bind_line_edit(self.adsb_edit, "adsb_hex", transform=str.upper)
        perf_grid.addWidget(QLabel("ADS-B Hex"), 1, 4)
        perf_grid.addWidget(self.adsb_edit, 1, 5)

        radio_row = QHBoxLayout()
        radio_row.setSpacing(6)
        self.radio_buttons: Dict[str, QToolButton] = {}
        for label in RADIO_KEYS:
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, key=label: self._emit_radio(key, checked))
            radio_row.addWidget(btn)
            self.radio_buttons[label] = btn
        radio_row.addStretch()
        perf_grid.addWidget(QLabel("Radio Fits"), 2, 0)
        perf_grid.addLayout(radio_row, 2, 1, 1, 2)

        cap_row = QHBoxLayout()
        cap_row.setSpacing(6)
        self.capability_buttons: Dict[str, QToolButton] = {}
        for label in CAPABILITY_KEYS:
            btn = QToolButton()
            btn.setText(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, key=label: self._emit_capability(key, checked))
            self.capability_buttons[label] = btn
            cap_row.addWidget(btn)
        cap_row.addStretch()
        perf_grid.addWidget(QLabel("Capabilities"), 2, 3)
        perf_grid.addLayout(cap_row, 2, 4, 1, 2)

        self.payload_spin = QDoubleSpinBox()
        self.payload_spin.setRange(0.0, 10000.0)
        self.payload_spin.setSuffix(" kg")
        self.payload_spin.valueChanged.connect(lambda value: self._emit_spin("payload_kg", value))
        perf_grid.addWidget(QLabel("Payload/Winch"), 3, 0)
        perf_grid.addWidget(self.payload_spin, 3, 1)

        self.med_combo = QComboBox()
        self.med_combo.addItems(MED_CONFIG_OPTIONS)
        self.med_combo.currentTextChanged.connect(lambda text: self._emit_combo("med_config", text))
        perf_grid.addWidget(QLabel("Med Config"), 3, 2)
        perf_grid.addWidget(self.med_combo, 3, 3)

        form_layout.addWidget(perf_group)

        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Free-text notes. Supports @mention and #tag syntax.")
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self.notes_edit)
        form_layout.addWidget(notes_group)

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self._build_details_tab(), "Details")
        self.tab_widget.addTab(self._build_capabilities_tab(), "Capabilities")
        self.tab_widget.addTab(self._build_maintenance_tab(), "Maintenance")
        self.tab_widget.addTab(self._build_attachments_tab(), "Attachments")
        self.tab_widget.addTab(self._build_history_tab(), "History")
        form_layout.addWidget(self.tab_widget)

        layout.addWidget(scroll)

    def _build_details_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.serial_edit = QLineEdit()
        self._bind_line_edit(self.serial_edit, "serial_number")
        form.addRow("Serial #:", self.serial_edit)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.valueChanged.connect(lambda value: self._emit_spin("year", value if value else None))
        form.addRow("Year:", self.year_spin)
        self.owner_edit = QLineEdit()
        self._bind_line_edit(self.owner_edit, "owner_operator")
        form.addRow("Owner/Operator:", self.owner_edit)
        self.reg_edit = QLineEdit()
        self._bind_line_edit(self.reg_edit, "registration_exp")
        form.addRow("Reg. Exp (YYYY-MM-DD):", self.reg_edit)
        self.inspection_edit = QLineEdit()
        self._bind_line_edit(self.inspection_edit, "inspection_due")
        form.addRow("Inspection Due:", self.inspection_edit)
        self.last100_edit = QLineEdit()
        self._bind_line_edit(self.last100_edit, "last_100hr")
        form.addRow("Last 100-hr:", self.last100_edit)
        self.next100_edit = QLineEdit()
        self._bind_line_edit(self.next100_edit, "next_100hr")
        form.addRow("Next 100-hr:", self.next100_edit)
        return widget

    def _build_capabilities_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.capability_checks: Dict[str, QCheckBox] = {}
        for label in CAPABILITY_KEYS:
            chk = QCheckBox(label)
            chk.toggled.connect(lambda state, key=label: self._emit_capability(key, state))
            self.capability_checks[label] = chk
            layout.addWidget(chk)
        layout.addStretch()
        return widget

    def _build_maintenance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.maintenance_list = QListWidget()
        layout.addWidget(self.maintenance_list)
        add_btn = QPushButton("Add Entry")
        add_btn.clicked.connect(self._show_maintenance_placeholder)
        layout.addWidget(add_btn)
        return widget

    def _build_attachments_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.attachments_list = QListWidget()
        layout.addWidget(self.attachments_list)
        add_btn = QPushButton("Add Attachment…")
        add_btn.clicked.connect(self._show_attachment_placeholder)
        layout.addWidget(add_btn)
        return widget

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        return widget
    # ------------------------------------------------------------------
    # Signal helpers
    # ------------------------------------------------------------------
    def _bind_line_edit(self, edit: QLineEdit, key: str, transform=lambda v: v) -> None:
        def _commit() -> None:
            if self._updating:
                return
            self._debouncer.add_update(key, transform(edit.text()))

        edit.editingFinished.connect(_commit)

    def _emit_combo(self, key: str, value: str) -> None:
        if self._updating:
            return
        self._debouncer.add_update(key, value)

    def _emit_spin(self, key: str, value: Any) -> None:
        if self._updating:
            return
        self._debouncer.add_update(key, value)

    def _emit_radio(self, key: str, checked: bool) -> None:
        if self._updating:
            return
        mapping = {
            "VHF Air": "radio_vhf_air",
            "VHF SAR": "radio_vhf_sar",
            "UHF": "radio_uhf",
        }
        column = mapping.get(key)
        if column:
            self._debouncer.add_update(column, bool(checked))

    def _emit_capability(self, key: str, checked: bool) -> None:
        if self._updating:
            return
        mapping = {
            "Hoist": "cap_hoist",
            "Night Ops": "cap_nvg",
            "FLIR": "cap_flir",
            "IFR": "cap_ifr",
        }
        column = mapping.get(key)
        if column:
            self._debouncer.add_update(column, bool(checked))
            chk = self.capability_checks.get(key)
            if chk and chk.isChecked() != checked:
                chk.blockSignals(True)
                chk.setChecked(checked)
                chk.blockSignals(False)
            btn = self.capability_buttons.get(key)
            if btn and btn.isChecked() != checked:
                btn.blockSignals(True)
                btn.setChecked(checked)
                btn.blockSignals(False)

    def _on_crew_changed(self, value: int, is_min: bool) -> None:
        if self._updating:
            return
        if is_min and value > self.crew_max_spin.value():
            self.crew_max_spin.blockSignals(True)
            self.crew_max_spin.setValue(value)
            self.crew_max_spin.blockSignals(False)
            self._debouncer.add_update("crew_max", value)
        self._debouncer.add_update("crew_min" if is_min else "crew_max", value)

    def _on_notes_changed(self) -> None:
        if self._updating:
            return
        self._debouncer.add_update("notes", self.notes_edit.toPlainText())

    def _show_maintenance_placeholder(self) -> None:
        QMessageBox.information(self, "Maintenance", "Detailed maintenance tracking will be added in a later iteration.")

    def _show_attachment_placeholder(self) -> None:
        QMessageBox.information(self, "Attachments", "Attachment upload is not yet implemented in this mockup.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_bases(self, bases: Sequence[str]) -> None:
        unique = sorted({b for b in bases if b})
        self._bases = unique
        current = self.base_combo.currentText()
        self.base_combo.blockSignals(True)
        self.base_combo.clear()
        if unique:
            self.base_combo.addItems(unique)
        self.base_combo.setCurrentText(current)
        self.base_combo.blockSignals(False)

    def set_record(self, record: Optional[Dict[str, Any]]) -> None:
        self._record = record
        self._debouncer.set_record_id(record.get("id") if record else None)
        self._updating = True
        try:
            if not record:
                self.tail_display.setText("—")
                self.callsign_edit.clear()
                self.type_combo.setCurrentIndex(0)
                self.make_edit.clear()
                self.model_edit.clear()
                self.base_combo.setCurrentText("")
                self.location_edit.clear()
                self.status_combo.setCurrentIndex(0)
                self.assigned_display.setText("(none)")
                self.fuel_combo.setCurrentIndex(0)
                self.range_spin.setValue(0)
                self.endurance_spin.setValue(0.0)
                self.cruise_spin.setValue(0)
                self.crew_min_spin.setValue(0)
                self.crew_max_spin.setValue(0)
                self.adsb_edit.clear()
                for btn in self.radio_buttons.values():
                    btn.setChecked(False)
                for btn in self.capability_buttons.values():
                    btn.setChecked(False)
                for chk in self.capability_checks.values():
                    chk.setChecked(False)
                self.payload_spin.setValue(0.0)
                self.med_combo.setCurrentIndex(0)
                self.notes_edit.clear()
                self.serial_edit.clear()
                self.year_spin.setValue(self.year_spin.minimum())
                self.owner_edit.clear()
                self.reg_edit.clear()
                self.inspection_edit.clear()
                self.last100_edit.clear()
                self.next100_edit.clear()
                self.maintenance_list.clear()
                self.maintenance_list.addItem("No maintenance entries recorded.")
                self.attachments_list.clear()
                self.attachments_list.addItem("No attachments uploaded.")
                self.history_list.clear()
                self.history_list.addItem("No history yet.")
                return
            base_value = record.get("base") or ""
            if base_value and base_value not in self._bases:
                self.base_combo.addItem(base_value)
            self.tail_display.setText(record.get("tail_number", ""))
            self.callsign_edit.setText(record.get("callsign", ""))
            self.type_combo.setCurrentText(record.get("type", TYPE_OPTIONS[0]))
            self.make_edit.setText(record.get("make", ""))
            self.model_edit.setText(record.get("model", ""))
            self.base_combo.setCurrentText(base_value)
            self.location_edit.setText(record.get("current_location", ""))
            self.status_combo.setCurrentText(record.get("status", STATUS_OPTIONS[0]))
            self.assigned_display.setText(record.get("assigned_team_name") or "(none)")
            self.fuel_combo.setCurrentText(record.get("fuel_type", FUEL_OPTIONS[0]))
            self.range_spin.setValue(int(record.get("range_nm", 0) or 0))
            self.endurance_spin.setValue(float(record.get("endurance_hr", 0.0) or 0.0))
            self.cruise_spin.setValue(int(record.get("cruise_kt", 0) or 0))
            self.crew_min_spin.setValue(int(record.get("crew_min", 0) or 0))
            self.crew_max_spin.setValue(int(record.get("crew_max", 0) or 0))
            self.adsb_edit.setText(record.get("adsb_hex", ""))
            radio_map = {
                "VHF Air": record.get("radio_vhf_air", False),
                "VHF SAR": record.get("radio_vhf_sar", False),
                "UHF": record.get("radio_uhf", False),
            }
            for key, btn in self.radio_buttons.items():
                btn.setChecked(bool(radio_map.get(key)))
            cap_map = {
                "Hoist": record.get("cap_hoist", False),
                "Night Ops": record.get("cap_nvg", False),
                "FLIR": record.get("cap_flir", False),
                "IFR": record.get("cap_ifr", False),
            }
            for key, btn in self.capability_buttons.items():
                btn.setChecked(bool(cap_map.get(key)))
            for key, chk in self.capability_checks.items():
                chk.setChecked(bool(cap_map.get(key)))
            self.payload_spin.setValue(float(record.get("payload_kg", 0.0) or 0.0))
            self.med_combo.setCurrentText(record.get("med_config", MED_CONFIG_OPTIONS[0]))
            self.notes_edit.setPlainText(record.get("notes", ""))
            self.serial_edit.setText(record.get("serial_number", ""))
            year_value = record.get("year")
            if year_value:
                self.year_spin.setValue(int(year_value))
            else:
                self.year_spin.setValue(self.year_spin.minimum())
            self.owner_edit.setText(record.get("owner_operator", ""))
            self.reg_edit.setText(record.get("registration_exp", "") or "")
            self.inspection_edit.setText(record.get("inspection_due", "") or "")
            self.last100_edit.setText(record.get("last_100hr", "") or "")
            self.next100_edit.setText(record.get("next_100hr", "") or "")
            self._refresh_maintenance(record)
            self._refresh_attachments(record)
            self._refresh_history(record)
        finally:
            self._updating = False

    def _refresh_maintenance(self, record: Dict[str, Any]) -> None:
        self.maintenance_list.clear()
        history = record.get("history") or []
        entries = [entry for entry in history if entry.get("action") == "maintenance"]
        if not entries:
            self.maintenance_list.addItem("No maintenance entries recorded.")
            return
        for item in entries:
            summary = f"{item.get('ts', '')}: {item.get('details', '')}"
            self.maintenance_list.addItem(summary)

    def _refresh_attachments(self, record: Dict[str, Any]) -> None:
        self.attachments_list.clear()
        attachments = record.get("attachments") or []
        if not attachments:
            self.attachments_list.addItem("No attachments uploaded.")
            return
        for item in attachments:
            summary = f"{item.get('name', 'Attachment')} ({item.get('type', '')})"
            self.attachments_list.addItem(summary)

    def _refresh_history(self, record: Dict[str, Any]) -> None:
        self.history_list.clear()
        history = record.get("history") or []
        if not history:
            self.history_list.addItem("No history yet.")
            return
        for item in reversed(history):
            summary = f"{item.get('ts', '')} • {item.get('action', '')}: {item.get('details', '')}"
            self.history_list.addItem(summary)

class NewAircraftDialog(QDialog):
    """Modal dialog for adding new aircraft records."""

    recordCreated = Signal(dict)

    def __init__(self, repository: AircraftRepository, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("New Aircraft")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        self.resize(660, 360)
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        row = 0
        self.tail_edit = QLineEdit()
        grid.addWidget(QLabel("Tail #"), row, 0)
        grid.addWidget(self.tail_edit, row, 1)
        self.callsign_edit = QLineEdit()
        grid.addWidget(QLabel("Callsign"), row, 2)
        grid.addWidget(self.callsign_edit, row, 3)
        row += 1

        self.type_combo = QComboBox()
        self.type_combo.addItems(TYPE_OPTIONS)
        grid.addWidget(QLabel("Type"), row, 0)
        grid.addWidget(self.type_combo, row, 1)
        make_model_widget = QWidget()
        make_model_layout = QHBoxLayout(make_model_widget)
        make_model_layout.setContentsMargins(0, 0, 0, 0)
        make_model_layout.setSpacing(6)
        self.make_edit = QLineEdit()
        self.make_edit.setPlaceholderText("Make")
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("Model")
        make_model_layout.addWidget(self.make_edit)
        make_model_layout.addWidget(self.model_edit)
        grid.addWidget(QLabel("Make/Model"), row, 2)
        grid.addWidget(make_model_widget, row, 3)
        row += 1

        self.base_combo = QComboBox()
        self.base_combo.setEditable(True)
        self.base_combo.addItem("")
        for record in self.repository.list_aircraft():
            base = record.get("base")
            if base and base not in [self.base_combo.itemText(i) for i in range(self.base_combo.count())]:
                self.base_combo.addItem(base)
        grid.addWidget(QLabel("Base"), row, 0)
        grid.addWidget(self.base_combo, row, 1)
        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_OPTIONS)
        grid.addWidget(QLabel("Status"), row, 2)
        grid.addWidget(self.status_combo, row, 3)
        row += 1

        self.assigned_edit = QLineEdit()
        self.assigned_edit.setPlaceholderText("(none)")
        grid.addWidget(QLabel("Assigned Team"), row, 0)
        grid.addWidget(self.assigned_edit, row, 1)
        self.location_edit = QLineEdit()
        grid.addWidget(QLabel("Current Location"), row, 2)
        grid.addWidget(self.location_edit, row, 3)
        row += 1

        self.fuel_combo = QComboBox()
        self.fuel_combo.addItems(FUEL_OPTIONS)
        grid.addWidget(QLabel("Fuel"), row, 0)
        grid.addWidget(self.fuel_combo, row, 1)
        self.range_spin = QSpinBox()
        self.range_spin.setRange(0, 2000)
        grid.addWidget(QLabel("Range (nm)"), row, 2)
        grid.addWidget(self.range_spin, row, 3)
        row += 1

        self.endurance_spin = QDoubleSpinBox()
        self.endurance_spin.setRange(0.0, 24.0)
        self.endurance_spin.setDecimals(1)
        grid.addWidget(QLabel("Endurance (hr)"), row, 0)
        grid.addWidget(self.endurance_spin, row, 1)
        self.cruise_spin = QSpinBox()
        self.cruise_spin.setRange(0, 400)
        grid.addWidget(QLabel("Cruise (kt)"), row, 2)
        grid.addWidget(self.cruise_spin, row, 3)
        row += 1

        crew_widget = QWidget()
        crew_layout = QHBoxLayout(crew_widget)
        crew_layout.setContentsMargins(0, 0, 0, 0)
        crew_layout.setSpacing(6)
        self.crew_min_spin = QSpinBox()
        self.crew_min_spin.setRange(0, 20)
        self.crew_max_spin = QSpinBox()
        self.crew_max_spin.setRange(0, 20)
        crew_layout.addWidget(self.crew_min_spin)
        crew_layout.addWidget(QLabel("/"))
        crew_layout.addWidget(self.crew_max_spin)
        grid.addWidget(QLabel("Crew Min/Max"), row, 0)
        grid.addWidget(crew_widget, row, 1)
        self.adsb_edit = QLineEdit()
        grid.addWidget(QLabel("ADS-B Hex"), row, 2)
        grid.addWidget(self.adsb_edit, row, 3)
        row += 1

        radio_row = QHBoxLayout()
        radio_row.setSpacing(6)
        self.radio_checks: Dict[str, QCheckBox] = {}
        for key in RADIO_KEYS:
            chk = QCheckBox(key)
            self.radio_checks[key] = chk
            radio_row.addWidget(chk)
        radio_row.addStretch()
        grid.addWidget(QLabel("Radio Fits"), row, 0)
        grid.addLayout(radio_row, row, 1, 1, 3)
        row += 1

        cap_row = QHBoxLayout()
        cap_row.setSpacing(6)
        self.cap_checks: Dict[str, QCheckBox] = {}
        for key in CAPABILITY_KEYS:
            chk = QCheckBox(key)
            self.cap_checks[key] = chk
            cap_row.addWidget(chk)
        cap_row.addStretch()
        grid.addWidget(QLabel("Capabilities"), row, 0)
        grid.addLayout(cap_row, row, 1, 1, 3)
        row += 1

        self.payload_spin = QDoubleSpinBox()
        self.payload_spin.setRange(0.0, 5000.0)
        grid.addWidget(QLabel("Payload/Winch"), row, 0)
        grid.addWidget(self.payload_spin, row, 1)
        self.med_combo = QComboBox()
        self.med_combo.addItems(MED_CONFIG_OPTIONS)
        grid.addWidget(QLabel("Med Config"), row, 2)
        grid.addWidget(self.med_combo, row, 3)
        row += 1

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notes")
        grid.addWidget(QLabel("Notes"), row, 0)
        grid.addWidget(self.notes_edit, row, 1, 1, 3)

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(lambda: self._handle_save(close_after=False))
        self.save_close_btn = QPushButton("Save & Close")
        self.save_close_btn.clicked.connect(lambda: self._handle_save(close_after=True))
        for btn in (cancel_btn, self.save_btn, self.save_close_btn):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

    def _handle_save(self, close_after: bool) -> None:
        tail = self.tail_edit.text().strip().upper()
        if not tail:
            QMessageBox.warning(self, "Validation", "Tail number is required.")
            return
        for record in self.repository.list_aircraft():
            if record.get("tail_number") == tail:
                QMessageBox.warning(self, "Validation", "Tail number must be unique.")
                return
        payload = {
            "tail_number": tail,
            "callsign": self.callsign_edit.text().strip(),
            "type": self.type_combo.currentText(),
            "make": self.make_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "base": self.base_combo.currentText().strip(),
            "current_location": self.location_edit.text().strip(),
            "status": self.status_combo.currentText(),
            "assigned_team_name": self.assigned_edit.text().strip() or None,
            "fuel_type": self.fuel_combo.currentText(),
            "range_nm": self.range_spin.value(),
            "endurance_hr": self.endurance_spin.value(),
            "cruise_kt": self.cruise_spin.value(),
            "crew_min": self.crew_min_spin.value(),
            "crew_max": self.crew_max_spin.value(),
            "adsb_hex": self.adsb_edit.text().strip().upper(),
            "radio_vhf_air": self.radio_checks["VHF Air"].isChecked(),
            "radio_vhf_sar": self.radio_checks["VHF SAR"].isChecked(),
            "radio_uhf": self.radio_checks["UHF"].isChecked(),
            "cap_hoist": self.cap_checks["Hoist"].isChecked(),
            "cap_nvg": self.cap_checks["Night Ops"].isChecked(),
            "cap_flir": self.cap_checks["FLIR"].isChecked(),
            "cap_ifr": self.cap_checks["IFR"].isChecked(),
            "payload_kg": self.payload_spin.value(),
            "med_config": self.med_combo.currentText(),
            "notes": self.notes_edit.toPlainText().strip(),
        }
        try:
            record = self.repository.create_aircraft(payload)
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.critical(self, "Error", f"Failed to create aircraft: {exc}")
            return
        self.recordCreated.emit(record)
        if close_after:
            self.accept()
        else:
            self._reset_form()

    def _reset_form(self) -> None:
        self.tail_edit.clear()
        self.callsign_edit.clear()
        self.make_edit.clear()
        self.model_edit.clear()
        self.base_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.assigned_edit.clear()
        self.location_edit.clear()
        self.range_spin.setValue(0)
        self.endurance_spin.setValue(0.0)
        self.cruise_spin.setValue(0)
        self.crew_min_spin.setValue(0)
        self.crew_max_spin.setValue(0)
        self.adsb_edit.clear()
        for chk in self.radio_checks.values():
            chk.setChecked(False)
        for chk in self.cap_checks.values():
            chk.setChecked(False)
        self.payload_spin.setValue(0.0)
        self.notes_edit.clear()
        self.tail_edit.setFocus()


class SetStatusDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Status")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_OPTIONS)
        form.addRow("New Status", self.status_combo)
        self.notes_edit = QPlainTextEdit()
        form.addRow("Reason/Notes", self.notes_edit)
        layout.addLayout(form)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

    def values(self) -> Tuple[str, str]:
        return self.status_combo.currentText(), self.notes_edit.toPlainText().strip()


class AssignTeamDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign to Team")
        self.setModal(True)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.team_name_edit = QLineEdit()
        form.addRow("Team Name", self.team_name_edit)
        self.team_id_edit = QLineEdit()
        self.team_id_edit.setPlaceholderText("Optional numeric team id")
        form.addRow("Team ID", self.team_id_edit)
        self.notify_check = QCheckBox("Auto-notify Ops lead")
        self.notify_check.setChecked(True)
        form.addRow("", self.notify_check)
        layout.addLayout(form)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Assign")
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

    def values(self) -> Tuple[Optional[str], Optional[str], bool]:
        return (
            self.team_id_edit.text().strip() or None,
            self.team_name_edit.text().strip() or None,
            self.notify_check.isChecked(),
        )

class ImportAircraftDialog(QDialog):
    recordsImported = Signal(list)

    FIELD_LABELS: List[Tuple[str, str]] = [
        ("tail_number", "Tail #"),
        ("callsign", "Callsign"),
        ("type", "Type"),
        ("make", "Make"),
        ("model", "Model"),
        ("status", "Status"),
        ("base", "Base"),
        ("fuel_type", "Fuel"),
        ("adsb_hex", "ADS-B"),
        ("range_nm", "Range (nm)"),
        ("endurance_hr", "Endurance (hr)"),
        ("cruise_kt", "Cruise (kt)"),
        ("crew_min", "Crew Min"),
        ("crew_max", "Crew Max"),
        ("notes", "Notes"),
    ]

    def __init__(self, repository: AircraftRepository, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Import Aircraft")
        self.setModal(True)
        self._rows: List[Dict[str, Any]] = []
        self._headers: List[str] = []
        self._mapping: Dict[str, QComboBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.resize(720, 540)
        layout = QVBoxLayout(self)

        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(QLabel("Step 1: Choose File"))
        file_row.addWidget(self.file_edit)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        self.mapping_group = QGroupBox("Step 2: Map Fields")
        self.mapping_grid = QGridLayout(self.mapping_group)
        self.mapping_grid.setHorizontalSpacing(6)
        layout.addWidget(self.mapping_group)

        layout.addWidget(QLabel("Step 3: Preview (first 50 rows)"))
        self.preview_table = QTableWidget()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.preview_table, stretch=1)

        options_row = QHBoxLayout()
        self.update_existing_check = QCheckBox("Update existing by Tail #")
        options_row.addWidget(self.update_existing_check)
        options_row.addSpacing(12)
        options_row.addWidget(QLabel("On conflict:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(["Skip", "Overwrite", "Merge"])
        options_row.addWidget(self.conflict_combo)
        options_row.addStretch()
        layout.addLayout(options_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.import_btn = QPushButton("Import")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.import_btn)
        layout.addLayout(btn_row)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Aircraft", str(Path.home()), "Data Files (*.csv *.json)")
        if not path:
            return
        try:
            self._load_file(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Import", f"Failed to load file: {exc}")
            return
        self.file_edit.setText(path)
        self.import_btn.setEnabled(bool(self._rows))

    def _load_file(self, path: Path) -> None:
        suffix = path.suffix.lower()
        rows: List[Dict[str, Any]]
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                rows = [data]
            else:
                rows = [dict(item) for item in data]
        else:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = [dict(row) for row in reader]
        if not rows:
            raise ValueError("No rows found in file")
        self._rows = rows
        self._headers = sorted({key for row in rows for key in row.keys()})
        self._build_mapping_controls()
        self._populate_preview()

    def _build_mapping_controls(self) -> None:
        # clear existing
        for i in reversed(range(self.mapping_grid.count())):
            item = self.mapping_grid.itemAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._mapping.clear()
        for row, (field, label) in enumerate(self.FIELD_LABELS):
            combo = QComboBox()
            combo.addItem("<skip>")
            for header in self._headers:
                combo.addItem(header)
            combo.setCurrentIndex(self._auto_guess(field))
            self.mapping_grid.addWidget(QLabel(label), row, 0)
            self.mapping_grid.addWidget(combo, row, 1)
            self._mapping[field] = combo

    def _auto_guess(self, field: str) -> int:
        target = field.lower()
        for index, header in enumerate(["<skip>"] + self._headers):
            if header.lower() == target:
                return index
            if header.lower().replace("_", " ") == target:
                return index
        return 0

    def _populate_preview(self) -> None:
        headers = self._headers[:]
        self.preview_table.clear()
        self.preview_table.setColumnCount(len(headers))
        self.preview_table.setHorizontalHeaderLabels(headers)
        limit = min(50, len(self._rows))
        self.preview_table.setRowCount(limit)
        for row_idx in range(limit):
            row = self._rows[row_idx]
            for col_idx, header in enumerate(headers):
                value = row.get(header, "")
                item = QTableWidgetItem(str(value))
                self.preview_table.setItem(row_idx, col_idx, item)
        self.preview_table.resizeColumnsToContents()

    def _import(self) -> None:
        if not self._rows:
            return
        imported: List[Dict[str, Any]] = []
        created = 0
        updated = 0
        for row in self._rows:
            payload: Dict[str, Any] = {}
            for field, combo in self._mapping.items():
                header = combo.currentText()
                if not header or header == "<skip>":
                    continue
                payload[field] = row.get(header)
            tail = str(payload.get("tail_number") or "").strip().upper()
            if not tail:
                continue
            payload["tail_number"] = tail
            payload.setdefault("status", "Available")
            for numeric in ("range_nm", "cruise_kt", "crew_min", "crew_max"):
                if numeric in payload and payload[numeric] not in (None, ""):
                    try:
                        payload[numeric] = int(float(payload[numeric]))
                    except (ValueError, TypeError):
                        payload[numeric] = 0
            if "endurance_hr" in payload and payload["endurance_hr"] not in (None, ""):
                try:
                    payload["endurance_hr"] = float(payload["endurance_hr"])
                except (ValueError, TypeError):
                    payload["endurance_hr"] = 0.0
            existing = self.repository.find_by_tail(tail)
            if existing and self.update_existing_check.isChecked():
                mode = self.conflict_combo.currentText()
                patch = payload.copy()
                patch.pop("tail_number", None)
                if mode == "Skip":
                    continue
                if mode == "Merge":
                    patch = {k: v for k, v in patch.items() if v not in ("", None)}
                try:
                    record = self.repository.update_aircraft(int(existing["id"]), patch)
                except Exception:
                    continue
                imported.append(record)
                updated += 1
            elif existing and not self.update_existing_check.isChecked():
                continue
            else:
                try:
                    record = self.repository.create_aircraft(payload)
                except Exception:
                    continue
                imported.append(record)
                created += 1
        if not imported:
            QMessageBox.information(self, "Import", "No records imported.")
            return
        QMessageBox.information(
            self,
            "Import",
            f"Imported {created} new and {updated} updated aircraft.",
        )
        self.recordsImported.emit(imported)
        self.accept()

class AircraftInventoryWindow(QDialog):
    """Main window combining filters, table and detail pane."""

    def __init__(self, repository: Optional[AircraftRepository] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aircraft Inventory")
        self.resize(1300, 760)
        self.repository = repository or AircraftRepository()
        self.filter_state = AircraftFilterState()
        self.records: List[Dict[str, Any]] = []
        self.filtered_records: List[Dict[str, Any]] = []
        self.current_page = 1
        self.total_pages = 1
        self.selected_ids: set[int] = set()
        self.sort_options: List[Tuple[str, str, bool]] = [
            ("Tail # ↑", "tail_number", False),
            ("Tail # ↓", "tail_number", True),
            ("Name ↑", "callsign", False),
            ("Name ↓", "callsign", True),
            ("Type ↑", "type", False),
            ("Type ↓", "type", True),
            ("Status ↑", "status", False),
            ("Status ↓", "status", True),
            ("Base ↑", "base", False),
            ("Base ↓", "base", True),
            ("Fuel ↑", "fuel_type", False),
            ("Fuel ↓", "fuel_type", True),
            ("Endurance ↑", "endurance_hr", False),
            ("Endurance ↓", "endurance_hr", True),
            ("Updated ↑", "updated_at", False),
            ("Updated ↓", "updated_at", True),
        ]
        self.table_model = AircraftTableModel(self)
        self.table_model.selectionChanged.connect(self._on_checkbox_selection)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self._apply_filters)
        self._build_ui()
        self._setup_shortcuts()
        self._load_records()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Toolbar
        toolbar = QHBoxLayout()
        title_lbl = QLabel("Aircraft Inventory Management")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 600;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._open_add_dialog)
        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._open_import_dialog)
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._export_records)
        self.bulk_btn = QToolButton()
        self.bulk_btn.setText("Bulk Actions")
        self.bulk_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.bulk_menu = QMenu(self.bulk_btn)
        self.bulk_btn.setMenu(self.bulk_menu)
        self._populate_bulk_menu()
        for btn in (self.add_btn, self.import_btn, self.export_btn, self.bulk_btn):
            toolbar.addWidget(btn)
        layout.addLayout(toolbar)

        # Filters
        filter_frame = QFrame()
        filter_frame.setFrameShape(QFrame.StyledPanel)
        filter_layout = QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(8, 8, 8, 8)
        filter_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search tail #, callsign, model, ADS-B, base")
        self.search_edit.textChanged.connect(self._on_search_text)
        top_row.addWidget(self.search_edit, stretch=2)
        top_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("All")
        self.type_combo.addItems(TYPE_OPTIONS)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        top_row.addWidget(self.type_combo)
        top_row.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("All")
        self.status_combo.addItems(STATUS_OPTIONS)
        self.status_combo.currentTextChanged.connect(self._on_status_changed)
        top_row.addWidget(self.status_combo)
        top_row.addWidget(QLabel("Base:"))
        self.base_combo = QComboBox()
        self.base_combo.addItem("All")
        self.base_combo.currentTextChanged.connect(self._on_base_changed)
        top_row.addWidget(self.base_combo)
        top_row.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        for label, key, desc in self.sort_options:
            self.sort_combo.addItem(label, (key, desc))
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self.sort_combo.setCurrentIndex(0)
        top_row.addWidget(self.sort_combo)
        filter_layout.addLayout(top_row)

        second_row = QHBoxLayout()
        second_row.setSpacing(6)
        self.filters_label = QLabel("Filters")
        second_row.addWidget(self.filters_label)
        self.capabilities_btn = QToolButton()
        self.capabilities_btn.setText("Capabilities")
        self.capabilities_btn.setPopupMode(QToolButton.InstantPopup)
        self.capabilities_menu = QMenu(self.capabilities_btn)
        self.capabilities_actions: Dict[str, QAction] = {}
        for label in CAPABILITY_KEYS:
            action = self.capabilities_menu.addAction(label)
            action.setCheckable(True)
            action.toggled.connect(lambda state, key=label: self._on_capability_filter(key, state))
            self.capabilities_actions[label] = action
        self.capabilities_btn.setMenu(self.capabilities_menu)
        second_row.addWidget(self.capabilities_btn)

        self.fuel_btn = QToolButton()
        self.fuel_btn.setText("Fuel")
        self.fuel_btn.setPopupMode(QToolButton.InstantPopup)
        self.fuel_menu = QMenu(self.fuel_btn)
        self.fuel_actions: Dict[str, QAction] = {}
        for fuel in FUEL_OPTIONS:
            action = self.fuel_menu.addAction(fuel)
            action.setCheckable(True)
            action.toggled.connect(lambda state, key=fuel: self._on_fuel_filter(key, state))
            self.fuel_actions[fuel] = action
        self.fuel_btn.setMenu(self.fuel_menu)
        second_row.addWidget(self.fuel_btn)

        self.night_btn = QToolButton()
        self.night_btn.setText("Night Ops")
        self.night_btn.setCheckable(True)
        self.night_btn.toggled.connect(lambda state: self._on_quick_filter("night_ops", state))
        second_row.addWidget(self.night_btn)

        self.ifr_btn = QToolButton()
        self.ifr_btn.setText("IFR")
        self.ifr_btn.setCheckable(True)
        self.ifr_btn.toggled.connect(lambda state: self._on_quick_filter("ifr", state))
        second_row.addWidget(self.ifr_btn)

        self.hoist_btn = QToolButton()
        self.hoist_btn.setText("Hoist")
        self.hoist_btn.setCheckable(True)
        self.hoist_btn.toggled.connect(lambda state: self._on_quick_filter("hoist", state))
        second_row.addWidget(self.hoist_btn)

        self.flir_btn = QToolButton()
        self.flir_btn.setText("FLIR")
        self.flir_btn.setCheckable(True)
        self.flir_btn.toggled.connect(lambda state: self._on_quick_filter("flir", state))
        second_row.addWidget(self.flir_btn)

        reset_btn = QPushButton("Reset Filters")
        reset_btn.clicked.connect(self._reset_filters)
        second_row.addWidget(reset_btn)
        second_row.addStretch()
        filter_layout.addLayout(second_row)
        layout.addWidget(filter_frame)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.doubleClicked.connect(self._on_row_activated)
        self.table_view.selectionModel().selectionChanged.connect(lambda *_: self._update_detail_from_selection())
        left_layout.addWidget(self.table_view)

        pagination_row = QHBoxLayout()
        self.pagination_label = QLabel("Rows: 0")
        pagination_row.addWidget(self.pagination_label)
        pagination_row.addStretch()
        self.first_page_btn = QPushButton("<<")
        self.first_page_btn.clicked.connect(lambda: self._change_page(1))
        self.prev_page_btn = QPushButton("<")
        self.prev_page_btn.clicked.connect(lambda: self._change_page(self.current_page - 1))
        self.page_info_label = QLabel("Page 1/1")
        self.next_page_btn = QPushButton(">")
        self.next_page_btn.clicked.connect(lambda: self._change_page(self.current_page + 1))
        self.last_page_btn = QPushButton(">>")
        self.last_page_btn.clicked.connect(lambda: self._change_page(self.total_pages))
        for btn in (
            self.first_page_btn,
            self.prev_page_btn,
            self.page_info_label,
            self.next_page_btn,
            self.last_page_btn,
        ):
            pagination_row.addWidget(btn)
        pagination_row.addStretch()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_filtered)
        self.clear_selection_btn = QPushButton("Clear")
        self.clear_selection_btn.clicked.connect(self._clear_selection)
        pagination_row.addWidget(self.select_all_btn)
        pagination_row.addWidget(self.clear_selection_btn)
        left_layout.addLayout(pagination_row)

        splitter.addWidget(left_panel)
        self.detail_pane = AircraftDetailPane()
        self.detail_pane.patchReady.connect(self._handle_patch)
        self.detail_pane.requestAssign.connect(self._open_assign_dialog)
        self.detail_pane.requestStatus.connect(self._open_set_status_dialog)
        self.detail_pane.requestClearAssignment.connect(self._clear_assignment)
        self.detail_pane.requestPrint.connect(self._print_current_summary)
        self.detail_pane.requestOpenLog.connect(self._open_history_tab)
        self.detail_pane.requestDelete.connect(self._delete_current_record)
        splitter.addWidget(self.detail_pane)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        # Status legend
        legend_frame = QFrame()
        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(8, 4, 8, 4)
        legend_layout.setSpacing(12)
        legend_layout.addWidget(QLabel("Status Legend:"))
        for label, color in [
            ("Available", "#2E8B57"),
            ("Assigned", "#1E88E5"),
            ("Out of Service", "#C62828"),
            ("Standby", "#F9A825"),
            ("In Transit", "#6D4C41"),
        ]:
            swatch = QFrame()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
            legend_layout.addWidget(swatch)
            legend_layout.addWidget(QLabel(label))
        legend_layout.addStretch()
        layout.addWidget(legend_frame)

        self._update_bulk_state()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._open_add_dialog)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self._open_import_dialog)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._export_records)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_edit.setFocus)

    # ------------------------------------------------------------------
    # Data loading and filtering
    # ------------------------------------------------------------------
    def _load_records(self) -> None:
        self.records = self.repository.list_aircraft()
        existing_ids = {int(record.get("id")) for record in self.records if record.get("id") is not None}
        self.selected_ids = {rid for rid in self.selected_ids if rid in existing_ids}
        self._update_base_options()
        self._apply_filters()

    def _apply_filters(self) -> None:
        search = self.filter_state.search.lower().strip()
        results: List[Dict[str, Any]] = []
        for record in self.records:
            if search:
                haystack = " ".join(
                    [
                        record.get("tail_number", ""),
                        record.get("callsign", ""),
                        record.get("make", ""),
                        record.get("model", ""),
                        record.get("make_model", ""),
                        record.get("adsb_hex", ""),
                        record.get("base", ""),
                    ]
                ).lower()
                if search not in haystack:
                    continue
            if self.filter_state.type_filter != "All" and record.get("type") != self.filter_state.type_filter:
                continue
            if self.filter_state.status_filter != "All" and record.get("status") != self.filter_state.status_filter:
                continue
            if self.filter_state.base_filter != "All" and record.get("base") != self.filter_state.base_filter:
                continue
            caps = self.filter_state.capabilities
            if caps:
                if "Hoist" in caps and not record.get("cap_hoist"):
                    continue
                if "Night Ops" in caps and not record.get("cap_nvg"):
                    continue
                if "FLIR" in caps and not record.get("cap_flir"):
                    continue
                if "IFR" in caps and not record.get("cap_ifr"):
                    continue
            fuels = self.filter_state.fuels
            if fuels and record.get("fuel_type") not in fuels:
                continue
            if self.filter_state.night_ops and not record.get("cap_nvg"):
                continue
            if self.filter_state.ifr and not record.get("cap_ifr"):
                continue
            if self.filter_state.hoist and not record.get("cap_hoist"):
                continue
            if self.filter_state.flir and not record.get("cap_flir"):
                continue
            results.append(record)
        key = self.filter_state.sort_key
        desc = self.filter_state.sort_desc
        results.sort(key=lambda item: self._sort_value(item, key), reverse=desc)
        self.filtered_records = results
        self.total_pages = max(1, math.ceil(len(results) / PAGE_SIZE))
        self.current_page = min(self.current_page, self.total_pages) or 1
        self._update_filter_badge()
        self._update_page_view()
        self._update_bulk_state()

    def _update_page_view(self) -> None:
        start = (self.current_page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_records = self.filtered_records[start:end]
        self.table_model.set_records(page_records)
        self.table_model.set_selected_ids(self.selected_ids)
        self.pagination_label.setText(
            f"Rows: {start + 1 if page_records else 0}–{start + len(page_records)} of {len(self.filtered_records)}"
        )
        self.page_info_label.setText(f"Page {self.current_page}/{self.total_pages}")
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
        self.last_page_btn.setEnabled(self.current_page < self.total_pages)
        if page_records:
            index = self.table_model.index(0, 0)
            self.table_view.selectRow(0)
            self._update_detail_from_selection()
        else:
            self.table_view.clearSelection()
            self.detail_pane.set_record(None)

    def _update_filter_badge(self) -> None:
        count = self.filter_state.active_filter_count()
        self.filters_label.setText(f"Filters ({count})" if count else "Filters")

    def _update_base_options(self) -> None:
        bases = sorted({record.get("base", "") for record in self.records if record.get("base")})
        self.base_combo.blockSignals(True)
        current = self.base_combo.currentText()
        self.base_combo.clear()
        self.base_combo.addItem("All")
        for base in bases:
            self.base_combo.addItem(base)
        if current in ("All", *bases):
            self.base_combo.setCurrentText(current)
        self.base_combo.blockSignals(False)
        self.detail_pane.set_bases(bases)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_search_text(self, text: str) -> None:
        self.filter_state.search = text
        self.search_timer.start()

    def _on_type_changed(self, text: str) -> None:
        self.filter_state.type_filter = text
        self._apply_filters()

    def _on_status_changed(self, text: str) -> None:
        self.filter_state.status_filter = text
        self._apply_filters()

    def _on_base_changed(self, text: str) -> None:
        self.filter_state.base_filter = text
        self._apply_filters()

    def _on_sort_changed(self) -> None:
        data = self.sort_combo.currentData()
        if not data:
            return
        key, desc = data
        self.filter_state.sort_key = key
        self.filter_state.sort_desc = bool(desc)
        self._apply_filters()

    def _on_capability_filter(self, key: str, state: bool) -> None:
        if state:
            self.filter_state.capabilities.add(key)
        else:
            self.filter_state.capabilities.discard(key)
        self._apply_filters()

    def _on_fuel_filter(self, key: str, state: bool) -> None:
        if state:
            self.filter_state.fuels.add(key)
        else:
            self.filter_state.fuels.discard(key)
        self._apply_filters()

    def _on_quick_filter(self, attr: str, state: bool) -> None:
        setattr(self.filter_state, attr, state)
        self._apply_filters()

    def _reset_filters(self) -> None:
        self.filter_state = AircraftFilterState()
        self.search_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.base_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)
        for action in self.capabilities_actions.values():
            action.setChecked(False)
        for action in self.fuel_actions.values():
            action.setChecked(False)
        self.night_btn.setChecked(False)
        self.ifr_btn.setChecked(False)
        self.hoist_btn.setChecked(False)
        self.flir_btn.setChecked(False)
        self._apply_filters()

    def _on_checkbox_selection(self, record_id: int, checked: bool) -> None:
        if checked:
            self.selected_ids.add(record_id)
        else:
            self.selected_ids.discard(record_id)
        self._update_bulk_state()

    def _on_row_activated(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        record = self.table_model.record_at(index.row())
        if record:
            self.detail_pane.set_record(record)

    def _change_page(self, page: int) -> None:
        page = max(1, min(page, self.total_pages))
        if page == self.current_page:
            return
        self.current_page = page
        self._update_page_view()

    def _select_all_filtered(self) -> None:
        self.selected_ids = {int(record.get("id")) for record in self.filtered_records if record.get("id") is not None}
        self.table_model.set_selected_ids(self.selected_ids)
        self._update_bulk_state()

    def _clear_selection(self) -> None:
        self.selected_ids.clear()
        self.table_model.set_selected_ids(self.selected_ids)
        self._update_bulk_state()

    def _update_detail_from_selection(self) -> None:
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            record = self.table_model.record_at(indexes[0].row())
            self.detail_pane.set_record(record)
        else:
            self.detail_pane.set_record(None)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _populate_bulk_menu(self) -> None:
        self.bulk_menu.clear()
        status_action = self.bulk_menu.addAction("Set Status…")
        status_action.triggered.connect(self._open_set_status_dialog)
        assign_action = self.bulk_menu.addAction("Assign to Team…")
        assign_action.triggered.connect(self._open_assign_dialog)
        clear_action = self.bulk_menu.addAction("Clear Assignment")
        clear_action.triggered.connect(self._clear_assignment)
        delete_action = self.bulk_menu.addAction("Delete")
        delete_action.triggered.connect(self._delete_selected)

    def _open_add_dialog(self) -> None:
        dialog = NewAircraftDialog(self.repository, self)
        dialog.recordCreated.connect(self._on_record_created)
        dialog.exec()

    def _open_import_dialog(self) -> None:
        dialog = ImportAircraftDialog(self.repository, self)
        dialog.recordsImported.connect(self._on_records_imported)
        dialog.exec()

    def _on_record_created(self, record: Dict[str, Any]) -> None:
        self.records.append(record)
        self.selected_ids.add(int(record.get("id")))
        self._update_base_options()
        self._apply_filters()
        self._update_bulk_state()

    def _on_records_imported(self, records: List[Dict[str, Any]]) -> None:
        by_id = {record["id"]: record for record in self.records if record.get("id") is not None}
        for record in records:
            rid = record.get("id")
            if rid in by_id:
                by_id[rid] = record
            else:
                by_id[rid] = record
        self.records = list(by_id.values())
        self._update_base_options()
        self._apply_filters()
        self.selected_ids = {rid for rid in self.selected_ids if rid in {int(r.get("id")) for r in self.records if r.get("id")}}
        self._update_bulk_state()

    def _export_records(self) -> None:
        if not self.filtered_records:
            QMessageBox.information(self, "Export", "No records to export.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Aircraft",
            str(Path.home() / "aircraft"),
            "CSV Files (*.csv);;JSON Files (*.json);;PDF Files (*.pdf)",
        )
        if not path:
            return
        suffix = Path(path).suffix.lower()
        if "csv" in selected_filter or suffix == ".csv":
            self._export_csv(Path(path))
        elif "json" in selected_filter or suffix == ".json":
            self._export_json(Path(path))
        else:
            if suffix != ".pdf":
                path = f"{path}.pdf"
            self._export_pdf(Path(path))

    def _export_csv(self, path: Path) -> None:
        rows = self.filtered_records
        headers = ["tail_number", "callsign", "type", "make", "model", "status", "base", "assigned_team_name"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Tail #", "Callsign", "Type", "Make", "Model", "Status", "Base", "Assigned To"])
            for record in rows:
                writer.writerow([record.get(key, "") for key in headers])
        QMessageBox.information(self, "Export", f"Exported {len(rows)} rows to {path}.")

    def _export_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.filtered_records, indent=2), encoding="utf-8")
        QMessageBox.information(self, "Export", f"Exported {len(self.filtered_records)} rows to {path}.")

    def _export_pdf(self, path: Path) -> None:
        html_rows = []
        for record in self.filtered_records:
            html_rows.append(
                "<tr>" + "".join(
                    f"<td>{value}</td>"
                    for value in [
                        record.get("tail_number", ""),
                        record.get("callsign", ""),
                        record.get("type", ""),
                        record.get("make_model", ""),
                        record.get("status", ""),
                        record.get("base", ""),
                        record.get("assigned_team_name", "") or "(none)",
                    ]
                ) + "</tr>"
            )
        html = (
            "<h2>Aircraft Inventory Export</h2>"
            "<table border='1' cellspacing='0' cellpadding='4'>"
            "<tr><th>Tail #</th><th>Callsign</th><th>Type</th><th>Make/Model</th><th>Status</th><th>Base</th><th>Assigned To</th></tr>"
            + "".join(html_rows)
            + "</table>"
        )
        doc = QTextDocument()
        doc.setHtml(html)
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(path))
        doc.print(printer)
        QMessageBox.information(self, "Export", f"Exported PDF to {path}.")

    def _open_set_status_dialog(self) -> None:
        if not self.selected_ids:
            QMessageBox.information(self, "Status", "Select at least one aircraft.")
            return
        dialog = SetStatusDialog(self)
        if dialog.exec() == QDialog.Accepted:
            status, notes = dialog.values()
            self.repository.set_status(self.selected_ids, status, notes)
            self._load_records()

    def _open_assign_dialog(self) -> None:
        if not self.selected_ids:
            QMessageBox.information(self, "Assign", "Select at least one aircraft.")
            return
        dialog = AssignTeamDialog(self)
        if dialog.exec() == QDialog.Accepted:
            team_id, team_name, notify = dialog.values()
            self.repository.assign_team(self.selected_ids, team_id, team_name, notify)
            self._load_records()

    def _clear_assignment(self) -> None:
        if not self.selected_ids:
            return
        self.repository.clear_assignment(self.selected_ids)
        self._load_records()

    def _delete_selected(self) -> None:
        if not self.selected_ids:
            return
        count = len(self.selected_ids)
        msg = QMessageBox.question(
            self,
            "Delete",
            f"Delete {count} aircraft? This action cannot be undone.",
        )
        if msg != QMessageBox.Yes:
            return
        for record_id in list(self.selected_ids):
            self.repository.delete_aircraft(record_id)
        self.selected_ids.clear()
        self._load_records()

    def _print_current_summary(self) -> None:
        record = self.detail_pane._record
        if not record:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Print Aircraft Summary",
            str(Path.home() / f"{record.get('tail_number', 'aircraft')}.pdf"),
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path = f"{path}.pdf"
        html = self._build_summary_html(record)
        doc = QTextDocument()
        doc.setHtml(html)
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        doc.print(printer)
        QMessageBox.information(self, "Print", f"Saved summary to {path}.")

    def _build_summary_html(self, record: Dict[str, Any]) -> str:
        return f"""
        <h2>Aircraft {record.get('tail_number', '')}</h2>
        <p><strong>Callsign:</strong> {record.get('callsign', '')}<br/>
        <strong>Status:</strong> {record.get('status', '')}<br/>
        <strong>Base:</strong> {record.get('base', '')}<br/>
        <strong>Assigned:</strong> {record.get('assigned_team_name') or '(none)'}<br/>
        <strong>Make/Model:</strong> {record.get('make_model', '')}<br/>
        <strong>Fuel:</strong> {record.get('fuel_type', '')}<br/>
        <strong>Range:</strong> {record.get('range_nm', 0)} nm<br/>
        <strong>Endurance:</strong> {record.get('endurance_hr', 0)} hr<br/>
        <strong>Crew:</strong> {record.get('crew_min', 0)} / {record.get('crew_max', 0)}</p>
        <p><strong>Notes:</strong><br/>{record.get('notes', '').replace('\n', '<br/>')}</p>
        <h3>Recent History</h3>
        <ul>
        {''.join(f"<li>{item.get('ts', '')}: {item.get('action', '')} — {item.get('details', '')}</li>" for item in (record.get('history') or [])[-5:])}
        </ul>
        """

    def _open_history_tab(self) -> None:
        self.detail_pane.tab_widget.setCurrentIndex(4)

    def _delete_current_record(self) -> None:
        record = self.detail_pane._record
        if not record:
            return
        tail = record.get("tail_number", "")
        confirm = QMessageBox.question(
            self,
            "Delete",
            f"Delete aircraft {tail}?",
        )
        if confirm != QMessageBox.Yes:
            return
        rid = record.get("id")
        if rid is not None:
            self.repository.delete_aircraft(int(rid))
            self.selected_ids.discard(int(rid))
            self._load_records()

    # ------------------------------------------------------------------
    # Detail pane integration
    # ------------------------------------------------------------------
    def _handle_patch(self, patch: Dict[str, Any]) -> None:
        record_id = patch.pop("id", None)
        if record_id is None:
            return
        if patch.get("status", "").lower() == "out of service":
            patch.setdefault("assigned_team_id", None)
            patch.setdefault("assigned_team_name", None)
        try:
            updated = self.repository.update_aircraft(int(record_id), patch)
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.critical(self, "Update", f"Failed to update aircraft: {exc}")
            return
        self.records = [updated if item.get("id") == updated.get("id") else item for item in self.records]
        self._apply_filters()
        self.detail_pane.set_record(updated)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_bulk_state(self) -> None:
        enabled = bool(self.selected_ids)
        self.bulk_btn.setEnabled(enabled)
        self.clear_selection_btn.setEnabled(enabled)

    def _sort_value(self, record: Dict[str, Any], key: str) -> Any:
        value = record.get(key)
        if value is None:
            return ""
        return value

*** End Patch
