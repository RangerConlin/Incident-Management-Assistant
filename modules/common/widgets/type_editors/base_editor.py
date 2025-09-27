from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSettings,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QBrush, QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ColumnSpec:
    key: str
    label: str


class LookupTableModel(QAbstractTableModel):
    def __init__(self, columns: List[ColumnSpec], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows: List[dict] = []
        palette = QApplication.instance().palette() if QApplication.instance() else None
        alt_color = palette.color(QPalette.AlternateBase) if palette else QColor("#dddddd")
        self._inactive_brush = QBrush(alt_color)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = self._columns[index.column()]
        key = column.key
        if role == Qt.DisplayRole:
            if key == "is_active":
                return ""
            value = row.get(key, "")
            return value
        if role == Qt.CheckStateRole and key == "is_active":
            return Qt.Checked if row.get("is_active", 1) else Qt.Unchecked
        if role == Qt.ToolTipRole:
            value = row.get(key)
            if isinstance(value, str) and value:
                return value
        if role == Qt.BackgroundRole and key == "is_active" and not row.get("is_active", 1):
            return self._inactive_brush
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section].label
        return section + 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore[override]
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if self._columns[index.column()].key == "is_active":
            flags |= Qt.ItemIsUserCheckable
        return flags

    def set_rows(self, rows: Iterable[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_data(self, row: int) -> dict:
        return self._rows[row]

    def row_for_id(self, record_id: int) -> Optional[int]:
        for idx, row in enumerate(self._rows):
            if row.get("id") == record_id:
                return idx
        return None


class LookupSortFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._filter_text: str = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_filter_text(self, text: str) -> None:
        self._filter_text = (text or "").strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self._filter_text:
            return True
        model = self.sourceModel()
        if not isinstance(model, LookupTableModel):
            return super().filterAcceptsRow(source_row, source_parent)
        row = model.row_data(source_row)
        for key in ("name", "description", "category", "default_priority"):
            value = row.get(key)
            if isinstance(value, str) and self._filter_text in value.lower():
                return True
        return False


class CopyableTableView(QTableView):
    def keyPressEvent(self, event):  # type: ignore[override]
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    def copy_selection(self) -> None:
        indexes = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not indexes:
            return
        indexes = sorted(indexes, key=lambda idx: (idx.row(), idx.column()))
        rows: dict[int, dict[int, str]] = {}
        for index in indexes:
            rows.setdefault(index.row(), {})[index.column()] = str(index.data() or "")
        lines: List[str] = []
        for row in sorted(rows.keys()):
            values = [rows[row].get(col, "") for col in range(self.model().columnCount())]
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(lines))


class BaseTypeEditorDialog(QWidget):
    window_title: str = ""
    settings_group: str = "TypeEditors/Base"
    columns: List[ColumnSpec] = []
    repository = None
    has_priority_field: bool = False

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle(self.window_title)
        self.setMinimumSize(800, 520)
        self._current_id: Optional[int] = None
        self._current_data: dict = {}
        self._dirty: bool = False

        self.repo = self.repository() if callable(self.repository) else self.repository
        if self.repo is None:
            raise RuntimeError("Repository is not configured for editor")

        self._build_ui()
        self._install_shortcuts()
        self._load_settings()
        self.refresh()

    # --- ui ---------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search name, description, category…")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self.search_edit)
        # Normalize placeholder text to ASCII ellipsis to avoid encoding artifacts
        self.search_edit.setPlaceholderText("Search name, description, category...")

        self.show_archived = QToolButton(self)
        self.show_archived.setText("Show Archived")
        self.show_archived.setCheckable(True)
        self.show_archived.toggled.connect(self._on_show_archived_toggled)
        toolbar.addWidget(self.show_archived)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.btn_import = QPushButton("Import CSV…", self)
        self.btn_import.clicked.connect(self._on_import)
        toolbar.addWidget(self.btn_import)
        # Normalize label to ASCII ellipsis
        self.btn_import.setText("Import CSV...")

        self.btn_export = QPushButton("Export CSV…", self)
        self.btn_export.clicked.connect(self._on_export)
        toolbar.addWidget(self.btn_export)
        # Normalize label to ASCII ellipsis
        self.btn_export.setText("Export CSV...")

        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.close)
        toolbar.addWidget(self.btn_close)

        layout.addLayout(toolbar)

        self.splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(self.splitter)

        table_container = QWidget(self.splitter)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.model = LookupTableModel(self.columns, self)
        self.proxy_model = LookupSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = CopyableTableView(table_container)
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        table_layout.addWidget(self.table)

        self.splitter.addWidget(table_container)

        self.form_group = QGroupBox("Details", self.splitter)
        form_layout = QVBoxLayout(self.form_group)
        form_layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.chk_active = QCheckBox("Active", self.form_group)
        form.addRow(self.chk_active)

        self.txt_name = QLineEdit(self.form_group)
        form.addRow("Name", self.txt_name)

        self.cbo_category = QComboBox(self.form_group)
        self.cbo_category.setEditable(True)
        form.addRow("Category", self.cbo_category)

        if self.has_priority_field:
            self.cbo_priority = QComboBox(self.form_group)
            self.cbo_priority.addItems(["Low", "Normal", "High", "Critical"])
            form.addRow("Default Priority", self.cbo_priority)
        else:
            self.cbo_priority = None

        self.txt_description = QPlainTextEdit(self.form_group)
        self.txt_description.setPlaceholderText("Description")
        form.addRow("Description", self.txt_description)

        form_layout.addLayout(form)

        button_bar = QHBoxLayout()
        button_bar.setSpacing(6)
        self.btn_new = QPushButton("New", self.form_group)
        self.btn_new.clicked.connect(self.new_record)
        button_bar.addWidget(self.btn_new)

        self.btn_save = QPushButton("Save", self.form_group)
        self.btn_save.clicked.connect(self.save_record)
        self.btn_save.setEnabled(False)
        button_bar.addWidget(self.btn_save)

        self.btn_delete = QPushButton("Archive", self.form_group)
        self.btn_delete.clicked.connect(self.archive_or_restore)
        self.btn_delete.setEnabled(False)
        button_bar.addWidget(self.btn_delete)

        self.btn_revert = QPushButton("Revert", self.form_group)
        self.btn_revert.clicked.connect(self.revert_changes)
        self.btn_revert.setEnabled(False)
        button_bar.addWidget(self.btn_revert)

        button_bar.addStretch()
        form_layout.addLayout(button_bar)

        self.splitter.addWidget(self.form_group)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

        self.chk_active.stateChanged.connect(self._mark_dirty)
        self.txt_name.textChanged.connect(self._mark_dirty)
        self.cbo_category.editTextChanged.connect(self._mark_dirty)
        self.txt_description.textChanged.connect(self._mark_dirty)
        if self.cbo_priority is not None:
            self.cbo_priority.currentTextChanged.connect(self._mark_dirty)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence.New, self, activated=self.new_record)
        QShortcut(QKeySequence.Save, self, activated=self.save_record)
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self.archive_or_restore)
        QShortcut(QKeySequence.StandardKey.Close, self, activated=self.close)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)

    # --- state ------------------------------------------------------------------
    def _load_settings(self) -> None:
        settings = QSettings()
        settings.beginGroup(self.settings_group)
        geometry = settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        splitter = settings.value("splitter")
        if splitter is not None:
            self.splitter.restoreState(splitter)
        column_widths = settings.value("columns")
        if isinstance(column_widths, list):
            for idx, width in enumerate(column_widths):
                try:
                    self.table.setColumnWidth(idx, int(width))
                except (TypeError, ValueError):
                    continue
        settings.endGroup()

    def _save_settings(self) -> None:
        settings = QSettings()
        settings.beginGroup(self.settings_group)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("splitter", self.splitter.saveState())
        settings.setValue("columns", [self.table.columnWidth(i) for i in range(self.table.model().columnCount())])
        settings.endGroup()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_settings()
        super().closeEvent(event)

    # --- data -------------------------------------------------------------------
    def refresh(self, preserve_id: Optional[int] = None) -> None:
        filter_text = self.search_edit.text()
        include_inactive = self.show_archived.isChecked()
        rows = self.repo.list(filter_text=filter_text, include_inactive=include_inactive)
        self.model.set_rows(rows)
        self.proxy_model.set_filter_text(filter_text)
        if preserve_id is not None:
            self._select_by_id(preserve_id)
        else:
            self.table.clearSelection()
        self._update_categories(rows)

    def _update_categories(self, rows: Iterable[dict]) -> None:
        categories = sorted({row.get("category", "").strip() for row in rows if row.get("category")})
        current_text = self.cbo_category.currentText()
        self.cbo_category.blockSignals(True)
        self.cbo_category.clear()
        self.cbo_category.addItems(categories)
        self.cbo_category.setEditText(current_text)
        self.cbo_category.blockSignals(False)

    def _select_by_id(self, record_id: int) -> None:
        source_row = self.model.row_for_id(record_id)
        if source_row is None:
            return
        proxy_index = self.proxy_model.mapFromSource(self.model.index(source_row, 0))
        if proxy_index.isValid():
            self.table.selectRow(proxy_index.row())
            self.table.scrollTo(proxy_index, QAbstractItemView.PositionAtCenter)

    # --- form handling ----------------------------------------------------------
    def new_record(self) -> None:
        self.table.clearSelection()
        self._load_record(self._empty_record())

    def revert_changes(self) -> None:
        if self._current_id is None:
            self._load_record(self._empty_record())
        else:
            record = self.repo.get(self._current_id)
            if record:
                self._load_record(record)

    def save_record(self) -> None:
        data = self._collect_form_data()
        if not data.get("name"):
            QMessageBox.warning(self, "Validation", "Name is required.")
            self.txt_name.setFocus()
            return
        if self.repo.exists_with_name(data["name"], exclude_id=self._current_id):
            QMessageBox.warning(self, "Duplicate", "A record with that name already exists.")
            return
        if self._current_id is None:
            new_id = self.repo.create(data)
            self._current_id = new_id
        else:
            self.repo.update(self._current_id, data)
        refreshed = self.repo.get(self._current_id) if self._current_id is not None else None
        if refreshed:
            self._load_record(refreshed)
            self.refresh(preserve_id=self._current_id)
        else:
            self.refresh()

    def archive_or_restore(self) -> None:
        if self._current_id is None:
            return
        is_active = bool(self._current_data.get("is_active", 1))
        if is_active:
            self.repo.soft_delete(self._current_id)
        else:
            self.repo.restore(self._current_id)
        record = self.repo.get(self._current_id)
        self._load_record(record if record else self._empty_record())
        self.refresh(preserve_id=self._current_id)

    def _collect_form_data(self) -> dict:
        data = {
            "name": self.txt_name.text(),
            "category": self.cbo_category.currentText(),
            "description": self.txt_description.toPlainText(),
            "is_active": 1 if self.chk_active.isChecked() else 0,
        }
        if self.cbo_priority is not None:
            data["default_priority"] = self.cbo_priority.currentText()
        return data

    def _empty_record(self) -> dict:
        record = {
            "id": None,
            "name": "",
            "category": "",
            "description": "",
            "is_active": 1,
        }
        if self.cbo_priority is not None:
            record["default_priority"] = "Normal"
        return record

    def _load_record(self, record: Optional[dict]) -> None:
        if record is None:
            record = self._empty_record()
        self._current_id = record.get("id")
        self._current_data = dict(record)
        self.chk_active.blockSignals(True)
        self.chk_active.setChecked(bool(record.get("is_active", 1)))
        self.chk_active.blockSignals(False)

        self.txt_name.blockSignals(True)
        self.txt_name.setText(record.get("name", ""))
        self.txt_name.blockSignals(False)

        self.cbo_category.blockSignals(True)
        text = record.get("category", "") or ""
        if text and text not in [self.cbo_category.itemText(i) for i in range(self.cbo_category.count())]:
            self.cbo_category.addItem(text)
        self.cbo_category.setCurrentText(text)
        self.cbo_category.blockSignals(False)

        if self.cbo_priority is not None:
            value = (record.get("default_priority") or "Normal").title()
            self.cbo_priority.blockSignals(True)
            self.cbo_priority.setCurrentText(value)
            self.cbo_priority.blockSignals(False)

        self.txt_description.blockSignals(True)
        self.txt_description.setPlainText(record.get("description", ""))
        self.txt_description.blockSignals(False)

        is_active = bool(record.get("is_active", 1))
        self.btn_delete.setText("Archive" if is_active else "Restore")
        self.btn_delete.setEnabled(self._current_id is not None)
        self._set_dirty(False)

    # --- events -----------------------------------------------------------------
    def _on_search_text_changed(self, text: str) -> None:
        self.refresh(preserve_id=self._current_id)

    def _on_show_archived_toggled(self, _: bool) -> None:
        self.refresh(preserve_id=self._current_id)

    def _on_selection_changed(self, *_args) -> None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return
        index = selected[0]
        source_index = self.proxy_model.mapToSource(index)
        record = self.model.row_data(source_index.row())
        self._load_record(record)

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        self._on_selection_changed()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", str(Path.home()), "CSV Files (*.csv)")
        if not path:
            return
        result = self.repo.import_csv(Path(path))
        message_lines = []
        if result.inserted:
            message_lines.append(f"Imported {result.inserted} record(s).")
        if result.skipped_duplicates:
            message_lines.append(
                "Skipped duplicates: " + ", ".join(result.skipped_duplicates[:10]) + (
                    "…" if len(result.skipped_duplicates) > 10 else ""
                )
            )
        if result.errors:
            message_lines.append("Errors:\n" + "\n".join(result.errors))
        if not message_lines:
            message_lines.append("No records were imported.")
        QMessageBox.information(self, "Import", "\n".join(message_lines))
        self.refresh()

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", str(Path.home() / "type_export.csv"), "CSV Files (*.csv)")
        if not path:
            return
        rows = self._gather_filtered_rows()
        final_path = self.repo.export_csv(Path(path), rows)
        QMessageBox.information(self, "Export", f"Exported {len(rows)} record(s) to {final_path}.")

    def _gather_filtered_rows(self) -> List[dict]:
        rows: List[dict] = []
        for proxy_row in range(self.proxy_model.rowCount()):
            src_index = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
            rows.append(self.model.row_data(src_index.row()))
        return rows

    def _mark_dirty(self) -> None:
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self.btn_save.setEnabled(dirty)
        self.btn_revert.setEnabled(dirty or self._current_id is not None)
