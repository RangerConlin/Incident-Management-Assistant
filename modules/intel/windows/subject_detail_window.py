"""SubjectDetailWindow — modeless standalone window for a single Subject record.

Opens independently; multiple detail windows can be open simultaneously.
The layout adapts based on subject_type — Missing Persons get the full SAR
profile while other types show a simplified view.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QScrollArea, QFrame, QSizePolicy, QDialog,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal

from modules.intel.models.subjects import Subject, SubjectType, SUBJECT_TYPES
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.services.intel_service import IntelService


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


class _EditSubjectDialog(QDialog):
    """Dialog for editing a Subject record."""

    def __init__(self, subject: Subject, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Subject — {subject.name}")
        self.setMinimumWidth(500)
        self._subject = subject
        self.updated_subject: Subject | None = None

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(8)

        self._name = QLineEdit(subject.name)
        form.addRow("Name *", self._name)

        self._type = QComboBox()
        self._type.addItems(SUBJECT_TYPES)
        self._type.setCurrentText(subject.subject_type)
        form.addRow("Type", self._type)

        self._status = QComboBox()
        self._status.addItems(["Active", "Located", "Deceased", "Archived"])
        self._status.setCurrentText(subject.status)
        form.addRow("Status", self._status)

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
        s.phone = self._phone.text().strip() or None
        s.email = self._email.text().strip() or None
        s.dob = self._dob.text().strip() or None
        s.lkp_place = self._lkp_place.text().strip() or None
        s.pls_place = self._pls_place.text().strip() or None
        s.clothing_description = self._clothing.text().strip() or None
        s.medical_conditions = self._medical.toPlainText().strip() or None
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
        self.resize(720, 560)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = self._build_header()
        root.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._tabs.addTab(self._build_timeline_tab(), "Timeline")
        self._tabs.addTab(self._build_links_tab(), "Linked Records")
        self._tabs.addTab(QWidget(), "Files")
        self._tabs.addTab(QWidget(), "Activity Log")
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

        layout.addWidget(name_lbl)
        layout.addWidget(type_lbl)
        layout.addWidget(status_chip)
        layout.addStretch()
        layout.addWidget(edit_btn)
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
        layout.addWidget(QLabel("Identity"))
        layout.addWidget(_FieldRow("Subject Type", s.subject_type))
        layout.addWidget(_FieldRow("Status", s.status))
        layout.addWidget(_FieldRow("Name", s.name))
        layout.addWidget(_FieldRow("Sex", s.sex))
        layout.addWidget(_FieldRow("Date of Birth", s.dob))
        layout.addWidget(_FieldRow("Age", str(s.age) if s.age else None))
        layout.addWidget(_FieldRow("Race", s.race))
        layout.addWidget(_FieldRow("Height", s.height))
        layout.addWidget(_FieldRow("Weight", s.weight))
        layout.addWidget(_FieldRow("Hair", s.hair_color))
        layout.addWidget(_FieldRow("Eyes", s.eye_color))
        layout.addWidget(_FieldRow("Distinguishing Features", s.distinguishing_features))

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        if s.subject_type == SubjectType.MISSING_PERSON:
            layout.addWidget(QLabel("SAR Profile"))
            layout.addWidget(_FieldRow("LKP Time", s.lkp_time))
            layout.addWidget(_FieldRow("LKP Place", s.lkp_place))
            layout.addWidget(_FieldRow("PLS Time", s.pls_time))
            layout.addWidget(_FieldRow("PLS Place", s.pls_place))
            layout.addWidget(_FieldRow("Clothing", s.clothing_description))
            layout.addWidget(_FieldRow("Equipment", s.equipment_description))
            layout.addWidget(_FieldRow("Vehicle", s.vehicle_description))
            layout.addWidget(_FieldRow("Outdoor Experience", s.outdoor_experience))
            layout.addWidget(_FieldRow("Behavioral Notes", s.behavioral_notes))
            layout.addWidget(_FieldRow("Medical Conditions", s.medical_conditions))
            layout.addWidget(_FieldRow("Medications", s.medications))
            layout.addWidget(_FieldRow("Mobility Limitations", s.mobility_limitations))
            sep2 = QFrame()
            sep2.setFrameShape(QFrame.HLine)
            layout.addWidget(sep2)

        layout.addWidget(QLabel("Contact"))
        layout.addWidget(_FieldRow("Phone", s.phone))
        layout.addWidget(_FieldRow("Email", s.email))
        layout.addWidget(_FieldRow("Address", s.address))
        layout.addWidget(_FieldRow("Organization", s.organization))

        if s.subject_type in (SubjectType.WITNESS, SubjectType.REPORTING_PARTY):
            sep3 = QFrame()
            sep3.setFrameShape(QFrame.HLine)
            layout.addWidget(sep3)
            layout.addWidget(_FieldRow("Reliability", s.reliability))
            layout.addWidget(_FieldRow("Initial Report", s.initial_report))

        if s.notes:
            sep4 = QFrame()
            sep4.setFrameShape(QFrame.HLine)
            layout.addWidget(sep4)
            layout.addWidget(QLabel("Notes"))
            notes_lbl = QLabel(s.notes)
            notes_lbl.setWordWrap(True)
            layout.addWidget(notes_lbl)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_timeline_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.addWidget(QLabel("Subject timeline coming in a future update."))
        layout.addWidget(QLabel(f"Created: {self._subject.created_at}"))
        layout.addWidget(QLabel(f"Last Updated: {self._subject.updated_at}"))
        layout.addStretch()
        return w

    def _build_links_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        s = self._subject
        if s.linked_item_ids:
            layout.addWidget(QLabel(f"Linked Intel Items: {len(s.linked_item_ids)}"))
            for item_id in s.linked_item_ids:
                layout.addWidget(QLabel(f"  • {item_id}"))
        if s.linked_task_ids:
            layout.addWidget(QLabel(f"Linked Tasks: {len(s.linked_task_ids)}"))
            for task_id in s.linked_task_ids:
                layout.addWidget(QLabel(f"  • {task_id}"))
        if not s.linked_item_ids and not s.linked_task_ids:
            layout.addWidget(QLabel("No linked records."))
        layout.addStretch()
        return w

    def _edit_subject(self) -> None:
        dlg = _EditSubjectDialog(self._subject, self)
        if dlg.exec() == QDialog.Accepted and dlg.updated_subject:
            saved = self._service.subjects.update(
                self._subject.id, dlg.updated_subject
            )
            if saved:
                self._subject = saved
                self.setWindowTitle(f"Subject: {saved.name}")
                self.subject_updated.emit(saved)
                # Refresh overview tab
                self._tabs.removeTab(0)
                self._tabs.insertTab(0, self._build_overview_tab(), "Overview")
                self._tabs.setCurrentIndex(0)
