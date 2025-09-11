from __future__ import annotations

"""Qt dialog for selecting and managing incidents.

This window exposes a sortable, searchable table of incidents stored in the
master database.  Users can create new incidents, import existing ones, refresh
the list, and view details about the currently selected incident.  Loading an
incident emits :pyattr:`incidentLoaded` with the incident number so the caller
may activate it.
"""

from typing import Any, Dict, Optional
import sqlite3

from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression, Signal, QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QShortcut, QKeySequence

from models.database import (
    get_connection,
    insert_new_incident,
    update_incident_status,
    deactivate_active_incidents,
)
from modules.incidents.new_incident_dialog import NewIncidentDialog, IncidentMeta
from ui.models.incident_table_model import IncidentTableModel
from utils.state import AppState


def _fetch_incidents() -> list[Dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM incidents ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


class _FilterProxy(QSortFilterProxyModel):
    """Proxy model supporting free-text search and status filtering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status: str = "active"

    def setStatusFilter(self, value: str) -> None:
        self._status = value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if isinstance(model, IncidentTableModel) and self._status != "all":
            try:
                col = model.columns.index("status")
                idx = model.index(source_row, col, source_parent)
                status = str(model.data(idx, Qt.DisplayRole)).lower()
                if self._status == "active" and status != "active":
                    return False
                if self._status == "archived" and status != "archived":
                    return False
            except ValueError:
                pass

        pattern = self.filterRegularExpression()
        if not pattern.pattern():
            return True
        for col in range(model.columnCount()):
            idx = model.index(source_row, col, source_parent)
            value = model.data(idx, Qt.DisplayRole)
            if value is not None and pattern.match(str(value)).hasMatch():
                return True
        return False


class IncidentSelectionWindow(QDialog):
    """Dialog to view, filter and load incidents."""

    incidentLoaded = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Incident")
        self.setModal(True)

        # --- Toolbar ----------------------------------------------------
        toolbar = QHBoxLayout()
        new_btn = QPushButton("New Incident")
        import_btn = QPushButton("Import Incident")
        refresh_btn = QPushButton("Refresh List")
        toolbar.addWidget(new_btn)
        toolbar.addWidget(import_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()

        # --- Filters ----------------------------------------------------
        filter_row = QHBoxLayout()
        self._filter = QComboBox()
        self._filter.addItems(["Active Only", "All", "Archived"])
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search")
        filter_row.addWidget(self._filter)
        filter_row.addWidget(self._search)

        # --- Table ------------------------------------------------------
        self._table = QTableView()
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.doubleClicked.connect(self._load_selected)

        self._model = IncidentTableModel(_fetch_incidents())
        self._proxy = _FilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)

        # --- Details ----------------------------------------------------
        details_box = QFormLayout()
        self._detail_widgets: dict[str, QLabel] = {}
        for key in [
            "name",
            "number",
            "type",
            "status",
            "start_time",
            "icp_location",
            "description",
        ]:
            lab = QLabel()
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            details_box.addRow(key.replace("_", " ").title(), lab)
            self._detail_widgets[key] = lab

        details_widget = QWidget()
        details_widget.setLayout(details_box)

        # --- Action buttons ---------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._load_btn = QPushButton("Load Incident")
        archive_btn = QPushButton("Archive")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(self._load_btn)
        btn_row.addWidget(archive_btn)
        btn_row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addLayout(filter_row)
        layout.addWidget(self._table)
        layout.addWidget(details_widget)
        layout.addLayout(btn_row)

        # Connections ---------------------------------------------------
        self._search.textChanged.connect(self._on_search)
        self._filter.currentIndexChanged.connect(self._on_filter_changed)
        self._table.selectionModel().selectionChanged.connect(lambda *_: self._populate_details())
        self._load_btn.clicked.connect(self._load_selected)
        archive_btn.clicked.connect(self._archive_selected)
        cancel_btn.clicked.connect(self.reject)
        new_btn.clicked.connect(self._on_new)
        refresh_btn.clicked.connect(self.reload_missions)
        import_btn.clicked.connect(self._on_import)

        QShortcut(QKeySequence.Refresh, self, activated=self.reload_missions)

        self._populate_details()

    # ------------------------------------------------------------------
    def reload_missions(self, select_slug: Optional[str] = None) -> None:
        rows = _fetch_incidents()
        self._model.refresh(rows)
        if select_slug:
            for row in range(self._model.rowCount()):
                data = self._model.row_dict(row)
                if data.get("number") == select_slug:
                    src = self._model.index(row, 0)
                    proxy = self._proxy.mapFromSource(src)
                    self._table.selectRow(proxy.row())
                    break
        self._populate_details()

    # ------------------------------------------------------------------
    def _on_search(self, text: str) -> None:
        regex = QRegularExpression(text, QRegularExpression.CaseInsensitiveOption)
        self._proxy.setFilterRegularExpression(regex)

    # ------------------------------------------------------------------
    def _on_filter_changed(self) -> None:
        mapping = {0: "active", 1: "all", 2: "archived"}
        self._proxy.setStatusFilter(mapping.get(self._filter.currentIndex(), "all"))

    # ------------------------------------------------------------------
    def _current_row(self) -> Optional[Dict[str, Any]]:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        src = self._proxy.mapToSource(indexes[0])
        return self._model.row_dict(src.row())

    # ------------------------------------------------------------------
    def _populate_details(self) -> None:
        row = self._current_row() or {}
        for key, lab in self._detail_widgets.items():
            lab.setText(str(row.get(key, "")))
        self._load_btn.setEnabled(bool(row))

    # ------------------------------------------------------------------
    def _load_selected(self) -> None:
        row = self._current_row()
        if not row:
            return
        number = row.get("number")
        if not number:
            QMessageBox.warning(self, "No Incident", "Selected incident has no number.")
            return
        try:
            deactivate_active_incidents()
            update_incident_status(int(row["id"]), "Active")
        except Exception:
            pass
        AppState.set_active_incident(number)
        self.incidentLoaded.emit(str(number))
        self.accept()

    # ------------------------------------------------------------------
    def _archive_selected(self) -> None:
        row = self._current_row()
        if not row:
            return
        if QMessageBox.question(self, "Archive", "Archive selected incident?") != QMessageBox.Yes:
            return
        try:
            update_incident_status(int(row["id"]), "Archived")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
        self.reload_missions()

    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        dlg = NewIncidentDialog(self)

        def _created(meta: IncidentMeta, db_path: str) -> None:
            try:
                insert_new_incident(
                    number=meta.number,
                    name=meta.name,
                    type=meta.type,
                    description=meta.description,
                    icp_location=meta.location,
                    is_training=meta.is_training,
                    status=meta.status,
                    start_time=meta.start_time,
                )
            except Exception:
                pass
            self.reload_missions(select_slug=meta.number)

        dlg.created.connect(_created)
        dlg.exec()

    # ------------------------------------------------------------------
    def _on_import(self) -> None:
        QFileDialog.getOpenFileName(self, "Import Incident", "", "Incident Files (*.db)")


__all__ = ["IncidentSelectionWindow"]

