"""Dialog widgets for Units and Organizations editor."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..controller import UnitsOrganizationsController


class NewOrganizationDialog(QDialog):
    """Create or edit an organization record."""

    def __init__(
        self,
        controller: UnitsOrganizationsController,
        *,
        parent=None,
        parent_id: int | None = None,
        initial: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.initial = initial or {}
        self.setWindowTitle("New Organization" if not initial else "Edit Organization")
        self.resize(540, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(self.initial.get("name", ""), self)
        self.short_name_edit = QLineEdit(self.initial.get("short_name", ""), self)
        self.parent_combo = QComboBox(self)
        self.org_type_combo = QComboBox(self)
        self.rank_structure_combo = QComboBox(self)
        self.active_check = QCheckBox("Active", self)
        self.active_check.setChecked(bool(self.initial.get("is_active", 1)))
        self.external_id_edit = QLineEdit(self.initial.get("external_id") or "", self)
        self.callsign_prefix_edit = QLineEdit(self.initial.get("callsign_prefix") or "", self)
        self.sort_order_spin = QSpinBox(self)
        self.sort_order_spin.setRange(0, 1_000_000)
        self.sort_order_spin.setValue(int(self.initial.get("sort_order", 0)))
        self.notes_edit = QTextEdit(self.initial.get("notes") or "", self)

        form.addRow("Organization Name", self.name_edit)
        form.addRow("Short Name / Abbreviation", self.short_name_edit)
        form.addRow("Parent Organization", self.parent_combo)
        form.addRow("Organization Type", self.org_type_combo)
        form.addRow("Assigned Rank Structure", self.rank_structure_combo)
        form.addRow("Status", self.active_check)
        form.addRow("External Identifier", self.external_id_edit)
        form.addRow("Callsign Prefix", self.callsign_prefix_edit)
        form.addRow("Sort Order", self.sort_order_spin)
        form.addRow("Notes", self.notes_edit)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._load_options(parent_id)

    def _load_options(self, default_parent_id: int | None) -> None:
        # Parent org list
        self.parent_combo.addItem("(Root)", None)
        for row in self.controller.list_organizations(include_inactive=True):
            if self.initial and int(row["id"]) == int(self.initial.get("id", -1)):
                continue
            self.parent_combo.addItem(row["name"], int(row["id"]))

        # Org types
        for row in self.controller.list_organization_types(include_inactive=True):
            self.org_type_combo.addItem(row["name"], int(row["id"]))

        # Rank structures
        self.rank_structure_combo.addItem("(None)", None)
        for row in self.controller.list_rank_structures(include_inactive=True):
            self.rank_structure_combo.addItem(row["name"], int(row["id"]))

        # Defaults
        parent_value = self.initial.get("parent_organization_id", default_parent_id)
        self._set_combo_data(self.parent_combo, parent_value)
        self._set_combo_data(self.org_type_combo, self.initial.get("organization_type_id"))
        self._set_combo_data(self.rank_structure_combo, self.initial.get("default_rank_structure_id"))

    def _set_combo_data(self, combo: QComboBox, value: Any) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Organization name is required.")
            return
        if self.org_type_combo.currentData() is None:
            QMessageBox.warning(self, "Validation", "Organization type is required.")
            return
        self.accept()

    def payload(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "short_name": self.short_name_edit.text().strip(),
            "parent_organization_id": self.parent_combo.currentData(),
            "organization_type_id": self.org_type_combo.currentData(),
            "default_rank_structure_id": self.rank_structure_combo.currentData(),
            "is_active": 1 if self.active_check.isChecked() else 0,
            "notes": self.notes_edit.toPlainText().strip(),
            "external_id": self.external_id_edit.text().strip() or None,
            "callsign_prefix": self.callsign_prefix_edit.text().strip() or None,
            "sort_order": int(self.sort_order_spin.value()),
        }


class OrganizationTypeManagerDialog(QDialog):
    """Simple manager for organization type records."""

    def __init__(self, controller: UnitsOrganizationsController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._current_id: int | None = None
        self.setWindowTitle("Organization Type Manager")
        self.resize(700, 460)

        layout = QHBoxLayout(self)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Description", "Active", "Sort"])
        self.table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.table, 2)

        form_wrap = QVBoxLayout()
        self.name_edit = QLineEdit(self)
        self.desc_edit = QTextEdit(self)
        self.active_check = QCheckBox("Active", self)
        self.sort_spin = QSpinBox(self)
        self.sort_spin.setRange(0, 1_000_000)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.desc_edit)
        form.addRow("Status", self.active_check)
        form.addRow("Sort Order", self.sort_spin)
        form_wrap.addLayout(form)

        actions = QHBoxLayout()
        btn_new = QPushButton("New", self)
        btn_save = QPushButton("Save", self)
        btn_close = QPushButton("Close", self)
        btn_new.clicked.connect(self._new)
        btn_save.clicked.connect(self._save)
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_new)
        actions.addWidget(btn_save)
        actions.addWidget(btn_close)
        form_wrap.addLayout(actions)
        layout.addLayout(form_wrap, 1)

        self._refresh()

    def _refresh(self) -> None:
        rows = self.controller.list_organization_types(include_inactive=True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row["name"]))
            self.table.setItem(r, 1, QTableWidgetItem(row.get("description") or ""))
            self.table.setItem(r, 2, QTableWidgetItem("Yes" if row.get("is_active") else "No"))
            self.table.setItem(r, 3, QTableWidgetItem(str(row.get("sort_order", 0))))
            self.table.item(r, 0).setData(Qt.UserRole, int(row["id"]))

    def _new(self) -> None:
        self._current_id = None
        self.name_edit.clear()
        self.desc_edit.clear()
        self.active_check.setChecked(True)
        self.sort_spin.setValue(0)

    def _on_select(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        self._current_id = int(item.data(Qt.UserRole))
        self.name_edit.setText(item.text())
        self.desc_edit.setPlainText(self.table.item(row, 1).text())
        self.active_check.setChecked(self.table.item(row, 2).text() == "Yes")
        self.sort_spin.setValue(int(self.table.item(row, 3).text() or "0"))

    def _save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Type name is required.")
            return
        self.controller.save_organization_type(
            self._current_id,
            {
                "name": self.name_edit.text(),
                "description": self.desc_edit.toPlainText(),
                "is_active": 1 if self.active_check.isChecked() else 0,
                "sort_order": self.sort_spin.value(),
            },
        )
        self._refresh()


class RankTemplateManagerDialog(QDialog):
    """Manager for reusable rank structure templates."""

    def __init__(self, controller: UnitsOrganizationsController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._current_id: int | None = None
        self.setWindowTitle("Rank Structure Template Manager")
        self.resize(780, 460)

        outer = QVBoxLayout(self)
        splitter = QSplitter(self)

        # Left: template list
        left = QVBoxLayout()
        left_wrap = QWidget(self)
        left_wrap.setLayout(left)
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Description", "Org Type", "Template", "Active"])
        self.table.itemSelectionChanged.connect(self._on_select)
        left.addWidget(self.table)

        actions = QHBoxLayout()
        self.btn_new = QPushButton("New Template", self)
        self.btn_duplicate = QPushButton("Duplicate", self)
        self.btn_convert = QPushButton("Convert Template to Custom Copy", self)
        self.btn_close = QPushButton("Close", self)
        self.btn_new.clicked.connect(self._create_template)
        self.btn_duplicate.clicked.connect(self._duplicate)
        self.btn_convert.clicked.connect(self._convert)
        self.btn_close.clicked.connect(self.accept)
        actions.addWidget(self.btn_new)
        actions.addWidget(self.btn_duplicate)
        actions.addWidget(self.btn_convert)
        actions.addStretch(1)
        actions.addWidget(self.btn_close)
        left.addLayout(actions)
        splitter.addWidget(left_wrap)

        # Right: template detail + ranks editor
        right_wrap = QWidget(self)
        right = QVBoxLayout(right_wrap)
        form = QFormLayout()
        self.t_name = QLineEdit(self)
        self.t_desc = QTextEdit(self)
        self.t_org_type = QComboBox(self)
        self.t_is_template = QCheckBox("Template", self)
        self.t_is_active = QCheckBox("Active", self)
        self.t_sort = QSpinBox(self)
        self.t_sort.setRange(0, 1_000_000)

        form.addRow("Name", self.t_name)
        form.addRow("Description", self.t_desc)
        form.addRow("Organization Type", self.t_org_type)
        form.addRow("Flags", self.t_is_template)
        form.addRow("Status", self.t_is_active)
        form.addRow("Sort Order", self.t_sort)
        right.addLayout(form)

        right.addWidget(QLabel("Ranks", self))
        self.ranks = QTableWidget(self)
        self.ranks.setColumnCount(4)
        self.ranks.setHorizontalHeaderLabels(["Order", "Code", "Name", "Short Display"])
        right.addWidget(self.ranks, 1)

        rank_actions = QHBoxLayout()
        self.btn_add_rank = QPushButton("Add Rank", self)
        self.btn_del_rank = QPushButton("Remove Rank", self)
        self.btn_up_rank = QPushButton("Move Up", self)
        self.btn_down_rank = QPushButton("Move Down", self)
        self.btn_save = QPushButton("Save Template", self)
        self.btn_add_rank.clicked.connect(self._add_rank)
        self.btn_del_rank.clicked.connect(self._del_rank)
        self.btn_up_rank.clicked.connect(lambda: self._move_rank(-1))
        self.btn_down_rank.clicked.connect(lambda: self._move_rank(1))
        self.btn_save.clicked.connect(self._save_template)
        for b in (self.btn_add_rank, self.btn_del_rank, self.btn_up_rank, self.btn_down_rank):
            rank_actions.addWidget(b)
        rank_actions.addStretch(1)
        rank_actions.addWidget(self.btn_save)
        right.addLayout(rank_actions)

        splitter.addWidget(right_wrap)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter, 1)

        self._refresh()
        self._load_org_type_options()

    def _refresh(self) -> None:
        rows = self.controller.list_rank_structures(include_inactive=True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row.get("name") or ""))
            self.table.setItem(r, 1, QTableWidgetItem(row.get("description") or ""))
            self.table.setItem(r, 2, QTableWidgetItem(row.get("organization_type_name") or ""))
            self.table.setItem(r, 3, QTableWidgetItem("Yes" if row.get("is_template") else "No"))
            self.table.setItem(r, 4, QTableWidgetItem("Yes" if row.get("is_active") else "No"))
            self.table.item(r, 0).setData(Qt.UserRole, int(row["id"]))

    def _on_select(self) -> None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            self._current_id = None
            self._clear_detail()
            return
        self._current_id = int(self.table.item(row, 0).data(Qt.UserRole))
        self._load_detail(self._current_id)

    def _create_template(self) -> None:
        name, ok = QInputDialog.getText(self, "New Rank Template", "Template name:")
        if not ok or not name.strip():
            return
        new_id = self.controller.save_rank_structure(
            None,
            {
                "name": name.strip(),
                "description": "",
                "organization_type_id": None,
                "is_template": 1,
                "is_system_template": 0,
                "is_active": 1,
                "sort_order": 0,
                "ranks": [],
            },
        )
        self._refresh()
        if new_id:
            self._select_by_id(int(new_id))

    def _duplicate(self) -> None:
        if not self._current_id:
            QMessageBox.warning(self, "Rank Templates", "Select a rank structure to duplicate.")
            return
        name, ok = QInputDialog.getText(self, "Duplicate Rank Template", "New template name:")
        if not ok or not name.strip():
            return
        self.controller.duplicate_rank_template(self._current_id, name.strip(), as_template=True)
        self._refresh()

    def _convert(self) -> None:
        if not self._current_id:
            QMessageBox.warning(self, "Rank Templates", "Select a rank template to convert.")
            return
        name, ok = QInputDialog.getText(self, "Custom Copy", "Custom rank structure name:")
        if not ok or not name.strip():
            return
        self.controller.convert_template_to_custom_copy(self._current_id, name.strip())
        QMessageBox.information(self, "Rank Templates", "Custom rank structure copy created.")
        self._refresh()

    # --- Detail helpers ------------------------------------------------------
    def _clear_detail(self) -> None:
        self.t_name.clear()
        self.t_desc.clear()
        self.t_org_type.setCurrentIndex(-1)
        self.t_is_template.setChecked(True)
        self.t_is_active.setChecked(True)
        self.t_sort.setValue(0)
        self.ranks.setRowCount(0)

    def _load_org_type_options(self) -> None:
        self.t_org_type.clear()
        self.t_org_type.addItem("(None)", None)
        for row in self.controller.list_organization_types(include_inactive=True):
            self.t_org_type.addItem(row["name"], int(row["id"]))

    def _set_combo_to_data(self, combo: QComboBox, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _select_by_id(self, rid: int) -> None:
        for r in range(self.table.rowCount()):
            if int(self.table.item(r, 0).data(Qt.UserRole)) == int(rid):
                self.table.setCurrentCell(r, 0)
                break

    def _load_detail(self, rid: int) -> None:
        # Load header fields from the list view row to avoid extra query
        row = self.table.currentRow()
        if row < 0:
            return
        self.t_name.setText(self.table.item(row, 0).text())
        self.t_desc.setPlainText(self.table.item(row, 1).text())
        # org type combobox
        name_at_cell = self.table.item(row, 2).text()
        # Ensure options are fresh
        self._load_org_type_options()
        # Try to match by name
        idx = self.t_org_type.findText(name_at_cell) if name_at_cell else -1
        if idx >= 0:
            self.t_org_type.setCurrentIndex(idx)
        self.t_is_template.setChecked(self.table.item(row, 3).text() == "Yes")
        self.t_is_active.setChecked(self.table.item(row, 4).text() == "Yes")
        # Sort order is not shown in the list; keep as 0 by default
        self.t_sort.setValue(0)

        # Load ranks
        self.ranks.setRowCount(0)
        for r in self.controller.list_ranks(rid):
            rr = self.ranks.rowCount()
            self.ranks.insertRow(rr)
            self.ranks.setItem(rr, 0, QTableWidgetItem(str(r.get("sort_order", rr))))
            self.ranks.setItem(rr, 1, QTableWidgetItem(r.get("rank_code") or ""))
            self.ranks.setItem(rr, 2, QTableWidgetItem(r.get("rank_name") or ""))
            self.ranks.setItem(rr, 3, QTableWidgetItem(r.get("short_display") or ""))

    def _add_rank(self) -> None:
        rr = self.ranks.rowCount()
        self.ranks.insertRow(rr)
        self.ranks.setItem(rr, 0, QTableWidgetItem(str(rr)))
        self.ranks.setItem(rr, 1, QTableWidgetItem(""))
        self.ranks.setItem(rr, 2, QTableWidgetItem(""))
        self.ranks.setItem(rr, 3, QTableWidgetItem(""))

    def _del_rank(self) -> None:
        row = self.ranks.currentRow()
        if row >= 0:
            self.ranks.removeRow(row)
            # Re-number orders
            for i in range(self.ranks.rowCount()):
                self.ranks.setItem(i, 0, QTableWidgetItem(str(i)))

    def _move_rank(self, delta: int) -> None:
        row = self.ranks.currentRow()
        if row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.ranks.rowCount():
            return
        # Swap cells between rows
        values = [self.ranks.item(row, c).text() if self.ranks.item(row, c) else "" for c in range(4)]
        target_values = [self.ranks.item(target, c).text() if self.ranks.item(target, c) else "" for c in range(4)]
        for c in range(4):
            self.ranks.setItem(row, c, QTableWidgetItem(target_values[c]))
            self.ranks.setItem(target, c, QTableWidgetItem(values[c]))
        self.ranks.setCurrentCell(target, 0)
        # Update order column
        for i in range(self.ranks.rowCount()):
            self.ranks.setItem(i, 0, QTableWidgetItem(str(i)))

    def _collect_ranks(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for i in range(self.ranks.rowCount()):
            def _val(col: int) -> str:
                it = self.ranks.item(i, col)
                return it.text().strip() if it else ""
            out.append(
                {
                    "sort_order": int(_val(0) or i),
                    "rank_code": _val(1),
                    "rank_name": _val(2),
                    "short_display": _val(3),
                    "is_active": 1,
                }
            )
        return out

    def _save_template(self) -> None:
        name = self.t_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Rank Templates", "Template name is required.")
            return
        payload = {
            "name": name,
            "description": self.t_desc.toPlainText().strip(),
            "organization_type_id": self.t_org_type.currentData(),
            "is_template": 1 if self.t_is_template.isChecked() else 0,
            "is_system_template": 0,
            "is_active": 1 if self.t_is_active.isChecked() else 0,
            "sort_order": int(self.t_sort.value()),
        }
        ranks = self._collect_ranks()
        rid = self.controller.save_rank_structure_with_ranks(self._current_id, payload, ranks)
        self._refresh()
        self._select_by_id(int(rid))


class ReparentOrganizationDialog(QDialog):
    """Dialog for reparenting an organization under another parent."""

    def __init__(
        self,
        controller: UnitsOrganizationsController,
        organization: dict[str, Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.organization = organization
        self.setWindowTitle("Reparent / Move Organization")
        self.resize(420, 140)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Move '{organization.get('name')}' under:", self))

        self.parent_combo = QComboBox(self)
        self.parent_combo.addItem("(Root)", None)
        for row in self.controller.list_organizations(include_inactive=True):
            if int(row["id"]) == int(organization["id"]):
                continue
            self.parent_combo.addItem(row["name"], int(row["id"]))
        idx = self.parent_combo.findData(organization.get("parent_organization_id"))
        if idx >= 0:
            self.parent_combo.setCurrentIndex(idx)
        layout.addWidget(self.parent_combo)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_parent_id(self) -> int | None:
        return self.parent_combo.currentData()


__all__ = [
    "NewOrganizationDialog",
    "OrganizationTypeManagerDialog",
    "RankTemplateManagerDialog",
    "ReparentOrganizationDialog",
]
