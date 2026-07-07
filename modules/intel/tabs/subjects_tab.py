"""SubjectsTab — table view for Intel subjects."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout, QTextEdit,
    QDialogButtonBox, QScrollArea, QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush

from modules.intel.models.subjects import Subject, SUBJECT_TYPES, SubjectType
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import intel_subject_status_colors, subscribe_theme


def _row_color(subject: Subject) -> QBrush | None:
    colors = intel_subject_status_colors()
    if subject.subject_type == SubjectType.MISSING_PERSON:
        return colors["missing"]["bg"]
    status = (subject.status or "").lower()
    if status in colors:
        return colors[status]["bg"]
    return None


def _action_btn(label: str, callback) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(22)
    btn.setFixedWidth(52)
    btn.clicked.connect(callback)
    return btn


def _color_blob(hex_color: str, label: str) -> str:
    return (
        f'<span style="color: {hex_color}; font-size: 16px; vertical-align: middle;">&#9679;</span> '
        f'<span style="vertical-align: middle;">{label}</span>'
    )


def _mode_btn(label: str, callback, primary: bool = False) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(28)
    if primary:
        btn.setStyleSheet("font-weight: 700;")
    btn.clicked.connect(callback)
    return btn


class _NewSubjectDialog(QDialog):
    _PERSON_TYPES = frozenset({
        SubjectType.MISSING_PERSON, SubjectType.WITNESS,
        SubjectType.REPORTING_PARTY, SubjectType.CONTACT, SubjectType.PATIENT,
    })

    def __init__(
        self,
        parent: QWidget | None = None,
        quick: bool = False,
        subject_type: str = SubjectType.MISSING_PERSON,
    ) -> None:
        super().__init__(parent)
        self._quick = quick
        self.subject: Subject | None = None
        is_mp_quick = quick and subject_type == SubjectType.MISSING_PERSON
        self.setWindowTitle("Quick Capture" if is_mp_quick else f"New {subject_type} Profile")
        self.setMinimumWidth(580)

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        vbox = QVBoxLayout(inner)
        vbox.setSpacing(8)

        # --- Common: name / type / status ---
        common_box = QGroupBox("Basic Information")
        cf = QFormLayout(common_box)
        cf.setSpacing(8)
        self._name = QLineEdit()
        self._name.setPlaceholderText("Name or identifier")
        cf.addRow("Name *", self._name)
        self._type = QComboBox()
        self._type.addItems(SUBJECT_TYPES)
        cf.addRow("Type", self._type)
        self._status = QComboBox()
        self._status.addItems(["Active", "Located", "Deceased", "Archived"])
        cf.addRow("Status", self._status)
        vbox.addWidget(common_box)

        # --- Identity (Missing Person + Patient) ---
        self._identity_box = QGroupBox("Identity")
        idf = QFormLayout(self._identity_box)
        idf.setSpacing(6)
        self._age = QLineEdit()
        self._age.setPlaceholderText("Estimated or exact")
        self._sex = QLineEdit()
        self._dob = QLineEdit()
        self._dob.setPlaceholderText("YYYY-MM-DD")
        idf.addRow("Age", self._age)
        idf.addRow("Sex", self._sex)
        idf.addRow("DOB", self._dob)
        self._race = QLineEdit()
        self._height_edit = QLineEdit()
        self._weight_edit = QLineEdit()
        self._hair_color = QLineEdit()
        self._eye_color = QLineEdit()
        self._distinguishing = QTextEdit()
        self._distinguishing.setFixedHeight(48)
        idf.addRow("Race", self._race)
        idf.addRow("Height", self._height_edit)
        idf.addRow("Weight", self._weight_edit)
        idf.addRow("Hair Color", self._hair_color)
        idf.addRow("Eye Color", self._eye_color)
        idf.addRow("Distinguishing Features", self._distinguishing)
        vbox.addWidget(self._identity_box)

        # --- Contact info (all person-type subjects) ---
        self._contact_box = QGroupBox("Contact Information")
        ctf = QFormLayout(self._contact_box)
        ctf.setSpacing(6)
        self._phone = QLineEdit()
        self._email = QLineEdit()
        self._address = QLineEdit()
        self._organization = QLineEdit()
        self._relationship = QLineEdit()
        ctf.addRow("Phone", self._phone)
        ctf.addRow("Email", self._email)
        ctf.addRow("Address", self._address)
        ctf.addRow("Organization", self._organization)
        ctf.addRow("Relationship to Incident", self._relationship)
        vbox.addWidget(self._contact_box)

        # --- SAR Details (Missing Person) ---
        self._sar_box = QGroupBox("SAR Details")
        sarf = QFormLayout(self._sar_box)
        sarf.setSpacing(6)
        self._lkp_place = QLineEdit()
        self._lkp_time = QLineEdit()
        self._lkp_time.setPlaceholderText("YYYY-MM-DD HH:MM")
        self._clothing = QTextEdit()
        self._clothing.setFixedHeight(48)
        sarf.addRow("LKP Place", self._lkp_place)
        sarf.addRow("LKP Time", self._lkp_time)
        sarf.addRow("Clothing", self._clothing)
        if not quick:
            self._pls_place = QLineEdit()
            self._pls_time_edit = QLineEdit()
            self._pls_time_edit.setPlaceholderText("YYYY-MM-DD HH:MM")
            self._equipment = QTextEdit()
            self._equipment.setFixedHeight(48)
            self._vehicle_desc = QLineEdit()
            self._outdoor_exp = QLineEdit()
            self._behavioral = QTextEdit()
            self._behavioral.setFixedHeight(48)
            self._communication = QLineEdit()
            self._sensory = QLineEdit()
            self._routine = QTextEdit()
            self._routine.setFixedHeight(48)
            self._wandering = QLineEdit()
            self._favorites = QLineEdit()
            self._triggers = QLineEdit()
            self._recent_changes = QLineEdit()
            self._medical_mp = QTextEdit()
            self._medical_mp.setFixedHeight(48)
            self._medications_mp = QLineEdit()
            self._mobility = QLineEdit()
            sarf.addRow("PLS Place", self._pls_place)
            sarf.addRow("PLS Time", self._pls_time_edit)
            sarf.addRow("Equipment", self._equipment)
            sarf.addRow("Vehicle Description", self._vehicle_desc)
            sarf.addRow("Outdoor Experience", self._outdoor_exp)
            sarf.addRow("Behavioral Notes", self._behavioral)
            sarf.addRow("Communication Needs", self._communication)
            sarf.addRow("Sensory Considerations", self._sensory)
            sarf.addRow("Routine Habits", self._routine)
            sarf.addRow("Wandering History", self._wandering)
            sarf.addRow("Favorite Places", self._favorites)
            sarf.addRow("Triggers/Stressors", self._triggers)
            sarf.addRow("Recent Changes", self._recent_changes)
            sarf.addRow("Medical Conditions", self._medical_mp)
            sarf.addRow("Medications", self._medications_mp)
            sarf.addRow("Mobility Limitations", self._mobility)
        else:
            self._pls_place = self._pls_time_edit = self._equipment = None
            self._vehicle_desc = self._outdoor_exp = self._behavioral = None
            self._communication = self._sensory = self._routine = None
            self._wandering = self._favorites = self._triggers = None
            self._recent_changes = self._medical_mp = self._medications_mp = None
            self._mobility = None
        vbox.addWidget(self._sar_box)

        # --- Patient Care ---
        self._patient_box = QGroupBox("Patient Care")
        patf = QFormLayout(self._patient_box)
        patf.setSpacing(6)
        self._medical = QTextEdit()
        self._medical.setFixedHeight(48)
        self._medications = QLineEdit()
        self._treatment = QTextEdit()
        self._treatment.setFixedHeight(48)
        self._transport_req = QLineEdit()
        self._transport_method = QLineEdit()
        self._transport_dest = QLineEdit()
        self._disposition = QLineEdit()
        patf.addRow("Medical Conditions", self._medical)
        patf.addRow("Medications", self._medications)
        patf.addRow("Treatment Given", self._treatment)
        patf.addRow("Transport Required", self._transport_req)
        patf.addRow("Transport Method", self._transport_method)
        patf.addRow("Transport Destination", self._transport_dest)
        patf.addRow("Disposition", self._disposition)
        vbox.addWidget(self._patient_box)

        # --- Vehicle Details ---
        self._vehicle_box = QGroupBox("Vehicle Details")
        vehf = QFormLayout(self._vehicle_box)
        vehf.setSpacing(6)
        self._make = QLineEdit()
        self._model_edit = QLineEdit()
        self._year_edit = QLineEdit()
        self._year_edit.setPlaceholderText("e.g. 2019")
        self._color_edit = QLineEdit()
        self._plate = QLineEdit()
        self._plate_state = QLineEdit()
        self._vin = QLineEdit()
        self._owner_op = QLineEdit()
        self._veh_description = QTextEdit()
        self._veh_description.setFixedHeight(48)
        vehf.addRow("Make", self._make)
        vehf.addRow("Model", self._model_edit)
        vehf.addRow("Year", self._year_edit)
        vehf.addRow("Color", self._color_edit)
        vehf.addRow("License Plate", self._plate)
        vehf.addRow("Plate State", self._plate_state)
        vehf.addRow("VIN", self._vin)
        vehf.addRow("Owner/Operator", self._owner_op)
        vehf.addRow("Description", self._veh_description)
        vbox.addWidget(self._vehicle_box)

        # --- Aircraft Details ---
        self._aircraft_box = QGroupBox("Aircraft Details")
        acrf = QFormLayout(self._aircraft_box)
        acrf.setSpacing(6)
        self._tail_number = QLineEdit()
        self._aircraft_type_edit = QLineEdit()
        self._make_model = QLineEdit()
        self._color_markings = QLineEdit()
        self._pilot_op = QLineEdit()
        self._departure = QLineEdit()
        self._destination_edit = QLineEdit()
        self._occupants_edit = QLineEdit()
        self._fuel_endurance = QLineEdit()
        self._elt_gear = QLineEdit()
        self._route_contact = QTextEdit()
        self._route_contact.setFixedHeight(48)
        self._remarks = QTextEdit()
        self._remarks.setFixedHeight(48)
        acrf.addRow("Tail Number", self._tail_number)
        acrf.addRow("Aircraft Type", self._aircraft_type_edit)
        acrf.addRow("Make/Model", self._make_model)
        acrf.addRow("Color/Markings", self._color_markings)
        acrf.addRow("Pilot/Operator", self._pilot_op)
        acrf.addRow("Departure Point", self._departure)
        acrf.addRow("Destination", self._destination_edit)
        acrf.addRow("Occupants", self._occupants_edit)
        acrf.addRow("Fuel Endurance", self._fuel_endurance)
        acrf.addRow("ELT/Survival Gear", self._elt_gear)
        acrf.addRow("Route/Last Contact", self._route_contact)
        acrf.addRow("Remarks", self._remarks)
        vbox.addWidget(self._aircraft_box)

        # --- Notes (always shown) ---
        notes_box = QGroupBox("Notes")
        nf = QFormLayout(notes_box)
        nf.setSpacing(6)
        self._notes = QTextEdit()
        self._notes.setFixedHeight(56)
        nf.addRow("", self._notes)
        vbox.addWidget(notes_box)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._type.currentTextChanged.connect(self._update_subject_form)
        self._type.setCurrentText(subject_type)
        self._update_subject_form(subject_type)

    def _update_subject_form(self, subject_type: str) -> None:
        is_missing = subject_type == SubjectType.MISSING_PERSON
        is_patient = subject_type == SubjectType.PATIENT
        is_person = subject_type in self._PERSON_TYPES
        is_vehicle = subject_type == SubjectType.VEHICLE
        is_aircraft = subject_type == SubjectType.AIRCRAFT

        _name_hints = {
            SubjectType.VEHICLE: "Vehicle identifier (e.g. Blue Ford F-150)",
            SubjectType.AIRCRAFT: "Aircraft identifier (e.g. N12345 Cessna 172)",
        }
        self._name.setPlaceholderText(_name_hints.get(subject_type, "Name or temporary identifier"))

        # Identity: Missing Person and Patient have age/sex/DOB/physical details
        self._identity_box.setVisible(is_missing or is_patient)
        # Contact block: all person-type subjects
        self._contact_box.setVisible(is_person)
        self._sar_box.setVisible(is_missing)
        self._patient_box.setVisible(is_patient)
        self._vehicle_box.setVisible(is_vehicle)
        self._aircraft_box.setVisible(is_aircraft)

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            return

        subject_type = self._type.currentText()
        is_missing = subject_type == SubjectType.MISSING_PERSON
        is_patient = subject_type == SubjectType.PATIENT
        is_person = subject_type in self._PERSON_TYPES
        is_vehicle = subject_type == SubjectType.VEHICLE
        is_aircraft = subject_type == SubjectType.AIRCRAFT
        has_identity = is_missing or is_patient

        def _t(w: QLineEdit | None) -> str | None:
            return (w.text().strip() or None) if w is not None else None

        def _p(w: QTextEdit | None) -> str | None:
            return (w.toPlainText().strip() or None) if w is not None else None

        def _int(w: QLineEdit | None) -> int | None:
            if w is None:
                return None
            v = w.text().strip()
            return int(v) if v.isdigit() else None

        age_text = self._age.text().strip() if has_identity else ""
        self.subject = Subject(
            id="",
            incident_id="",
            subject_type=subject_type,
            name=name,
            status=self._status.currentText(),
            # Identity
            age=int(age_text) if age_text.isdigit() else None,
            sex=_t(self._sex) if has_identity else None,
            dob=_t(self._dob) if has_identity else None,
            race=_t(self._race) if has_identity else None,
            height=_t(self._height_edit) if has_identity else None,
            weight=_t(self._weight_edit) if has_identity else None,
            hair_color=_t(self._hair_color) if has_identity else None,
            eye_color=_t(self._eye_color) if has_identity else None,
            distinguishing_features=_p(self._distinguishing) if has_identity else None,
            # Contact
            phone=_t(self._phone) if is_person else None,
            email=_t(self._email) if is_person else None,
            address=_t(self._address) if is_person else None,
            organization=_t(self._organization) if is_person else None,
            relationship_to_incident=_t(self._relationship) if is_person else None,
            # SAR
            lkp_place=_t(self._lkp_place) if is_missing else None,
            lkp_time=_t(self._lkp_time) if is_missing else None,
            clothing_description=_p(self._clothing) if is_missing else None,
            pls_place=_t(self._pls_place) if is_missing else None,
            pls_time=_t(self._pls_time_edit) if is_missing else None,
            equipment_description=_p(self._equipment) if is_missing else None,
            vehicle_description=_t(self._vehicle_desc) if is_missing else None,
            outdoor_experience=_t(self._outdoor_exp) if is_missing else None,
            behavioral_notes=_p(self._behavioral) if is_missing else None,
            communication_needs=_t(self._communication) if is_missing else None,
            sensory_considerations=_t(self._sensory) if is_missing else None,
            routine_habits=_p(self._routine) if is_missing else None,
            wandering_history=_t(self._wandering) if is_missing else None,
            favorite_places=_t(self._favorites) if is_missing else None,
            triggers_or_stressors=_t(self._triggers) if is_missing else None,
            recent_changes=_t(self._recent_changes) if is_missing else None,
            medical_conditions=_p(self._medical_mp) if is_missing else (
                _p(self._medical) if is_patient else None
            ),
            medications=_t(self._medications_mp) if is_missing else (
                _t(self._medications) if is_patient else None
            ),
            mobility_limitations=_t(self._mobility) if is_missing else None,
            # Patient care
            treatment_given=_p(self._treatment) if is_patient else None,
            transport_required=_t(self._transport_req) if is_patient else None,
            transport_method=_t(self._transport_method) if is_patient else None,
            transport_destination=_t(self._transport_dest) if is_patient else None,
            disposition=_t(self._disposition) if is_patient else None,
            # Vehicle
            make=_t(self._make) if is_vehicle else None,
            model=_t(self._model_edit) if is_vehicle else None,
            year=_int(self._year_edit) if is_vehicle else None,
            color=_t(self._color_edit) if is_vehicle else None,
            plate=_t(self._plate) if is_vehicle else None,
            plate_state=_t(self._plate_state) if is_vehicle else None,
            vin=_t(self._vin) if is_vehicle else None,
            owner_or_operator=_t(self._owner_op) if is_vehicle else None,
            description=_p(self._veh_description) if is_vehicle else None,
            # Aircraft
            tail_number=_t(self._tail_number) if is_aircraft else None,
            aircraft_type=_t(self._aircraft_type_edit) if is_aircraft else None,
            make_model=_t(self._make_model) if is_aircraft else None,
            color_markings=_t(self._color_markings) if is_aircraft else None,
            pilot_or_operator=_t(self._pilot_op) if is_aircraft else None,
            departure_point=_t(self._departure) if is_aircraft else None,
            destination=_t(self._destination_edit) if is_aircraft else None,
            occupants=_t(self._occupants_edit) if is_aircraft else None,
            fuel_endurance=_t(self._fuel_endurance) if is_aircraft else None,
            elt_survival_gear=_t(self._elt_gear) if is_aircraft else None,
            route_or_last_contact=_p(self._route_contact) if is_aircraft else None,
            remarks=_p(self._remarks) if is_aircraft else None,
            notes=_p(self._notes),
        )
        self.accept()


class SubjectsTab(QWidget):
    open_subject_detail = Signal(object)
    create_subject_requested = Signal()

    _COLS = ["#", "Name", "Type", "Status", "LKP / Context", "Age", "Updated", "Actions"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._subjects: list[Subject] = []
        self._filtered: list[Subject] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Subjects")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        self._type_filter = QComboBox()
        self._type_filter.addItem("All Types")
        self._type_filter.addItems(SUBJECT_TYPES)
        self._type_filter.currentTextChanged.connect(self._apply_filter)

        self._status_filter = QComboBox()
        self._status_filter.addItems(["All Statuses", "Active", "Located", "Deceased", "Archived"])
        self._status_filter.currentTextChanged.connect(self._apply_filter)

        profile_box = QGroupBox("Create Profiles")
        profile_box.setStyleSheet("QGroupBox { font-weight: 700; }")
        btn_row = QHBoxLayout(profile_box)
        btn_row.setContentsMargins(10, 16, 10, 8)
        btn_row.setSpacing(6)
        btn_row.addWidget(_mode_btn("Missing Person - Quick", self._quick_capture, primary=True))
        btn_row.addWidget(_mode_btn("Missing Person - Full", self._full_profile))
        btn_row.addWidget(_mode_btn("Witness", lambda: self._create_subject_type(SubjectType.WITNESS)))
        btn_row.addWidget(_mode_btn("Reporting Party", lambda: self._create_subject_type(SubjectType.REPORTING_PARTY)))
        btn_row.addWidget(_mode_btn("Contact", lambda: self._create_subject_type(SubjectType.CONTACT)))
        btn_row.addWidget(_mode_btn("Patient", lambda: self._create_subject_type(SubjectType.PATIENT)))
        btn_row.addWidget(_mode_btn("Vehicle", lambda: self._create_subject_type(SubjectType.VEHICLE)))
        btn_row.addWidget(_mode_btn("Aircraft", lambda: self._create_subject_type(SubjectType.AIRCRAFT)))
        btn_row.addStretch()

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._type_filter)
        toolbar.addWidget(self._status_filter)
        layout.addLayout(toolbar)
        layout.addWidget(profile_box)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        apply_statusboard_table_behavior(self._table)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)
        self._legend = QLabel()
        self._legend.setTextFormat(Qt.RichText)
        self._legend.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
        layout.addWidget(self._legend)
        self._update_legend()

        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def _update_legend(self) -> None:
        status_colors = intel_subject_status_colors()
        self._legend.setText(
            "  ".join([
                _color_blob(status_colors["missing"]["fg"].color().name(), "Missing Person"),
                _color_blob(status_colors["located"]["fg"].color().name(), "Located"),
                _color_blob(status_colors["deceased"]["fg"].color().name(), "Deceased"),
            ])
        )

    def _on_theme_changed(self, *_: object) -> None:
        self._update_legend()
        self._render()

    def refresh(self) -> None:
        if self._service is None:
            return
        self._subjects = self._service.subjects.list()
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        type_sel = self._type_filter.currentText()
        status_sel = self._status_filter.currentText()
        self._filtered = [
            s for s in self._subjects
            if (not q or q in (s.name or "").lower() or q in (s.lkp_place or "").lower())
            and (type_sel == "All Types" or s.subject_type == type_sel)
            and (status_sel == "All Statuses" or s.status == status_sel)
        ]
        self._render()

    def _render(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered))
        for row, s in enumerate(self._filtered):
            context = ""
            if s.subject_type == SubjectType.MISSING_PERSON and s.lkp_place:
                context = f"LKP: {s.lkp_place}"
            elif s.phone:
                context = s.phone
            elif s.organization:
                context = s.organization

            cells = [
                str(row + 1), s.name or "", s.subject_type or "", s.status or "",
                context, str(s.age) if s.age else "",
                s.updated_at[:16].replace("T", " ") if s.updated_at else "",
            ]
            brush = _row_color(s)
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if brush:
                    item.setBackground(brush)
                self._table.setItem(row, col, item)

            # Actions widget
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)
            subject = s  # capture
            al.addWidget(_action_btn("View", lambda _, x=subject: self.open_subject_detail.emit(x)))
            self._table.setCellWidget(row, len(self._COLS) - 1, actions)
            self._table.setRowHeight(row, 30)

        for col in (0, 2, 3, 5, 6):
            self._table.resizeColumnToContents(col)
        self._table.setColumnWidth(len(self._COLS) - 1, 70)
        self._table.setSortingEnabled(True)

    def _on_double_click(self, index) -> None:
        col = index.column()
        row = index.row()
        if col < len(self._COLS) - 1 and 0 <= row < len(self._filtered):
            self.open_subject_detail.emit(self._filtered[row])

    def _quick_capture(self) -> None:
        self._create_subject(quick=True)

    def _full_profile(self) -> None:
        self._create_subject(quick=False)

    def _create_subject_type(self, subject_type: str) -> None:
        if self._service is None:
            return
        dlg = _NewSubjectDialog(self, quick=False, subject_type=subject_type)
        if dlg.exec() == QDialog.Accepted and dlg.subject:
            dlg.subject.incident_id = self._service.incident_id or ""
            dlg.subject.subject_type = subject_type
            created = self._service.subjects.create(dlg.subject)
            if created:
                self.refresh()
                self.open_subject_detail.emit(created)

    def _delete_profile(self, subject: Subject) -> None:
        if self._service is None:
            return
        from PySide6.QtWidgets import QMessageBox
        confirm = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile for {subject.name}?\n\nThis will archive the subject record.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes and self._service.subjects.archive(subject.id):
            self.refresh()

    def _create_subject(self, quick: bool) -> None:
        if self._service is None:
            return
        dlg = _NewSubjectDialog(self, quick=quick)
        if dlg.exec() == QDialog.Accepted and dlg.subject:
            dlg.subject.incident_id = self._service.incident_id or ""
            created = self._service.subjects.create(dlg.subject)
            if created:
                self.refresh()
                self.open_subject_detail.emit(created)
