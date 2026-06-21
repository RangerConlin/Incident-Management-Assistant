"""Detail dialog for a single IWI (Safety Incident) report — mirrors ACSF-11 sections."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
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
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.state import AppState
from modules.safety import services

# ---------------------------------------------------------------------------
# Constants matching the form
# ---------------------------------------------------------------------------

INCIDENT_TYPES = [
    "Near-Miss",
    "Unsafe Condition",
    "Unsafe Act",
    "Equipment Failure",
    "Medical / Injury",
    "Environmental",
    "Crowd / Public Safety",
]

OUTCOMES = [
    "No contact / no harm — hazard only",
    "First aid treated on scene",
    "Medical treatment required (beyond first aid)",
    "Hospitalization",
    "Fatality",
    "Property / equipment damage only",
    "Operational disruption (no injury)",
]

SEVERITIES = ["MINOR", "MODERATE", "SERIOUS", "CRITICAL"]

SEVERITY_COLORS = {
    "MINOR": "#2e7d32",
    "MODERATE": "#e65100",
    "SERIOUS": "#b71c1c",
    "CRITICAL": "#4a148c",
}

ACTIVITY_IMPACTS = [
    "No operational impact",
    "Brief disruption",
    "Partial suspension",
    "Full suspension",
    "Event termination",
]

HUMAN_FACTORS = [
    "Inattention / distraction",
    "Fatigue",
    "Rushing / time pressure",
    "Inadequate training / briefing",
    "Procedure not followed",
    "Miscommunication",
    "Poor decision-making",
    "Crowd / public behavior",
]

ENVIRONMENTAL_FACTORS = [
    "Weather / lightning",
    "Extreme heat / cold",
    "Poor visibility / lighting",
    "Terrain / ground conditions",
    "Structural / infrastructure",
    "Equipment defect / failure",
    "Inadequate barriers / signage",
    "Crowd density / flow",
]

ORGANIZATIONAL_FACTORS = [
    "Inadequate supervision",
    "Planning deficiency",
    "Resource / staffing shortfall",
    "Communication system failure",
    "ICS structure unclear",
    "Policy / procedure gap",
    "Inspection / maintenance gap",
    "Coordination failure (agencies)",
]

NOTIFICATION_ROLES = [
    "Safety Officer",
    "IC / Unified Command",
    "Operations Section Chief",
    "Medical / EMS",
    "PIO",
    "Agency Liaison",
    "Other",
]

ESCALATION_OPTIONS = [
    "No escalation — monitor situation",
    "Increased monitoring required",
    "Activity suspension ref issued",
    "Partial suspension ordered",
    "Full suspension ordered",
]

SIGNOFF_ROLES = [
    ("reporter", "Reporter / Submitter"),
    ("supervisor", "Supervisor / Branch Director"),
    ("ops_chief", "Operations Section Chief"),
]

STATUS_COLORS = {
    "draft": "#546e7a",
    "submitted": "#1565c0",
    "reviewed": "#e65100",
    "closed": "#2e7d32",
}


# ---------------------------------------------------------------------------
# Helper widgets
# ---------------------------------------------------------------------------

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    font = QFont()
    font.setBold(True)
    font.setPointSize(9)
    lbl.setFont(font)
    lbl.setStyleSheet("color: #1a237e; padding-top: 6px;")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #e0e0e0;")
    return line


def _scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    area.setFrameShape(QFrame.NoFrame)
    return area


# ---------------------------------------------------------------------------
# Sub-dialogs
# ---------------------------------------------------------------------------

class PersonDialog(QDialog):
    def __init__(self, parent=None, data: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Person Involved")
        self.setMinimumWidth(440)
        layout = QFormLayout(self)
        self._name = QLineEdit(data.get("name", "") if data else "")
        self._role = QLineEdit(data.get("role", "") if data else "")
        self._agency = QLineEdit(data.get("agency", "") if data else "")
        self._contact = QLineEdit(data.get("contact", "") if data else "")
        self._injury = QCheckBox()
        self._injury.setChecked(bool(data.get("injury_illness", False)) if data else False)
        self._disposition = QLineEdit(data.get("disposition", "") if data else "")
        layout.addRow("Name", self._name)
        layout.addRow("Role / ICS Position", self._role)
        layout.addRow("Agency / Affiliation", self._agency)
        layout.addRow("Contact / Radio", self._contact)
        layout.addRow("Injury / Illness?", self._injury)
        layout.addRow("Disposition", self._disposition)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def result_data(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "role": self._role.text().strip(),
            "agency": self._agency.text().strip(),
            "contact": self._contact.text().strip(),
            "injury_illness": self._injury.isChecked(),
            "disposition": self._disposition.text().strip(),
        }


class InjuryDialog(QDialog):
    def __init__(self, parent=None, data: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Injury / Illness Detail")
        self.setMinimumWidth(460)
        layout = QFormLayout(self)
        d = data or {}
        self._person = QLineEdit(d.get("person_name", ""))
        self._nature = QLineEdit(d.get("nature", ""))
        self._body_part = QLineEdit(d.get("body_part", ""))
        self._treatment = QLineEdit(d.get("treatment", ""))
        self._treated_by = QLineEdit(d.get("treated_by", ""))
        self._ems = QCheckBox()
        self._ems.setChecked(bool(d.get("ems_involved", False)))
        self._transport = QLineEdit(d.get("transport_disposition", ""))
        self._facility = QLineEdit(d.get("receiving_facility", ""))
        self._transport_time = QLineEdit(d.get("time_of_transport", ""))
        self._notes = QTextEdit(d.get("notes", ""))
        self._notes.setFixedHeight(70)
        layout.addRow("Person Name", self._person)
        layout.addRow("Nature of Injury / Illness", self._nature)
        layout.addRow("Body Part Affected", self._body_part)
        layout.addRow("Treatment Rendered", self._treatment)
        layout.addRow("Treated By", self._treated_by)
        layout.addRow("EMS / Hospital Involved?", self._ems)
        layout.addRow("Transport / Disposition", self._transport)
        layout.addRow("Receiving Facility", self._facility)
        layout.addRow("Time of Transport", self._transport_time)
        layout.addRow("Additional Notes", self._notes)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def result_data(self) -> dict:
        return {
            "person_name": self._person.text().strip(),
            "nature": self._nature.text().strip(),
            "body_part": self._body_part.text().strip(),
            "treatment": self._treatment.text().strip(),
            "treated_by": self._treated_by.text().strip(),
            "ems_involved": self._ems.isChecked(),
            "transport_disposition": self._transport.text().strip(),
            "receiving_facility": self._facility.text().strip(),
            "time_of_transport": self._transport_time.text().strip(),
            "notes": self._notes.toPlainText().strip(),
        }


class WitnessDialog(QDialog):
    def __init__(self, parent=None, data: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Witness Statement")
        self.setMinimumWidth(500)
        self.setMinimumHeight(520)
        layout = QFormLayout(self)
        d = data or {}
        self._name = QLineEdit(d.get("full_name", ""))
        self._role = QLineEdit(d.get("position_role", ""))
        self._agency = QLineEdit(d.get("agency", ""))
        self._contact = QLineEdit(d.get("contact", ""))
        self._direct = QCheckBox()
        self._direct.setChecked(bool(d.get("directly_involved", False)))
        self._location = QLineEdit(d.get("location_at_time", ""))
        self._distance = QLineEdit(d.get("distance_from_incident", ""))
        self._obs_time = QLineEdit(d.get("time_of_observation", ""))
        self._statement = QTextEdit(d.get("statement", ""))
        self._statement.setMinimumHeight(160)
        self._complete = QCheckBox("Statement complete as written")
        self._complete.setChecked(bool(d.get("statement_complete", False)))
        self._received_by = QLineEdit(d.get("received_by", ""))
        layout.addRow("Full Name", self._name)
        layout.addRow("Position / Role", self._role)
        layout.addRow("Agency", self._agency)
        layout.addRow("Cell / Contact", self._contact)
        layout.addRow("Directly Involved?", self._direct)
        layout.addRow("Location at Time of Incident", self._location)
        layout.addRow("Distance from Incident", self._distance)
        layout.addRow("Time of Observation", self._obs_time)
        layout.addRow("Statement", self._statement)
        layout.addRow("", self._complete)
        layout.addRow("Received By", self._received_by)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def result_data(self) -> dict:
        return {
            "full_name": self._name.text().strip(),
            "position_role": self._role.text().strip(),
            "agency": self._agency.text().strip(),
            "contact": self._contact.text().strip(),
            "directly_involved": self._direct.isChecked(),
            "location_at_time": self._location.text().strip(),
            "distance_from_incident": self._distance.text().strip(),
            "time_of_observation": self._obs_time.text().strip(),
            "statement": self._statement.toPlainText().strip(),
            "statement_complete": self._complete.isChecked(),
            "received_by": self._received_by.text().strip(),
        }


class CorrectiveActionDialog(QDialog):
    def __init__(self, parent=None, data: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Corrective Action")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        d = data or {}
        self._action = QTextEdit(d.get("action", ""))
        self._action.setFixedHeight(80)
        self._assigned = QLineEdit(d.get("assigned_to", ""))
        self._due = QLineEdit(d.get("due_date", ""))
        self._status = QComboBox()
        self._status.addItems(["Open", "Done"])
        if d.get("status", "open").lower() == "done":
            self._status.setCurrentText("Done")
        layout.addRow("Recommended Action", self._action)
        layout.addRow("Assigned To", self._assigned)
        layout.addRow("Due Date", self._due)
        layout.addRow("Status", self._status)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def result_data(self) -> dict:
        return {
            "action": self._action.toPlainText().strip(),
            "assigned_to": self._assigned.text().strip(),
            "due_date": self._due.text().strip(),
            "status": self._status.currentText().lower(),
        }


# ---------------------------------------------------------------------------
# Main detail dialog
# ---------------------------------------------------------------------------

class IWIDetailDialog(QDialog):
    """Full detail dialog for a Safety Incident report (ACSF-11 fields)."""

    def __init__(
        self,
        incident_id: str,
        report_id: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._incident_id = incident_id
        self._report_id = report_id
        self._data: dict[str, Any] = {}
        self._persons: list[dict] = []
        self._injuries: list[dict] = []
        self._witnesses: list[dict] = []
        self._corrective_actions: list[dict] = []
        self._sequence: list[dict] = []
        self._notifications: list[dict] = []

        self.setWindowTitle("Safety Incident Report")
        self.setMinimumSize(820, 680)
        self.resize(900, 720)

        self._build_ui()
        if report_id:
            self._load()

    # ---------------------------------------------------------------------- build
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Status bar
        status_row = QHBoxLayout()
        self._form_num_lbl = QLabel("New Report")
        self._form_num_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
        self._status_chip = QLabel("Draft")
        self._status_chip.setAlignment(Qt.AlignCenter)
        self._status_chip.setStyleSheet(
            "background: #546e7a; color: white; border-radius: 10px; padding: 2px 10px; font-weight: 600;"
        )
        status_row.addWidget(self._form_num_lbl)
        status_row.addStretch()
        status_row.addWidget(QLabel("Status:"))
        status_row.addWidget(self._status_chip)
        outer.addLayout(status_row)

        self._tabs = QTabWidget()
        outer.addWidget(self._tabs, 1)

        self._build_tab_occurrence()
        self._build_tab_classification()
        self._build_tab_people()
        self._build_tab_narrative()
        self._build_tab_resolution()

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

    # ---- Tab 1: Occurrence ---------------------------------------------------
    def _build_tab_occurrence(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(_section_label("Occurrence Identification"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self._op_period = QSpinBox()
        self._op_period.setRange(1, 99)
        self._date_of_occurrence = QLineEdit()
        self._date_of_occurrence.setPlaceholderText("YYYY-MM-DD")
        self._day_of_event = QSpinBox()
        self._day_of_event.setRange(1, 30)
        self._time_of_occurrence = QLineEdit()
        self._time_of_occurrence.setPlaceholderText("HH:MM (24-hr)")
        self._time_reported = QLineEdit()
        self._time_reported.setPlaceholderText("HH:MM (24-hr)")
        self._reported_by = QLineEdit()

        grid.addWidget(QLabel("Op Period"), 0, 0)
        grid.addWidget(self._op_period, 0, 1)
        grid.addWidget(QLabel("Date of Occurrence"), 0, 2)
        grid.addWidget(self._date_of_occurrence, 0, 3)
        grid.addWidget(QLabel("Day of Event"), 0, 4)
        grid.addWidget(self._day_of_event, 0, 5)

        grid.addWidget(QLabel("Time of Occurrence"), 1, 0)
        grid.addWidget(self._time_of_occurrence, 1, 1)
        grid.addWidget(QLabel("Time Reported"), 1, 2)
        grid.addWidget(self._time_reported, 1, 3)
        grid.addWidget(QLabel("Reported By"), 1, 4)
        grid.addWidget(self._reported_by, 1, 5)
        layout.addLayout(grid)

        layout.addWidget(_divider())
        layout.addWidget(_section_label("Location Details"))
        loc_grid = QGridLayout()
        loc_grid.setHorizontalSpacing(10)
        loc_grid.setVerticalSpacing(6)
        self._loc_general = QLineEdit()
        self._loc_zone = QLineEdit()
        self._loc_sector = QLineEdit()
        self._loc_specific = QLineEdit()
        loc_grid.addWidget(QLabel("General Location"), 0, 0)
        loc_grid.addWidget(self._loc_general, 0, 1)
        loc_grid.addWidget(QLabel("Zone / Division"), 0, 2)
        loc_grid.addWidget(self._loc_zone, 0, 3)
        loc_grid.addWidget(QLabel("Sector / Post"), 0, 4)
        loc_grid.addWidget(self._loc_sector, 0, 5)
        loc_grid.addWidget(QLabel("Specific Location"), 1, 0)
        loc_grid.addWidget(self._loc_specific, 1, 1, 1, 5)
        layout.addLayout(loc_grid)
        layout.addStretch()

        self._tabs.addTab(_scrollable(page), "Occurrence")

    # ---- Tab 2: Classification & Conditions ----------------------------------
    def _build_tab_classification(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(_section_label("Incident Classification"))

        type_box = QGroupBox("Incident Type (select all that apply)")
        type_layout = QGridLayout(type_box)
        self._type_checks: dict[str, QCheckBox] = {}
        for i, t in enumerate(INCIDENT_TYPES):
            cb = QCheckBox(t)
            self._type_checks[t] = cb
            type_layout.addWidget(cb, i // 2, i % 2)
        other_row = QHBoxLayout()
        self._type_other_check = QCheckBox("Other:")
        self._type_other_text = QLineEdit()
        self._type_other_text.setPlaceholderText("specify")
        other_row.addWidget(self._type_other_check)
        other_row.addWidget(self._type_other_text)
        type_layout.addLayout(other_row, len(INCIDENT_TYPES) // 2 + 1, 0, 1, 2)
        layout.addWidget(type_box)

        outcome_row = QFormLayout()
        self._actual_outcome = QComboBox()
        self._actual_outcome.addItem("")
        self._actual_outcome.addItems(OUTCOMES)
        outcome_row.addRow("Actual Outcome", self._actual_outcome)
        layout.addLayout(outcome_row)

        sev_box = QGroupBox("Actual Severity")
        sev_layout = QHBoxLayout(sev_box)
        self._severity_group: dict[str, QPushButton] = {}
        for s in SEVERITIES:
            btn = QPushButton(s)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            color = SEVERITY_COLORS[s]
            btn.setStyleSheet(
                f"QPushButton:checked {{ background-color: {color}; color: white; font-weight: 700; border-radius: 4px; }}"
            )
            btn.clicked.connect(lambda checked, sev=s: self._on_severity_click(sev))
            self._severity_group[s] = btn
            sev_layout.addWidget(btn)
        layout.addWidget(sev_box)

        impact_row = QFormLayout()
        self._activity_impact = QComboBox()
        self._activity_impact.addItem("")
        self._activity_impact.addItems(ACTIVITY_IMPACTS)
        self._suspension_ref = QLineEdit()
        self._suspension_ref.setPlaceholderText("Activity suspension form reference #")
        impact_row.addRow("Activity Impact", self._activity_impact)
        impact_row.addRow("Activity Suspension Ref", self._suspension_ref)
        layout.addLayout(impact_row)

        layout.addWidget(_divider())
        layout.addWidget(_section_label("Conditions at Time of Occurrence"))
        cond_grid = QGridLayout()
        cond_grid.setHorizontalSpacing(10)
        cond_grid.setVerticalSpacing(6)
        self._cond_weather = QLineEdit()
        self._cond_temp = QLineEdit()
        self._cond_wind = QLineEdit()
        self._cond_visibility = QLineEdit()
        self._cond_crowd = QLineEdit()
        self._cond_lighting = QLineEdit()
        self._cond_nws = QLineEdit()
        self._cond_other = QLineEdit()
        cond_grid.addWidget(QLabel("Weather"), 0, 0); cond_grid.addWidget(self._cond_weather, 0, 1)
        cond_grid.addWidget(QLabel("Temp / Heat Index"), 0, 2); cond_grid.addWidget(self._cond_temp, 0, 3)
        cond_grid.addWidget(QLabel("Wind Speed / Dir"), 0, 4); cond_grid.addWidget(self._cond_wind, 0, 5)
        cond_grid.addWidget(QLabel("Visibility"), 1, 0); cond_grid.addWidget(self._cond_visibility, 1, 1)
        cond_grid.addWidget(QLabel("Crowd Density"), 1, 2); cond_grid.addWidget(self._cond_crowd, 1, 3)
        cond_grid.addWidget(QLabel("Lighting Conditions"), 1, 4); cond_grid.addWidget(self._cond_lighting, 1, 5)
        cond_grid.addWidget(QLabel("Active NWS Warnings"), 2, 0); cond_grid.addWidget(self._cond_nws, 2, 1, 1, 2)
        cond_grid.addWidget(QLabel("Other Relevant Conditions"), 2, 3); cond_grid.addWidget(self._cond_other, 2, 4, 1, 2)
        layout.addLayout(cond_grid)
        layout.addStretch()

        self._tabs.addTab(_scrollable(page), "Classification")

    def _on_severity_click(self, selected: str) -> None:
        for s, btn in self._severity_group.items():
            btn.setChecked(s == selected)

    # ---- Tab 3: People & Events ---------------------------------------------
    def _build_tab_people(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        # Persons Involved
        layout.addWidget(_section_label("Persons Involved"))
        p_toolbar = QHBoxLayout()
        add_p = QPushButton("Add Person")
        edit_p = QPushButton("Edit")
        del_p = QPushButton("Remove")
        add_p.clicked.connect(self._add_person)
        edit_p.clicked.connect(self._edit_person)
        del_p.clicked.connect(self._remove_person)
        p_toolbar.addWidget(add_p); p_toolbar.addWidget(edit_p); p_toolbar.addWidget(del_p); p_toolbar.addStretch()
        layout.addLayout(p_toolbar)
        self._persons_table = QTableWidget(0, 6)
        self._persons_table.setHorizontalHeaderLabels(["Name", "Role / ICS Position", "Agency", "Contact", "Injury/Illness", "Disposition"])
        self._persons_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._persons_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._persons_table.verticalHeader().setVisible(False)
        self._persons_table.setFixedHeight(140)
        self._persons_table.doubleClicked.connect(self._edit_person)
        layout.addWidget(self._persons_table)

        # Injury Detail
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Injury / Illness Detail"))
        i_toolbar = QHBoxLayout()
        add_i = QPushButton("Add Entry")
        edit_i = QPushButton("Edit")
        del_i = QPushButton("Remove")
        add_i.clicked.connect(self._add_injury)
        edit_i.clicked.connect(self._edit_injury)
        del_i.clicked.connect(self._remove_injury)
        i_toolbar.addWidget(add_i); i_toolbar.addWidget(edit_i); i_toolbar.addWidget(del_i); i_toolbar.addStretch()
        layout.addLayout(i_toolbar)
        self._injuries_table = QTableWidget(0, 5)
        self._injuries_table.setHorizontalHeaderLabels(["Person", "Nature of Injury/Illness", "Body Part", "Treatment", "EMS?"])
        self._injuries_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._injuries_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._injuries_table.verticalHeader().setVisible(False)
        self._injuries_table.setFixedHeight(140)
        self._injuries_table.doubleClicked.connect(self._edit_injury)
        layout.addLayout(i_toolbar)
        layout.addWidget(self._injuries_table)

        # Equipment
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Equipment / Asset Involved"))
        eq_grid = QGridLayout()
        eq_grid.setHorizontalSpacing(10)
        eq_grid.setVerticalSpacing(6)
        self._eq_desc = QLineEdit()
        self._eq_asset_id = QLineEdit()
        self._eq_owner = QLineEdit()
        self._eq_condition = QLineEdit()
        self._eq_last_inspection = QLineEdit()
        self._eq_last_inspection.setPlaceholderText("YYYY-MM-DD")
        self._eq_oos = QComboBox()
        self._eq_oos.addItems(["N/A", "Yes", "No"])
        eq_grid.addWidget(QLabel("Equipment / Asset"), 0, 0); eq_grid.addWidget(self._eq_desc, 0, 1)
        eq_grid.addWidget(QLabel("Asset ID / Tag #"), 0, 2); eq_grid.addWidget(self._eq_asset_id, 0, 3)
        eq_grid.addWidget(QLabel("Owner / Operator"), 0, 4); eq_grid.addWidget(self._eq_owner, 0, 5)
        eq_grid.addWidget(QLabel("Condition at Incident"), 1, 0); eq_grid.addWidget(self._eq_condition, 1, 1)
        eq_grid.addWidget(QLabel("Last Inspection"), 1, 2); eq_grid.addWidget(self._eq_last_inspection, 1, 3)
        eq_grid.addWidget(QLabel("Taken Out of Service?"), 1, 4); eq_grid.addWidget(self._eq_oos, 1, 5)
        layout.addLayout(eq_grid)

        # Sequence of Events
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Sequence of Events"))
        seq_toolbar = QHBoxLayout()
        add_seq = QPushButton("Add Event")
        del_seq = QPushButton("Remove")
        add_seq.clicked.connect(self._add_sequence_event)
        del_seq.clicked.connect(self._remove_sequence_event)
        seq_toolbar.addWidget(add_seq); seq_toolbar.addWidget(del_seq); seq_toolbar.addStretch()
        layout.addLayout(seq_toolbar)
        self._sequence_table = QTableWidget(0, 2)
        self._sequence_table.setHorizontalHeaderLabels(["Time (24-hr)", "Event / Action"])
        self._sequence_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._sequence_table.verticalHeader().setVisible(False)
        self._sequence_table.setFixedHeight(150)
        self._sequence_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._sequence_table)
        layout.addStretch()

        self._tabs.addTab(_scrollable(page), "People & Events")

    # ---- Tab 4: Narrative & Analysis ----------------------------------------
    def _build_tab_narrative(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(_section_label("Incident Narrative"))
        self._narrative = QTextEdit()
        self._narrative.setPlaceholderText(
            "Full description in reporter's own words — include observations, conditions, actions taken, and relevant communications."
        )
        self._narrative.setMinimumHeight(120)
        layout.addWidget(self._narrative)

        layout.addWidget(_divider())
        layout.addWidget(_section_label("Contributing Factors"))

        factor_grid = QHBoxLayout()

        human_box = QGroupBox("Human Factors")
        hf_layout = QVBoxLayout(human_box)
        self._human_checks: dict[str, QCheckBox] = {}
        for f in HUMAN_FACTORS:
            cb = QCheckBox(f)
            self._human_checks[f] = cb
            hf_layout.addWidget(cb)
        self._human_other = QCheckBox("Other:")
        self._human_other_text = QLineEdit()
        self._human_other_text.setPlaceholderText("specify")
        hf_layout.addWidget(self._human_other)
        hf_layout.addWidget(self._human_other_text)

        env_box = QGroupBox("Environmental / Physical")
        ef_layout = QVBoxLayout(env_box)
        self._env_checks: dict[str, QCheckBox] = {}
        for f in ENVIRONMENTAL_FACTORS:
            cb = QCheckBox(f)
            self._env_checks[f] = cb
            ef_layout.addWidget(cb)
        self._env_other = QCheckBox("Other:")
        self._env_other_text = QLineEdit()
        ef_layout.addWidget(self._env_other)
        ef_layout.addWidget(self._env_other_text)

        org_box = QGroupBox("Systems / Organizational")
        of_layout = QVBoxLayout(org_box)
        self._org_checks: dict[str, QCheckBox] = {}
        for f in ORGANIZATIONAL_FACTORS:
            cb = QCheckBox(f)
            self._org_checks[f] = cb
            of_layout.addWidget(cb)
        self._org_other = QCheckBox("Other:")
        self._org_other_text = QLineEdit()
        of_layout.addWidget(self._org_other)
        of_layout.addWidget(self._org_other_text)

        factor_grid.addWidget(human_box)
        factor_grid.addWidget(env_box)
        factor_grid.addWidget(org_box)
        layout.addLayout(factor_grid)

        layout.addWidget(QLabel("Contributing Factor Notes / Root Cause Analysis:"))
        self._factor_notes = QTextEdit()
        self._factor_notes.setFixedHeight(70)
        layout.addWidget(self._factor_notes)

        layout.addWidget(_divider())
        layout.addWidget(_section_label("Immediate Actions & Notifications"))
        layout.addWidget(QLabel("Immediate actions taken at scene:"))
        self._immediate_actions = QTextEdit()
        self._immediate_actions.setFixedHeight(70)
        layout.addWidget(self._immediate_actions)

        layout.addWidget(QLabel("Notifications made:"))
        self._notifications_table = QTableWidget(len(NOTIFICATION_ROLES), 3)
        self._notifications_table.setHorizontalHeaderLabels(["Role", "Notified", "Time"])
        self._notifications_table.verticalHeader().setVisible(False)
        self._notifications_table.setFixedHeight(200)
        self._notif_checks: list[QCheckBox] = []
        self._notif_times: list[QLineEdit] = []
        for row, role in enumerate(NOTIFICATION_ROLES):
            self._notifications_table.setItem(row, 0, QTableWidgetItem(role))
            cb = QCheckBox()
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.setContentsMargins(4, 0, 0, 0)
            cb_layout.addWidget(cb)
            self._notifications_table.setCellWidget(row, 1, cb_widget)
            self._notif_checks.append(cb)
            time_edit = QLineEdit()
            time_edit.setPlaceholderText("HH:MM")
            self._notifications_table.setCellWidget(row, 2, time_edit)
            self._notif_times.append(time_edit)
        layout.addWidget(self._notifications_table)

        layout.addWidget(_divider())
        layout.addWidget(_section_label("Witness Statements"))
        w_toolbar = QHBoxLayout()
        add_w = QPushButton("Add Witness")
        edit_w = QPushButton("Edit")
        del_w = QPushButton("Remove")
        add_w.clicked.connect(self._add_witness)
        edit_w.clicked.connect(self._edit_witness)
        del_w.clicked.connect(self._remove_witness)
        w_toolbar.addWidget(add_w); w_toolbar.addWidget(edit_w); w_toolbar.addWidget(del_w); w_toolbar.addStretch()
        layout.addLayout(w_toolbar)
        self._witnesses_table = QTableWidget(0, 4)
        self._witnesses_table.setHorizontalHeaderLabels(["Name", "Role", "Agency", "Statement"])
        self._witnesses_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._witnesses_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._witnesses_table.verticalHeader().setVisible(False)
        self._witnesses_table.setFixedHeight(120)
        self._witnesses_table.doubleClicked.connect(self._edit_witness)
        layout.addWidget(self._witnesses_table)
        layout.addStretch()

        self._tabs.addTab(_scrollable(page), "Narrative & Analysis")

    # ---- Tab 5: Resolution & Sign-offs --------------------------------------
    def _build_tab_resolution(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        # Corrective Actions
        layout.addWidget(_section_label("Corrective Actions"))
        ca_toolbar = QHBoxLayout()
        add_ca = QPushButton("Add Action")
        edit_ca = QPushButton("Edit")
        del_ca = QPushButton("Remove")
        add_ca.clicked.connect(self._add_corrective_action)
        edit_ca.clicked.connect(self._edit_corrective_action)
        del_ca.clicked.connect(self._remove_corrective_action)
        ca_toolbar.addWidget(add_ca); ca_toolbar.addWidget(edit_ca); ca_toolbar.addWidget(del_ca); ca_toolbar.addStretch()
        layout.addLayout(ca_toolbar)
        self._ca_table = QTableWidget(0, 4)
        self._ca_table.setHorizontalHeaderLabels(["Recommended Action", "Assigned To", "Due Date", "Status"])
        self._ca_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._ca_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._ca_table.verticalHeader().setVisible(False)
        self._ca_table.setFixedHeight(150)
        self._ca_table.horizontalHeader().setStretchLastSection(False)
        self._ca_table.doubleClicked.connect(self._edit_corrective_action)
        layout.addWidget(self._ca_table)

        # Escalation
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Escalation Decision"))
        esc_form = QFormLayout()
        self._escalation = QComboBox()
        self._escalation.addItem("")
        self._escalation.addItems(ESCALATION_OPTIONS)
        esc_form.addRow("Decision", self._escalation)
        layout.addLayout(esc_form)
        layout.addWidget(QLabel("Rationale for escalation decision:"))
        self._escalation_rationale = QTextEdit()
        self._escalation_rationale.setFixedHeight(70)
        layout.addWidget(self._escalation_rationale)

        # Sign-offs — informal acknowledgements
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Command Review & Sign-offs"))
        self._signoff_widgets: dict[str, tuple[QLabel, QLabel, QPushButton]] = {}
        for role_key, role_label in SIGNOFF_ROLES:
            row = QHBoxLayout()
            role_lbl = QLabel(role_label)
            role_lbl.setFixedWidth(200)
            name_lbl = QLabel("—")
            name_lbl.setStyleSheet("color: #555;")
            time_lbl = QLabel("")
            time_lbl.setStyleSheet("color: #555; font-size: 10px;")
            sign_btn = QPushButton("Sign")
            sign_btn.setFixedWidth(60)
            sign_btn.clicked.connect(lambda _, rk=role_key: self._sign_off(rk))
            row.addWidget(role_lbl)
            row.addWidget(name_lbl)
            row.addWidget(time_lbl)
            row.addStretch()
            row.addWidget(sign_btn)
            layout.addLayout(row)
            self._signoff_widgets[role_key] = (name_lbl, time_lbl, sign_btn)

        # Formal approval — Safety Officer + IC via the approval system
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Formal Approval (Safety Officer & IC)"))

        submit_row = QHBoxLayout()
        self._submit_approval_btn = QPushButton("Submit for Approval")
        self._submit_approval_btn.clicked.connect(self._submit_for_approval)
        submit_row.addWidget(self._submit_approval_btn)
        submit_row.addStretch()
        layout.addLayout(submit_row)

        from modules.approvals.panels.approval_timeline import ApprovalTimeline
        self._approval_timeline = ApprovalTimeline()
        self._approval_timeline.sign_requested.connect(self._on_sign_requested)
        layout.addWidget(self._approval_timeline)

        layout.addStretch()

        self._tabs.addTab(_scrollable(page), "Resolution")

    # ---------------------------------------------------------------------- load
    def _load(self) -> None:
        data = services.get_iwi_report(self._incident_id, self._report_id)
        if not data:
            QMessageBox.warning(self, "Load Error", "Could not load report.")
            return
        self._data = data
        self._populate(data)

    def _populate(self, d: dict) -> None:
        fn = d.get("form_number", "")
        self._form_num_lbl.setText(f"Safety Incident Report #{fn}" if fn else "New Report")
        status = d.get("status", "draft")
        self._status_chip.setText(status.replace("_", " ").title())
        chip_color = STATUS_COLORS.get(status, "#546e7a")
        self._status_chip.setStyleSheet(
            f"background: {chip_color}; color: white; border-radius: 10px; padding: 2px 10px; font-weight: 600;"
        )

        # Tab 1
        self._op_period.setValue(int(d.get("op_period") or 1))
        self._date_of_occurrence.setText(d.get("date_of_occurrence") or "")
        self._day_of_event.setValue(int(d.get("day_of_event") or 1))
        self._time_of_occurrence.setText(d.get("time_of_occurrence") or "")
        self._time_reported.setText(d.get("time_reported") or "")
        self._reported_by.setText(d.get("reported_by") or "")
        self._loc_general.setText(d.get("location_general") or "")
        self._loc_zone.setText(d.get("location_zone") or "")
        self._loc_sector.setText(d.get("location_sector") or "")
        self._loc_specific.setText(d.get("location_specific") or "")

        # Tab 2 — classification
        types = d.get("incident_types") or []
        for t, cb in self._type_checks.items():
            cb.setChecked(t in types)
        other = d.get("incident_type_other") or ""
        if other:
            self._type_other_check.setChecked(True)
            self._type_other_text.setText(other)
        combo_set(self._actual_outcome, d.get("actual_outcome") or "")
        sev = d.get("actual_severity") or ""
        for s, btn in self._severity_group.items():
            btn.setChecked(s == sev)
        combo_set(self._activity_impact, d.get("activity_impact") or "")
        self._suspension_ref.setText(d.get("activity_suspension_ref") or "")
        cond = d.get("conditions") or {}
        self._cond_weather.setText(cond.get("weather") or "")
        self._cond_temp.setText(cond.get("temp_heat_index") or "")
        self._cond_wind.setText(cond.get("wind") or "")
        self._cond_visibility.setText(cond.get("visibility") or "")
        self._cond_crowd.setText(cond.get("crowd_density") or "")
        self._cond_lighting.setText(cond.get("lighting") or "")
        self._cond_nws.setText(cond.get("nws_warnings") or "")
        self._cond_other.setText(cond.get("other") or "")

        # Tab 3 — people
        self._persons = list(d.get("persons_involved") or [])
        self._injuries = list(d.get("injury_details") or [])
        self._sequence = list(d.get("sequence_of_events") or [])
        self._refresh_persons_table()
        self._refresh_injuries_table()
        self._refresh_sequence_table()
        eq = d.get("equipment") or {}
        self._eq_desc.setText(eq.get("description") or "")
        self._eq_asset_id.setText(eq.get("asset_id") or "")
        self._eq_owner.setText(eq.get("owner_operator") or "")
        self._eq_condition.setText(eq.get("condition") or "")
        self._eq_last_inspection.setText(eq.get("last_inspection") or "")
        combo_set(self._eq_oos, (eq.get("taken_out_of_service") or "N/A").capitalize())

        # Tab 4 — narrative
        self._narrative.setPlainText(d.get("narrative") or "")
        cf = d.get("contributing_factors") or {}
        for f, cb in self._human_checks.items():
            cb.setChecked(f in (cf.get("human") or []))
        for f, cb in self._env_checks.items():
            cb.setChecked(f in (cf.get("environmental") or []))
        for f, cb in self._org_checks.items():
            cb.setChecked(f in (cf.get("organizational") or []))
        self._factor_notes.setPlainText(cf.get("notes") or "")
        self._immediate_actions.setPlainText(d.get("immediate_actions") or "")
        notifs = {n.get("role"): n for n in (d.get("notifications") or [])}
        for i, role in enumerate(NOTIFICATION_ROLES):
            n = notifs.get(role, {})
            self._notif_checks[i].setChecked(bool(n.get("notified", False)))
            self._notif_times[i].setText(n.get("time") or "")

        # Tab 5 — resolution
        self._corrective_actions = list(d.get("corrective_actions") or [])
        self._refresh_ca_table()
        combo_set(self._escalation, d.get("escalation_decision") or "")
        self._escalation_rationale.setPlainText(d.get("escalation_rationale") or "")
        signoffs = d.get("signoffs") or {}
        for role_key, (name_lbl, time_lbl, sign_btn) in self._signoff_widgets.items():
            so = signoffs.get(role_key)
            if so:
                name_lbl.setText(so.get("name") or "")
                name_lbl.setStyleSheet("color: #2e7d32; font-weight: 600;")
                time_lbl.setText(so.get("signed_at") or "")
                sign_btn.setEnabled(False)
                sign_btn.setText("✓")
            else:
                name_lbl.setText("—")
                name_lbl.setStyleSheet("color: #555;")
                time_lbl.setText("")
                sign_btn.setEnabled(True)
                sign_btn.setText("Sign")
        self._load_approval_state()
        self._witnesses = list(d.get("witnesses") or [])
        self._refresh_witnesses_table()

    # ---------------------------------------------------------------------- save
    def _collect(self) -> dict:
        types = [t for t, cb in self._type_checks.items() if cb.isChecked()]
        if self._type_other_check.isChecked() and self._type_other_text.text().strip():
            types.append("Other")
        severity = next((s for s, btn in self._severity_group.items() if btn.isChecked()), None)
        notifications = [
            {"role": NOTIFICATION_ROLES[i], "notified": self._notif_checks[i].isChecked(), "time": self._notif_times[i].text().strip()}
            for i in range(len(NOTIFICATION_ROLES))
        ]
        human = [f for f, cb in self._human_checks.items() if cb.isChecked()]
        if self._human_other.isChecked() and self._human_other_text.text().strip():
            human.append(self._human_other_text.text().strip())
        env = [f for f, cb in self._env_checks.items() if cb.isChecked()]
        if self._env_other.isChecked() and self._env_other_text.text().strip():
            env.append(self._env_other_text.text().strip())
        org = [f for f, cb in self._org_checks.items() if cb.isChecked()]
        if self._org_other.isChecked() and self._org_other_text.text().strip():
            org.append(self._org_other_text.text().strip())

        return {
            "op_period": self._op_period.value(),
            "date_of_occurrence": self._date_of_occurrence.text().strip(),
            "day_of_event": self._day_of_event.value(),
            "time_of_occurrence": self._time_of_occurrence.text().strip(),
            "time_reported": self._time_reported.text().strip(),
            "reported_by": self._reported_by.text().strip(),
            "location_general": self._loc_general.text().strip(),
            "location_zone": self._loc_zone.text().strip(),
            "location_sector": self._loc_sector.text().strip(),
            "location_specific": self._loc_specific.text().strip(),
            "incident_types": types,
            "incident_type_other": self._type_other_text.text().strip() if self._type_other_check.isChecked() else "",
            "actual_outcome": self._actual_outcome.currentText(),
            "actual_severity": severity or "",
            "activity_impact": self._activity_impact.currentText(),
            "activity_suspension_ref": self._suspension_ref.text().strip(),
            "conditions": {
                "weather": self._cond_weather.text().strip(),
                "temp_heat_index": self._cond_temp.text().strip(),
                "wind": self._cond_wind.text().strip(),
                "visibility": self._cond_visibility.text().strip(),
                "crowd_density": self._cond_crowd.text().strip(),
                "lighting": self._cond_lighting.text().strip(),
                "nws_warnings": self._cond_nws.text().strip(),
                "other": self._cond_other.text().strip(),
            },
            "persons_involved": self._persons,
            "injury_details": self._injuries,
            "equipment": {
                "description": self._eq_desc.text().strip(),
                "asset_id": self._eq_asset_id.text().strip(),
                "owner_operator": self._eq_owner.text().strip(),
                "condition": self._eq_condition.text().strip(),
                "last_inspection": self._eq_last_inspection.text().strip(),
                "taken_out_of_service": self._eq_oos.currentText().lower(),
            },
            "sequence_of_events": self._sequence,
            "narrative": self._narrative.toPlainText().strip(),
            "contributing_factors": {
                "human": human,
                "environmental": env,
                "organizational": org,
                "notes": self._factor_notes.toPlainText().strip(),
            },
            "immediate_actions": self._immediate_actions.toPlainText().strip(),
            "notifications": notifications,
            "corrective_actions": self._corrective_actions,
            "escalation_decision": self._escalation.currentText(),
            "escalation_rationale": self._escalation_rationale.toPlainText().strip(),
            "witnesses": self._witnesses,
            "prepared_by": str(AppState.get_active_user_id() or ""),
        }

    def _save(self) -> None:
        payload = self._collect()
        try:
            if self._report_id:
                updated = services.update_iwi_report(self._incident_id, self._report_id, payload)
            else:
                updated = services.create_iwi_report(self._incident_id, payload)
                self._report_id = updated.get("_id") or updated.get("id")
            self._data = updated
            self._populate(updated)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    # ---------------------------------------------------------------------- sign-off
    def _sign_off(self, role_key: str) -> None:
        if not self._report_id:
            QMessageBox.warning(self, "Save First", "Save the report before signing off.")
            return
        user_id = AppState.get_active_user_id()
        name = str(user_id) if user_id else "Unknown"
        try:
            updated = services.signoff_iwi_report(self._incident_id, self._report_id, role_key, name)
            self._data = updated
            self._populate(updated)
        except Exception as exc:
            QMessageBox.critical(self, "Sign-off Failed", str(exc))

    # ---------------------------------------------------------------------- approval
    def _load_approval_state(self) -> None:
        if not self._report_id:
            return
        try:
            from modules.approvals.service import ApprovalService
            svc = ApprovalService(self._incident_id)
            instance = svc.get("iwi_report", self._report_id)
            personnel_id = str(AppState.get_active_user_id() or "")
            assignment_type = self._resolve_assignment_type()
            if instance:
                self._approval_timeline.set_state(instance, personnel_id, assignment_type)
                self._submit_approval_btn.setEnabled(instance.status == "not_started")
            else:
                self._approval_timeline.set_state(None)
                self._submit_approval_btn.setEnabled(bool(self._report_id))
        except Exception:
            pass

    def _submit_for_approval(self) -> None:
        if not self._report_id:
            QMessageBox.warning(self, "Save First", "Save the report before submitting for approval.")
            return
        try:
            from modules.approvals.service import ApprovalService
            svc = ApprovalService(self._incident_id)
            instance = svc.start("iwi_report", self._report_id)
            personnel_id = str(AppState.get_active_user_id() or "")
            assignment_type = self._resolve_assignment_type()
            self._approval_timeline.set_state(instance, personnel_id, assignment_type)
            self._submit_approval_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "Submission Failed", str(exc))

    def _on_sign_requested(self, step_id: str) -> None:
        if not self._report_id:
            return
        try:
            from modules.approvals.service import ApprovalService
            svc = ApprovalService(self._incident_id)
            instance = svc.get("iwi_report", self._report_id)
            if not instance:
                return
            personnel_id = str(AppState.get_active_user_id() or "")
            assignment_type = self._resolve_assignment_type()
            step = next((s for s in instance.steps if s.step_id == step_id), None)
            role_at_time = (step.resolved_role or step.role) if step else ""
            updated = svc.sign(
                instance,
                step_id=step_id,
                actor_id=personnel_id,
                role_at_time=role_at_time,
                assignment_type=assignment_type or "primary",
                action="approved",
            )
            self._approval_timeline.set_state(updated, personnel_id, assignment_type)
            if updated.status in ("approved", "rejected"):
                self._load()
        except Exception as exc:
            QMessageBox.critical(self, "Sign Failed", str(exc))

    def _resolve_assignment_type(self) -> str:
        """Return the assignment type (primary/deputy/trainee) for the active user, defaulting to 'primary'."""
        try:
            from modules.command.incident_organization.controller import IncidentOrganizationController
            personnel_id = str(AppState.get_active_user_id() or "")
            if not personnel_id:
                return "primary"
            org = IncidentOrganizationController(self._incident_id)
            assignments = org.list_assignments_for_person(personnel_id, active_only=True)
            if assignments:
                return getattr(assignments[0], "assignment_type", "primary") or "primary"
        except Exception:
            pass
        return "primary"

    # ---------------------------------------------------------------------- persons
    def _add_person(self) -> None:
        dlg = PersonDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._persons.append(dlg.result_data())
            self._refresh_persons_table()

    def _edit_person(self) -> None:
        row = self._persons_table.currentRow()
        if row < 0 or row >= len(self._persons):
            return
        dlg = PersonDialog(self, self._persons[row])
        if dlg.exec() == QDialog.Accepted:
            self._persons[row] = dlg.result_data()
            self._refresh_persons_table()

    def _remove_person(self) -> None:
        row = self._persons_table.currentRow()
        if 0 <= row < len(self._persons):
            self._persons.pop(row)
            self._refresh_persons_table()

    def _refresh_persons_table(self) -> None:
        t = self._persons_table
        t.setRowCount(len(self._persons))
        for r, p in enumerate(self._persons):
            t.setItem(r, 0, QTableWidgetItem(p.get("name") or ""))
            t.setItem(r, 1, QTableWidgetItem(p.get("role") or ""))
            t.setItem(r, 2, QTableWidgetItem(p.get("agency") or ""))
            t.setItem(r, 3, QTableWidgetItem(p.get("contact") or ""))
            t.setItem(r, 4, QTableWidgetItem("Yes" if p.get("injury_illness") else "No"))
            t.setItem(r, 5, QTableWidgetItem(p.get("disposition") or ""))
        t.resizeColumnsToContents()

    # ---------------------------------------------------------------------- injuries
    def _add_injury(self) -> None:
        dlg = InjuryDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._injuries.append(dlg.result_data())
            self._refresh_injuries_table()

    def _edit_injury(self) -> None:
        row = self._injuries_table.currentRow()
        if row < 0 or row >= len(self._injuries):
            return
        dlg = InjuryDialog(self, self._injuries[row])
        if dlg.exec() == QDialog.Accepted:
            self._injuries[row] = dlg.result_data()
            self._refresh_injuries_table()

    def _remove_injury(self) -> None:
        row = self._injuries_table.currentRow()
        if 0 <= row < len(self._injuries):
            self._injuries.pop(row)
            self._refresh_injuries_table()

    def _refresh_injuries_table(self) -> None:
        t = self._injuries_table
        t.setRowCount(len(self._injuries))
        for r, i in enumerate(self._injuries):
            t.setItem(r, 0, QTableWidgetItem(i.get("person_name") or ""))
            t.setItem(r, 1, QTableWidgetItem(i.get("nature") or ""))
            t.setItem(r, 2, QTableWidgetItem(i.get("body_part") or ""))
            t.setItem(r, 3, QTableWidgetItem(i.get("treatment") or ""))
            t.setItem(r, 4, QTableWidgetItem("Yes" if i.get("ems_involved") else "No"))
        t.resizeColumnsToContents()

    # ---------------------------------------------------------------------- sequence
    def _add_sequence_event(self) -> None:
        row = self._sequence_table.rowCount()
        self._sequence_table.insertRow(row)
        self._sequence_table.setItem(row, 0, QTableWidgetItem(""))
        self._sequence_table.setItem(row, 1, QTableWidgetItem(""))
        self._sequence.append({"time": "", "action": ""})
        self._sequence_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self._sequence_table.editItem(self._sequence_table.item(row, 0))

    def _remove_sequence_event(self) -> None:
        row = self._sequence_table.currentRow()
        if 0 <= row < len(self._sequence):
            self._sequence.pop(row)
            self._sequence_table.removeRow(row)

    def _refresh_sequence_table(self) -> None:
        t = self._sequence_table
        t.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        t.setRowCount(len(self._sequence))
        for r, s in enumerate(self._sequence):
            t.setItem(r, 0, QTableWidgetItem(s.get("time") or ""))
            t.setItem(r, 1, QTableWidgetItem(s.get("action") or ""))

    def _sync_sequence(self) -> None:
        t = self._sequence_table
        self._sequence = []
        for r in range(t.rowCount()):
            time_item = t.item(r, 0)
            action_item = t.item(r, 1)
            self._sequence.append({
                "time": time_item.text() if time_item else "",
                "action": action_item.text() if action_item else "",
            })

    # ---------------------------------------------------------------------- corrective actions
    def _add_corrective_action(self) -> None:
        dlg = CorrectiveActionDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._corrective_actions.append(dlg.result_data())
            self._refresh_ca_table()

    def _edit_corrective_action(self) -> None:
        row = self._ca_table.currentRow()
        if row < 0 or row >= len(self._corrective_actions):
            return
        dlg = CorrectiveActionDialog(self, self._corrective_actions[row])
        if dlg.exec() == QDialog.Accepted:
            self._corrective_actions[row] = dlg.result_data()
            self._refresh_ca_table()

    def _remove_corrective_action(self) -> None:
        row = self._ca_table.currentRow()
        if 0 <= row < len(self._corrective_actions):
            self._corrective_actions.pop(row)
            self._refresh_ca_table()

    def _refresh_ca_table(self) -> None:
        t = self._ca_table
        t.setRowCount(len(self._corrective_actions))
        for r, ca in enumerate(self._corrective_actions):
            t.setItem(r, 0, QTableWidgetItem(ca.get("action") or ""))
            t.setItem(r, 1, QTableWidgetItem(ca.get("assigned_to") or ""))
            t.setItem(r, 2, QTableWidgetItem(ca.get("due_date") or ""))
            status = ca.get("status", "open")
            status_item = QTableWidgetItem(status.title())
            if status == "done":
                status_item.setForeground(Qt.darkGreen)
            t.setItem(r, 3, status_item)
        t.resizeColumnsToContents()

    # ---------------------------------------------------------------------- witnesses
    def _add_witness(self) -> None:
        dlg = WitnessDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._witnesses.append(dlg.result_data())
            self._refresh_witnesses_table()

    def _edit_witness(self) -> None:
        row = self._witnesses_table.currentRow()
        if row < 0 or row >= len(self._witnesses):
            return
        dlg = WitnessDialog(self, self._witnesses[row])
        if dlg.exec() == QDialog.Accepted:
            self._witnesses[row] = dlg.result_data()
            self._refresh_witnesses_table()

    def _remove_witness(self) -> None:
        row = self._witnesses_table.currentRow()
        if 0 <= row < len(self._witnesses):
            self._witnesses.pop(row)
            self._refresh_witnesses_table()

    def _refresh_witnesses_table(self) -> None:
        t = self._witnesses_table
        t.setRowCount(len(self._witnesses))
        for r, w in enumerate(self._witnesses):
            t.setItem(r, 0, QTableWidgetItem(w.get("full_name") or ""))
            t.setItem(r, 1, QTableWidgetItem(w.get("position_role") or ""))
            t.setItem(r, 2, QTableWidgetItem(w.get("agency") or ""))
            stmt = w.get("statement") or ""
            t.setItem(r, 3, QTableWidgetItem(stmt[:60] + "…" if len(stmt) > 60 else stmt))
        t.resizeColumnsToContents()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def combo_set(combo: QComboBox, value: str) -> None:
    idx = combo.findText(value)
    combo.setCurrentIndex(idx if idx >= 0 else 0)
