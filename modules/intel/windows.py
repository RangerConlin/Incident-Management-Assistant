from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFormLayout,
    QLineEdit,
    QDateTimeEdit,
    QSpinBox,
    QTextEdit,
    QPushButton,
    QMessageBox,
)

from .panels import IntelDashboard, CluePanel
from .models import Clue
from .utils import validators, db_access

__all__ = [
    "get_dashboard_panel",
    "get_clue_log_panel",
    "get_add_clue_panel",
]


def get_dashboard_panel(incident_id: object | None = None) -> QWidget:
    """Return the main Intel dashboard panel.

    The panel itself internally queries the active incident context, so the
    optional ``incident_id`` is currently informational only and may be used in
    future to scope data queries if needed.
    """
    # Ensure the incident database has required intel tables before any panel
    # attempts to query. This avoids first-run crashes on a fresh incident DB.
    try:
        db_access.ensure_incident_schema()
    except Exception:
        # Non-fatal; panels may still surface specific errors to the user.
        pass
    return IntelDashboard()


def get_clue_log_panel(incident_id: object | None = None) -> QWidget:
    """Return the clue log panel (SAR-134)."""
    try:
        db_access.ensure_incident_schema()
    except Exception:
        pass
    return CluePanel()


class _AddCluePanel(QWidget):
    """Lightweight dockable panel to add a new clue (SAR-135).

    Mirrors the fields from the modal ClueEditorDialog, but presented inline so
    it can live inside a dock widget per main window expectations.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._type = QLineEdit()
        self._score = QSpinBox(); self._score.setRange(0, 100)
        self._time = QDateTimeEdit(datetime.now())
        self._location = QLineEdit()
        self._entered_by = QLineEdit()
        self._team = QLineEdit()
        self._desc = QTextEdit()

        form = QFormLayout()
        form.addRow("Type", self._type)
        form.addRow("Score", self._score)
        form.addRow("Time", self._time)
        form.addRow("Location", self._location)
        form.addRow("Entered By", self._entered_by)
        form.addRow("Team", self._team)
        form.addRow("Description", self._desc)

        self._save = QPushButton("Save Clue")
        self._save.clicked.connect(self._on_save)

        layout = QVBoxLayout(self)
        title = QLabel("Add Clue (SAR-135)")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(self._save)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    def _on_save(self) -> None:
        clue = Clue(
            type=self._type.text().strip(),
            score=int(self._score.value()),
            at_time=self._time.dateTime().toPython(),
            location_text=self._location.text().strip(),
            entered_by=self._entered_by.text().strip(),
            team_text=self._team.text().strip() or None,
            description=self._desc.toPlainText().strip() or None,
        )
        try:
            validators.validate_clue(clue)
            with db_access.incident_session() as session:
                db_access.ensure_incident_schema()
                session.add(clue)
                session.commit()
            QMessageBox.information(self, "Add Clue", "Clue saved.")
            # Reset basic fields after save
            self._type.clear()
            self._score.setValue(0)
            self._location.clear()
            self._entered_by.clear()
            self._team.clear()
            self._desc.clear()
        except Exception as e:
            QMessageBox.warning(self, "Add Clue", f"Could not save clue: {e}")


def get_add_clue_panel(incident_id: object | None = None) -> QWidget:
    """Return a dockable panel to add a new clue (SAR-135)."""
    return _AddCluePanel()
