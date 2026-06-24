"""Equipment master catalog editor — MongoDB-backed via API.

Implements ``Design Documents/edit_window_style_guide.md``: card shell, header
with Add/Delete/Import/Export, filter bar with empty states, condition pill
column, pagination footer, import wizard, and export dialog with async export.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QStyle,
    QTableView,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from notifications.models import Notification
from notifications.services import get_notifier
from utils.edit_window_kit import (
    ExportDialog,
    FieldSpec,
    ImportWizard,
    PillDelegate,
    PaginationControls,
    run_async,
    write_export_file,
)
from utils.itemview_delegates import RowOutlineSelectionDelegate

log = logging.getLogger(__name__)

_BASE = "/api/master/equipment"

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

CONDITION_COLORS: dict[str, tuple[str, str]] = {
    "serviceable": ("#2e7d32", "#ffffff"),
    "needs repair": ("#ef6c00", "#ffffff"),
    "out of service": ("#c62828", "#ffffff"),
    "unknown": ("#757575", "#ffffff"),
}

FIELDS: list[FieldSpec] = [
    FieldSpec("name", "Name", required=True),
    FieldSpec("type", "Type"),
    FieldSpec("id_number", "ID Number"),
    FieldSpec("serial_number", "Serial Number"),
    FieldSpec("condition", "Condition"),
    FieldSpec("notes", "Notes"),
]
_FIELD_LABELS = {spec.key: spec.label for spec in FIELDS}
_COLUMN_KEYS = [spec.key for spec in FIELDS]


def _api():
    from utils.api_client import api_client
    return api_client


class EquipmentTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = []

    def set_rows(self, rows: List[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(_COLUMN_KEYS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _FIELD_LABELS[_COLUMN_KEYS[section]]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = _COLUMN_KEYS[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row.get(key) or "")
        return None

    def record_at(self, row: int) -> Optional[Dict[str, Any]]:
        return dict(self._rows[row]) if 0 <= row < len(self._rows) else None


class EquipmentEditDialog(QDialog):
    def __init__(self, record: Optional[Dict[str, Any]] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Equipment" if record is None else "Edit Equipment")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.e_name = QLineEdit()
        self.e_type = QComboBox()
        self.e_type.addItems([""] + list(EQUIPMENT_TYPES))
        self.e_id_number = QLineEdit()
        self.e_serial = QLineEdit()
        self.e_condition = QComboBox()
        self.e_condition.addItems(list(CONDITION_OPTIONS))
        self.e_notes = QTextEdit()
        self.e_notes.setFixedHeight(64)

        form.addRow("Name *", self.e_name)
        form.addRow("Type", self.e_type)
        form.addRow("ID Number", self.e_id_number)
        form.addRow("Serial Number", self.e_serial)
        form.addRow("Condition", self.e_condition)
        form.addRow("Notes", self.e_notes)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if record:
            self._load(record)

    def _load(self, r: Dict[str, Any]) -> None:
        self.e_name.setText(str(r.get("name") or ""))
        i = self.e_type.findText(str(r.get("type") or ""))
        self.e_type.setCurrentIndex(i if i >= 0 else 0)
        self.e_id_number.setText(str(r.get("id_number") or ""))
        self.e_serial.setText(str(r.get("serial_number") or ""))
        i = self.e_condition.findText(str(r.get("condition") or ""))
        self.e_condition.setCurrentIndex(i if i >= 0 else 0)
        self.e_notes.setPlainText(str(r.get("notes") or ""))

    def _on_accept(self) -> None:
        if not self.e_name.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        self.accept()

    def payload(self) -> Dict[str, Any]:
        return {
            "name": self.e_name.text().strip(),
            "type": self.e_type.currentText() or None,
            "id_number": self.e_id_number.text().strip() or None,
            "serial_number": self.e_serial.text().strip() or None,
            "condition": self.e_condition.currentText() or None,
            "notes": self.e_notes.toPlainText().strip() or None,
        }


class EquipmentEditPanel(QWidget):
    """Master equipment catalog editor (MongoDB-backed)."""

    def __init__(self, db_path=None, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Equipment")
        self.resize(960, 620)
        self._notifier = get_notifier()
        self._all_rows: List[Dict[str, Any]] = []
        self._filtered_rows: List[Dict[str, Any]] = []
        self._page = 1
        self._page_size = 20
        self._search_text = ""

        self._build_ui()
        self.refresh()

    # ----- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        card = QFrame(self)
        card.setObjectName("equipmentCard")
        card.setStyleSheet(
            """
            #equipmentCard {
                border-radius: 16px;
                background: palette(Base);
                border: 1px solid palette(Midlight);
            }
            QTableView {
                border: none;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Equipment")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)

        self.add_button = QPushButton("Add")
        self.add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setToolTip("Add equipment")
        header.addWidget(self.add_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setToolTip("Delete the selected equipment")
        self.delete_button.setEnabled(False)
        header.addWidget(self.delete_button)

        self.import_button = QPushButton("Import")
        self.import_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.setToolTip("Import equipment from CSV/XLSX")
        header.addWidget(self.import_button)

        self.export_button = QPushButton("Export")
        self.export_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.setToolTip("Export equipment")
        header.addWidget(self.export_button)

        card_layout.addLayout(header)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search equipment…")
        self.search_edit.setClearButtonEnabled(True)
        filter_bar.addWidget(self.search_edit, stretch=2)

        self.reset_button = QToolButton()
        self.reset_button.setText("Reset filters")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setStyleSheet("QToolButton { text-decoration: underline; border: none; padding: 4px; }")
        self.reset_button.hide()
        filter_bar.addWidget(self.reset_button)
        filter_bar.addStretch(1)
        card_layout.addLayout(filter_bar)

        # Error banner
        self.error_banner = QFrame()
        self.error_banner.setObjectName("equipmentErrorBanner")
        self.error_banner.setStyleSheet(
            """
            #equipmentErrorBanner {
                background: #fdecea;
                border-radius: 8px;
                border: 1px solid #f5c6cb;
            }
            """
        )
        self.error_banner.hide()
        error_layout = QHBoxLayout(self.error_banner)
        error_layout.setContentsMargins(12, 8, 12, 8)
        self.error_label = QLabel("Failed to load data.")
        self.error_label.setStyleSheet("color: #b71c1c;")
        error_layout.addWidget(self.error_label, stretch=1)
        self.retry_button = QPushButton("Retry")
        error_layout.addWidget(self.retry_button)
        card_layout.addWidget(self.error_banner)

        # Table + empty states
        self.model = EquipmentTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self._sel_delegate = RowOutlineSelectionDelegate(self.table, QColor("#FFFFFF"))
        self.table.setItemDelegate(self._sel_delegate)
        self.table.setItemDelegateForColumn(
            _COLUMN_KEYS.index("condition"), PillDelegate(self.table, CONDITION_COLORS)
        )
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionsClickable(True)

        self.table_stack = QStackedLayout()
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)
        self.table_stack.addWidget(table_container)

        self.no_results_widget = QWidget()
        nr_layout = QVBoxLayout(self.no_results_widget)
        nr_layout.addStretch(1)
        nr_message = QLabel("No equipment matches your filters.")
        nr_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nr_message.setStyleSheet("font-size: 16px; color: palette(Mid);")
        nr_layout.addWidget(nr_message)
        clear_btn = QPushButton("Clear filters")
        clear_btn.setFixedWidth(160)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._on_reset_filters)
        nr_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        nr_layout.addStretch(1)
        self.table_stack.addWidget(self.no_results_widget)

        self.first_run_widget = QWidget()
        fr_layout = QVBoxLayout(self.first_run_widget)
        fr_layout.addStretch(1)
        fr_message = QLabel("Add your first piece of equipment.")
        fr_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fr_message.setStyleSheet("font-size: 16px; color: palette(Mid);")
        fr_layout.addWidget(fr_message)
        fr_add_button = QPushButton("Add equipment")
        fr_add_button.setFixedWidth(160)
        fr_add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        fr_add_button.clicked.connect(self._on_add)
        fr_layout.addWidget(fr_add_button, alignment=Qt.AlignmentFlag.AlignCenter)
        fr_layout.addStretch(1)
        self.table_stack.addWidget(self.first_run_widget)

        card_layout.addLayout(self.table_stack, stretch=1)

        self.pagination = PaginationControls(self)
        card_layout.addWidget(self.pagination)

        outer.addWidget(card)

        # Signals
        self._debounce = QTimer(self)
        self._debounce.setInterval(250)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._apply_filters)
        self.search_edit.textChanged.connect(self._on_search_text)
        self.reset_button.clicked.connect(self._on_reset_filters)

        self.add_button.clicked.connect(self._on_add)
        self.delete_button.clicked.connect(self._on_delete)
        self.import_button.clicked.connect(self._on_import)
        self.export_button.clicked.connect(self._on_export)
        self.retry_button.clicked.connect(self.refresh)
        self.table.activated.connect(lambda _: self._on_edit_selected())

        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._update_buttons)

        self.pagination.pageRequested.connect(self._on_page_requested)
        self.pagination.pageSizeChanged.connect(self._on_page_size_changed)

        self.search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.search_shortcut.activated.connect(self.search_edit.setFocus)

    # ----- Data loading -----------------------------------------------------
    def refresh(self) -> None:
        try:
            rows = _api().get(_BASE) or []
        except Exception as exc:
            log.warning("Failed to load equipment: %s", exc)
            self._show_error(f"Unable to load equipment: {exc}")
            return
        self._hide_error()
        self._all_rows = rows
        self._apply_filters()

    def _apply_filters(self) -> None:
        needle = self._search_text.strip().lower()
        if needle:
            self._filtered_rows = [
                r for r in self._all_rows
                if needle in " ".join(str(r.get(k) or "") for k in _COLUMN_KEYS).lower()
            ]
        else:
            self._filtered_rows = list(self._all_rows)
        self.reset_button.setVisible(bool(needle))
        self._page = 1
        self._render_page()

    def _render_page(self) -> None:
        total = len(self._filtered_rows)
        max_page = max(1, -(-total // self._page_size)) if self._page_size else 1
        self._page = min(max(1, self._page), max_page)
        start = (self._page - 1) * self._page_size
        page_rows = self._filtered_rows[start:start + self._page_size]
        self.model.set_rows(page_rows)
        self.pagination.update_state(total=total, page=self._page, page_size=self._page_size)

        if total == 0:
            if self._search_text.strip():
                self.table_stack.setCurrentWidget(self.no_results_widget)
            else:
                self.table_stack.setCurrentWidget(self.first_run_widget)
        else:
            self.table_stack.setCurrentIndex(0)
        self._update_buttons()

    def _on_search_text(self, text: str) -> None:
        self._search_text = text
        self._debounce.start()

    def _on_reset_filters(self) -> None:
        self.search_edit.clear()
        self._search_text = ""
        self._apply_filters()

    def _on_page_requested(self, page: int) -> None:
        self._page = page
        self._render_page()

    def _on_page_size_changed(self, page_size: int) -> None:
        self._page_size = page_size
        self._page = 1
        self._render_page()

    # ----- Selection ---------------------------------------------------------
    def _selected_row(self) -> Optional[Dict[str, Any]]:
        idxs = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not idxs:
            return None
        return self.model.record_at(idxs[0].row())

    def _update_buttons(self) -> None:
        self.delete_button.setEnabled(self._selected_row() is not None)

    # ----- Error banner --------------------------------------------------
    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_banner.show()

    def _hide_error(self) -> None:
        self.error_banner.hide()

    # ----- Add / Edit / Delete -------------------------------------------
    def _on_add(self) -> None:
        dlg = EquipmentEditDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            _api().post(_BASE, json=dlg.payload())
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to create equipment:\n{exc}")
            return
        self.refresh()
        self._show_toast("Equipment saved", "Equipment added successfully.")

    def _on_edit_selected(self) -> None:
        rec = self._selected_row()
        if rec is None:
            return
        dlg = EquipmentEditDialog(record=rec, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        eq_id = rec.get("id")
        if eq_id is None:
            return
        try:
            _api().patch(f"{_BASE}/{eq_id}", json=dlg.payload())
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to update equipment:\n{exc}")
            return
        self.refresh()
        self._show_toast("Equipment saved", f"Equipment '{dlg.payload().get('name')}' updated.")

    def _on_delete(self) -> None:
        rec = self._selected_row()
        if rec is None:
            return
        name = rec.get("name") or "this item"
        if QMessageBox.question(
            self, "Confirm Delete", f"Delete '{name}'? This cannot be undone."
        ) != QMessageBox.StandardButton.Yes:
            return
        eq_id = rec.get("id")
        if eq_id is None:
            return
        try:
            _api().delete(f"{_BASE}/{eq_id}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to delete equipment:\n{exc}")
            return
        self.refresh()
        self._show_toast("Equipment deleted", f"'{name}' was deleted.")

    # ----- Import ----------------------------------------------------------
    def _on_import(self) -> None:
        def _import_row(payload: Dict[str, Any]) -> Any:
            return _api().post(_BASE, json=payload)

        wizard = ImportWizard(fields=FIELDS, import_row=_import_row, title="Import Equipment", parent=self)
        result = wizard.exec()
        created = wizard.created_records()
        errors = wizard.error_count()
        if result == QDialog.DialogCode.Accepted and (created or errors):
            self.refresh()
            if created and errors:
                self._show_toast(
                    "Import complete", f"{len(created)} items imported with {errors} errors.", severity="warning"
                )
            elif created:
                self._show_toast("Import complete", f"Imported {len(created)} items.")
            elif errors:
                self._show_toast("Import issues", "No rows were imported. Check the error report.", severity="warning")

    # ----- Export ------------------------------------------------------------
    def _on_export(self) -> None:
        selection_model = self.table.selectionModel()
        allow_selected = bool(selection_model and selection_model.hasSelection())
        dialog = ExportDialog(fields=FIELDS, allow_selected=allow_selected, title="Export Equipment", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        scope = dialog.selected_scope()
        file_format = dialog.selected_format()
        fields = dialog.selected_fields()

        if scope == "selected":
            rec = self._selected_row()
            if rec is None:
                QMessageBox.information(self, "No selection", "Select a row to export or choose a different scope.")
                return
            rows = [rec]
        elif scope == "filters":
            rows = list(self._filtered_rows)
        else:
            rows = list(self._all_rows)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path(tempfile.gettempdir()) / f"equipment-{scope}-{timestamp}.{file_format}"

        def _task() -> dict[str, Any]:
            write_export_file(path, rows, fields, _FIELD_LABELS, file_format)
            return {"path": str(path), "count": len(rows)}

        self.export_button.setEnabled(False)
        run_async(self, _task, self._on_export_done, self._on_export_failed)

    def _on_export_done(self, result: dict[str, Any]) -> None:
        self.export_button.setEnabled(True)
        message = f"{result.get('count', 0)} items exported. Saved to {result.get('path')}."
        self._show_toast("Export ready", message)
        QMessageBox.information(self, "Export ready", message)

    def _on_export_failed(self, message: str) -> None:
        self.export_button.setEnabled(True)
        self._show_toast("Export failed", message, severity="error")
        QMessageBox.critical(self, "Export failed", message)

    # ----- Toast helper ------------------------------------------------------
    def _show_toast(self, title: str, message: str, *, severity: str = "success") -> None:
        try:
            self._notifier.notify(
                Notification(
                    title=title,
                    message=message,
                    severity=severity if severity in {"info", "success", "warning", "error"} else "info",
                    source="Equipment",
                )
            )
        except Exception:
            pass
