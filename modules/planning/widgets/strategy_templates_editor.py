"""Modeless editor for master Strategy Templates (suggested ICS-204 work
assignments). Mirrors objectives_editor.py's structure but trimmed down —
strategy templates have fewer fields and don't need the tag-chip UI.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.planning.models.objectives_dao import ObjectivesDAO
from modules.planning.models.strategy_templates_dao import (
    ASSIGNMENT_KIND_VALUES,
    PRIORITY_VALUES,
    StrategyTemplate,
    StrategyTemplatesDAO,
)

SETTINGS_GROUP = "Modules/Planning/StrategyTemplatesEditor"


class StrategyTemplatesEditor(QMainWindow):
    """Modeless editor window for managing strategy templates."""

    window_closed = Signal()

    def __init__(self, dao: Optional[StrategyTemplatesDAO] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Strategy Templates")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMinimumSize(820, 480)

        self._dao = dao or StrategyTemplatesDAO()
        self._objectives_dao = ObjectivesDAO()
        self._current: Optional[StrategyTemplate] = None
        self._templates: list[StrategyTemplate] = []
        self._settings = QSettings()

        self._build_ui()
        self._restore_state()
        self._reload()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        self._splitter = splitter

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search title/description…")
        self._search_edit.returnPressed.connect(self._reload)
        search_row.addWidget(self._search_edit)
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self._on_new_clicked)
        search_row.addWidget(new_btn)
        table_layout.addLayout(search_row)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Title", "Objective Template", "Assignment Kind", "Priority"])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        table_layout.addWidget(self._table)

        splitter.addWidget(table_container)

        self._detail_panel = self._build_detail_panel()
        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)

        form_group = QGroupBox("Strategy Template")
        form = QGridLayout(form_group)

        row = 0
        form.addWidget(QLabel("Title"), row, 0)
        self._title_input = QLineEdit()
        form.addWidget(self._title_input, row, 1)

        row += 1
        form.addWidget(QLabel("Suggested for Objective"), row, 0)
        self._objective_combo = QComboBox()
        form.addWidget(self._objective_combo, row, 1)

        row += 1
        form.addWidget(QLabel("Assignment Kind"), row, 0)
        self._kind_combo = QComboBox()
        self._kind_combo.addItems(ASSIGNMENT_KIND_VALUES)
        form.addWidget(self._kind_combo, row, 1)

        row += 1
        form.addWidget(QLabel("Priority"), row, 0)
        self._priority_combo = QComboBox()
        self._priority_combo.addItems(PRIORITY_VALUES)
        form.addWidget(self._priority_combo, row, 1)

        row += 1
        form.addWidget(QLabel("Branch"), row, 0)
        self._branch_input = QLineEdit()
        form.addWidget(self._branch_input, row, 1)

        row += 1
        form.addWidget(QLabel("Division/Group"), row, 0)
        self._division_input = QLineEdit()
        form.addWidget(self._division_input, row, 1)

        row += 1
        form.addWidget(QLabel("Tags (comma separated)"), row, 0)
        self._tags_input = QLineEdit()
        form.addWidget(self._tags_input, row, 1)

        row += 1
        form.addWidget(QLabel("Description"), row, 0, Qt.AlignTop)
        self._description_edit = QTextEdit()
        form.addWidget(self._description_edit, row, 1)

        panel_layout.addWidget(form_group)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #D14343;")
        panel_layout.addWidget(self._error_label)

        button_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save_clicked)
        button_row.addWidget(save_btn)
        self._archive_btn = QPushButton("Archive")
        self._archive_btn.clicked.connect(self._toggle_archive)
        button_row.addWidget(self._archive_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        button_row.addWidget(delete_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_row.addWidget(close_btn)
        button_row.addStretch(1)
        panel_layout.addLayout(button_row)
        panel_layout.addStretch(1)
        return panel

    # ------------------------------------------------------------------
    def _restore_state(self) -> None:
        self._settings.beginGroup(SETTINGS_GROUP)
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self._settings.endGroup()

    def _save_state(self) -> None:
        self._settings.beginGroup(SETTINGS_GROUP)
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.endGroup()

    # ------------------------------------------------------------------
    def _reload(self) -> None:
        self._populate_objective_choices()
        search = self._search_edit.text().strip() or None
        try:
            self._templates = self._dao.list_templates(search=search, include_archived=True)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy Templates", f"Failed to load templates:\n{exc}")
            self._templates = []
        self._table.setRowCount(0)
        for template in self._templates:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(template.title))
            self._table.setItem(row, 1, QTableWidgetItem(self._objective_label(template.objective_template_id)))
            self._table.setItem(row, 2, QTableWidgetItem(template.assignment_kind))
            self._table.setItem(row, 3, QTableWidgetItem(template.priority))
            self._table.item(row, 0).setData(Qt.UserRole, template.id)
        self._clear_editor()

    def _populate_objective_choices(self) -> None:
        try:
            objectives = self._objectives_dao.list_templates(include_archived=False)
        except Exception:
            objectives = []
        self._objective_combo.blockSignals(True)
        self._objective_combo.clear()
        self._objective_combo.addItem("(Generic — any objective)", None)
        for obj in objectives:
            self._objective_combo.addItem(f"{obj.code or obj.id} — {obj.title}", obj.id)
        self._objective_combo.blockSignals(False)
        self._objective_choices = {obj.id: obj.title for obj in objectives}

    def _objective_label(self, objective_template_id: Optional[int]) -> str:
        if objective_template_id is None:
            return "(Generic)"
        return getattr(self, "_objective_choices", {}).get(objective_template_id, str(objective_template_id))

    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._clear_editor()
            return
        item = self._table.item(rows[0].row(), 0)
        template_id = item.data(Qt.UserRole) if item else None
        template = next((t for t in self._templates if t.id == template_id), None)
        if template:
            self._set_current(template)

    def _set_current(self, template: StrategyTemplate) -> None:
        self._current = replace(template)
        self._error_label.clear()
        self._title_input.setText(template.title)
        index = self._objective_combo.findData(template.objective_template_id)
        self._objective_combo.setCurrentIndex(index if index >= 0 else 0)
        self._kind_combo.setCurrentText(template.assignment_kind)
        self._priority_combo.setCurrentText(template.priority)
        self._branch_input.setText(template.branch or "")
        self._division_input.setText(template.division_group or "")
        self._tags_input.setText(", ".join(template.tags))
        self._description_edit.setPlainText(template.description)
        self._archive_btn.setText("Unarchive" if not template.active else "Archive")

    def _clear_editor(self) -> None:
        self._current = None
        self._title_input.clear()
        self._objective_combo.setCurrentIndex(0)
        self._kind_combo.setCurrentIndex(0)
        self._priority_combo.setCurrentIndex(1)
        self._branch_input.clear()
        self._division_input.clear()
        self._tags_input.clear()
        self._description_edit.clear()
        self._error_label.clear()
        self._archive_btn.setText("Archive")

    # ------------------------------------------------------------------
    def _on_new_clicked(self) -> None:
        self._clear_editor()
        self._title_input.setFocus()

    def _collect_from_fields(self) -> StrategyTemplate:
        template = self._current or StrategyTemplate()
        template.title = self._title_input.text().strip()
        template.objective_template_id = self._objective_combo.currentData()
        template.assignment_kind = self._kind_combo.currentText()
        template.priority = self._priority_combo.currentText()
        template.branch = self._branch_input.text().strip() or None
        template.division_group = self._division_input.text().strip() or None
        template.tags = [t.strip() for t in self._tags_input.text().split(",") if t.strip()]
        template.description = self._description_edit.toPlainText()
        return template

    def _on_save_clicked(self) -> None:
        template = self._collect_from_fields()
        if not (3 <= len(template.title) <= 200):
            self._error_label.setText("Title must be between 3 and 200 characters.")
            return
        try:
            if template.id is None:
                new_id = self._dao.create_template(template)
                template = self._dao.get_template(new_id) or template
            else:
                self._dao.update_template(template)
                template = self._dao.get_template(template.id) or template
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy Templates", f"Failed to save:\n{exc}")
            return
        self._reload()

    def _toggle_archive(self) -> None:
        if not self._current or self._current.id is None:
            return
        try:
            self._dao.set_active(self._current.id, not self._current.active)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy Templates", f"Failed to update:\n{exc}")
            return
        self._reload()

    def _delete_selected(self) -> None:
        if not self._current or self._current.id is None:
            return
        confirm = QMessageBox.question(self, "Delete Template", "Delete this strategy template permanently?")
        if confirm != QMessageBox.Yes:
            return
        try:
            self._dao.delete_template(self._current.id)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Strategy Templates", f"Failed to delete:\n{exc}")
            return
        self._reload()

    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._save_state()
        self.window_closed.emit()
        super().closeEvent(event)


_open_editor: Optional[StrategyTemplatesEditor] = None


def show_strategy_templates_editor() -> StrategyTemplatesEditor:
    """Create (or focus) the modeless strategy templates editor window."""
    global _open_editor
    if _open_editor is not None:
        _open_editor.raise_()
        _open_editor.activateWindow()
        return _open_editor

    editor = StrategyTemplatesEditor()

    def _clear_reference() -> None:
        global _open_editor
        _open_editor = None

    editor.window_closed.connect(_clear_reference)
    editor.show()
    _open_editor = editor
    return editor
