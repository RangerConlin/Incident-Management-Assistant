from __future__ import annotations

import csv
import os
import re
import sqlite3
from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets, QtSql


# App settings and defaults
APP_ORG = "SARApp"
APP_NAME = "ICSCommandAssistant"
DEFAULT_DB_PATH = os.path.join("data", "master.db")
TABLE_NAME = "comms_resources"

MODE_ALLOWED = ["A", "D", "M"]

# Columns: (key, label, required, editable, visible)
COLUMNS: List[Tuple[str, str, bool, bool, bool]] = [
    ("id", "ID", False, False, False),
    ("channel_name", "Channel Name", True, True, True),
    ("function", "[Function / Use]", False, True, True),
    ("rx_freq", "Freq Rx", True, True, True),
    ("rx_tone_nac", "Tone Rx", False, True, True),
    ("tx_freq", "Freq Tx", True, True, True),
    ("tx_tone_nac", "Tone Tx", False, True, True),
    ("system_name", "System", False, True, True),
    ("mode", "Mode", True, True, True),
    ("remarks", "Notes", False, True, True),
    ("line_a", "Line A Restrictions", False, True, True),
    ("line_c", "Line C Restrictions", False, True, True),
    ("zone", "Zone", False, True, False),
    ("channel_number", "Channel #", False, True, False),
    ("bandwidth_khz", "Bandwidth (kHz)", False, True, False),
    ("encryption", "Encrypted", False, True, False),
]

COL_INDEX: Dict[str, int] = {name: i for i, (name, *_rest) in enumerate(COLUMNS)}


def ensure_data_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def ensure_schema(db_path: str = DEFAULT_DB_PATH) -> bool:
    ensure_data_dir(db_path)
    created = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_name TEXT NOT NULL UNIQUE,
  function TEXT,
  zone TEXT,
  channel_number TEXT,
  rx_freq TEXT NOT NULL,
  rx_tone_nac TEXT,
  tx_freq TEXT NOT NULL,
  tx_tone_nac TEXT,
  mode TEXT NOT NULL,
  bandwidth_khz INTEGER,
  encryption INTEGER DEFAULT 0,
  system_name TEXT,
  remarks TEXT
);
"""
        )
        conn.commit()
        # Schema upgrades for new flags
        try:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()}
            if "line_a" not in cols:
                conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN line_a INTEGER DEFAULT 0")
            if "line_c" not in cols:
                conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN line_c INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()
    return created


def get_connection(db_path: str = DEFAULT_DB_PATH) -> QtSql.QSqlDatabase:
    conn_name = f"comms_editor_{os.path.abspath(db_path)}"
    if QtSql.QSqlDatabase.contains(conn_name):
        db = QtSql.QSqlDatabase.database(conn_name)
    else:
        db = QtSql.QSqlDatabase.addDatabase("QSQLITE", conn_name)
        db.setDatabaseName(db_path)
        if not db.open():
            raise RuntimeError(f"Failed to open database: {db.lastError().text()}")
    return db


def normalize_row_for_db(row: Dict[str, str]) -> Dict[str, Optional[str]]:
    keymap = {
        "line a": "line_a",
        "line a restrictions": "line_a",
        "line c": "line_c",
        "line c restrictions": "line_c",
        "channel": "channel_name",
        "name": "channel_name",
        "function/use": "function",
        "rx freq": "rx_freq",
        "rx frequency": "rx_freq",
        "rx tone": "rx_tone_nac",
        "rx nac": "rx_tone_nac",
        "tx freq": "tx_freq",
        "tx frequency": "tx_freq",
        "tx tone": "tx_tone_nac",
        "tx nac": "tx_tone_nac",
        "bw": "bandwidth_khz",
        "bandwidth": "bandwidth_khz",
        "mode (a/d/m)": "mode",
        "enc": "encryption",
        "encr": "encryption",
        "system": "system_name",
        "system/net": "system_name",
    }
    norm = {}
    for k, v in row.items():
        if k is None:
            continue
        kk = k.strip().lower()
        key = keymap.get(kk, kk)
        if key in COL_INDEX:
            norm[key] = v.strip() if isinstance(v, str) else v
    if "mode" in norm and norm["mode"]:
        norm["mode"] = str(norm["mode"]).strip().upper()
    if "encryption" in norm and norm["encryption"] not in (None, ""):
        val = str(norm["encryption"]).strip().lower()
        norm["encryption"] = 1 if val in ("1", "true", "yes", "y", "on") else 0
    for flag in ("line_a", "line_c"):
        if flag in norm and norm[flag] not in (None, ""):
            fval = str(norm[flag]).strip().lower()
            norm[flag] = 1 if fval in ("1", "true", "yes", "y", "on") else 0
    if "bandwidth_khz" in norm and norm["bandwidth_khz"] not in (None, ""):
        try:
            norm["bandwidth_khz"] = int(float(norm["bandwidth_khz"]))
        except Exception:
            norm["bandwidth_khz"] = None
    return norm


def seed_from_csv_if_available(db_path: str = DEFAULT_DB_PATH) -> None:
    candidates = [
        os.path.join("data", "comms_resources.csv"),
        os.path.join(os.sep, "mnt", "data", "comms_resources.csv"),
    ]
    csv_path = next((p for p in candidates if os.path.exists(p)), None)
    if not csv_path:
        return
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("BEGIN")
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                payload = normalize_row_for_db(row)
                if not payload.get("channel_name"):
                    continue
                existing_id = conn.execute(
                    f"SELECT id FROM {TABLE_NAME} WHERE lower(channel_name)=lower(?)",
                    (payload["channel_name"],),
                ).fetchone()
                fields = [k for k in payload.keys() if k in COL_INDEX]
                if existing_id:
                    set_clause = ",".join([f"{k}=?" for k in fields if k != "id"])
                    values = [payload[k] for k in fields if k != "id"]
                    values.append(existing_id[0])
                    conn.execute(
                        f"UPDATE {TABLE_NAME} SET {set_clause} WHERE id=?",
                        values,
                    )
                else:
                    placeholders = ",".join(["?" for _ in fields])
                    conn.execute(
                        f"INSERT INTO {TABLE_NAME} ({','.join(fields)}) VALUES ({placeholders})",
                        [payload[k] for k in fields],
                    )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

class EncryptionCheckDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        chk = QtWidgets.QCheckBox(parent)
        chk.setTristate(False)
        return chk

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        editor.setChecked(bool(int(value) if value not in (None, "") else 0))

    def setModelData(self, editor, model, index):
        model.setData(index, 1 if editor.isChecked() else 0, QtCore.Qt.EditRole)

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.DisplayRole)
        opt = QtWidgets.QStyleOptionButton()
        opt.state |= QtWidgets.QStyle.State_On if str(value) in ("1", "True", "true") else QtWidgets.QStyle.State_Off
        opt.rect = self.getCheckBoxRect(option)
        QtWidgets.QApplication.style().drawControl(QtWidgets.QStyle.CE_CheckBox, opt, painter)

    def getCheckBoxRect(self, option):
        style = QtWidgets.QApplication.style()
        check_box_style_option = QtWidgets.QStyleOptionButton()
        check_box_rect = style.subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, check_box_style_option, None)
        x = option.rect.x() + (option.rect.width() - check_box_rect.width()) / 2
        y = option.rect.y() + (option.rect.height() - check_box_rect.height()) / 2
        return QtCore.QRect(int(x), int(y), check_box_rect.width(), check_box_rect.height())


class ModeComboDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(MODE_ALLOWED)
        return combo


class YesNoDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(["No", "Yes"])
        return combo

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.EditRole)
        is_yes = int(value or 0) == 1
        editor.setCurrentIndex(1 if is_yes else 0)

    def setModelData(self, editor, model, index):
        model.setData(index, 1 if editor.currentIndex() == 1 else 0, QtCore.Qt.EditRole)

    def displayText(self, value, locale):
        try:
            return "Yes" if int(value) == 1 else "No"
        except Exception:
            return "No"
    def setEditorData(self, editor, index):
        value = str(index.model().data(index, QtCore.Qt.EditRole) or "").upper()
        i = editor.findText(value)
        if i >= 0:
            editor.setCurrentIndex(i)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)


class MultiColumnFilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, search_columns: List[int], parent=None):
        super().__init__(parent)
        self._search_columns = search_columns
        self._pattern = ""
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

    def setPattern(self, text: str):
        self._pattern = text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        if not self._pattern:
            return True
        pat = self._pattern.lower()
        model = self.sourceModel()
        for col in self._search_columns:
            idx = model.index(source_row, col, source_parent)
            data = model.data(idx, QtCore.Qt.DisplayRole)
            if data and pat in str(data).lower():
                return True
        return False


class _DetailDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Channel Details")
        self.setMinimumWidth(520)
        layout = QtWidgets.QVBoxLayout(self)
        formw = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(formw)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self.e_channel_name = QtWidgets.QLineEdit()
        self.e_function = QtWidgets.QLineEdit()
        self.e_zone = QtWidgets.QLineEdit()
        self.e_channel_number = QtWidgets.QLineEdit()
        self.e_rx_freq = QtWidgets.QLineEdit()
        self.e_rx_tone = QtWidgets.QLineEdit()
        self.e_tx_freq = QtWidgets.QLineEdit()
        self.e_tx_tone = QtWidgets.QLineEdit()
        self.e_mode = QtWidgets.QComboBox(); self.e_mode.addItems(MODE_ALLOWED)
        self.e_bandwidth = QtWidgets.QSpinBox(); self.e_bandwidth.setRange(0, 100); self.e_bandwidth.setSingleStep(1)
        self.e_encryption = QtWidgets.QCheckBox("Encrypted")
        self.e_system = QtWidgets.QLineEdit()
        self.e_remarks = QtWidgets.QTextEdit()

        form.addRow("Channel Name", self.e_channel_name)
        form.addRow("Function/Use", self.e_function)
        form.addRow("Zone", self.e_zone)
        form.addRow("Ch #", self.e_channel_number)
        form.addRow("RX Freq (MHz)", self.e_rx_freq)
        form.addRow("RX Tone/NAC", self.e_rx_tone)
        form.addRow("TX Freq (MHz)", self.e_tx_freq)
        form.addRow("TX Tone/NAC", self.e_tx_tone)
        form.addRow("Mode (A/D/M)", self.e_mode)
        form.addRow("BW (kHz)", self.e_bandwidth)
        form.addRow("Enc (0/1)", self.e_encryption)
        form.addRow("System/Net", self.e_system)
        form.addRow("Remarks", self.e_remarks)

        layout.addWidget(formw)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def load_from_record(self, rec: QtSql.QSqlRecord) -> None:  # type: ignore[name-defined]
        self.e_channel_name.setText(rec.value("channel_name") or "")
        self.e_function.setText(rec.value("function") or "")
        self.e_zone.setText(rec.value("zone") or "")
        self.e_channel_number.setText(rec.value("channel_number") or "")
        self.e_rx_freq.setText(rec.value("rx_freq") or "")
        self.e_rx_tone.setText(rec.value("rx_tone_nac") or "")
        self.e_tx_freq.setText(rec.value("tx_freq") or "")
        self.e_tx_tone.setText(rec.value("tx_tone_nac") or "")
        mode = (rec.value("mode") or "").upper(); i = self.e_mode.findText(mode)
        self.e_mode.setCurrentIndex(i if i >= 0 else 0)
        self.e_bandwidth.setValue(int(rec.value("bandwidth_khz") or 0))
        self.e_encryption.setChecked(bool(int(rec.value("encryption") or 0)))
        self.e_system.setText(rec.value("system_name") or "")
        self.e_remarks.setPlainText(rec.value("remarks") or "")

    def payload(self) -> Dict[str, object]:
        return {
            "channel_name": self.e_channel_name.text().strip(),
            "function": self.e_function.text().strip(),
            "zone": self.e_zone.text().strip(),
            "channel_number": self.e_channel_number.text().strip(),
            "rx_freq": self.e_rx_freq.text().strip(),
            "rx_tone_nac": self.e_rx_tone.text().strip(),
            "tx_freq": self.e_tx_freq.text().strip(),
            "tx_tone_nac": self.e_tx_tone.text().strip(),
            "mode": self.e_mode.currentText().strip().upper(),
            "bandwidth_khz": self.e_bandwidth.value() or None,
            "encryption": 1 if self.e_encryption.isChecked() else 0,
            "system_name": self.e_system.text().strip(),
            "remarks": self.e_remarks.toPlainText().strip(),
        }

class CommsResourceEditor(QtWidgets.QWidget):
    channelsChanged = QtCore.Signal()

    def __init__(self, db_path: str = DEFAULT_DB_PATH, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Comms Resource Editor")
        self.setObjectName("CommsResourceEditor")
        self._db_path = db_path
        self._db_created_now = ensure_schema(db_path)
        if self._db_created_now:
            seed_from_csv_if_available(db_path)

        self.db = get_connection(db_path)
        self.model = QtSql.QSqlTableModel(self, self.db)
        self.model.setTable(TABLE_NAME)
        self.model.setEditStrategy(QtSql.QSqlTableModel.OnFieldChange)
        # Ensure model has field metadata before applying headers/indices
        self.model.select()
        # Dynamic name->index mapping based on actual DB order
        self._rebuild_column_index()
        self._apply_headers()

        self._dirty = False
        self.model.dataChanged.connect(self._on_data_changed)
        self.model.rowsInserted.connect(self._on_data_changed)
        self.model.rowsRemoved.connect(self._on_data_changed)

        self._build_ui()
        self._restore_ui_state()

        self.selection_model.selectionChanged.connect(self._on_selection_changed)
        self._on_selection_changed()

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        toolbar = QtWidgets.QToolBar()
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        main_layout.addWidget(toolbar)

        self.action_new = QtGui.QAction(QtGui.QIcon.fromTheme("document-new"), "New", self)
        self.action_edit = QtGui.QAction(QtGui.QIcon.fromTheme("document-edit"), "Edit", self)
        self.action_delete = QtGui.QAction(QtGui.QIcon.fromTheme("edit-delete"), "Delete", self)
        self.action_import = QtGui.QAction(QtGui.QIcon.fromTheme("document-import"), "Import CSV", self)
        self.action_export = QtGui.QAction(QtGui.QIcon.fromTheme("document-export"), "Export CSV", self)

        for act, tip in [
            (self.action_new, "Create a new channel (Ctrl+N)"),
            (self.action_edit, "Edit selected channel (Ctrl+E)"),
            (self.action_delete, "Delete selected channel (Del)"),
            (self.action_import, "Import channels from CSV"),
            (self.action_export, "Export channels to CSV"),
        ]:
            act.setToolTip(tip)

        toolbar.addAction(self.action_new)
        toolbar.addAction(self.action_edit)
        toolbar.addAction(self.action_delete)
        toolbar.addSeparator()
        # Save/Cancel not needed in auto-commit mode
        toolbar.addAction(self.action_import)
        toolbar.addAction(self.action_export)
        toolbar.addSeparator()

        find_label = QtWidgets.QLabel("Find:")
        self.find_edit = QtWidgets.QLineEdit()
        self.find_edit.setPlaceholderText("Filter by name, function, zone, system, remarks")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(find_label)
        toolbar.addWidget(self.find_edit)

        self.column_menu_button = QtWidgets.QToolButton()
        self.column_menu_button.setText("Columns")
        self.column_menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.column_menu = QtWidgets.QMenu(self)
        self.column_actions = {}
        for i, (name, label, _req, _ed, visible) in enumerate(COLUMNS):
            if name == "id":
                continue
            act = self.column_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(visible)
            act.toggled.connect(lambda checked, key=name: self.table.setColumnHidden(self.col_index.get(key, -1), not checked))
            self.column_actions[name] = act
        self.column_menu_button.setMenu(self.column_menu)
        toolbar.addWidget(self.column_menu_button)

        # Main content is the table

        self.table = QtWidgets.QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.SelectedClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setSortingEnabled(True)

        search_cols = [
            self.col_index.get("channel_name", -1),
            self.col_index.get("function", -1),
            self.col_index.get("zone", -1),
            self.col_index.get("system_name", -1),
            self.col_index.get("remarks", -1),
        ]
        # Filter out any -1 entries in case of schema drift
        search_cols = [c for c in search_cols if c >= 0]
        self.proxy = MultiColumnFilterProxy(search_cols, self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.selection_model = self.table.selectionModel()
        self.table.doubleClicked.connect(lambda _ix: self._open_detail_for_current())

        # Delegates bound using dynamic indices
        if self.col_index.get("line_a", -1) >= 0:
            self.table.setItemDelegateForColumn(self.col_index["line_a"], YesNoDelegate(self.table))
        if self.col_index.get("line_c", -1) >= 0:
            self.table.setItemDelegateForColumn(self.col_index["line_c"], YesNoDelegate(self.table))
        if self.col_index.get("encryption", -1) >= 0:
            self.table.setItemDelegateForColumn(self.col_index["encryption"], EncryptionCheckDelegate(self.table))
        if self.col_index.get("mode", -1) >= 0:
            self.table.setItemDelegateForColumn(self.col_index["mode"], ModeComboDelegate(self.table))

        # Always hide id
        if self.col_index.get("id", -1) >= 0:
            self.table.setColumnHidden(self.col_index["id"], True)
        # Apply default visibility for columns marked not visible
        for name, _label, _req, _ed, vis in COLUMNS:
            if name == 'id':
                continue
            idx = self.col_index.get(name, -1)
            if idx >= 0 and not vis:
                self.table.setColumnHidden(idx, True)
                act = self.column_actions.get(name)
                if act:
                    act.blockSignals(True)
                    act.setChecked(False)
                    act.blockSignals(False)
        # Apply default visibility for columns marked not visible
        for name, _label, _req, _ed, vis in COLUMNS:
            if name == 'id':
                continue
            idx = self.col_index.get(name, -1)
            if idx >= 0 and not vis:
                self.table.setColumnHidden(idx, True)
                act = self.column_actions.get(name)
                if act:
                    act.blockSignals(True)
                    act.setChecked(False)
                    act.blockSignals(False)
        main_layout.addWidget(self.table, 1)

        self.status_strip = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel()
        self.filter_label = QtWidgets.QLabel()
        self.dirty_label = QtWidgets.QLabel()
        self.dirty_label.setStyleSheet("color: #b00;")
        self.status_strip.addWidget(self.status_label)
        self.status_strip.addStretch(1)
        self.status_strip.addWidget(self.filter_label)
        self.status_strip.addSpacing(12)
        self.status_strip.addWidget(self.dirty_label)
        main_layout.addLayout(self.status_strip)

        self.action_new.triggered.connect(self.on_new)
        self.action_edit.triggered.connect(self.on_edit)
        self.action_delete.triggered.connect(self.on_delete)
        self.action_import.triggered.connect(self.on_import_csv)
        self.action_export.triggered.connect(self.on_export_csv)

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self.on_new)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, activated=self.on_edit)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self.on_delete)
        # Default editor behavior handles cancel; no explicit save/cancel shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.find_edit.setFocus)

        self._editing = False
        self._inserting = False
        self._update_ui_state()
        self._refresh_status()

    def _apply_headers(self):
        # Set headers by field name to avoid mismatches if DB column order differs
        for name, label, _req, _ed, _visible in COLUMNS:
            idx = self.model.fieldIndex(name)
            if idx >= 0:
                self.model.setHeaderData(idx, QtCore.Qt.Horizontal, label)

    def _rebuild_column_index(self):
        # Build a name->index map from the actual model fields
        self.col_index: Dict[str, int] = {}
        for name, _label, _req, _ed, _visible in COLUMNS:
            self.col_index[name] = self.model.fieldIndex(name)

    def _on_filter_changed(self, text: str):
        self.proxy.setPattern(text)
        self._refresh_status()

    def _refresh_status(self):
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        self.status_label.setText(f"Records: {shown} / {total}")
        self.filter_label.setText(f"Filter: '{self.find_edit.text()}'" if self.find_edit.text() else "")
        self.dirty_label.setText("")

    def _on_data_changed(self, *args):
        self._dirty = True
        self._refresh_status()
        self._update_ui_state()

    def _on_selection_changed(self):
        # Do not auto-open detail on selection; user must double-click or press Edit
        self._update_ui_state()

    def _open_detail_for_current(self):
        index = self._current_source_index()
        if index.isValid():
            self._open_detail_dialog(new=False, row=index.row())

    def _open_detail_dialog(self, new: bool, row: Optional[int] = None):
        dlg = _DetailDialog(self)
        if not new and row is not None:
            rec = self.model.record(row)
            dlg.load_from_record(rec)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            payload = dlg.payload()
            err = self._validate(payload)
            if err:
                QtWidgets.QMessageBox.warning(self, "Validation Error", err)
                return
            try:
                name = payload.get("channel_name")
                q = QtSql.QSqlQuery(self.db)
                if new:
                    q.prepare(f"SELECT id FROM {TABLE_NAME} WHERE lower(channel_name)=lower(?)")
                    q.addBindValue(name)
                else:
                    rec = self.model.record(row)
                    current_id = rec.value("id")
                    q.prepare(f"SELECT id FROM {TABLE_NAME} WHERE lower(channel_name)=lower(?) AND id<>?")
                    q.addBindValue(name)
                    q.addBindValue(current_id)
                if not q.exec():
                    raise RuntimeError(q.lastError().text())
                if q.next():
                    QtWidgets.QMessageBox.warning(self, "Duplicate Channel Name", "Channel Name must be unique (case-insensitive).")
                    return
                if new:
                    rec = self.model.record()
                    for k, v in payload.items():
                        rec.setValue(k, v)
                    if not self.model.insertRecord(-1, rec):
                        raise RuntimeError(self.model.lastError().text())
                    self.model.select()
                    self.channelsChanged.emit()
                else:
                    r = row
                    for k, v in payload.items():
                        col = self.col_index.get(k, -1)
                        if col >= 0:
                            self.model.setData(self.model.index(r, col), v)
                    if self.model.lastError().isValid():
                        raise RuntimeError(self.model.lastError().text())
                    self.channelsChanged.emit()
                self._refresh_status()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Update Failed", str(e))

    def _current_source_index(self) -> QtCore.QModelIndex:
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return QtCore.QModelIndex()
        proxy_idx = idxs[0]
        return self.proxy.mapToSource(proxy_idx)

    def _clear_form(self):
        pass

    def _load_form_from_index(self, index: QtCore.QModelIndex):
        pass

    def _enable_form(self, enabled: bool):
        # Deprecated; form moved to dialog
        return

    def _update_ui_state(self):
        has_selection = self._current_source_index().isValid()
        self.action_edit.setEnabled(has_selection)
        self.action_delete.setEnabled(has_selection)
        self.action_new.setEnabled(True)
        self.action_import.setEnabled(True)
        self.action_export.setEnabled(True)
        self._enable_form(False)

    FREQ_RE = re.compile(r"^\d{2,4}\.\d{3,}$")

    def _validate(self, payload: Dict[str, object]) -> Optional[str]:
        name = str(payload.get("channel_name") or "").strip()
        if not name:
            return "Channel Name is required."
        for k, label in [("rx_freq", "RX Freq (MHz)"), ("tx_freq", "TX Freq (MHz)")]:
            v = str(payload.get(k) or "").strip()
            if not v:
                return f"{label} is required."
            if not self.FREQ_RE.match(v):
                return f"{label} must be MHz with at least 3 decimals (e.g., 155.7525)."
        mode = str(payload.get("mode") or "").upper()
        if mode not in MODE_ALLOWED:
            return "Mode must be one of A, D, or M."
        bw = payload.get("bandwidth_khz")
        if bw not in (None, ""):
            try:
                ival = int(bw)
            except Exception:
                return "BW (kHz) must be an integer (e.g., 12, 20, 25)."
            if ival not in {12, 20, 25}:
                return "BW (kHz) must be one of 12, 20, or 25."
        enc = payload.get("encryption")
        if enc not in (0, 1, None, ""):
            try:
                payload["encryption"] = 1 if int(enc) else 0
            except Exception:
                return "Encryption must be 0 or 1."
        return None

    def _payload_from_form(self) -> Dict[str, object]:
        return {
            "channel_name": self.e_channel_name.text().strip(),
            "function": self.e_function.text().strip(),
            "zone": self.e_zone.text().strip(),
            "channel_number": self.e_channel_number.text().strip(),
            "rx_freq": self.e_rx_freq.text().strip(),
            "rx_tone_nac": self.e_rx_tone.text().strip(),
            "tx_freq": self.e_tx_freq.text().strip(),
            "tx_tone_nac": self.e_tx_tone.text().strip(),
            "mode": self.e_mode.currentText().strip().upper(),
            "bandwidth_khz": self.e_bandwidth.value() or None,
            "encryption": 1 if self.e_encryption.isChecked() else 0,
            "system_name": self.e_system.text().strip(),
            "remarks": self.e_remarks.toPlainText().strip(),
        }

    def on_new(self):
        # Open detail dialog to add a new record
        self._open_detail_dialog(new=True)

    def on_edit(self):
        self._open_detail_for_current()

    def on_delete(self):
        index = self._current_source_index()
        if not index.isValid():
            return
        rec = self.model.record(index.row())
        name = rec.value("channel_name") or "this channel"
        if QtWidgets.QMessageBox.question(
            self, "Confirm Delete", f"Delete '{name}'? This cannot be undone."
        ) != QtWidgets.QMessageBox.Yes:
            return
        if not self.model.removeRow(index.row()):
            QtWidgets.QMessageBox.critical(self, "Delete Failed", self.model.lastError().text())
            return
        # OnFieldChange auto-commits; verify no error
        if self.model.lastError().isValid():
            QtWidgets.QMessageBox.critical(self, "Delete Failed", self.model.lastError().text())
            self.model.select()
            return
        self.model.select()
        self.channelsChanged.emit()
        self._refresh_status()

    # on_save removed; auto-commit is used with detail dialog
    def on_save(self):
        return

    def on_cancel(self):
        # Not used in auto-commit mode
        return

    def _confirm_discard_if_needed(self) -> bool:
        return True

    def on_export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV", "comms_resources.csv", "CSV Files (*.csv)")
        if not path:
            return
        all_cols = False
        mb = QtWidgets.QMessageBox(self)
        mb.setWindowTitle("Export Options")
        mb.setText("Export currently visible columns only?")
        yes = mb.addButton("Visible Only", QtWidgets.QMessageBox.AcceptRole)
        allb = mb.addButton("All Columns", QtWidgets.QMessageBox.ActionRole)
        cancel = mb.addButton(QtWidgets.QMessageBox.Cancel)
        mb.exec()
        if mb.clickedButton() is cancel:
            return
        if mb.clickedButton() is allb:
            all_cols = True
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                cols = []
                for i, (name, label, _req, _ed, _vis) in enumerate(COLUMNS):
                    if name == "id":
                        continue
                    idx = self.col_index.get(name, -1)
                    if idx < 0:
                        continue
                    if all_cols or not self.table.isColumnHidden(idx):
                        cols.append((idx, name, label))
                writer.writerow([label for _i, _n, label in cols])
                for r in range(self.proxy.rowCount()):
                    row_vals = []
                    for i, name, _label in cols:
                        idx = self.proxy.index(r, i)
                        val = self.proxy.data(idx, QtCore.Qt.DisplayRole)
                        row_vals.append(val)
                    writer.writerow(row_vals)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(e))

    def on_import_csv(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            rows, headers = self._parse_csv_with_mapping(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Failed", f"Could not read CSV: {e}")
            return

        preview = QtWidgets.QDialog(self)
        preview.setWindowTitle("Import Preview")
        layout = QtWidgets.QVBoxLayout(preview)
        info = QtWidgets.QLabel(f"Rows: {len(rows)}")
        layout.addWidget(info)
        table = QtWidgets.QTableWidget()
        layout.addWidget(table)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels([h[1] for h in headers])
        table.setRowCount(min(200, len(rows)))
        for r in range(min(200, len(rows))):
            for c, (key, _label) in enumerate(headers):
                item = QtWidgets.QTableWidgetItem(str(rows[r].get(key, "")))
                table.setItem(r, c, item)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(preview.accept)
        buttons.rejected.connect(preview.reject)
        if preview.exec() != QtWidgets.QDialog.Accepted:
            return

        inserted = updated = skipped = 0
        reasons: List[str] = []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("BEGIN")
            for payload in rows:
                err = self._validate(payload)
                if err:
                    skipped += 1
                    reasons.append(f"Skip '{payload.get('channel_name','')}' - {err}")
                    continue
                name = payload.get("channel_name")
                cur = conn.execute(
                    f"SELECT id FROM {TABLE_NAME} WHERE lower(channel_name)=lower(?)",
                    (name,),
                )
                row = cur.fetchone()
                if row:
                    fields = [k for k in payload.keys() if k in COL_INDEX and k != "id"]
                    set_clause = ",".join([f"{k}=?" for k in fields])
                    values = [payload[k] for k in fields]
                    values.append(row[0])
                    conn.execute(
                        f"UPDATE {TABLE_NAME} SET {set_clause} WHERE id=?",
                        values,
                    )
                    updated += 1
                else:
                    fields = [k for k in payload.keys() if k in COL_INDEX and k != "id"]
                    placeholders = ",".join(["?" for _ in fields])
                    conn.execute(
                        f"INSERT INTO {TABLE_NAME} ({','.join(fields)}) VALUES ({placeholders})",
                        [payload[k] for k in fields],
                    )
                    inserted += 1
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            QtWidgets.QMessageBox.critical(self, "Import Failed", str(e))
            return
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.model.select()
        self.channelsChanged.emit()

        summary = QtWidgets.QMessageBox(self)
        summary.setWindowTitle("Import Summary")
        summary.setIcon(QtWidgets.QMessageBox.Information)
        summary.setText(f"Inserted: {inserted}\nUpdated: {updated}\nSkipped: {skipped}")
        if reasons:
            details = "\n".join(reasons[:50])
            summary.setDetailedText(details)
        summary.exec()

    def _parse_csv_with_mapping(self, path: str) -> Tuple[List[Dict[str, object]], List[Tuple[str, str]]]:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers_in = reader.fieldnames or []
            # Build mapping in the order of CSV headers
            mapped: List[Tuple[str, str]] = []
            seen: set[str] = set()
            for hdr in headers_in:
                norm = normalize_row_for_db({hdr: hdr})
                # Take the first key that maps from this header
                key = next(iter(norm.keys()), None)
                if key and key in COL_INDEX and key != "id" and key not in seen:
                    label = next(lbl for k, lbl, *_ in COLUMNS if k == key)
                    mapped.append((key, label))
                    seen.add(key)
            rows: List[Dict[str, object]] = []
            for row in reader:
                payload = normalize_row_for_db(row)
                rows.append(payload)
        return rows, mapped

    def _settings(self) -> QtCore.QSettings:
        return QtCore.QSettings(APP_ORG, APP_NAME)

    def _restore_ui_state(self):
        s = self._settings()
        geom = s.value("comms_editor/geometry")
        if geom:
            self.restoreGeometry(geom)
        header = s.value("comms_editor/header_state")
        if header:
            self.table.horizontalHeader().restoreState(header)
        hidden = s.value("comms_editor/hidden_cols", [])
        if hidden is None:
            hidden = []
        # hidden may be a legacy list of ints or new list of field names; leave as-is
        # Support legacy int-based hidden list by mapping to names
        hidden_names: List[str] = []
        if hidden and all(isinstance(x, int) for x in hidden):
            for i, (name, _label, _req, _ed, _vis) in enumerate(COLUMNS):
                if i in hidden and name != 'id':
                    hidden_names.append(name)
        elif hidden and all(isinstance(x, str) for x in hidden):
            hidden_names = [x for x in hidden if x in self.col_index and x != 'id']

        for name, _label, _req, _ed, _vis in COLUMNS:
            if name == 'id':
                continue
            idx = self.col_index.get(name, -1)
            if idx < 0:
                continue
            hide = name in hidden_names
            self.table.setColumnHidden(idx, hide)
            act = self.column_actions.get(name)
            if act:
                act.blockSignals(True)
                act.setChecked(not hide)
                act.blockSignals(False)

    def _save_ui_state(self):
        s = self._settings()
        s.setValue("comms_editor/geometry", self.saveGeometry())
        s.setValue("comms_editor/header_state", self.table.horizontalHeader().saveState())
        # Persist hidden using field names for stability
        hidden_names: List[str] = []
        for name, _label, _req, _ed, _vis in COLUMNS:
            idx = self.col_index.get(name, -1)
            if name != 'id' and idx >= 0 and self.table.isColumnHidden(idx):
                hidden_names.append(name)
        s.setValue('comms_editor/hidden_cols', hidden_names)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Auto-commit mode: just persist UI state
        self._save_ui_state()
        super().closeEvent(event)

def launch_comms_resource_editor(parent: Optional[QtWidgets.QWidget] = None) -> "CommsResourceEditor":
    widget = CommsResourceEditor(DEFAULT_DB_PATH, parent)
    widget.show()
    return widget


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName(APP_ORG)
    app.setApplicationName(APP_NAME)
    editor = CommsResourceEditor(DEFAULT_DB_PATH)
    editor.resize(1100, 700)
    editor.show()
    sys.exit(app.exec())







