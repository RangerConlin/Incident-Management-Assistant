"""Full-screen editor for the array_sources section of binding_catalog.json."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QAbstractItemView,
    QComboBox,
)

from .dialogs.ArraySourceDialog import ArraySourceDialog, _COL_TYPES, _slugify

_CATALOG_PATH = Path(__file__).resolve().parents[3] / "forms" / "binding_catalog.json"


def _load_catalog() -> dict:
    try:
        return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_catalog(raw: dict) -> None:
    _CATALOG_PATH.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )


class ArrayCatalogEditorWindow(QMainWindow):
    """Browse and edit all array sources in binding_catalog.json."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Array Catalog Editor")
        self.resize(1000, 680)

        self._raw: dict = {}
        self._sources: list[dict] = []
        self._current_idx: int = -1
        self._dirty = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left sidebar ──────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background: #1a1a2e;")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(8, 8, 8, 8)
        sb_layout.setSpacing(6)

        sb_layout.addWidget(QLabel("Array Sources"))

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter…")
        self._search_edit.textChanged.connect(self._on_search)
        sb_layout.addWidget(self._search_edit)

        self._source_list = QListWidget()
        self._source_list.currentRowChanged.connect(self._on_source_selected)
        sb_layout.addWidget(self._source_list, 1)

        add_btn = QPushButton("+ New Array Source")
        add_btn.clicked.connect(self._on_add_source)
        sb_layout.addWidget(add_btn)

        root.addWidget(sidebar)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # ── Right detail panel ────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 12, 16, 12)
        right_layout.setSpacing(8)

        # Header
        hdr_row = QHBoxLayout()
        self._detail_title = QLabel("<i>Select an array source</i>")
        self._detail_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        hdr_row.addWidget(self._detail_title, 1)
        self._edit_btn = QPushButton("Edit Metadata…")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit_metadata)
        hdr_row.addWidget(self._edit_btn)
        self._delete_btn = QPushButton("Delete Source")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setStyleSheet("color: #c0392b;")
        self._delete_btn.clicked.connect(self._on_delete_source)
        hdr_row.addWidget(self._delete_btn)
        right_layout.addLayout(hdr_row)

        self._meta_label = QLabel()
        self._meta_label.setStyleSheet("font-size: 11px; color: #888;")
        right_layout.addWidget(self._meta_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(sep2)

        # Columns section
        col_hdr = QHBoxLayout()
        col_hdr.addWidget(QLabel("Columns"))
        col_hdr.addStretch()
        self._add_col_btn = QPushButton("+ Add Column")
        self._add_col_btn.setEnabled(False)
        self._add_col_btn.clicked.connect(self._on_add_column)
        col_hdr.addWidget(self._add_col_btn)
        right_layout.addLayout(col_hdr)

        self._col_table = QTableWidget(0, 5)
        self._col_table.setHorizontalHeaderLabels(
            ["ID / Source Key", "Label", "Data Field", "Type", ""]
        )
        hh = self._col_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._col_table.verticalHeader().setVisible(False)
        self._col_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._col_table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        self._col_table.itemChanged.connect(self._on_col_table_edited)
        right_layout.addWidget(self._col_table, 1)

        col_note = QLabel(
            "ID — used as the col_pattern key and data lookup key. "
            "Data Field — only needed if it differs from ID. "
            "Checkbox columns output X or blank based on truthiness."
        )
        col_note.setWordWrap(True)
        col_note.setStyleSheet("font-size: 11px; color: #666;")
        right_layout.addWidget(col_note)

        # Save bar
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("Save Catalog")
        self._save_btn.setEnabled(False)
        self._save_btn.setFixedWidth(120)
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        right_layout.addLayout(save_row)

        root.addWidget(right, 1)

        self.setStatusBar(QStatusBar())
        self._load()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._raw = _load_catalog()
        self._sources = self._raw.get("array_sources", [])
        self._rebuild_list()

    def _on_save(self) -> None:
        self._flush_col_table()
        self._raw["array_sources"] = self._sources
        try:
            _save_catalog(self._raw)
            self._dirty = False
            self._save_btn.setEnabled(False)
            self.statusBar().showMessage("Saved.", 2000)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._save_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def _rebuild_list(self, preserve_selection: str | None = None) -> None:
        filter_text = self._search_edit.text().lower()
        self._source_list.blockSignals(True)
        self._source_list.clear()
        for i, src in enumerate(self._sources):
            label = src.get("label", src.get("id", ""))
            if filter_text and filter_text not in label.lower():
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._source_list.addItem(item)
            if preserve_selection and src.get("id") == preserve_selection:
                self._source_list.setCurrentItem(item)
        self._source_list.blockSignals(False)
        if preserve_selection is None and self._source_list.count() > 0:
            self._source_list.setCurrentRow(0)

    def _on_search(self) -> None:
        current_id = ""
        if self._current_idx >= 0 and self._current_idx < len(self._sources):
            current_id = self._sources[self._current_idx].get("id", "")
        self._rebuild_list(preserve_selection=current_id or None)

    def _on_source_selected(self, _row: int) -> None:
        item = self._source_list.currentItem()
        if not item:
            self._current_idx = -1
            self._show_empty()
            return
        self._current_idx = item.data(Qt.ItemDataRole.UserRole)
        self._show_source(self._sources[self._current_idx])

    def _show_empty(self) -> None:
        self._detail_title.setText("<i>Select an array source</i>")
        self._meta_label.clear()
        self._edit_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._add_col_btn.setEnabled(False)
        self._col_table.blockSignals(True)
        self._col_table.setRowCount(0)
        self._col_table.blockSignals(False)

    def _show_source(self, src: dict) -> None:
        self._detail_title.setText(src.get("label", src.get("id", "")))
        dk = src.get("data_key", src.get("id", ""))
        self._meta_label.setText(
            f"id: {src.get('id', '')}   data_key: {dk}   "
            f"chars/row: {src.get('chars_per_row', 80)}"
        )
        self._edit_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        self._add_col_btn.setEnabled(True)
        self._populate_col_table(src.get("columns", []))

    # ------------------------------------------------------------------
    # Columns table
    # ------------------------------------------------------------------

    def _populate_col_table(self, columns: list[dict]) -> None:
        self._col_table.blockSignals(True)
        self._col_table.setRowCount(0)
        for col in columns:
            self._append_col_row(col)
        self._col_table.blockSignals(False)
        self._rebind_remove_buttons()

    def _append_col_row(self, col: dict) -> None:
        col_id     = col.get("id", col.get("source_key", ""))
        col_label  = col.get("label", "")
        source_key = col.get("source_key", "")
        col_type   = col.get("type", "text")

        row = self._col_table.rowCount()
        self._col_table.insertRow(row)
        self._col_table.setItem(row, 0, QTableWidgetItem(col_id))
        self._col_table.setItem(row, 1, QTableWidgetItem(col_label))
        self._col_table.setItem(row, 2, QTableWidgetItem(source_key if source_key != col_id else ""))

        type_combo = QComboBox()
        for lbl, val in _COL_TYPES:
            type_combo.addItem(lbl, val)
        idx = type_combo.findData(col_type)
        type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        type_combo.currentIndexChanged.connect(self._on_type_combo_changed)
        self._col_table.setCellWidget(row, 3, type_combo)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedHeight(24)
        self._col_table.setCellWidget(row, 4, remove_btn)

    def _rebind_remove_buttons(self) -> None:
        for r in range(self._col_table.rowCount()):
            btn = self._col_table.cellWidget(r, 4)
            if btn:
                try:
                    btn.clicked.disconnect()
                except RuntimeError:
                    pass
                btn.clicked.connect(lambda _=False, row=r: self._on_remove_column(row))

    def _on_add_column(self) -> None:
        if self._current_idx < 0:
            return
        self._col_table.blockSignals(True)
        self._append_col_row({"id": "", "label": "", "source_key": "", "type": "text"})
        self._col_table.blockSignals(False)
        self._rebind_remove_buttons()
        self._flush_col_table()

    def _on_remove_column(self, row: int) -> None:
        self._col_table.removeRow(row)
        self._rebind_remove_buttons()
        self._flush_col_table()

    def _on_col_table_edited(self, _item) -> None:
        self._flush_col_table()

    def _on_type_combo_changed(self) -> None:
        self._flush_col_table()

    def _flush_col_table(self) -> None:
        """Write the current table state back into self._sources."""
        if self._current_idx < 0 or self._current_idx >= len(self._sources):
            return
        cols = []
        for r in range(self._col_table.rowCount()):
            def _cell(c):
                it = self._col_table.item(r, c)
                return it.text().strip() if it else ""
            col_id    = _cell(0)
            col_label = _cell(1)
            sk        = _cell(2) or col_id
            type_w    = self._col_table.cellWidget(r, 3)
            col_type  = type_w.currentData() if type_w else "text"
            entry = {"id": col_id, "label": col_label, "source_key": sk}
            if col_type != "text":
                entry["type"] = col_type
            cols.append(entry)
        self._sources[self._current_idx]["columns"] = cols
        self._mark_dirty()

    # ------------------------------------------------------------------
    # Source CRUD
    # ------------------------------------------------------------------

    def _on_add_source(self) -> None:
        dlg = ArraySourceDialog(parent=self)
        if dlg.exec() != ArraySourceDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        if any(s.get("id") == data["id"] for s in self._sources):
            QMessageBox.warning(self, "Duplicate", f"Array source '{data['id']}' already exists.")
            return
        self._sources.append(data)
        self._mark_dirty()
        self._rebuild_list(preserve_selection=data["id"])

    def _on_edit_metadata(self) -> None:
        if self._current_idx < 0:
            return
        src = self._sources[self._current_idx]
        dlg = ArraySourceDialog(existing=src, parent=self)
        if dlg.exec() != ArraySourceDialog.DialogCode.Accepted:
            return
        updated = dlg.result_data()
        if not updated:
            return
        # Preserve columns from the live table (which may have unsaved edits)
        updated["columns"] = src.get("columns", [])
        self._sources[self._current_idx] = updated
        self._mark_dirty()
        self._rebuild_list(preserve_selection=updated["id"])

    def _on_delete_source(self) -> None:
        if self._current_idx < 0:
            return
        src = self._sources[self._current_idx]
        label = src.get("label", src.get("id", ""))
        reply = QMessageBox.question(
            self, "Delete Array Source",
            f"Delete '{label}'? This cannot be undone and will break any "
            f"form mappings that reference it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._sources.pop(self._current_idx)
        self._current_idx = -1
        self._mark_dirty()
        self._rebuild_list()

    # ------------------------------------------------------------------
    # Close guard
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        super().closeEvent(event)
