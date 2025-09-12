"""Panel providing CRUD operations for clues."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QMessageBox,
)
from sqlmodel import select

from ..models import Clue
from ..utils import db_access
from .clue_editor_dialog import ClueEditorDialog


class CluePanel(QWidget):
    """Table view and controls for incident clues."""

    headers = ["Type", "Score", "Time", "Location", "Team"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        self.add_btn = QPushButton("New Clue")
        self.edit_btn = QPushButton("Edit")
        self.del_btn = QPushButton("Delete")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.del_btn.clicked.connect(self._delete)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload clues from the database."""
        self.table.setRowCount(0)
        # Ensure schema exists on first run to avoid missing-table errors.
        try:
            db_access.ensure_incident_schema()
        except Exception:
            pass
        with db_access.incident_session() as session:
            clues: List[Clue] = session.exec(select(Clue)).all()
        for row, clue in enumerate(clues):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(clue.type))
            self.table.setItem(row, 1, QTableWidgetItem(str(clue.score)))
            self.table.setItem(row, 2, QTableWidgetItem(clue.at_time.strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(row, 3, QTableWidgetItem(clue.location_text))
            self.table.setItem(row, 4, QTableWidgetItem(clue.team_text or ""))
            self.table.item(row, 0).setData(Qt.UserRole, clue.id)

    # ------------------------------------------------------------------
    def _current_clue_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    # ------------------------------------------------------------------
    def _add(self) -> None:
        dlg = ClueEditorDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            with db_access.incident_session() as session:
                session.add(dlg.clue)
                session.commit()
            self.refresh()

    def _edit(self) -> None:
        clue_id = self._current_clue_id()
        if clue_id is None:
            QMessageBox.warning(self, "Edit Clue", "Select a clue to edit")
            return
        with db_access.incident_session() as session:
            clue = session.get(Clue, clue_id)
        dlg = ClueEditorDialog(clue, self)
        if dlg.exec() == QDialog.Accepted:
            with db_access.incident_session() as session:
                session.add(dlg.clue)
                session.commit()
            self.refresh()

    def _delete(self) -> None:
        clue_id = self._current_clue_id()
        if clue_id is None:
            QMessageBox.warning(self, "Delete Clue", "Select a clue to delete")
            return
        if (
            QMessageBox.question(self, "Delete Clue", "Delete selected clue?")
            != QMessageBox.Yes
        ):
            return
        with db_access.incident_session() as session:
            clue = session.get(Clue, clue_id)
            if clue:
                session.delete(clue)
                session.commit()
        self.refresh()
