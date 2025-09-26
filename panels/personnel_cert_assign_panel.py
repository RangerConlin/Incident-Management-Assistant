"""Personnel Certification Assignment Panel (Qt Widgets).

This panel allows editing of a selected person's certifications. It is
standalone and can be embedded in a dock or opened as a modal dialog by
wrapping it in a QDialog.

Columns: Code, Name, Category, Level, Attachment.
Toolbar: Add, Edit Level, Remove, Refresh; search box filters code/name.
"""

from __future__ import annotations

from typing import List, Dict, Any

from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QToolBar, QTableView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QPushButton, QFileDialog,
    QMessageBox
)

from modules.personnel.api import cert_api
from modules.personnel.services.cert_formatter import level_to_label, render_badge
from modules.personnel.models.validation_profiles import PROFILES


class _CertsTableModel(QAbstractTableModel):
    columns = ("Code", "Name", "Category", "Level", "Attachment")

    def __init__(self, rows: List[Dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._rows: List[Dict[str, Any]] = rows or []

    def set_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # noqa: N802
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == 0:
                return row.get("code")
            if col == 1:
                return row.get("name")
            if col == 2:
                return row.get("category")
            if col == 3:
                return level_to_label(int(row.get("level", 0)))
            if col == 4:
                return "Yes" if row.get("attachment_url") else ""
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section]
        return super().headerData(section, orientation, role)

    def row(self, index: QModelIndex) -> Dict[str, Any]:
        return self._rows[index.row()]


class _AddEditDialog(QDialog):
    """Modal dialog for adding or editing a person's certification level."""

    def __init__(self, parent=None, *,
                 initial_cert_id: int | None = None,
                 initial_level: int = 0,
                 initial_attachment: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Certification Level")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._attachment: str | None = initial_attachment

        form = QFormLayout()

        self.cmb_cert = QComboBox()
        self._catalog = cert_api.list_catalog()
        for item in self._catalog:
            self.cmb_cert.addItem(f"{item['code']} – {item['name']}", item["id"])
        if initial_cert_id is not None:
            idx = max(0, self.cmb_cert.findData(initial_cert_id))
            self.cmb_cert.setCurrentIndex(idx)

        self.cmb_level = QComboBox()
        self.cmb_level.addItem("None", 0)
        self.cmb_level.addItem("Trainee", 1)
        self.cmb_level.addItem("Qualified", 2)
        self.cmb_level.addItem("Evaluator", 3)
        self.cmb_level.setCurrentIndex(max(0, min(3, int(initial_level))))

        self.lbl_preview = QLabel("")

        self.btn_pick = QPushButton("Choose File…")
        self.btn_pick.clicked.connect(self._pick_file)
        self.lbl_file = QLabel(initial_attachment or "")

        form.addRow("Certification:", self.cmb_cert)
        form.addRow("Level:", self.cmb_level)
        form.addRow("Badge Preview:", self.lbl_preview)
        row = QHBoxLayout()
        row.addWidget(self.btn_pick)
        row.addWidget(self.lbl_file)
        form.addRow("Attachment:", row.parent() if hasattr(row, 'parent') else self.btn_pick)

        # Update preview on changes
        def _update_preview():
            code = self.cmb_cert.currentText().split(" – ")[0]
            lvl = int(self.cmb_level.currentData() or self.cmb_level.currentIndex())
            self.lbl_preview.setText(render_badge(code, lvl))

        self.cmb_cert.currentIndexChanged.connect(_update_preview)
        self.cmb_level.currentIndexChanged.connect(_update_preview)
        _update_preview()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        v = QVBoxLayout(self)
        v.addLayout(form)
        v.addWidget(btns)

        # Keyboard shortcuts: Enter=Save, Esc=Cancel handled by button box

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Attachment")
        if path:
            self._attachment = path
            self.lbl_file.setText(path)

    def selected_values(self) -> tuple[int, int, str | None]:
        cert_id = int(self.cmb_cert.currentData())
        level = int(self.cmb_level.currentData() or self.cmb_level.currentIndex())
        return cert_id, level, self._attachment


class PersonnelCertAssignPanel(QWidget):
    """Widget that manages certifications for a single person."""

    def __init__(self, personnel: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.person = personnel or {
            "id": 0,
            "name": "Unknown",
            "role": "",
            "callsign": "",
            "phone": "",
        }
        self._model = _CertsTableModel([])

        v = QVBoxLayout(self)

        # Header with basic read-only info
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel(f"Name: {self.person.get('name','')}") )
        hdr.addWidget(QLabel(f"ID: {self.person.get('id','')}") )
        hdr.addWidget(QLabel(f"Role: {self.person.get('role','')}") )
        hdr.addWidget(QLabel(f"Callsign: {self.person.get('callsign','')}") )
        hdr.addWidget(QLabel(f"Phone: {self.person.get('phone','')}") )
        hdr.addStretch(1)
        v.addLayout(hdr)

        # Toolbar
        tb = QToolBar()
        act_add = QAction("Add", self)
        act_edit = QAction("Edit Level", self)
        act_del = QAction("Remove", self)
        act_refresh = QAction("Refresh", self)
        tb.addAction(act_add)
        tb.addAction(act_edit)
        tb.addAction(act_del)
        tb.addSeparator()
        tb.addAction(act_refresh)
        tb.addSeparator()
        tb.addWidget(QLabel("Search:"))
        self.txt_search = QLineEdit()
        tb.addWidget(self.txt_search)
        v.addWidget(tb)

        # Table view with sort/filter
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self._proxy.setSourceModel(self._model)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)

        # Footer: profiles met
        self.lbl_profiles = QLabel("")
        v.addWidget(self.lbl_profiles)

        # Wire actions
        act_add.triggered.connect(self._on_add)
        act_edit.triggered.connect(self._on_edit)
        act_del.triggered.connect(self._on_delete)
        act_refresh.triggered.connect(self.refresh)
        self.txt_search.textChanged.connect(self._on_search)

        # Initial load
        self.refresh()

    # ----- Actions ---------------------------------------------------------
    def _on_search(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    def _selected_row(self) -> Dict[str, Any] | None:
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return None
        src = self._proxy.mapToSource(idxs[0])
        return self._model.row(src)

    def _on_add(self) -> None:
        dlg = _AddEditDialog(self)
        if dlg.exec() == QDialog.Accepted:
            cert_id, level, attachment = dlg.selected_values()
            try:
                cert_api.set_personnel_cert(int(self.person["id"]), cert_id, level, attachment)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_edit(self) -> None:
        row = self._selected_row()
        if not row:
            return
        dlg = _AddEditDialog(self, initial_cert_id=int(row["id"]), initial_level=int(row["level"]), initial_attachment=row.get("attachment_url"))
        if dlg.exec() == QDialog.Accepted:
            cert_id, level, attachment = dlg.selected_values()
            try:
                cert_api.set_personnel_cert(int(self.person["id"]), cert_id, level, attachment)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_delete(self) -> None:
        row = self._selected_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove", f"Remove {row['code']} from {self.person.get('name','this person')}?") != QMessageBox.Yes:
            return
        try:
            cert_api.delete_personnel_cert(int(self.person["id"]), int(row["id"]))
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self) -> None:
        rows = cert_api.list_personnel_certs(int(self.person["id"]))
        self._model.set_rows(rows)
        # Update profiles met
        met: list[str] = []
        for p in PROFILES:
            try:
                if cert_api.person_meets_profile(int(self.person["id"]), p.code):
                    met.append(p.name)
            except Exception:
                pass
        if met:
            self.lbl_profiles.setText("Profiles Met: " + ", ".join(met))
        else:
            self.lbl_profiles.setText("Profiles Met: (none)")


__all__ = ["PersonnelCertAssignPanel"]
