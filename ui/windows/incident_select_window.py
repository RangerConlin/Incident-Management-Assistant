from __future__ import annotations

"""QtWidgets-based Incident selection dialog.

This module exposes :class:`IncidentSelectDialog`, a modal dialog that lists
incidents stored in the master database and allows the user to add, edit, delete
or choose an incident. Selecting an incident updates the global application
state via :mod:`utils.state.AppState`.
"""

from typing import Dict, Any, Iterable, Optional
import sqlite3

from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression, Signal, QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
    QDialogButtonBox,
    QCheckBox,
    QShortcut,
)
from PySide6.QtGui import QKeySequence

from models import database
from utils.state import AppState
from ui.models.incident_table_model import IncidentTableModel


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    """Return a connection to the master database with row factory."""
    conn = database.get_connection()
    conn.row_factory = sqlite3.Row
    return conn


def list_incidents() -> list[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM incidents ORDER BY id DESC")
        return [dict(row) for row in cur.fetchall()]


def get_incident(incident_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM incidents WHERE id=?", (incident_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def create_incident(payload: Dict[str, Any]) -> int:
    keys = ", ".join(payload.keys())
    placeholders = ", ".join(["?"] * len(payload))
    values = list(payload.values())
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(f"INSERT INTO incidents ({keys}) VALUES ({placeholders})", values)
        conn.commit()
        return int(cur.lastrowid)


def update_incident(incident_id: int, payload: Dict[str, Any]) -> None:
    assigns = ", ".join(f"{k}=?" for k in payload.keys())
    values = list(payload.values()) + [incident_id]
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE incidents SET {assigns} WHERE id=?", values)
        conn.commit()


def delete_incident(incident_id: int) -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM incidents WHERE id=?", (incident_id,))
        conn.commit()


def incident_columns() -> list[str]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(incidents)")
        return [row[1] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Auxiliary dialogs
# ---------------------------------------------------------------------------


class _IncidentEditDialog(QDialog):
    """Generic editor for incident rows."""

    def __init__(self, columns: Iterable[str], data: Optional[Dict[str, Any]] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self._widgets: Dict[str, QWidget] = {}

        title = "Add Incident" if data is None else "Edit Incident"
        self.setWindowTitle(title)

        form = QFormLayout()
        editable = [c for c in columns if c not in {"id", "created_at", "updated_at"}]
        for col in editable:
            value = None if data is None else data.get(col)
            w: QWidget
            if self._is_bool(col, value):
                w = QCheckBox()
                if value not in (None, "", 0, False):
                    w.setChecked(bool(value))  # type: ignore[arg-type]
            else:
                w = QLineEdit()
                if value is not None:
                    w.setText(str(value))
            form.addRow(col.replace("_", " ").title(), w)
            self._widgets[col] = w

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _is_bool(self, col: str, value: Any) -> bool:
        if col.startswith("is_"):
            return True
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)) and value in (0, 1):
            return True
        return False

    # ------------------------------------------------------------------
    def values(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for col, widget in self._widgets.items():
            if isinstance(widget, QCheckBox):
                data[col] = 1 if widget.isChecked() else 0
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    data[col] = text
        return data


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class _FilterProxy(QSortFilterProxyModel):
    """Proxy model filtering across all columns."""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        pattern = self.filterRegularExpression()
        if not pattern.pattern():
            return True
        model = self.sourceModel()
        for col in range(model.columnCount()):
            idx = model.index(source_row, col, source_parent)
            value = model.data(idx, Qt.DisplayRole)
            if value is not None and pattern.match(str(value)).hasMatch():
                return True
        return False


class IncidentSelectDialog(QDialog):
    """Modal dialog to list and choose an incident. Emits incidentSelected."""

    incidentSelected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Incident")
        self.setModal(True)

        # Header --------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Select Incident"))
        header_layout.addStretch()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search")
        header_layout.addWidget(self._search)

        # Table ---------------------------------------------------------
        self._table = QTableView()
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.doubleClicked.connect(self._accept_current)

        self._model = IncidentTableModel(list_incidents())
        self._proxy = _FilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)

        # Footer --------------------------------------------------------
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._on_edit)
        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._on_delete)
        self._select_btn = QPushButton("Select")
        self._select_btn.clicked.connect(self._accept_current)
        self._select_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        footer = QHBoxLayout()
        footer.addWidget(add_btn)
        footer.addWidget(self._edit_btn)
        footer.addWidget(self._del_btn)
        footer.addStretch()
        footer.addWidget(cancel_btn)
        footer.addWidget(self._select_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self._table)
        layout.addLayout(footer)

        # Connections ---------------------------------------------------
        self._search.textChanged.connect(self._on_search)
        sel_model = self._table.selectionModel()
        sel_model.selectionChanged.connect(lambda *_: self._update_buttons())
        self._update_buttons()

        QShortcut(QKeySequence.Delete, self, activated=self._on_delete)

        # Hide ID column if present
        self._hide_id_column()

    # ------------------------------------------------------------------
    def _hide_id_column(self) -> None:
        cols = self._model.columns
        if "id" in cols:
            idx = cols.index("id")
            self._table.setColumnHidden(idx, True)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        rows = list_incidents()
        self._model.refresh(rows)
        self._hide_id_column()
        self._update_buttons()

    # ------------------------------------------------------------------
    def _on_search(self, text: str) -> None:
        regex = QRegularExpression(text, QRegularExpression.CaseInsensitiveOption)
        self._proxy.setFilterRegularExpression(regex)

    # ------------------------------------------------------------------
    def _get_selected_row(self) -> Optional[Dict[str, Any]]:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        src = self._proxy.mapToSource(indexes[0])
        return self._model.row_dict(src.row())

    # ------------------------------------------------------------------
    def selected_incident_id(self) -> Optional[int]:
        row = self._get_selected_row()
        if not row:
            return None
        return int(row.get("id")) if row.get("id") is not None else None

    # ------------------------------------------------------------------
    def _accept_current(self) -> None:
        row = self._get_selected_row()
        if not row:
            return
        incident_id = row.get("id")
        identifier = row.get("number") or incident_id
        if identifier is None:
            QMessageBox.warning(self, "No Incident", "Unable to determine incident identifier.")
            return
        AppState.set_active_incident(identifier)
        if incident_id is not None:
            self.incidentSelected.emit(int(incident_id))
        self.accept()

    # ------------------------------------------------------------------
    def _on_add(self) -> None:
        columns = incident_columns()
        dlg = _IncidentEditDialog(columns, parent=self)
        if dlg.exec() == QDialog.Accepted:
            payload = dlg.values()
            if not payload:
                return
            try:
                incident_id = create_incident(payload)
                # Create incident DB if number provided
                number = payload.get("number")
                if number:
                    try:
                        from utils.incident_db import create_incident_database
                        create_incident_database(str(number))
                    except Exception:
                        pass
                self.refresh()
                # Select newly added row
                self._select_by_id(incident_id)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    def _on_edit(self) -> None:
        row = self._get_selected_row()
        if not row:
            return
        columns = incident_columns()
        dlg = _IncidentEditDialog(columns, data=row, parent=self)
        if dlg.exec() == QDialog.Accepted:
            payload = dlg.values()
            if not payload:
                return
            try:
                update_incident(int(row["id"]), payload)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    def _on_delete(self) -> None:
        row = self._get_selected_row()
        if not row:
            return
        name = row.get("name") or row.get("number") or str(row.get("id"))
        if QMessageBox.question(
            self,
            "Delete Incident",
            f"Delete incident '{name}'?",
        ) == QMessageBox.Yes:
            try:
                delete_incident(int(row["id"]))
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    def _select_by_id(self, incident_id: int) -> None:
        if incident_id is None:
            return
        for row in range(self._model.rowCount()):
            data = self._model.row_dict(row)
            if data.get("id") == incident_id:
                src_idx = self._model.index(row, 0)
                proxy_idx = self._proxy.mapFromSource(src_idx)
                self._table.selectRow(proxy_idx.row())
                break

    # ------------------------------------------------------------------
    def _update_buttons(self) -> None:
        has = self._get_selected_row() is not None
        for btn in (self._edit_btn, self._del_btn, self._select_btn):
            btn.setEnabled(has)


__all__ = ["IncidentSelectDialog"]
