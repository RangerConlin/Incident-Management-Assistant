from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.app_signals import app_signals
from utils.state import AppState

from ..models import FACILITY_STATUSES, FACILITY_TYPES, FacilityRecord
from ..service import FacilitiesService
from ..widgets import PersonnelPicker


class FacilitiesManagerPanel(QWidget):
    panel_title = "Facilities Manager"

    def __init__(self, incident_id: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        del incident_id
        self._current_id = ""
        self._service = FacilitiesService()
        self._build_ui()
        try:
            app_signals.incidentChanged.connect(lambda *_: self.reload())
        except Exception:
            pass
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        self._incident_label = QLabel("No active incident selected")
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._incident_label)
        header.addStretch(1)
        header.addWidget(self._status)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        self._filter_type = QComboBox()
        self._filter_type.addItem("all")
        self._filter_type.addItems(FACILITY_TYPES)
        self._filter_status = QComboBox()
        self._filter_status.addItem("all")
        self._filter_status.addItems(FACILITY_STATUSES)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search facilities, tags, sections, notes...")
        btn_refresh = QPushButton("Refresh")
        btn_new = QPushButton("New Facility")
        btn_save = QPushButton("Save")
        btn_delete = QPushButton("Delete")
        btn_geocode = QPushButton("Geocode")
        btn_reverse = QPushButton("Reverse Geocode")
        btn_refresh.clicked.connect(self.reload)
        btn_new.clicked.connect(self._new_record)
        btn_save.clicked.connect(self.save)
        btn_delete.clicked.connect(self._delete_current)
        btn_geocode.clicked.connect(self._geocode)
        btn_reverse.clicked.connect(self._reverse_geocode)
        self._filter_type.currentTextChanged.connect(lambda *_: self.reload())
        self._filter_status.currentTextChanged.connect(lambda *_: self.reload())
        self._search.textChanged.connect(lambda *_: self.reload())
        toolbar.addWidget(QLabel("Type"))
        toolbar.addWidget(self._filter_type)
        toolbar.addWidget(QLabel("Status"))
        toolbar.addWidget(self._filter_status)
        toolbar.addWidget(self._search, 1)
        toolbar.addStretch(1)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_new)
        toolbar.addWidget(btn_geocode)
        toolbar.addWidget(btn_reverse)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_delete)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._handle_selection_changed)
        splitter.addWidget(self._list)

        editor = QWidget()
        editor_layout = QVBoxLayout(editor)

        details_box = QGroupBox("Facility Details")
        details_form = QFormLayout(details_box)
        self._name = QLineEdit()
        self._facility_type = QComboBox()
        self._facility_type.addItems(FACILITY_TYPES)
        self._status_combo = QComboBox()
        self._status_combo.addItems(FACILITY_STATUSES)
        self._is_primary = QCheckBox("Primary for this type")
        self._address = QLineEdit()
        self._latitude = QLineEdit()
        self._longitude = QLineEdit()
        self._geocoded_address = QLineEdit()
        self._manager_picker = PersonnelPicker()
        self._contact_name = QLineEdit()
        self._contact_phone = QLineEdit()
        self._manager_picker.personnelSelected.connect(self._on_manager_selected)
        details_form.addRow("Name", self._name)
        details_form.addRow("Type", self._facility_type)
        details_form.addRow("Status", self._status_combo)
        details_form.addRow("", self._is_primary)
        details_form.addRow("Address / Description", self._address)
        details_form.addRow("Latitude", self._latitude)
        details_form.addRow("Longitude", self._longitude)
        details_form.addRow("Matched Address", self._geocoded_address)
        details_form.addRow("Manager", self._manager_picker)
        details_form.addRow("Contact Name", self._contact_name)
        details_form.addRow("Contact Phone", self._contact_phone)
        editor_layout.addWidget(details_box)

        use_box = QGroupBox("Cross-Module Use")
        use_form = QFormLayout(use_box)
        self._function_tags = QLineEdit()
        self._served_sections = QLineEdit()
        self._notes = QTextEdit()
        self._notes.setFixedHeight(140)
        self._function_tags.setPlaceholderText("parking, supplies, check-in, communications")
        self._served_sections.setPlaceholderText("command, logistics, operations")
        use_form.addRow("Functions", self._function_tags)
        use_form.addRow("Sections", self._served_sections)
        use_form.addRow("Notes", self._notes)
        editor_layout.addWidget(use_box)
        editor_layout.addStretch(1)

        splitter.addWidget(editor)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def _incident_id(self) -> str:
        return str(AppState.get_active_incident() or "")

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _new_record(self) -> None:
        self._current_id = ""
        self._list.clearSelection()
        self._name.clear()
        self._facility_type.setCurrentText("command_post")
        self._status_combo.setCurrentText("active")
        self._is_primary.setChecked(False)
        self._address.clear()
        self._latitude.clear()
        self._longitude.clear()
        self._geocoded_address.clear()
        self._manager_picker.clear()
        self._contact_name.clear()
        self._contact_phone.clear()
        self._function_tags.clear()
        self._served_sections.clear()
        self._notes.clear()
        self._set_status("New facility")

    def _facility_from_form(self) -> FacilityRecord:
        return FacilityRecord(
            id=self._current_id,
            incident_id=self._incident_id(),
            name=self._name.text().strip(),
            facility_type=self._facility_type.currentText().strip(),
            status=self._status_combo.currentText().strip(),
            address=self._address.text().strip(),
            latitude=self._parse_float(self._latitude.text()),
            longitude=self._parse_float(self._longitude.text()),
            geocoded_address=self._geocoded_address.text().strip(),
            manager_personnel_id=self._manager_picker.personnel_id,
            manager_name=self._manager_picker.personnel_text,
            contact_name=self._contact_name.text().strip(),
            contact_phone=self._contact_phone.text().strip(),
            notes=self._notes.toPlainText().strip(),
            function_tags=self._csv_to_list(self._function_tags.text()),
            served_sections=self._csv_to_list(self._served_sections.text()),
            is_primary=self._is_primary.isChecked(),
        )

    def _apply_record(self, facility: FacilityRecord) -> None:
        self._current_id = facility.id
        self._name.setText(facility.name)
        self._facility_type.setCurrentText(facility.facility_type or "other")
        self._status_combo.setCurrentText(facility.status or "active")
        self._is_primary.setChecked(facility.is_primary)
        self._address.setText(facility.address)
        self._latitude.setText("" if facility.latitude is None else f"{facility.latitude:.6f}")
        self._longitude.setText("" if facility.longitude is None else f"{facility.longitude:.6f}")
        self._geocoded_address.setText(facility.geocoded_address)
        self._manager_picker.set_value(facility.manager_personnel_id, facility.manager_name)
        self._contact_name.setText(facility.contact_name)
        self._contact_phone.setText(facility.contact_phone)
        self._function_tags.setText(", ".join(facility.function_tags))
        self._served_sections.setText(", ".join(facility.served_sections))
        self._notes.setPlainText(facility.notes)

    def _handle_selection_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        facility = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(facility, FacilityRecord):
            self._apply_record(facility)

    def _on_manager_selected(self, personnel_id: object, name: str) -> None:
        del personnel_id
        if not self._contact_name.text().strip():
            self._contact_name.setText(name)

    def _populate_list(self, facilities: list[FacilityRecord]) -> None:
        self._list.clear()
        for facility in facilities:
            label = facility.name or "(unnamed facility)"
            suffix = f" [{facility.facility_type}]"
            if facility.is_primary:
                suffix += " primary"
            item = QListWidgetItem(label + suffix)
            item.setData(Qt.ItemDataRole.UserRole, facility)
            self._list.addItem(item)

    def reload(self) -> None:
        incident_id = self._incident_id()
        self._service = FacilitiesService(incident_id)
        if not incident_id:
            self._incident_label.setText("No active incident selected")
            self._populate_list([])
            self._new_record()
            self._set_status("Select an incident to manage facilities.", error=True)
            return
        self._incident_label.setText(f"Incident {incident_id}")
        facility_type = self._filter_type.currentText()
        status = self._filter_status.currentText()
        facilities = self._service.list_facilities(
            facility_type=None if facility_type == "all" else facility_type,
            status=None if status == "all" else status,
            text_search=self._search.text(),
        )
        self._populate_list(facilities)
        if facilities:
            self._list.setCurrentRow(0)
            self._set_status(f"Loaded {len(facilities)} facilities")
        else:
            self._new_record()
            self._set_status("No facilities yet")

    def save(self) -> None:
        if not self._incident_id():
            QMessageBox.warning(self, self.panel_title, "No active incident is selected.")
            return
        try:
            saved = self._service.save_facility(self._facility_from_form())
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return
        self._apply_record(saved)
        self.reload()
        self._set_status("Facility saved")

    def _delete_current(self) -> None:
        if not self._current_id:
            return
        if QMessageBox.question(self, self.panel_title, "Delete this facility?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_facility(self._current_id)
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return
        self._new_record()
        self.reload()
        self._set_status("Facility deleted")

    def _geocode(self) -> None:
        address = self._address.text().strip()
        if not address:
            self._set_status("Enter an address or description first.", error=True)
            return
        try:
            facility = self._service.geocode_facility(self._facility_from_form())
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return
        self._apply_record(facility)
        self._set_status("Address geocoded")

    def _reverse_geocode(self) -> None:
        latitude = self._parse_float(self._latitude.text())
        longitude = self._parse_float(self._longitude.text())
        if latitude is None or longitude is None:
            self._set_status("Enter valid coordinates first.", error=True)
            return
        try:
            facility = self._service.reverse_geocode_facility(self._facility_from_form())
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return
        self._apply_record(facility)
        self._set_status("Coordinates reverse geocoded")

    @staticmethod
    def _csv_to_list(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    @staticmethod
    def _parse_float(value: str) -> float | None:
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None


__all__ = ["FacilitiesManagerPanel"]
