""""New Checklist" dialog: pick a catalog template, or build a blank one.

Browsing/searching templates reads the existing checklist-template catalog
(`checklist_templates.py`) — this dialog never edits or manages templates
itself; template management stays entirely in the existing catalog UI.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.facilities.widgets.personnel_picker import PersonnelPicker

from .. import api

ITEM_TYPES = [
    ("checkbox", "Checkbox"),
    ("pass_fail_na", "Pass / Fail / N/A"),
    ("text", "Text / Notes"),
    ("numeric", "Numeric"),
    ("selection", "Selection"),
]
_ITEM_COLUMNS = ("Section", "Label", "Type", "Required", "N/A Allowed", "Config")


class NewChecklistDialog(QDialog):
    """Returns either ``{"template_id": int}`` or ``{"sections": [...]}`` via
    :meth:`result_payload`, plus a common ``name``/``owner_person_record``.
    """

    def __init__(self, incident_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self._templates: list[dict[str, Any]] = []
        self.setWindowTitle("New Checklist")
        self.resize(760, 560)
        self._build_ui()
        self._load_templates()

    # -- construction -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        common_form = QFormLayout()
        self.name_edit = QLineEdit()
        self.owner_picker = PersonnelPicker()
        common_form.addRow("Checklist name", self.name_edit)
        common_form.addRow("Owner (optional)", self.owner_picker)
        layout.addLayout(common_form)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_template_tab(), "From Template")
        self.tabs.addTab(self._build_blank_tab(), "Blank Checklist")
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_template_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        filters = QHBoxLayout()
        self.template_search_edit = QLineEdit()
        self.template_search_edit.setPlaceholderText("Search templates by name…")
        self.template_category_combo = QComboBox()
        self.template_category_combo.addItem("All categories")
        filters.addWidget(self.template_search_edit, 2)
        filters.addWidget(self.template_category_combo, 1)
        layout.addLayout(filters)

        self.template_search_edit.textChanged.connect(self._apply_template_filters)
        self.template_category_combo.currentTextChanged.connect(self._apply_template_filters)

        self.template_list = QListWidget()
        layout.addWidget(self.template_list, 1)
        return tab

    def _build_blank_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        hint = QLabel(
            "Add items below. Checklists without sections are supported — leave "
            "\"Section\" blank to put an item at the top level. For a Selection "
            "item, enter comma-separated options in Config (e.g. \"Good,Fair,Poor\"). "
            "For a Numeric item, enter \"unit,min,max\" (any part may be left blank, "
            "e.g. \"%,0,100\" or \"gal,,\")."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        actions = QHBoxLayout()
        add_btn = QPushButton("Add Item")
        remove_btn = QPushButton("Remove Selected")
        add_btn.clicked.connect(self._add_item_row)
        remove_btn.clicked.connect(self._remove_selected_item_row)
        actions.addWidget(add_btn)
        actions.addWidget(remove_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.item_table = QTableWidget(0, len(_ITEM_COLUMNS))
        self.item_table.setHorizontalHeaderLabels(list(_ITEM_COLUMNS))
        self.item_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.item_table, 1)
        return tab

    # -- templates ------------------------------------------------------------

    def _load_templates(self) -> None:
        try:
            self._templates = api.list_templates()
            categories = api.list_template_categories()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "New Checklist", f"Unable to load templates.\n{exc}")
            self._templates = []
            categories = []
        self.template_category_combo.blockSignals(True)
        for category in categories:
            self.template_category_combo.addItem(category)
        self.template_category_combo.blockSignals(False)
        self._apply_template_filters()

    def _apply_template_filters(self, *_args: Any) -> None:
        search = self.template_search_edit.text().strip().lower()
        category = self.template_category_combo.currentText()
        self.template_list.clear()
        for template in self._templates:
            if search and search not in (template.get("name") or "").lower():
                continue
            if category != "All categories" and template.get("category") != category:
                continue
            item_count = sum(len(section.get("items") or []) for section in template.get("sections") or [])
            label = f"{template.get('name', '')}  ({template.get('category', '')}, {item_count} item{'s' if item_count != 1 else ''})"
            description = template.get("description") or ""
            list_item = QListWidgetItem(f"{label}\n{description}" if description else label)
            list_item.setData(Qt.ItemDataRole.UserRole, template)
            self.template_list.addItem(list_item)

    # -- blank builder --------------------------------------------------------

    def _add_item_row(self) -> None:
        row = self.item_table.rowCount()
        self.item_table.insertRow(row)
        self.item_table.setItem(row, 0, QTableWidgetItem(""))
        self.item_table.setItem(row, 1, QTableWidgetItem(""))
        type_combo = QComboBox()
        for value, label in ITEM_TYPES:
            type_combo.addItem(label, value)
        self.item_table.setCellWidget(row, 2, type_combo)
        required_check = QCheckBox()
        self.item_table.setCellWidget(row, 3, _centered(required_check))
        na_check = QCheckBox()
        self.item_table.setCellWidget(row, 4, _centered(na_check))
        self.item_table.setItem(row, 5, QTableWidgetItem(""))

    def _remove_selected_item_row(self) -> None:
        rows = sorted({index.row() for index in self.item_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.item_table.removeRow(row)

    def _build_blank_sections(self) -> Optional[list[dict[str, Any]]]:
        sections_by_name: dict[str, dict[str, Any]] = {}
        ordered_sections: list[dict[str, Any]] = []
        for row in range(self.item_table.rowCount()):
            section_name = (self.item_table.item(row, 0).text() or "").strip()
            label = (self.item_table.item(row, 1).text() or "").strip()
            if not label:
                QMessageBox.warning(self, "New Checklist", f"Row {row + 1} needs a label.")
                return None
            type_combo: QComboBox = self.item_table.cellWidget(row, 2)
            item_type = type_combo.currentData()
            required = self.item_table.cellWidget(row, 3).findChild(QCheckBox).isChecked()
            na_allowed = self.item_table.cellWidget(row, 4).findChild(QCheckBox).isChecked()
            config = (self.item_table.item(row, 5).text() or "").strip()

            item: dict[str, Any] = {
                "id": uuid.uuid4().hex[:12],
                "item_type": item_type,
                "label": label,
                "instructions": "",
                "required": required,
                "na_allowed": na_allowed,
            }
            if item_type == "selection":
                options = [part.strip() for part in config.split(",") if part.strip()]
                if not options:
                    QMessageBox.warning(self, "New Checklist", f"Row {row + 1} (Selection) needs comma-separated options.")
                    return None
                item["options"] = [{"id": uuid.uuid4().hex[:8], "label": option} for option in options]
            elif item_type == "numeric":
                parts = [part.strip() for part in config.split(",")]
                unit, min_value, max_value = (parts + ["", "", ""])[:3]
                item["unit"] = unit
                item["min_value"] = float(min_value) if min_value else None
                item["max_value"] = float(max_value) if max_value else None

            key = section_name or ""
            if key not in sections_by_name:
                section = {"id": uuid.uuid4().hex[:12], "name": section_name, "items": []}
                sections_by_name[key] = section
                ordered_sections.append(section)
            sections_by_name[key]["items"].append(item)

        if not ordered_sections:
            QMessageBox.warning(self, "New Checklist", "Add at least one item.")
            return None
        return ordered_sections

    # -- result ---------------------------------------------------------------

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "New Checklist", "A checklist name is required.")
            return
        if self.tabs.currentIndex() == 0:
            current = self.template_list.currentItem()
            if current is None:
                QMessageBox.warning(self, "New Checklist", "Select a template, or switch to the Blank Checklist tab.")
                return
        else:
            if self._build_blank_sections() is None:
                return
        self.accept()

    def result_payload(self) -> dict[str, Any]:
        """Call only after `exec()` returns `QDialog.Accepted`."""

        owner_id = self.owner_picker.personnel_id
        owner_person_record = int(owner_id) if owner_id and owner_id.isdigit() else None
        common = {"name": self.name_edit.text().strip(), "owner_person_record": owner_person_record}

        if self.tabs.currentIndex() == 0:
            template = self.template_list.currentItem().data(Qt.ItemDataRole.UserRole)
            return {**common, "template_id": template["id"]}
        return {**common, "sections": self._build_blank_sections()}


def _centered(widget: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(widget)
    return container


__all__ = ["NewChecklistDialog"]
