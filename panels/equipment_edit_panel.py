from __future__ import annotations

import csv
import os
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PySide6 import QtCore, QtGui, QtWidgets


# Database config
DEFAULT_DB_PATH = os.path.join("data", "master.db")
TABLE_NAME = "equipment"


EQUIPMENT_TYPES: Tuple[str, ...] = (
    "Radio",
    "Medical",
    "Tool",
    "Other",
    "Communications",
    "Protective Gear",
    "Electronics",
    "Lighting",
    "Navigation",
    "Support Equipment",
)

CONDITION_OPTIONS: Tuple[str, ...] = (
    "Serviceable",
    "Needs Repair",
    "Out of Service",
    "Unknown",
)


CSV_HEADERS: Tuple[str, ...] = (
    "id",
    "name",
    "type",
    "id_number",
    "serial_number",
    "condition",
    "notes",
    "radio_alias",
)


def _ensure_data_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def ensure_schema(db_path: str = DEFAULT_DB_PATH) -> None:
    """Ensure the equipment table exists with the required schema."""
    _ensure_data_dir(db_path)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            f"""
CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" (
  "id"            INTEGER PRIMARY KEY AUTOINCREMENT,
  "name"          TEXT NOT NULL,
  "type"          TEXT NOT NULL,
  "id_number"     TEXT,
  "serial_number" TEXT,
  "condition"     TEXT NOT NULL,
  "notes"         TEXT,
  "radio_alias"   TEXT
);
"""
        )
        con.commit()
    finally:
        con.close()


def _dict_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


class MultiColumnFilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, search_columns: List[int], parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._search_columns = search_columns
        self._pattern = ""
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

    def setPattern(self, text: str) -> None:
        self._pattern = text or ""
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:  # type: ignore[override]
        if not self._pattern:
            return True
        pat = self._pattern.lower()
        model = self.sourceModel()
        for col in self._search_columns:
            idx = model.index(source_row, col, source_parent)
            data = model.data(idx, QtCore.Qt.DisplayRole)
            if data is None:
                continue
            if pat in str(data).lower():
                return True
        return False


class EquipmentDetailDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Equipment Details")
        self.setMinimumWidth(520)

        layout = QtWidgets.QVBoxLayout(self)
        formw = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(formw)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self.e_name = QtWidgets.QLineEdit()
        self.e_type = QtWidgets.QComboBox(); self.e_type.setEditable(False); self.e_type.addItems(EQUIPMENT_TYPES)
        self.e_id_number = QtWidgets.QLineEdit()
        self.e_serial_number = QtWidgets.QLineEdit()
        self.e_condition = QtWidgets.QComboBox(); self.e_condition.setEditable(False); self.e_condition.addItems(CONDITION_OPTIONS)
        self.e_notes = QtWidgets.QPlainTextEdit()
        self.e_radio_alias = QtWidgets.QLineEdit()

        form.addRow("Name", self.e_name)
        form.addRow("Type", self.e_type)
        form.addRow("ID Number", self.e_id_number)
        form.addRow("Serial Number", self.e_serial_number)
        form.addRow("Condition", self.e_condition)
        form.addRow("Notes", self.e_notes)
        form.addRow("Radio Alias", self.e_radio_alias)

        layout.addWidget(formw)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._row_id: Optional[int] = None

    def set_values(self, values: Dict[str, Any]) -> None:
        self._row_id = values.get("id") if values else None
        self.e_name.setText(str(values.get("name") or ""))
        t = str(values.get("type") or "")
        ti = self.e_type.findText(t)
        self.e_type.setCurrentIndex(ti if ti >= 0 else -1)
        self.e_id_number.setText(str(values.get("id_number") or ""))
        self.e_serial_number.setText(str(values.get("serial_number") or ""))
        c = str(values.get("condition") or "")
        ci = self.e_condition.findText(c)
        self.e_condition.setCurrentIndex(ci if ci >= 0 else -1)
        self.e_notes.setPlainText(str(values.get("notes") or ""))
        self.e_radio_alias.setText(str(values.get("radio_alias") or ""))

    def get_values(self) -> Optional[Dict[str, Any]]:
        name = self.e_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return None
        type_val = self.e_type.currentText().strip()
        if not type_val:
            QtWidgets.QMessageBox.warning(self, "Validation", "Type is required.")
            return None
        cond_val = self.e_condition.currentText().strip()
        if not cond_val:
            QtWidgets.QMessageBox.warning(self, "Validation", "Condition is required.")
            return None
        return {
            "id": self._row_id,
            "name": name,
            "type": type_val,
            "id_number": self.e_id_number.text().strip() or None,
            "serial_number": self.e_serial_number.text().strip() or None,
            "condition": cond_val,
            "notes": self.e_notes.toPlainText().strip() or None,
            "radio_alias": self.e_radio_alias.text().strip() or None,
        }


class EquipmentEditPanel(QtWidgets.QWidget):
    """Modeless dockable panel for managing equipment.

    Selecting a row opens a modal detail dialog when OPEN_DETAIL_ON_SELECT is True.
    """

    OPEN_DETAIL_ON_SELECT: bool = True

    def __init__(self, db_path: str = DEFAULT_DB_PATH, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._db_path = db_path
        ensure_schema(self._db_path)

        self.setWindowTitle("Equipment")
        self._suppress_open: bool = False

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # Toolbar
        tb = QtWidgets.QToolBar()
        tb.setIconSize(QtCore.QSize(16, 16))
        act_new = tb.addAction("New")
        act_edit = tb.addAction("Edit")
        act_delete = tb.addAction("Delete")
        tb.addSeparator()
        act_export = tb.addAction("Export CSV")
        act_import = tb.addAction("Import CSV")
        tb.addSeparator()
        act_close = tb.addAction("Close")
        tb.addSeparator()
        tb.addWidget(QtWidgets.QLabel("Search:"))
        self.e_search = QtWidgets.QLineEdit()
        self.e_search.setPlaceholderText("Filter across all fields…")
        self.e_search.setClearButtonEnabled(True)
        self.e_search.setMaximumWidth(320)
        tb.addWidget(self.e_search)
        outer.addWidget(tb)

        # Table
        self.model = QtGui.QStandardItemModel(0, len(CSV_HEADERS), self)
        self.model.setHorizontalHeaderLabels([
            "ID",
            "Name",
            "Type",
            "ID Number",
            "Serial #",
            "Condition",
            "Notes",
            "Radio Alias",
        ])

        self.proxy = MultiColumnFilterProxy(search_columns=list(range(len(CSV_HEADERS))))
        self.proxy.setSourceModel(self.model)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.verticalHeader().setVisible(False)
        outer.addWidget(self.table, 1)

        # Connections
        act_new.triggered.connect(self.new_item)
        act_edit.triggered.connect(self.edit_selected)
        act_delete.triggered.connect(self.delete_selected)
        act_close.triggered.connect(self._close_container)
        act_export.triggered.connect(self.export_csv)
        act_import.triggered.connect(self.import_csv)
        self.table.doubleClicked.connect(lambda _=None: self.edit_selected())
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.e_search.textChanged.connect(self.proxy.setPattern)

        # Load initial data
        self.reload()

    # --- Data access helpers ---
    def _connect(self) -> sqlite3.Connection:
        ensure_schema(self._db_path)
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    def reload(self) -> None:
        rows: List[Dict[str, Any]] = []
        try:
            con = self._connect()
            cur = con.cursor()
            cur.execute(
                f"SELECT id, name, type, id_number, serial_number, condition, notes, radio_alias FROM {TABLE_NAME} ORDER BY name ASC"
            )
            rows = [_dict_from_row(r) for r in cur.fetchall()]
        except Exception as e:
            print("[EquipmentEditPanel] reload error:", e)
            rows = []
        finally:
            try:
                con.close()
            except Exception:
                pass

        self._suppress_open = True
        try:
            self.model.setRowCount(0)
            for r in rows:
                items = [
                    QtGui.QStandardItem(str(r.get("id") or "")),
                    QtGui.QStandardItem(str(r.get("name") or "")),
                    QtGui.QStandardItem(str(r.get("type") or "")),
                    QtGui.QStandardItem(str(r.get("id_number") or "")),
                    QtGui.QStandardItem(str(r.get("serial_number") or "")),
                    QtGui.QStandardItem(str(r.get("condition") or "")),
                    QtGui.QStandardItem(str(r.get("notes") or "")),
                    QtGui.QStandardItem(str(r.get("radio_alias") or "")),
                ]
                for it in items:
                    it.setEditable(False)
                self.model.appendRow(items)
        finally:
            QtCore.QTimer.singleShot(0, lambda: setattr(self, "_suppress_open", False))

        # Hide ID column by default but keep sortable/reorderable
        try:
            self.table.setColumnHidden(0, False)
        except Exception:
            pass

    # --- Selection open behavior ---
    def _on_selection_changed(self, *_args: Any) -> None:
        if not self.OPEN_DETAIL_ON_SELECT or self._suppress_open:
            return
        self.edit_selected()

    def _selected_source_row(self) -> Optional[int]:
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return None
        proxy_index = idxs[0]
        return self.proxy.mapToSource(proxy_index).row()

    def _row_values(self, source_row: int) -> Dict[str, Any]:
        vals: Dict[str, Any] = {}
        for c, key in enumerate(CSV_HEADERS):
            idx = self.model.index(source_row, c)
            vals[key] = self.model.data(idx, QtCore.Qt.DisplayRole)
        # Normalize ID to int when possible
        try:
            vals["id"] = int(vals.get("id") or 0) or None
        except Exception:
            vals["id"] = None
        return vals

    # --- CRUD actions ---
    def new_item(self) -> None:
        dlg = EquipmentDetailDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            values = dlg.get_values()
            if not values:
                return
            try:
                con = self._connect()
                cur = con.cursor()
                cur.execute(
                    f"""
INSERT INTO {TABLE_NAME} (name, type, id_number, serial_number, condition, notes, radio_alias)
VALUES (?, ?, ?, ?, ?, ?, ?)
""",
                    (
                        values.get("name"),
                        values.get("type"),
                        values.get("id_number"),
                        values.get("serial_number"),
                        values.get("condition"),
                        values.get("notes"),
                        values.get("radio_alias"),
                    ),
                )
                con.commit()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Insert Error", str(e))
            finally:
                try:
                    con.close()
                except Exception:
                    pass
            self.reload()

    def edit_selected(self) -> None:
        src_row = self._selected_source_row()
        if src_row is None:
            return
        values = self._row_values(src_row)
        if values.get("id") is None:
            return
        dlg = EquipmentDetailDialog(self)
        dlg.set_values(values)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            new_vals = dlg.get_values()
            if not new_vals:
                return
            try:
                con = self._connect()
                cur = con.cursor()
                cur.execute(
                    f"""
UPDATE {TABLE_NAME}
SET name=?, type=?, id_number=?, serial_number=?, condition=?, notes=?, radio_alias=?
WHERE id=?
""",
                    (
                        new_vals.get("name"),
                        new_vals.get("type"),
                        new_vals.get("id_number"),
                        new_vals.get("serial_number"),
                        new_vals.get("condition"),
                        new_vals.get("notes"),
                        new_vals.get("radio_alias"),
                        values.get("id"),
                    ),
                )
                con.commit()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Update Error", str(e))
            finally:
                try:
                    con.close()
                except Exception:
                    pass
            self.reload()

    def delete_selected(self) -> None:
        src_row = self._selected_source_row()
        if src_row is None:
            return
        values = self._row_values(src_row)
        row_id = values.get("id")
        if row_id is None:
            return
        resp = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete equipment ID {row_id} ('{values.get('name') or ''}')?",
        )
        if resp != QtWidgets.QMessageBox.Yes:
            return
        try:
            con = self._connect()
            cur = con.cursor()
            cur.execute(f"DELETE FROM {TABLE_NAME} WHERE id=?", (row_id,))
            con.commit()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Delete Error", str(e))
        finally:
            try:
                con.close()
            except Exception:
                pass
        self.reload()

    # --- CSV import/export ---
    def export_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Equipment CSV", "equipment.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            con = self._connect()
            cur = con.cursor()
            cur.execute(
                f"SELECT id, name, type, id_number, serial_number, condition, notes, radio_alias FROM {TABLE_NAME} ORDER BY id ASC"
            )
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                for row in cur.fetchall():
                    writer.writerow(list(row))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", str(e))
        finally:
            try:
                con.close()
            except Exception:
                pass

    def import_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Equipment CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                missing = [h for h in CSV_HEADERS if h not in (reader.fieldnames or [])]
                if missing:
                    QtWidgets.QMessageBox.warning(self, "Import Warning", f"Missing columns: {', '.join(missing)}")
                rows = list(reader)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))
            return

        try:
            con = self._connect()
            cur = con.cursor()
            for r in rows:
                # Normalize values
                name = (r.get("name") or "").strip()
                if not name:
                    continue
                type_val = (r.get("type") or "").strip()
                if type_val not in EQUIPMENT_TYPES:
                    # keep original text if not in list, but prefer Unknown bucket
                    type_val = type_val if type_val else "Other"
                cond_val = (r.get("condition") or "").strip()
                if cond_val not in CONDITION_OPTIONS:
                    cond_val = cond_val if cond_val else "Unknown"
                id_number = (r.get("id_number") or "").strip() or None
                serial_number = (r.get("serial_number") or "").strip() or None
                notes = (r.get("notes") or "").strip() or None
                radio_alias = (r.get("radio_alias") or "").strip() or None

                row_id_txt = (r.get("id") or "").strip()
                row_id = int(row_id_txt) if row_id_txt.isdigit() else None

                if row_id is not None:
                    # Attempt update; if 0 rows affected, try insert
                    cur.execute(
                        f"UPDATE {TABLE_NAME} SET name=?, type=?, id_number=?, serial_number=?, condition=?, notes=?, radio_alias=? WHERE id=?",
                        (name, type_val, id_number, serial_number, cond_val, notes, radio_alias, row_id),
                    )
                    if cur.rowcount == 0:
                        cur.execute(
                            f"INSERT INTO {TABLE_NAME} (id, name, type, id_number, serial_number, condition, notes, radio_alias) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (row_id, name, type_val, id_number, serial_number, cond_val, notes, radio_alias),
                        )
                else:
                    cur.execute(
                        f"INSERT INTO {TABLE_NAME} (name, type, id_number, serial_number, condition, notes, radio_alias) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (name, type_val, id_number, serial_number, cond_val, notes, radio_alias),
                    )
            con.commit()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))
        finally:
            try:
                con.close()
            except Exception:
                pass
        self.reload()

    # --- Utility ---
    def _close_container(self) -> None:
        # Try to close the nearest dock widget container if present
        w: Optional[QtWidgets.QWidget] = self
        while w is not None:
            if w.metaObject().className().endswith("CDockWidget"):
                try:
                    w.close()
                    return
                except Exception:
                    break
            w = w.parentWidget()
        self.close()


__all__ = [
    "EquipmentEditPanel",
    "EquipmentDetailDialog",
    "ensure_schema",
]

