"""SubjectsTab — table view for Intel subjects."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout, QTextEdit,
    QDialogButtonBox, QScrollArea, QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from modules.intel.models.subjects import Subject, SUBJECT_TYPES, SubjectType
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior

# Row tint colors (ARGB — semi-transparent so text stays readable)
_ROW_COLORS: dict[str, QColor] = {
    "missing":  QColor(180, 40,  40,  120),
    "located":  QColor(40,  160, 80,  100),
    "deceased": QColor(100, 100, 100, 90),
}


def _row_color(subject: Subject) -> QColor | None:
    if subject.subject_type == SubjectType.MISSING_PERSON:
        return _ROW_COLORS["missing"]
    if (subject.status or "").lower() == "located":
        return _ROW_COLORS["located"]
    if (subject.status or "").lower() == "deceased":
        return _ROW_COLORS["deceased"]
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
    def __init__(
        self,
        parent: QWidget | None = None,
        quick: bool = False,
        subject_type: str = SubjectType.MISSING_PERSON,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Capture" if quick else "Full Subject Profile")
        self.setMinimumWidth(560)
        self.subject: Subject | None = None
        self._quick = quick
        self._subject_type = subject_type

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(8)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Name or temporary identifier")
        form.addRow("Name *", self._name)

        self._type = QComboBox()
        self._type.addItems(SUBJECT_TYPES)
        self._type.setCurrentText(subject_type)
        self._type.currentTextChanged.connect(self._update_subject_form)
        form.addRow("Type", self._type)

        self._status = QComboBox()
        self._status.addItems(["Active", "Located", "Deceased", "Archived"])
        form.addRow("Status", self._status)

        self._age = QLineEdit()
        self._age.setPlaceholderText("Estimated or exact age")
        form.addRow("Age", self._age)

        self._sex = QLineEdit()
        form.addRow("Sex", self._sex)

        self._dob = QLineEdit()
        self._dob.setPlaceholderText("YYYY-MM-DD")
        form.addRow("DOB", self._dob)

        self._phone = QLineEdit()
        self._email = QLineEdit()
        self._address = QLineEdit()
        form.addRow("Phone", self._phone)
        form.addRow("Email", self._email)
        form.addRow("Address", self._address)

        self._notes = QTextEdit()
        self._notes.setFixedHeight(56)
        form.addRow("Notes", self._notes)

        self._shared_box = None
        self._patient_box = None

        if not quick:
            self._shared_box = QGroupBox("Profile Details")
            shared_form = QFormLayout(self._shared_box)
            shared_form.setSpacing(6)

            self._description = QTextEdit()
            self._description.setFixedHeight(60)
            shared_form.addRow("Description", self._description)

            self._relationship_to_incident = QLineEdit()
            shared_form.addRow("Relationship to Incident", self._relationship_to_incident)

            self._medical = QTextEdit()
            self._medical.setFixedHeight(56)
            shared_form.addRow("Medical Conditions", self._medical)

            self._organization = QLineEdit()
            shared_form.addRow("Organization", self._organization)

            outer.addWidget(self._shared_box)

            self._patient_box = QGroupBox("Patient Care")
            patient_form = QFormLayout(self._patient_box)
            patient_form.setSpacing(6)
            self._treatment_given = QTextEdit()
            self._treatment_given.setFixedHeight(60)
            self._transport_required = QLineEdit()
            self._transport_method = QLineEdit()
            self._transport_destination = QLineEdit()
            self._disposition = QLineEdit()
            patient_form.addRow("Treatment Given", self._treatment_given)
            patient_form.addRow("Transport Required", self._transport_required)
            patient_form.addRow("Transport Method", self._transport_method)
            patient_form.addRow("Transport Destination", self._transport_destination)
            patient_form.addRow("Disposition", self._disposition)
            self._patient_box.setVisible(subject_type == SubjectType.PATIENT)
            outer.addWidget(self._patient_box)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _set_subject_type(self, subject_type: str) -> None:
        self._type.setCurrentText(subject_type)
        self._quick = subject_type == SubjectType.MISSING_PERSON
        self._update_subject_form(subject_type)

    def _update_subject_form(self, subject_type: str) -> None:
        if self._patient_box is not None:
            self._patient_box.setVisible(subject_type == SubjectType.PATIENT and not self._quick)

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            return
        age_text = self._age.text().strip()
        self.subject = Subject(
            id="",
            incident_id="",
            subject_type=self._type.currentText(),
            name=name,
            status=self._status.currentText(),
            age=int(age_text) if age_text.isdigit() else None,
            sex=self._sex.text().strip() or None,
            dob=self._dob.text().strip() or None,
            phone=self._phone.text().strip() or None,
            email=self._email.text().strip() or None,
            address=self._address.text().strip() or None,
            notes=self._notes.toPlainText().strip() or None,
        )
        if not self._quick:
            self.subject.description = self._description.toPlainText().strip() or None
            self.subject.relationship_to_incident = self._relationship_to_incident.text().strip() or None
            self.subject.medical_conditions = self._medical.toPlainText().strip() or None
            self.subject.organization = self._organization.text().strip() or None
            if self.subject.subject_type == SubjectType.PATIENT:
                self.subject.treatment_given = self._treatment_given.toPlainText().strip() or None
                self.subject.transport_required = self._transport_required.text().strip() or None
                self.subject.transport_method = self._transport_method.text().strip() or None
                self.subject.transport_destination = self._transport_destination.text().strip() or None
                self.subject.disposition = self._disposition.text().strip() or None
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
        legend = QLabel(
            "  ".join([
                _color_blob("#b42828", "Missing Person"),
                _color_blob("#28a050", "Located"),
                _color_blob("#646464", "Deceased"),
            ])
        )
        legend.setTextFormat(Qt.RichText)
        legend.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
        layout.addWidget(legend)

        self.refresh()

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
            color = _row_color(s)
            brush = QBrush(color) if color else None
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
        dlg = _NewSubjectDialog(
            self,
            quick=subject_type != SubjectType.PATIENT,
            subject_type=subject_type,
        )
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
