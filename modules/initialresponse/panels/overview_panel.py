from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import APIError, api_client
from utils.app_signals import app_signals
from utils.geocoding import geocode_address, reverse_geocode_coordinates
from utils.state import AppState

from .. import services
from ..models import InitialOverviewRead, InitialOverviewUpdate

_MISSING_PERSON = "Missing Person"
_MISSING_AIRCRAFT = "Missing Aircraft"
_AIRCRAFT_BEHAVIOR = "Aircraft"

_BEHAVIOR_CATEGORIES = [
    "",
    "Abduction",
    "Aircraft",
    "Angler",
    "Autistic",
    "Camper",
    "Child (1-3)",
    "Child (4-6)",
    "Child (7-9)",
    "Child (10-12)",
    "Child (13-15)",
    "Climber",
    "Dementia",
    "Depression",
    "Despondent",
    "Gatherer",
    "Hiker",
    "Horseback Rider",
    "Hunter",
    "Intellectual Disability",
    "Mental Illness",
    "Runner",
    "Skier - Alpine",
    "Skier - Nordic",
    "Snowboarder",
    "Substance Use",
    "Suicidal",
]

_ANCHOR_TYPES = ["IPP", "LKP"]
_CONFIDENCE_LEVELS = ["", "Exact", "Approximate", "Estimated from report"]


class _SummaryCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #d0d0d0; border-radius: 4px; padding: 6px; }")
        layout = QVBoxLayout(self)
        self._title = QLabel(title)
        self._title.setStyleSheet("font-weight: 600;")
        self._value = QLabel("—")
        self._value.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value or "—")


class InitialOverviewPanel(QWidget):
    def __init__(
        self,
        incident_id: object | None = None,
        *,
        open_hasty: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        del incident_id
        self._open_hasty = open_hasty
        self._loading = False
        self._person_behavior = ""
        self._build_ui()
        try:
            app_signals.incidentChanged.connect(lambda *_: self.reload())
        except Exception:
            pass
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setStyleSheet("QFrame { border: 1px solid #d0d0d0; border-radius: 4px; padding: 8px; }")
        header_layout = QVBoxLayout(header)

        title_row = QHBoxLayout()
        title = QLabel("Initial Information")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self._status)
        header_layout.addLayout(title_row)

        self._incident_label = QLabel("No active incident selected")
        self._incident_label.setStyleSheet("font-weight: 600;")
        self._summary_label = QLabel("Build the initial incident picture here.")
        self._summary_label.setWordWrap(True)
        header_layout.addWidget(self._incident_label)
        header_layout.addWidget(self._summary_label)

        cards = QGridLayout()
        self._mode_card = _SummaryCard("Mode")
        self._behavior_card = _SummaryCard("Behavior")
        self._anchor_card = _SummaryCard("Primary Anchor")
        self._subject_card = _SummaryCard("Subject / Aircraft")
        cards.addWidget(self._mode_card, 0, 0)
        cards.addWidget(self._behavior_card, 0, 1)
        cards.addWidget(self._anchor_card, 1, 0)
        cards.addWidget(self._subject_card, 1, 1)
        header_layout.addLayout(cards)

        action_row = QHBoxLayout()
        btn_save = QPushButton("Save")
        btn_refresh = QPushButton("Refresh")
        btn_hasty = QPushButton("Open Early Tasking")
        btn_save.clicked.connect(self.save)
        btn_refresh.clicked.connect(self.reload)
        btn_hasty.clicked.connect(lambda: self._open_hasty and self._open_hasty())
        action_row.addWidget(btn_save)
        action_row.addWidget(btn_refresh)
        action_row.addStretch(1)
        action_row.addWidget(btn_hasty)
        header_layout.addLayout(action_row)
        layout.addWidget(header)

        context_box = QGroupBox("Incident Context")
        context_form = QFormLayout(context_box)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([_MISSING_PERSON, _MISSING_AIRCRAFT])
        self._behavior_combo = QComboBox()
        self._behavior_combo.addItems(_BEHAVIOR_CATEGORIES)
        self._reporting_source = QLineEdit()
        self._opened_time = QLineEdit()
        self._opened_time.setPlaceholderText("2026-06-14  09:30")
        self._updated_time = QLineEdit()
        self._updated_time.setReadOnly(True)
        context_form.addRow("Mode", self._mode_combo)
        context_form.addRow("Behavior Category", self._behavior_combo)
        context_form.addRow("Reporting Source", self._reporting_source)
        context_form.addRow("Time Opened", self._opened_time)
        context_form.addRow("Last Saved", self._updated_time)
        layout.addWidget(context_box)

        source_box = QGroupBox("Initial Source Information")
        source_form = QFormLayout(source_box)
        self._source_name = QLineEdit()
        self._source_role = QLineEdit()
        self._source_phone = QLineEdit()
        self._source_contact = QLineEdit()
        self._source_reliability = QTextEdit()
        self._source_reliability.setFixedHeight(70)
        source_form.addRow("Information Gathered From", self._source_name)
        source_form.addRow("Relation / Source Role", self._source_role)
        source_form.addRow("Phone / Callback", self._source_phone)
        source_form.addRow("Additional Contact", self._source_contact)
        source_form.addRow("Reliability / Notes", self._source_reliability)
        layout.addWidget(source_box)

        details_box = QGroupBox("Subject or Aircraft Information")
        details_layout = QVBoxLayout(details_box)
        self._details_stack = QStackedWidget()
        self._details_stack.addWidget(self._build_subject_page())
        self._details_stack.addWidget(self._build_aircraft_page())
        details_layout.addWidget(self._details_stack)
        layout.addWidget(details_box)

        timeline_box = QGroupBox("Initial Timeline / Last Known Information")
        timeline_form = QFormLayout(timeline_box)
        self._last_seen_time = QLineEdit()
        self._last_contact_time = QLineEdit()
        self._seen_by = QLineEdit()
        self._circumstances = QTextEdit()
        self._circumstances.setFixedHeight(70)
        self._direction_plans = QTextEdit()
        self._direction_plans.setFixedHeight(70)
        self._family_on_scene = QLineEdit()
        self._unknowns = QTextEdit()
        self._unknowns.setFixedHeight(70)
        timeline_form.addRow("Last Seen Time", self._last_seen_time)
        timeline_form.addRow("Last Contact Time", self._last_contact_time)
        timeline_form.addRow("Seen / Reported By", self._seen_by)
        timeline_form.addRow("Circumstances", self._circumstances)
        timeline_form.addRow("Direction / Plans / Route", self._direction_plans)
        timeline_form.addRow("Family / Involved Parties", self._family_on_scene)
        timeline_form.addRow("Unknowns / Conflicts", self._unknowns)
        layout.addWidget(timeline_box)

        anchor_box = QGroupBox("Primary Anchor")
        anchor_layout = QVBoxLayout(anchor_box)
        anchor_form = QFormLayout()
        self._anchor_type = QComboBox()
        self._anchor_type.addItems(_ANCHOR_TYPES)
        self._anchor_address = QLineEdit()
        self._anchor_lat = QLineEdit()
        self._anchor_lon = QLineEdit()
        self._anchor_confidence = QComboBox()
        self._anchor_confidence.addItems(_CONFIDENCE_LEVELS)
        self._anchor_source = QLineEdit()
        self._anchor_timestamp = QLineEdit()
        self._anchor_access = QTextEdit()
        self._anchor_access.setFixedHeight(70)
        anchor_form.addRow("Anchor Type", self._anchor_type)
        anchor_form.addRow("Address / Description", self._anchor_address)
        anchor_form.addRow("Latitude", self._anchor_lat)
        anchor_form.addRow("Longitude", self._anchor_lon)
        anchor_form.addRow("Confidence", self._anchor_confidence)
        anchor_form.addRow("Source", self._anchor_source)
        anchor_form.addRow("Timestamp", self._anchor_timestamp)
        anchor_form.addRow("Access / Approach Notes", self._anchor_access)
        anchor_layout.addLayout(anchor_form)

        geo_row = QHBoxLayout()
        btn_geocode = QPushButton("Geocode Address")
        btn_reverse = QPushButton("Reverse Geocode Coordinates")
        btn_geocode.clicked.connect(self._geocode_anchor)
        btn_reverse.clicked.connect(self._reverse_geocode_anchor)
        geo_row.addWidget(btn_geocode)
        geo_row.addWidget(btn_reverse)
        geo_row.addStretch(1)
        anchor_layout.addLayout(geo_row)
        layout.addWidget(anchor_box)

        related_box = QGroupBox("Related Locations")
        related_layout = QVBoxLayout(related_box)
        self._related_table = QTableWidget(0, 5)
        self._related_table.setHorizontalHeaderLabels(["Location", "Address / Description", "Latitude", "Longitude", "Notes"])
        self._related_table.horizontalHeader().setStretchLastSection(True)
        self._related_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        related_layout.addWidget(self._related_table)
        related_buttons = QHBoxLayout()
        btn_add_related = QPushButton("Add Related Location")
        btn_remove_related = QPushButton("Remove Selected")
        btn_add_related.clicked.connect(self._add_related_location)
        btn_remove_related.clicked.connect(self._remove_related_location)
        related_buttons.addWidget(btn_add_related)
        related_buttons.addWidget(btn_remove_related)
        related_buttons.addStretch(1)
        related_layout.addLayout(related_buttons)
        layout.addWidget(related_box)

        clues_box = QGroupBox("Clues & Environment")
        clues_form = QFormLayout(clues_box)
        self._clues = QTextEdit()
        self._terrain = QTextEdit()
        self._weather = QTextEdit()
        self._hazards = QTextEdit()
        self._access = QTextEdit()
        self._confinement = QTextEdit()
        for widget in (self._clues, self._terrain, self._weather, self._hazards, self._access, self._confinement):
            widget.setFixedHeight(70)
        clues_form.addRow("Clues", self._clues)
        clues_form.addRow("Terrain", self._terrain)
        clues_form.addRow("Weather", self._weather)
        clues_form.addRow("Hazards", self._hazards)
        clues_form.addRow("Access", self._access)
        clues_form.addRow("Confinement Features", self._confinement)
        layout.addWidget(clues_box)

        ops_box = QGroupBox("Operations Summary")
        ops_form = QFormLayout(ops_box)
        self._ops_actions = QTextEdit()
        self._ops_contacts = QTextEdit()
        self._ops_resources = QTextEdit()
        self._ops_gaps = QTextEdit()
        for widget in (self._ops_actions, self._ops_contacts, self._ops_resources, self._ops_gaps):
            widget.setFixedHeight(70)
        ops_form.addRow("Actions Already Taken", self._ops_actions)
        ops_form.addRow("Contacts Made", self._ops_contacts)
        ops_form.addRow("Resources Engaged", self._ops_resources)
        ops_form.addRow("Immediate Gaps / Pending", self._ops_gaps)
        layout.addWidget(ops_box)

        narrative_box = QGroupBox("Narrative")
        narrative_layout = QVBoxLayout(narrative_box)
        self._narrative = QTextEdit()
        self._narrative.setPlaceholderText("Rolling incident notes. This can feed a 214 log later.")
        narrative_layout.addWidget(self._narrative)
        layout.addWidget(narrative_box)

        self._mode_combo.currentTextChanged.connect(self._sync_mode_ui)
        self._behavior_combo.currentTextChanged.connect(lambda *_: self._refresh_summary())
        self._anchor_type.currentTextChanged.connect(lambda *_: self._refresh_summary())
        self._anchor_address.textChanged.connect(lambda *_: self._refresh_summary())
        self._subject_name.textChanged.connect(lambda *_: self._refresh_summary())
        self._aircraft_tail.textChanged.connect(lambda *_: self._refresh_summary())

    def _build_subject_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._subject_name = QLineEdit()
        self._subject_nickname = QLineEdit()
        self._subject_age = QLineEdit()
        self._subject_sex = QLineEdit()
        self._subject_description = QTextEdit()
        self._subject_clothing = QTextEdit()
        self._subject_medical = QTextEdit()
        self._subject_equipment = QTextEdit()
        for widget in (
            self._subject_description,
            self._subject_clothing,
            self._subject_medical,
            self._subject_equipment,
        ):
            widget.setFixedHeight(70)
        form.addRow("Name", self._subject_name)
        form.addRow("Nickname", self._subject_nickname)
        form.addRow("Age", self._subject_age)
        form.addRow("Sex", self._subject_sex)
        form.addRow("Physical Description", self._subject_description)
        form.addRow("Clothing Summary", self._subject_clothing)
        form.addRow("Medical / Cognitive / Mobility", self._subject_medical)
        form.addRow("Equipment Carried", self._subject_equipment)
        return page

    def _build_aircraft_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self._aircraft_tail = QLineEdit()
        self._aircraft_type = QLineEdit()
        self._aircraft_markings = QLineEdit()
        self._aircraft_pilot = QLineEdit()
        self._aircraft_occupants = QLineEdit()
        self._aircraft_route = QTextEdit()
        self._aircraft_fuel = QLineEdit()
        self._aircraft_elt = QTextEdit()
        self._aircraft_route.setFixedHeight(70)
        self._aircraft_elt.setFixedHeight(70)
        form.addRow("Tail Number", self._aircraft_tail)
        form.addRow("Aircraft Type", self._aircraft_type)
        form.addRow("Color / Markings", self._aircraft_markings)
        form.addRow("Pilot", self._aircraft_pilot)
        form.addRow("Occupants", self._aircraft_occupants)
        form.addRow("Route / Destination", self._aircraft_route)
        form.addRow("Fuel Endurance", self._aircraft_fuel)
        form.addRow("ELT / Survival Gear", self._aircraft_elt)
        return page

    def _incident(self) -> str | None:
        return AppState.get_active_incident()

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Initial response API unavailable: {exc}"
            return f"Initial response API error {exc.status_code}: {exc}"
        return str(exc)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {'#b00020' if error else '#375a2b'};")

    def _set_combo_text(self, combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        if index < 0 and value:
            combo.addItem(value)
            index = combo.findText(value)
        combo.setCurrentIndex(max(index, 0))

    def _load_incident_header(self, incident_id: str) -> str:
        try:
            profile = api_client.get(f"/api/incidents/{incident_id}/profile")
        except Exception:
            return f"Incident {incident_id}"
        name = str(profile.get("name") or "").strip()
        number = str(profile.get("number") or incident_id).strip()
        return f"{name} ({number})" if name else f"Incident {number}"

    def _sync_mode_ui(self) -> None:
        is_aircraft = self._mode_combo.currentText() == _MISSING_AIRCRAFT
        self._details_stack.setCurrentIndex(1 if is_aircraft else 0)
        self._behavior_combo.blockSignals(True)
        if is_aircraft:
            current = self._behavior_combo.currentText().strip()
            if current and current != _AIRCRAFT_BEHAVIOR:
                self._person_behavior = current
            self._set_combo_text(self._behavior_combo, _AIRCRAFT_BEHAVIOR)
            self._behavior_combo.setEnabled(False)
        else:
            self._behavior_combo.setEnabled(True)
            target = self._person_behavior if self._person_behavior and self._person_behavior != _AIRCRAFT_BEHAVIOR else ""
            self._set_combo_text(self._behavior_combo, target)
        self._behavior_combo.blockSignals(False)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        mode = self._mode_combo.currentText()
        behavior = self._behavior_combo.currentText().strip()
        anchor = " ".join(part for part in [self._anchor_type.currentText(), self._anchor_address.text().strip()] if part).strip()
        subject_value = self._subject_name.text().strip() if mode == _MISSING_PERSON else self._aircraft_tail.text().strip()
        self._mode_card.set_value(mode)
        self._behavior_card.set_value(behavior or "Not selected")
        self._anchor_card.set_value(anchor or "Not established")
        self._subject_card.set_value(subject_value or ("No subject details yet" if mode == _MISSING_PERSON else "No aircraft details yet"))
        self._summary_label.setText(
            f"{mode} incident. Behavior category: {behavior or 'not selected'}. "
            f"Primary anchor: {anchor or 'not established'}."
        )

    def _add_related_location(self, row_data: dict[str, str] | None = None) -> None:
        row = self._related_table.rowCount()
        self._related_table.insertRow(row)
        values = row_data or {}
        for col, key in enumerate(["label", "address", "latitude", "longitude", "notes"]):
            item = QTableWidgetItem(str(values.get(key, "")))
            self._related_table.setItem(row, col, item)

    def _remove_related_location(self) -> None:
        row = self._related_table.currentRow()
        if row >= 0:
            self._related_table.removeRow(row)

    def _serialize_related_locations(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in range(self._related_table.rowCount()):
            rows.append(
                {
                    "label": self._related_table.item(row, 0).text().strip() if self._related_table.item(row, 0) else "",
                    "address": self._related_table.item(row, 1).text().strip() if self._related_table.item(row, 1) else "",
                    "latitude": self._related_table.item(row, 2).text().strip() if self._related_table.item(row, 2) else "",
                    "longitude": self._related_table.item(row, 3).text().strip() if self._related_table.item(row, 3) else "",
                    "notes": self._related_table.item(row, 4).text().strip() if self._related_table.item(row, 4) else "",
                }
            )
        return rows

    def _geocode_anchor(self) -> None:
        address = self._anchor_address.text().strip()
        if not address:
            self._set_status("Enter an address or description first.", error=True)
            return
        result = geocode_address(address)
        if result is None:
            self._set_status("Geocoding did not return a match.", error=True)
            return
        self._anchor_address.setText(result.address)
        self._anchor_lat.setText(f"{result.latitude:.6f}")
        self._anchor_lon.setText(f"{result.longitude:.6f}")
        self._set_status("Address geocoded")
        self._refresh_summary()

    def _reverse_geocode_anchor(self) -> None:
        try:
            latitude = float(self._anchor_lat.text().strip())
            longitude = float(self._anchor_lon.text().strip())
        except ValueError:
            self._set_status("Enter valid latitude and longitude first.", error=True)
            return
        result = reverse_geocode_coordinates(latitude, longitude)
        if result is None:
            self._set_status("Reverse geocoding did not return a match.", error=True)
            return
        self._anchor_address.setText(result.address)
        self._set_status("Coordinates reverse geocoded")
        self._refresh_summary()

    def _clear_for_no_incident(self) -> None:
        self._incident_label.setText("No active incident selected")
        self._summary_label.setText("Select an incident to build the initial incident picture.")
        self._mode_card.set_value("—")
        self._behavior_card.set_value("—")
        self._anchor_card.set_value("—")
        self._subject_card.set_value("—")
        self._updated_time.clear()
        self._set_status("Select an incident to use this workspace.", error=True)

    def reload(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            self._clear_for_no_incident()
            return
        self._loading = True
        try:
            self._incident_label.setText(self._load_incident_header(incident_id))
            record = services.get_initial_overview_entry(incident_id)
            self._apply_record(record)
            self._set_status("Initial information loaded")
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            self._incident_label.setText(f"Incident {incident_id}")
        finally:
            self._loading = False
            self._refresh_summary()

    def _apply_record(self, record: InitialOverviewRead) -> None:
        self._set_combo_text(self._mode_combo, record.incident_mode or _MISSING_PERSON)
        self._reporting_source.setText(str(record.source_info.get("reporting_source", "")))
        self._opened_time.setText(str(record.timeline_info.get("opened_time", "")))
        self._updated_time.setText(record.updated_at or "")

        self._source_name.setText(str(record.source_info.get("name", "")))
        self._source_role.setText(str(record.source_info.get("role", "")))
        self._source_phone.setText(str(record.source_info.get("phone", "")))
        self._source_contact.setText(str(record.source_info.get("contact", "")))
        self._source_reliability.setPlainText(str(record.source_info.get("notes", "")))

        self._subject_name.setText(str(record.subject_info.get("name", "")))
        self._subject_nickname.setText(str(record.subject_info.get("nickname", "")))
        self._subject_age.setText(str(record.subject_info.get("age", "")))
        self._subject_sex.setText(str(record.subject_info.get("sex", "")))
        self._subject_description.setPlainText(str(record.subject_info.get("description", "")))
        self._subject_clothing.setPlainText(str(record.subject_info.get("clothing", "")))
        self._subject_medical.setPlainText(str(record.subject_info.get("medical", "")))
        self._subject_equipment.setPlainText(str(record.subject_info.get("equipment", "")))

        self._aircraft_tail.setText(str(record.aircraft_info.get("tail_number", "")))
        self._aircraft_type.setText(str(record.aircraft_info.get("aircraft_type", "")))
        self._aircraft_markings.setText(str(record.aircraft_info.get("markings", "")))
        self._aircraft_pilot.setText(str(record.aircraft_info.get("pilot", "")))
        self._aircraft_occupants.setText(str(record.aircraft_info.get("occupants", "")))
        self._aircraft_route.setPlainText(str(record.aircraft_info.get("route", "")))
        self._aircraft_fuel.setText(str(record.aircraft_info.get("fuel_endurance", "")))
        self._aircraft_elt.setPlainText(str(record.aircraft_info.get("elt_survival", "")))

        self._last_seen_time.setText(str(record.timeline_info.get("last_seen_time", "")))
        self._last_contact_time.setText(str(record.timeline_info.get("last_contact_time", "")))
        self._seen_by.setText(str(record.timeline_info.get("seen_by", "")))
        self._circumstances.setPlainText(str(record.timeline_info.get("circumstances", "")))
        self._direction_plans.setPlainText(str(record.timeline_info.get("direction_plans", "")))
        self._family_on_scene.setText(str(record.timeline_info.get("family_on_scene", "")))
        self._unknowns.setPlainText(str(record.timeline_info.get("unknowns", "")))

        self._set_combo_text(self._anchor_type, str(record.primary_anchor.get("anchor_type", "IPP")))
        self._anchor_address.setText(str(record.primary_anchor.get("address", "")))
        self._anchor_lat.setText(str(record.primary_anchor.get("latitude", "")))
        self._anchor_lon.setText(str(record.primary_anchor.get("longitude", "")))
        self._set_combo_text(self._anchor_confidence, str(record.primary_anchor.get("confidence", "")))
        self._anchor_source.setText(str(record.primary_anchor.get("source", "")))
        self._anchor_timestamp.setText(str(record.primary_anchor.get("timestamp", "")))
        self._anchor_access.setPlainText(str(record.primary_anchor.get("access_notes", "")))

        self._related_table.setRowCount(0)
        for row in record.related_locations:
            self._add_related_location(
                {
                    "label": str(row.get("label", "")),
                    "address": str(row.get("address", "")),
                    "latitude": str(row.get("latitude", "")),
                    "longitude": str(row.get("longitude", "")),
                    "notes": str(row.get("notes", "")),
                }
            )

        self._clues.setPlainText(str(record.clues_environment.get("clues", "")))
        self._terrain.setPlainText(str(record.clues_environment.get("terrain", "")))
        self._weather.setPlainText(str(record.clues_environment.get("weather", "")))
        self._hazards.setPlainText(str(record.clues_environment.get("hazards", "")))
        self._access.setPlainText(str(record.clues_environment.get("access", "")))
        self._confinement.setPlainText(str(record.clues_environment.get("confinement", "")))

        self._ops_actions.setPlainText(str(record.operations_summary.get("actions_taken", "")))
        self._ops_contacts.setPlainText(str(record.operations_summary.get("contacts_made", "")))
        self._ops_resources.setPlainText(str(record.operations_summary.get("resources_engaged", "")))
        self._ops_gaps.setPlainText(str(record.operations_summary.get("gaps_pending", "")))

        self._narrative.setPlainText(record.narrative or "")

        self._person_behavior = record.behavior_category if record.behavior_category != _AIRCRAFT_BEHAVIOR else ""
        self._sync_mode_ui()
        if self._mode_combo.currentText() == _MISSING_PERSON:
            self._set_combo_text(self._behavior_combo, record.behavior_category or "")

    def save(self) -> None:
        incident_id = self._incident()
        if not incident_id:
            QMessageBox.warning(self, "Initial Information", "No active incident is selected.")
            return
        payload = InitialOverviewUpdate(
            incident_mode=self._mode_combo.currentText(),
            behavior_category=self._behavior_combo.currentText().strip(),
            source_info={
                "reporting_source": self._reporting_source.text().strip(),
                "name": self._source_name.text().strip(),
                "role": self._source_role.text().strip(),
                "phone": self._source_phone.text().strip(),
                "contact": self._source_contact.text().strip(),
                "notes": self._source_reliability.toPlainText().strip(),
            },
            subject_info={
                "name": self._subject_name.text().strip(),
                "nickname": self._subject_nickname.text().strip(),
                "age": self._subject_age.text().strip(),
                "sex": self._subject_sex.text().strip(),
                "description": self._subject_description.toPlainText().strip(),
                "clothing": self._subject_clothing.toPlainText().strip(),
                "medical": self._subject_medical.toPlainText().strip(),
                "equipment": self._subject_equipment.toPlainText().strip(),
            },
            aircraft_info={
                "tail_number": self._aircraft_tail.text().strip(),
                "aircraft_type": self._aircraft_type.text().strip(),
                "markings": self._aircraft_markings.text().strip(),
                "pilot": self._aircraft_pilot.text().strip(),
                "occupants": self._aircraft_occupants.text().strip(),
                "route": self._aircraft_route.toPlainText().strip(),
                "fuel_endurance": self._aircraft_fuel.text().strip(),
                "elt_survival": self._aircraft_elt.toPlainText().strip(),
            },
            timeline_info={
                "opened_time": self._opened_time.text().strip(),
                "last_seen_time": self._last_seen_time.text().strip(),
                "last_contact_time": self._last_contact_time.text().strip(),
                "seen_by": self._seen_by.text().strip(),
                "circumstances": self._circumstances.toPlainText().strip(),
                "direction_plans": self._direction_plans.toPlainText().strip(),
                "family_on_scene": self._family_on_scene.text().strip(),
                "unknowns": self._unknowns.toPlainText().strip(),
            },
            primary_anchor={
                "anchor_type": self._anchor_type.currentText(),
                "address": self._anchor_address.text().strip(),
                "latitude": self._anchor_lat.text().strip(),
                "longitude": self._anchor_lon.text().strip(),
                "confidence": self._anchor_confidence.currentText(),
                "source": self._anchor_source.text().strip(),
                "timestamp": self._anchor_timestamp.text().strip(),
                "access_notes": self._anchor_access.toPlainText().strip(),
            },
            related_locations=self._serialize_related_locations(),
            clues_environment={
                "clues": self._clues.toPlainText().strip(),
                "terrain": self._terrain.toPlainText().strip(),
                "weather": self._weather.toPlainText().strip(),
                "hazards": self._hazards.toPlainText().strip(),
                "access": self._access.toPlainText().strip(),
                "confinement": self._confinement.toPlainText().strip(),
            },
            operations_summary={
                "actions_taken": self._ops_actions.toPlainText().strip(),
                "contacts_made": self._ops_contacts.toPlainText().strip(),
                "resources_engaged": self._ops_resources.toPlainText().strip(),
                "gaps_pending": self._ops_gaps.toPlainText().strip(),
            },
            narrative=self._narrative.toPlainText().strip(),
        )
        try:
            saved = services.save_initial_overview_entry(payload, incident_id)
        except Exception as exc:
            self._set_status(self._describe_error(exc), error=True)
            return
        self._updated_time.setText(saved.updated_at or "")
        self._set_status("Initial information saved")
        self._refresh_summary()
