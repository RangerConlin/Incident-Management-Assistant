"""Modal dialog for creating or editing a clue."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QSpinBox,
)

from ..models import Clue
from ..utils import validators


class ClueEditorDialog(QDialog):
    """Dialog allowing the user to enter or edit a :class:`Clue`."""

    def __init__(self, clue: Optional[Clue] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Clue")
        self._clue = clue

        self.type_edit = QLineEdit()
        self.score_spin = QSpinBox()
        self.score_spin.setRange(0, 100)
        self.time_edit = QDateTimeEdit(datetime.now())
        self.location_edit = QLineEdit()
        self.entered_by_edit = QLineEdit()
        self.team_edit = QLineEdit()
        self.desc_edit = QTextEdit()

        form = QFormLayout(self)
        form.addRow("Type", self.type_edit)
        form.addRow("Score", self.score_spin)
        form.addRow("Time", self.time_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Entered By", self.entered_by_edit)
        form.addRow("Team", self.team_edit)
        form.addRow("Description", self.desc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if clue:
            self.type_edit.setText(clue.type)
            self.score_spin.setValue(clue.score)
            self.time_edit.setDateTime(clue.at_time)
            self.location_edit.setText(clue.location_text)
            self.entered_by_edit.setText(clue.entered_by)
            self.team_edit.setText(clue.team_text or "")
            self.desc_edit.setPlainText(clue.description or "")

    @property
    def clue(self) -> Clue | None:
        return self._clue

    def accept(self) -> None:  # type: ignore[override]
        data = Clue(
            id=self._clue.id if self._clue else None,
            type=self.type_edit.text().strip(),
            score=int(self.score_spin.value()),
            at_time=self.time_edit.dateTime().toPython(),
            location_text=self.location_edit.text().strip(),
            entered_by=self.entered_by_edit.text().strip(),
            team_text=self.team_edit.text().strip() or None,
            description=self.desc_edit.toPlainText().strip() or None,
        )
        validators.validate_clue(data)
        self._clue = data
        super().accept()
