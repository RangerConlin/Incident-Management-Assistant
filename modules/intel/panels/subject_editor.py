"""Tabbed editor for subject profiles."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
)

from ..models import Subject
from ..utils import validators


class SubjectEditor(QDialog):
    """Dialog used to create or edit :class:`Subject` records."""

    def __init__(self, subject: Optional[Subject] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Subject")
        self._subject = subject

        tabs = QTabWidget()
        ident_widget = QWidget()
        ident_form = QFormLayout(ident_widget)
        self.name_edit = QLineEdit()
        self.sex_edit = QLineEdit()
        self.dob_edit = QLineEdit()
        self.race_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Required")
        self.name_edit.setToolTip("Subject full name (required)")
        ident_form.addRow("Name*", self.name_edit)
        ident_form.addRow("Sex", self.sex_edit)
        ident_form.addRow("DOB", self.dob_edit)
        ident_form.addRow("Race", self.race_edit)
        tabs.addTab(ident_widget, "Identity")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if subject:
            self.name_edit.setText(subject.name)
            self.sex_edit.setText(subject.sex or "")
            self.dob_edit.setText(subject.dob or "")
            self.race_edit.setText(subject.race or "")

    @property
    def subject(self) -> Subject | None:
        return self._subject

    def accept(self) -> None:  # type: ignore[override]
        data = Subject(
            id=self._subject.id if self._subject else None,
            name=self.name_edit.text().strip(),
            sex=self.sex_edit.text().strip() or None,
            dob=self.dob_edit.text().strip() or None,
            race=self.race_edit.text().strip() or None,
        )
        try:
            validators.validate_subject(data)
        except validators.ValidationError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Required Fields", str(e))
            self.name_edit.setFocus()
            return
        self._subject = data
        super().accept()
