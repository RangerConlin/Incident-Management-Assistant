"""SubjectDetailWindow — modeless standalone window for a single Subject record.

Opens independently; multiple detail windows can be open simultaneously.
The layout adapts based on subject_type — Missing Persons get the full SAR
profile, Vehicles get plate/VIN/make-model fields, Aircraft get tail/type/pilot
fields.  Other types show a simplified view.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QScrollArea, QFrame, QSizePolicy, QDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from modules.intel.models.subjects import Subject, SubjectType, SUBJECT_TYPES
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.services.intel_service import IntelService

_log = logging.getLogger(__name__)

_PERSON_TYPES = {
    SubjectType.MISSING_PERSON,
    SubjectType.WITNESS,
    SubjectType.REPORTING_PARTY,
    SubjectType.PATIENT,
    SubjectType.CONTACT,
}


class _FieldRow(QWidget):
    """Read-only label + value pair for the overview section."""

    def __init__(self, label: str, value: str | None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        lbl = QLabel(label + ":")
        lbl.setStyleSheet("font-weight: 600; min-width: 140px;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        val = QLabel(value or "—")
        val.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addWidget(val, 1)


def _section(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet("font-weight: 700; font-size: 13px; margin-top: 6px;")
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    return f


class _EditSubjectDialog(QDialog):
    """Dialog for editing a Subject record — adapts fields to subject_type."""

    def __init__(self, subject: Subject, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Subject — {subject.name}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
        self._subject = subject
        self.updated_subject: Subject | None = None

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(8)

        self._name = QLineEdit(subject.name)
        form.addRow("Name / Identifier *", self._name)

        self._type = QComboBox()
        self._type.addItems(SUBJECT_TYPES)
        self._type.setCurrentText(subject.subject_type)
        form.addRow("Type", self._type)

        self._status = QComboBox()
        self._status.addItems(["Active", "Located", "Deceased", "Archived"])
        self._status.setCurrentText(subject.status)
        form.addRow("Status", self._status)

        # --- Person fields ---
        self._phone = QLineEdit(subject.phone or "")
        form.addRow("Phone", self._phone)

        self._email = QLineEdit(subject.email or "")
        form.addRow("Email", self._email)

        self._dob = QLineEdit(subject.dob or "")
        self._dob.setPlaceholderText("YYYY-MM-DD")
        form.addRow("Date of Birth", self._dob)

        self._lkp_place = QLineEdit(subject.lkp_place or "")
        form.addRow("LKP Place", self._lkp_place)

        self._pls_place = QLineEdit(subject.pls_place or "")
        form.addRow("PLS Place", self._pls_place)

        self._clothing = QLineEdit(subject.clothing_description or "")
        form.addRow("Clothing", self._clothing)

        self._medical = QTextEdit()
        self._medical.setPlainText(subject.medical_conditions or "")
        self._medical.setFixedHeight(60)
        form.addRow("Medical Conditions", self._medical)

        self._treatment_given = QTextEdit()
        self._treatment_given.setPlainText(subject.treatment_given or "")
        self._treatment_given.setFixedHeight(60)
        form.addRow("Treatment Given", self._treatment_given)

        self._transport_required = QLineEdit(subject.transport_required or "")
        form.addRow("Transport Required", self._transport_required)

        self._transport_method = QLineEdit(subject.transport_method or "")
        form.addRow("Transport Method", self._transport_method)

        self._transport_destination = QLineEdit(subject.transport_destination or "")
        form.addRow("Transport Destination", self._transport_destination)

        self._disposition = QLineEdit(subject.disposition or "")
        form.addRow("Disposition", self._disposition)

        self._relationship_to_incident = QLineEdit(subject.relationship_to_incident or "")
        form.addRow("Relationship to Incident", self._relationship_to_incident)

        # --- Vehicle fields ---
        self._plate = QLineEdit(subject.plate or "")
        form.addRow("Plate", self._plate)

        self._plate_state = QLineEdit(subject.plate_state or "")
        form.addRow("State/Province", self._plate_state)

        self._make = QLineEdit(subject.make or "")
        form.addRow("Make", self._make)

        self._model = QLineEdit(subject.model or "")
        form.addRow("Model", self._model)

        self._year = QLineEdit(str(subject.year) if subject.year else "")
        self._year.setPlaceholderText("YYYY")
        form.addRow("Year", self._year)

        self._color = QLineEdit(subject.color or "")
        form.addRow("Color", self._color)

        self._vin = QLineEdit(subject.vin or "")
        form.addRow("VIN", self._vin)

        self._owner_or_operator = QLineEdit(subject.owner_or_operator or "")
        form.addRow("Owner / Operator", self._owner_or_operator)

        # --- Aircraft fields ---
        self._tail_number = QLineEdit(subject.tail_number or "")
        form.addRow("Tail Number", self._tail_number)

        self._aircraft_type = QLineEdit(subject.aircraft_type or "")
        form.addRow("Aircraft Type", self._aircraft_type)

        self._make_model = QLineEdit(subject.make_model or "")
        form.addRow("Make / Model", self._make_model)

        self._color_markings = QLineEdit(subject.color_markings or "")
        form.addRow("Color / Markings", self._color_markings)

        self._pilot_or_operator = QLineEdit(subject.pilot_or_operator or "")
        form.addRow("Pilot / Operator", self._pilot_or_operator)

        self._route_or_last_contact = QTextEdit()
        self._route_or_last_contact.setPlainText(subject.route_or_last_contact or "")
        self._route_or_last_contact.setFixedHeight(60)
        form.addRow("Route / Last Contact", self._route_or_last_contact)

        self._occupants = QLineEdit(subject.occupants or "")
        form.addRow("Occupants", self._occupants)

        self._fuel_endurance = QLineEdit(subject.fuel_endurance or "")
        form.addRow("Fuel Endurance", self._fuel_endurance)

        self._elt_survival_gear = QLineEdit(subject.elt_survival_gear or "")
        form.addRow("ELT / Survival Gear", self._elt_survival_gear)

        self._remarks = QTextEdit()
        self._remarks.setPlainText(subject.remarks or "")
        self._remarks.setFixedHeight(60)
        form.addRow("Remarks", self._remarks)

        self._departure_point = QLineEdit(subject.departure_point or "")
        form.addRow("Departure Point", self._departure_point)

        self._destination = QLineEdit(subject.destination or "")
        form.addRow("Destination", self._destination)

        # --- General description ---
        self._description = QTextEdit()
        self._description.setPlainText(subject.description or "")
        self._description.setFixedHeight(60)
        form.addRow("Description", self._description)

        self._notes = QTextEdit()
        self._notes.setPlainText(subject.notes or "")
        self._notes.setFixedHeight(60)
        form.addRow("Notes", self._notes)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_save(self) -> None:
        s = self._subject
        s.name = self._name.text().strip() or s.name
        s.subject_type = self._type.currentText()
        s.status = self._status.currentText()
        # Person fields
        s.phone = self._phone.text().strip() or None
        s.email = self._email.text().strip() or None
        s.dob = self._dob.text().strip() or None
        s.lkp_place = self._lkp_place.text().strip() or None
        s.pls_place = self._pls_place.text().strip() or None
        s.clothing_description = self._clothing.text().strip() or None
        s.medical_conditions = self._medical.toPlainText().strip() or None
        s.treatment_given = self._treatment_given.toPlainText().strip() or None
        s.transport_required = self._transport_required.text().strip() or None
        s.transport_method = self._transport_method.text().strip() or None
        s.transport_destination = self._transport_destination.text().strip() or None
        s.disposition = self._disposition.text().strip() or None
        s.relationship_to_incident = self._relationship_to_incident.text().strip() or None
        # Vehicle fields
        s.plate = self._plate.text().strip() or None
        s.plate_state = self._plate_state.text().strip() or None
        s.make = self._make.text().strip() or None
        s.model = self._model.text().strip() or None
        yr = self._year.text().strip()
        s.year = int(yr) if yr.isdigit() else None
        s.color = self._color.text().strip() or None
        s.vin = self._vin.text().strip() or None
        s.owner_or_operator = self._owner_or_operator.text().strip() or None
        # Aircraft fields
        s.tail_number = self._tail_number.text().strip() or None
        s.aircraft_type = self._aircraft_type.text().strip() or None
        s.make_model = self._make_model.text().strip() or None
        s.color_markings = self._color_markings.text().strip() or None
        s.pilot_or_operator = self._pilot_or_operator.text().strip() or None
        s.route_or_last_contact = self._route_or_last_contact.toPlainText().strip() or None
        s.departure_point = self._departure_point.text().strip() or None
        s.destination = self._destination.text().strip() or None
        s.occupants = self._occupants.text().strip() or None
        s.fuel_endurance = self._fuel_endurance.text().strip() or None
        s.elt_survival_gear = self._elt_survival_gear.text().strip() or None
        s.remarks = self._remarks.toPlainText().strip() or None
        # General
        s.description = self._description.toPlainText().strip() or None
        s.notes = self._notes.toPlainText().strip() or None
        self.updated_subject = s
        self.accept()


class SubjectDetailWindow(QMainWindow):
    """Modeless window showing full details for a single Subject.

    Multiple instances may be open simultaneously — each tracks its own subject.
    """

    subject_updated = Signal(object)   # emits updated Subject

    def __init__(
        self,
        subject: Subject,
        service: IntelService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._subject = subject
        self._service = service

        self.setWindowTitle(f"Subject: {subject.name}")
        self.resize(760, 640)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._tabs.addTab(self._build_timeline_tab(), "Timeline")
        self._tabs.addTab(self._build_links_tab(), "Linked Records")
        self._tabs.addTab(self._build_activity_log_tab(), "Activity Log")
        root.addWidget(self._tabs)

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(dark); padding: 12px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        name_lbl = QLabel(self._subject.name or "Unknown")
        name_lbl.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: palette(bright-text);"
        )

        type_lbl = QLabel(self._subject.subject_type)
        type_lbl.setStyleSheet("font-size: 13px; color: palette(placeholderText);")

        status_chip = StatusChip(self._subject.status)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_subject)
        delete_btn = QPushButton("Delete Profile")
        delete_btn.clicked.connect(self._delete_subject)

        layout.addWidget(name_lbl)
        layout.addWidget(type_lbl)
        layout.addWidget(status_chip)
        layout.addStretch()
        layout.addWidget(edit_btn)
        layout.addWidget(delete_btn)
        return w

    def _build_overview_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        s = self._subject

        # ---- Vehicle ----
        if s.subject_type == SubjectType.VEHICLE:
            layout.addWidget(_section("Vehicle"))
            layout.addWidget(_FieldRow("Type", s.subject_type))
            layout.addWidget(_FieldRow("Status", s.status))
            layout.addWidget(_FieldRow("Identifier / Name", s.name))
            layout.addWidget(_FieldRow("Make", s.make))
            layout.addWidget(_FieldRow("Model", s.model))
            layout.addWidget(_FieldRow("Year", str(s.year) if s.year else None))
            layout.addWidget(_FieldRow("Color", s.color))
            layout.addWidget(_sep())
            layout.addWidget(_section("Registration"))
            layout.addWidget(_FieldRow("Plate", s.plate))
            layout.addWidget(_FieldRow("State / Province", s.plate_state))
            layout.addWidget(_FieldRow("VIN", s.vin))
            layout.addWidget(_FieldRow("Owner / Operator", s.owner_or_operator))
            if s.description:
                layout.addWidget(_sep())
                layout.addWidget(_section("Description"))
                d = QLabel(s.description)
                d.setWordWrap(True)
                layout.addWidget(d)

        # ---- Aircraft ----
        elif s.subject_type == SubjectType.AIRCRAFT:
            layout.addWidget(_section("Aircraft Profile"))
            layout.addWidget(_FieldRow("Type", s.subject_type))
            layout.addWidget(_FieldRow("Status", s.status))
            layout.addWidget(_FieldRow("Identifier / Call Sign", s.name))

            layout.addWidget(_sep())
            layout.addWidget(_section("Identification"))
            layout.addWidget(_FieldRow("Tail Number", s.tail_number))
            layout.addWidget(_FieldRow("Aircraft Type", s.aircraft_type))
            layout.addWidget(_FieldRow("Make / Model", s.make_model))
            layout.addWidget(_FieldRow("Color / Markings", s.color_markings))

            layout.addWidget(_sep())
            layout.addWidget(_section("Flight / Operation"))
            layout.addWidget(_FieldRow("Pilot / Operator", s.pilot_or_operator))
            layout.addWidget(_FieldRow("Departure Point", s.departure_point))
            layout.addWidget(_FieldRow("Destination", s.destination))
            layout.addWidget(_FieldRow("Route / Last Contact", s.route_or_last_contact))
            layout.addWidget(_FieldRow("Occupants", s.occupants))

            layout.addWidget(_sep())
            layout.addWidget(_section("Performance / Safety"))
            layout.addWidget(_FieldRow("Fuel Endurance", s.fuel_endurance))
            layout.addWidget(_FieldRow("ELT / Survival Gear", s.elt_survival_gear))
            if s.remarks:
                layout.addWidget(_sep())
                layout.addWidget(_section("Remarks"))
                rem = QLabel(s.remarks)
                rem.setWordWrap(True)
                layout.addWidget(rem)
            if s.description:
                layout.addWidget(_sep())
                layout.addWidget(_section("Description"))
                d = QLabel(s.description)
                d.setWordWrap(True)
                layout.addWidget(d)
            # Cross-link initial response aircraft info
            self._add_initialresponse_section(layout, "aircraft")

        # ---- Person types ----
        else:
            layout.addWidget(_section("Human Profile"))
            layout.addWidget(_FieldRow("Subject Type", s.subject_type))
            layout.addWidget(_FieldRow("Status", s.status))
            layout.addWidget(_FieldRow("Name", s.name))
            layout.addWidget(_FieldRow("DOB", s.dob))
            layout.addWidget(_FieldRow("Sex", s.sex))
            layout.addWidget(_FieldRow("Phone", s.phone))
            layout.addWidget(_FieldRow("Email", s.email))
            layout.addWidget(_FieldRow("Address", s.address))
            layout.addWidget(_FieldRow("Organization", s.organization))
            layout.addWidget(_FieldRow("Relationship to Incident", s.relationship_to_incident))
            if s.medical_conditions:
                layout.addWidget(_FieldRow("Medical Conditions", s.medical_conditions))

            if s.subject_type == SubjectType.PATIENT:
                layout.addWidget(_sep())
                layout.addWidget(_section("Patient Care"))
                layout.addWidget(_FieldRow("Treatment Given", s.treatment_given))
                layout.addWidget(_FieldRow("Transport Required", s.transport_required))
                layout.addWidget(_FieldRow("Transport Method", s.transport_method))
                layout.addWidget(_FieldRow("Transport Destination", s.transport_destination))
                layout.addWidget(_FieldRow("Disposition", s.disposition))
            elif s.subject_type in (SubjectType.WITNESS, SubjectType.REPORTING_PARTY, SubjectType.CONTACT):
                layout.addWidget(_sep())
                layout.addWidget(_section("Contact / Role"))
                layout.addWidget(_FieldRow("Relationship to Incident", s.relationship_to_incident))
            elif s.subject_type == SubjectType.MISSING_PERSON:
                layout.addWidget(_sep())
                layout.addWidget(_section("SAR Profile"))
                layout.addWidget(_FieldRow("LKP Time", s.lkp_time))
                layout.addWidget(_FieldRow("LKP Place", s.lkp_place))
                layout.addWidget(_FieldRow("PLS Time", s.pls_time))
                layout.addWidget(_FieldRow("PLS Place", s.pls_place))
                layout.addWidget(_FieldRow("Clothing", s.clothing_description))
                layout.addWidget(_FieldRow("Equipment", s.equipment_description))
                layout.addWidget(_FieldRow("Vehicle", s.vehicle_description))
                layout.addWidget(_FieldRow("Outdoor Experience", s.outdoor_experience))
                layout.addWidget(_FieldRow("Behavioral Notes", s.behavioral_notes))
                layout.addWidget(_sep())
                self._add_initialresponse_section(layout, "subject")

        if s.notes:
            layout.addWidget(_sep())
            layout.addWidget(_section("Notes"))
            notes_lbl = QLabel(s.notes)
            notes_lbl.setWordWrap(True)
            layout.addWidget(notes_lbl)

        layout.addWidget(_FieldRow("Created", s.created_at[:16].replace("T", "  ") if s.created_at else None))
        layout.addWidget(_FieldRow("Updated", s.updated_at[:16].replace("T", "  ") if s.updated_at else None))
        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _add_initialresponse_section(self, layout: QVBoxLayout, kind: str) -> None:
        """Append a read-only Initial Response cross-reference section to layout.

        `kind` is "subject" (for Missing Person) or "aircraft".
        Makes one API call; silently skips if data is unavailable.
        """
        try:
            from utils.api_client import api_client
            data = api_client.get(
                f"/api/incidents/{self._service.incident_id}/initialresponse/overview"
            )
        except Exception:
            return

        if kind == "aircraft":
            info: dict = data.get("aircraft_info") or {}
            if not any(info.values()):
                return
            layout.addWidget(_sep())
            hdr = QLabel("Initial Response — Aircraft Info (read-only reference)")
            hdr.setStyleSheet("font-weight: 700; font-size: 12px; color: palette(placeholderText);")
            layout.addWidget(hdr)
            field_map = [
                ("Tail Number", "tail_number"),
                ("Aircraft Type", "aircraft_type"),
                ("Color / Markings", "markings"),
                ("Pilot", "pilot"),
                ("Occupants", "occupants"),
                ("Route / Destination", "route"),
                ("Fuel Endurance", "fuel_endurance"),
                ("ELT / Survival Gear", "elt_survival"),
            ]
            for label, key in field_map:
                val = info.get(key)
                if val:
                    layout.addWidget(_FieldRow(label, str(val)))
        elif kind == "subject":
            info = data.get("subject_info") or {}
            if not any(info.values()):
                return
            layout.addWidget(_sep())
            hdr = QLabel("Initial Response — Subject Info (read-only reference)")
            hdr.setStyleSheet("font-weight: 700; font-size: 12px; color: palette(placeholderText);")
            layout.addWidget(hdr)
            field_map = [
                ("Nickname", "nickname"),
                ("Physical Description", "description"),
                ("Clothing Summary", "clothing"),
                ("Medical / Cognitive", "medical"),
                ("Equipment", "equipment"),
            ]
            for label, key in field_map:
                val = info.get(key)
                if val:
                    layout.addWidget(_FieldRow(label, str(val)))

    def _build_timeline_tab(self) -> QWidget:
        """Chronological timeline combining Intel Log entries and linked item observations."""
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Subject timeline — Intel Log entries and linked item observations."))
        hdr.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_timeline)
        hdr.addWidget(refresh_btn)
        outer.addLayout(hdr)

        tl_cols = ["Time", "Event", "Source", "Detail"]
        self._timeline_table = QTableWidget()
        self._timeline_table.setColumnCount(len(tl_cols))
        self._timeline_table.setHorizontalHeaderLabels(tl_cols)
        self._timeline_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._timeline_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._timeline_table.verticalHeader().setVisible(False)
        self._timeline_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        outer.addWidget(self._timeline_table)
        legend = QLabel("Legend: row colors follow linked event or record context.")
        legend.setStyleSheet("color: palette(placeholderText); font-size: 11px;")
        outer.addWidget(legend)

        self._refresh_timeline()
        return w

    def _refresh_timeline(self) -> None:
        events: list[dict] = []

        s = self._subject
        # Created / updated anchors
        if s.created_at:
            events.append({"ts": s.created_at, "event": "Created", "source": "System", "detail": f"Subject record created: {s.name}"})
        if s.updated_at and s.updated_at != s.created_at:
            events.append({"ts": s.updated_at, "event": "Updated", "source": "System", "detail": "Subject record updated"})

        # Intel Log entries for this subject
        try:
            log_entries = self._service.log.list(entity_type="subject", entity_id=s.id, limit=200)
            for entry in log_entries:
                events.append({
                    "ts": entry.timestamp,
                    "event": entry.event_label,
                    "source": entry.actor or "system",
                    "detail": entry.summary,
                })
        except Exception as exc:
            _log.warning("Timeline: could not fetch log entries: %s", exc)

        # Observations from linked Intel Items
        for item_id in s.linked_item_ids:
            try:
                item = self._service.items.get(item_id)
                if item:
                    for obs in item.observations:
                        events.append({
                            "ts": obs.observed_at,
                            "event": "Observation",
                            "source": obs.observer or obs.source_team or "",
                            "detail": f"[{item.title}] {obs.summary}",
                        })
            except Exception as exc:
                _log.warning("Timeline: could not fetch item %s: %s", item_id, exc)

        # Sort newest first
        events.sort(key=lambda e: e.get("ts", ""), reverse=True)

        self._timeline_table.setRowCount(len(events))
        for row, ev in enumerate(events):
            ts = (ev["ts"] or "")[:16].replace("T", " ")
            self._timeline_table.setItem(row, 0, QTableWidgetItem(ts))
            self._timeline_table.setItem(row, 1, QTableWidgetItem(ev.get("event", "")))
            self._timeline_table.setItem(row, 2, QTableWidgetItem(ev.get("source", "")))
            self._timeline_table.setItem(row, 3, QTableWidgetItem(ev.get("detail", "")))
            self._timeline_table.setRowHeight(row, 26)

        for col in (0, 1, 2):
            self._timeline_table.resizeColumnToContents(col)

        if not events:
            self._timeline_table.setRowCount(1)
            placeholder = QTableWidgetItem("No timeline events found.")
            placeholder.setForeground(self._timeline_table.palette().placeholderText())
            self._timeline_table.setItem(0, 0, placeholder)

    def _build_links_tab(self) -> QWidget:
        """Linked Records tab — shows resolved Intel Items (with location) and Tasks."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        s = self._subject

        if s.linked_item_ids:
            layout.addWidget(_section(f"Linked Intel Items ({len(s.linked_item_ids)})"))
            location_items: list[Any] = []
            for item_id in s.linked_item_ids:
                item = None
                try:
                    item = self._service.items.get(item_id)
                except Exception:
                    pass
                if item:
                    row_w = QWidget()
                    row_l = QHBoxLayout(row_w)
                    row_l.setContentsMargins(0, 2, 0, 2)
                    # Title + type chip
                    title_lbl = QLabel(f"  • {item.item_type}: {item.title}")
                    title_lbl.setWordWrap(True)
                    row_l.addWidget(title_lbl, 1)
                    # Location inline (item 4 requirement)
                    if item.location_text:
                        loc_lbl = QLabel(f"  📍 {item.location_text}")
                        loc_lbl.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
                        location_items.append(item)

                    open_btn = QPushButton("View")
                    open_btn.setFixedHeight(22)
                    open_btn.setFixedWidth(44)
                    _it = item
                    open_btn.clicked.connect(lambda _, i=_it: self._open_item(i))
                    row_l.addWidget(open_btn)
                    layout.addWidget(row_w)
                    if item.location_text:
                        layout.addWidget(loc_lbl)
                else:
                    layout.addWidget(QLabel(f"  • Intel Item — {item_id}"))

        if s.linked_task_ids:
            layout.addWidget(_sep())
            layout.addWidget(_section(f"Linked Tasks ({len(s.linked_task_ids)})"))
            for tid in s.linked_task_ids:
                task_display = tid
                task_int_id = None
                try:
                    task_int_id = int(tid)
                    from modules.operations.taskings.repository import get_task
                    task = get_task(task_int_id)
                    task_display = f"{task.task_id} — {task.title}"
                except Exception:
                    pass

                row_w = QWidget()
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(0, 2, 0, 2)
                row_l.addWidget(QLabel(f"  • {task_display}"), 1)
                if task_int_id is not None:
                    open_btn = QPushButton("View")
                    open_btn.setFixedHeight(22)
                    open_btn.setFixedWidth(44)
                    _tid = task_int_id
                    open_btn.clicked.connect(lambda _, t=_tid: self._open_task(t))
                    row_l.addWidget(open_btn)
                layout.addWidget(row_w)

        if not s.linked_item_ids and not s.linked_task_ids:
            layout.addWidget(QLabel("No linked records."))
            note = QLabel(
                "Tip: link Intel Items to this subject to associate location information, "
                "observations, and clue findings."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
            layout.addWidget(note)

        layout.addStretch()
        return w

    def _build_activity_log_tab(self) -> QWidget:
        """Activity Log — Intel Log entries for this subject."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Intel Log entries for this subject."))
        hdr.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_activity_log)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        log_cols = ["Time", "Event", "Actor", "Summary"]
        self._log_table = QTableWidget()
        self._log_table.setColumnCount(len(log_cols))
        self._log_table.setHorizontalHeaderLabels(log_cols)
        self._log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self._log_table)
        legend = QLabel("Legend: row colors follow linked event or record context.")
        legend.setStyleSheet("color: palette(placeholderText); font-size: 11px;")
        layout.addWidget(legend)

        self._refresh_activity_log()
        return w

    def _refresh_activity_log(self) -> None:
        try:
            entries = self._service.log.list(
                entity_type="subject",
                entity_id=self._subject.id,
                limit=200,
            )
        except Exception as exc:
            _log.warning("Could not load activity log: %s", exc)
            entries = []

        self._log_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            ts = entry.timestamp[:16].replace("T", " ") if entry.timestamp else ""
            self._log_table.setItem(row, 0, QTableWidgetItem(ts))
            self._log_table.setItem(row, 1, QTableWidgetItem(entry.event_label))
            self._log_table.setItem(row, 2, QTableWidgetItem(entry.actor or "system"))
            self._log_table.setItem(row, 3, QTableWidgetItem(entry.summary))
            self._log_table.setRowHeight(row, 26)

        for col in (0, 1, 2):
            self._log_table.resizeColumnToContents(col)

        if not entries:
            self._log_table.setRowCount(1)
            placeholder = QTableWidgetItem("No log entries for this subject yet.")
            placeholder.setForeground(self._log_table.palette().placeholderText())
            self._log_table.setItem(0, 0, placeholder)

    # ------------------------------------------------------------------
    # Navigation helpers

    def _open_item(self, item) -> None:
        try:
            from modules.intel.windows.intel_item_detail_window import IntelItemDetailWindow
            win = IntelItemDetailWindow(item, self._service, parent=self)
            win.show()
            win.raise_()
        except Exception as exc:
            _log.warning("Could not open item detail: %s", exc)

    def _open_task(self, task_id: int) -> None:
        try:
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(task_id)
        except Exception as exc:
            _log.warning("Could not open task detail: %s", exc)

    # ------------------------------------------------------------------
    # Edit

    def _edit_subject(self) -> None:
        dlg = _EditSubjectDialog(self._subject, self)
        if dlg.exec() == QDialog.Accepted and dlg.updated_subject:
            saved = self._service.subjects.update(
                self._subject.id, dlg.updated_subject.to_api_dict()
            )
            if saved:
                self._subject = saved
                self.setWindowTitle(f"Subject: {saved.name}")
                self.subject_updated.emit(saved)
                # Rebuild overview tab in-place
                self._tabs.removeTab(0)
                self._tabs.insertTab(0, self._build_overview_tab(), "Overview")
                self._tabs.setCurrentIndex(0)

    def _delete_subject(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        confirm = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete the subject profile for {self._subject.name}?\n\nThis archives the record.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes and self._service.subjects.archive(self._subject.id):
            self.close()
