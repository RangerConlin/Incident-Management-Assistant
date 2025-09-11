"""Panel capturing environmental intel snapshots."""

from __future__ import annotations

from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
)
from sqlmodel import select

from ..models import EnvSnapshot
from ..utils import db_access


class _EnvDialog(QDialog):
    def __init__(self, snapshot: EnvSnapshot | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Environment")
        self._snapshot = snapshot
        self.op_edit = QLineEdit()
        self.weather_edit = QLineEdit()
        self.haz_edit = QLineEdit()
        self.terrain_edit = QLineEdit()
        self.notes_edit = QLineEdit()
        form = QFormLayout(self)
        form.addRow("OP", self.op_edit)
        form.addRow("Weather", self.weather_edit)
        form.addRow("Hazards", self.haz_edit)
        form.addRow("Terrain", self.terrain_edit)
        form.addRow("Notes", self.notes_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if snapshot:
            self.op_edit.setText(str(snapshot.op_period))
            self.weather_edit.setText(snapshot.weather_json or "")
            self.haz_edit.setText(snapshot.hazards_json or "")
            self.terrain_edit.setText(snapshot.terrain_json or "")
            self.notes_edit.setText(snapshot.notes or "")

    @property
    def snapshot(self) -> EnvSnapshot | None:
        return self._snapshot

    def accept(self) -> None:  # type: ignore[override]
        snap = EnvSnapshot(
            id=self._snapshot.id if self._snapshot else None,
            op_period=int(self.op_edit.text() or 0),
            weather_json=self.weather_edit.text() or None,
            hazards_json=self.haz_edit.text() or None,
            terrain_json=self.terrain_edit.text() or None,
            notes=self.notes_edit.text() or None,
        )
        self._snapshot = snap
        super().accept()


class EnvironmentPanel(QWidget):
    headers = ["OP", "Weather", "Hazards", "Terrain", "Notes"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)

        self.add_btn = QPushButton("New Snapshot")
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

    def refresh(self) -> None:
        self.table.setRowCount(0)
        with db_access.incident_session() as session:
            snaps: List[EnvSnapshot] = session.exec(select(EnvSnapshot)).all()
        for row, s in enumerate(snaps):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(s.op_period)))
            self.table.setItem(row, 1, QTableWidgetItem(s.weather_json or ""))
            self.table.setItem(row, 2, QTableWidgetItem(s.hazards_json or ""))
            self.table.setItem(row, 3, QTableWidgetItem(s.terrain_json or ""))
            self.table.setItem(row, 4, QTableWidgetItem(s.notes or ""))
            self.table.item(row, 0).setData(Qt.UserRole, s.id)

    def _current_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def _add(self) -> None:
        dlg = _EnvDialog(parent=self)
        if dlg.exec() == dlg.Accepted:
            with db_access.incident_session() as session:
                session.add(dlg.snapshot)
                session.commit()
            self.refresh()

    def _edit(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        with db_access.incident_session() as session:
            snap = session.get(EnvSnapshot, sid)
        dlg = _EnvDialog(snap, self)
        if dlg.exec() == dlg.Accepted:
            with db_access.incident_session() as session:
                session.add(dlg.snapshot)
                session.commit()
            self.refresh()

    def _delete(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        with db_access.incident_session() as session:
            snap = session.get(EnvSnapshot, sid)
            if snap:
                session.delete(snap)
                session.commit()
        self.refresh()
