"""Qt Widgets panel for master-data Units and Organizations management."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..controller import TreeNode, UnitsOrganizationsController
from ..widgets.dialogs import (
    NewOrganizationDialog,
    OrganizationTypeManagerDialog,
    RankTemplateManagerDialog,
    ReparentOrganizationDialog,
)


class UnitsOrganizationsPanel(QWidget):
    """Three-pane master-data editor for organizations and rank templates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = UnitsOrganizationsController()
        self._selected_org_id: int | None = None
        self._edit_mode = False

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        self._build_toolbar(root_layout)
        self._build_splitter(root_layout)

        self.refresh_all()

    def _build_toolbar(self, parent_layout: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("New Organization", self)
        self.btn_new_sub = QPushButton("New Sub-Organization", self)
        self.btn_edit = QPushButton("Edit", self)
        self.btn_save = QPushButton("Save", self)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_delete = QPushButton("Delete", self)
        self.btn_up = QPushButton("Move Up", self)
        self.btn_down = QPushButton("Move Down", self)
        self.btn_duplicate = QPushButton("Duplicate", self)
        self.btn_types = QPushButton("Manage Types", self)
        self.btn_rank_templates = QPushButton("Manage Rank Templates", self)
        self.btn_expand = QPushButton("Expand All", self)
        self.btn_collapse = QPushButton("Collapse All", self)

        for btn in (
            self.btn_new,
            self.btn_new_sub,
            self.btn_edit,
            self.btn_save,
            self.btn_cancel,
            self.btn_delete,
            self.btn_up,
            self.btn_down,
            self.btn_duplicate,
            self.btn_types,
            self.btn_rank_templates,
            self.btn_expand,
            self.btn_collapse,
        ):
            toolbar.addWidget(btn)

        self.btn_new.clicked.connect(self._create_root_organization)
        self.btn_new_sub.clicked.connect(self._create_sub_organization)
        self.btn_edit.clicked.connect(lambda: self._set_edit_mode(True))
        self.btn_save.clicked.connect(self._save_detail)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_down.clicked.connect(lambda: self._move_selected(1))
        self.btn_duplicate.clicked.connect(self._duplicate_selected)
        self.btn_types.clicked.connect(self._open_type_manager)
        self.btn_rank_templates.clicked.connect(self._open_rank_templates)
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())

        parent_layout.addLayout(toolbar)

    def _build_splitter(self, parent_layout: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Horizontal, self)

        # Left pane: organization tree
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Organization Tree", left))
        self.tree = QTreeWidget(left)
        self.tree.setHeaderLabel("Units and Organizations")
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        left_layout.addWidget(self.tree)
        splitter.addWidget(left)

        # Center pane: child list
        center = QWidget(self)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(QLabel("Children / Siblings", center))
        self.children_table = QTableWidget(center)
        self.children_table.setColumnCount(7)
        self.children_table.setHorizontalHeaderLabels(
            ["Name", "Short Name", "Parent", "Organization Type", "Rank Structure", "Status", "Notes"]
        )
        self.children_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.children_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.children_table.itemSelectionChanged.connect(self._on_children_table_selected)
        center_layout.addWidget(self.children_table)
        splitter.addWidget(center)

        # Right pane: detail form
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Organization Details", right))
        form = QFormLayout()

        self.name_edit = QLineEdit(self)
        self.short_name_edit = QLineEdit(self)
        self.parent_combo = QComboBox(self)
        self.org_type_combo = QComboBox(self)
        self.rank_structure_combo = QComboBox(self)
        self.active_check = QCheckBox("Active", self)
        self.external_id_edit = QLineEdit(self)
        self.callsign_prefix_edit = QLineEdit(self)
        self.notes_edit = QTextEdit(self)

        form.addRow("Organization Name", self.name_edit)
        form.addRow("Short Name / Abbreviation", self.short_name_edit)
        form.addRow("Parent Organization", self.parent_combo)
        form.addRow("Organization Type", self.org_type_combo)
        form.addRow("Assigned Rank Structure", self.rank_structure_combo)
        form.addRow("Status", self.active_check)
        form.addRow("External Identifier", self.external_id_edit)
        form.addRow("Callsign Prefix", self.callsign_prefix_edit)
        form.addRow("Notes", self.notes_edit)
        right_layout.addLayout(form)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 3)
        parent_layout.addWidget(splitter, 1)

        self._set_edit_mode(False)

    # ---- Refresh and selection ------------------------------------------------
    def refresh_all(self) -> None:
        self._load_reference_options()
        self._refresh_tree()
        self._refresh_center_table()
        self._reload_detail_form()

    def _load_reference_options(self) -> None:
        current_parent = self.parent_combo.currentData()
        current_type = self.org_type_combo.currentData()
        current_rank = self.rank_structure_combo.currentData()

        self.parent_combo.clear()
        self.parent_combo.addItem("(Root)", None)
        for row in self.controller.list_organizations(include_inactive=True):
            self.parent_combo.addItem(row["name"], int(row["id"]))

        self.org_type_combo.clear()
        for row in self.controller.list_organization_types(include_inactive=True):
            self.org_type_combo.addItem(row["name"], int(row["id"]))

        self.rank_structure_combo.clear()
        self.rank_structure_combo.addItem("(None)", None)
        for row in self.controller.list_rank_structures(include_inactive=True):
            self.rank_structure_combo.addItem(row["name"], int(row["id"]))

        self._set_combo_to_data(self.parent_combo, current_parent)
        self._set_combo_to_data(self.org_type_combo, current_type)
        self._set_combo_to_data(self.rank_structure_combo, current_rank)

    def _refresh_tree(self) -> None:
        selected = self._selected_org_id
        self.tree.clear()
        nodes = self.controller.build_tree(include_inactive=True)
        for node in nodes:
            self.tree.addTopLevelItem(self._make_tree_item(node))
        self.tree.expandAll()
        if selected is not None:
            self._select_tree_item(selected)

    def _make_tree_item(self, node: TreeNode) -> QTreeWidgetItem:
        name = node.organization.get("name") or "(Unnamed)"
        if not node.organization.get("is_active", 1):
            name = f"{name} [Inactive]"
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.UserRole, int(node.organization["id"]))
        for child in node.children:
            item.addChild(self._make_tree_item(child))
        return item

    def _select_tree_item(self, organization_id: int) -> None:
        def _walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if int(item.data(0, Qt.UserRole)) == int(organization_id):
                return item
            for i in range(item.childCount()):
                found = _walk(item.child(i))
                if found:
                    return found
            return None

        for i in range(self.tree.topLevelItemCount()):
            found = _walk(self.tree.topLevelItem(i))
            if found:
                self.tree.setCurrentItem(found)
                break

    def _on_tree_selection_changed(self) -> None:
        item = self.tree.currentItem()
        if not item:
            self._selected_org_id = None
            self._refresh_center_table()
            self._reload_detail_form()
            return
        self._selected_org_id = int(item.data(0, Qt.UserRole))
        self._refresh_center_table()
        self._reload_detail_form()

    def _refresh_center_table(self) -> None:
        parent = self._selected_org_id
        rows = self.controller.list_children(parent)
        self.children_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("name") or "",
                row.get("short_name") or "",
                row.get("parent_name") or "",
                row.get("organization_type_name") or "",
                row.get("rank_structure_name") or "",
                "Active" if row.get("is_active") else "Inactive",
                row.get("notes") or "",
            ]
            for c, value in enumerate(values):
                self.children_table.setItem(r, c, QTableWidgetItem(str(value)))
            self.children_table.item(r, 0).setData(Qt.UserRole, int(row["id"]))

    def _on_children_table_selected(self) -> None:
        row = self.children_table.currentRow()
        if row < 0:
            return
        item = self.children_table.item(row, 0)
        if not item:
            return
        org_id = int(item.data(Qt.UserRole))
        self._selected_org_id = org_id
        self._select_tree_item(org_id)

    def _reload_detail_form(self) -> None:
        org = self.controller.get_organization(self._selected_org_id) if self._selected_org_id else None
        if not org:
            self.name_edit.clear()
            self.short_name_edit.clear()
            self.external_id_edit.clear()
            self.callsign_prefix_edit.clear()
            self.notes_edit.clear()
            self.active_check.setChecked(True)
            return

        self.name_edit.setText(org.get("name") or "")
        self.short_name_edit.setText(org.get("short_name") or "")
        self.external_id_edit.setText(org.get("external_id") or "")
        self.callsign_prefix_edit.setText(org.get("callsign_prefix") or "")
        self.notes_edit.setPlainText(org.get("notes") or "")
        self.active_check.setChecked(bool(org.get("is_active", 1)))

        self._set_combo_to_data(self.parent_combo, org.get("parent_organization_id"))
        self._set_combo_to_data(self.org_type_combo, org.get("organization_type_id"))
        self._set_combo_to_data(self.rank_structure_combo, org.get("default_rank_structure_id"))

    # ---- CRUD actions ---------------------------------------------------------
    def _create_root_organization(self) -> None:
        dlg = NewOrganizationDialog(self.controller, parent=self, parent_id=None)
        if dlg.exec():
            org_id = self.controller.create_organization(dlg.payload())
            self._selected_org_id = org_id
            self.refresh_all()

    def _create_sub_organization(self) -> None:
        if not self._selected_org_id:
            QMessageBox.information(self, "Units and Organizations", "Select a parent organization first.")
            return
        dlg = NewOrganizationDialog(self.controller, parent=self, parent_id=self._selected_org_id)
        if dlg.exec():
            org_id = self.controller.create_organization(dlg.payload())
            self._selected_org_id = org_id
            self.refresh_all()

    def _save_detail(self) -> None:
        if not self._edit_mode:
            return
        if not self._selected_org_id:
            QMessageBox.warning(self, "Units and Organizations", "Select an organization to save.")
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Organization Name is required.")
            return
        if self.org_type_combo.currentData() is None:
            QMessageBox.warning(self, "Validation", "Organization Type is required.")
            return

        payload: dict[str, Any] = {
            "name": self.name_edit.text().strip(),
            "short_name": self.short_name_edit.text().strip(),
            "parent_organization_id": self.parent_combo.currentData(),
            "organization_type_id": self.org_type_combo.currentData(),
            "default_rank_structure_id": self.rank_structure_combo.currentData(),
            "is_active": 1 if self.active_check.isChecked() else 0,
            "notes": self.notes_edit.toPlainText().strip(),
            "external_id": self.external_id_edit.text().strip() or None,
            "callsign_prefix": self.callsign_prefix_edit.text().strip() or None,
            "sort_order": self.controller.get_organization(self._selected_org_id).get("sort_order", 0),
        }
        try:
            self.controller.update_organization(self._selected_org_id, payload)
        except ValueError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
            return

        self._set_edit_mode(False)
        self.refresh_all()

    def _cancel_edit(self) -> None:
        self._set_edit_mode(False)
        self._reload_detail_form()

    def _delete_selected(self) -> None:
        if not self._selected_org_id:
            QMessageBox.warning(self, "Units and Organizations", "Select an organization first.")
            return
        if QMessageBox.question(
            self,
            "Delete Organization",
            "Delete the selected organization? This action cannot be undone.",
        ) != QMessageBox.Yes:
            return

        result = self.controller.delete_organization(self._selected_org_id)
        if result.deleted:
            QMessageBox.information(self, "Units and Organizations", result.message)
            self._selected_org_id = None
        else:
            QMessageBox.warning(self, "Units and Organizations", result.message)
        self.refresh_all()

    def _move_selected(self, direction: int) -> None:
        if not self._selected_org_id:
            return
        self.controller.move_organization(self._selected_org_id, direction)
        self.refresh_all()

    def _duplicate_selected(self) -> None:
        if not self._selected_org_id:
            QMessageBox.warning(self, "Units and Organizations", "Select an organization to duplicate.")
            return
        org = self.controller.get_organization(self._selected_org_id)
        if not org:
            return
        copy_payload = {
            "name": f"{org['name']} Copy",
            "short_name": org.get("short_name") or "",
            "parent_organization_id": org.get("parent_organization_id"),
            "organization_type_id": org.get("organization_type_id"),
            "default_rank_structure_id": org.get("default_rank_structure_id"),
            "is_active": org.get("is_active", 1),
            "notes": org.get("notes") or "",
            "external_id": None,
            "callsign_prefix": org.get("callsign_prefix"),
            "sort_order": int(org.get("sort_order", 0)) + 1,
        }
        new_id = self.controller.create_organization(copy_payload)
        self._selected_org_id = new_id
        self.refresh_all()

    # ---- Dialog actions -------------------------------------------------------
    def _open_type_manager(self) -> None:
        dialog = OrganizationTypeManagerDialog(self.controller, parent=self)
        dialog.exec()
        self.refresh_all()

    def _open_rank_templates(self) -> None:
        dialog = RankTemplateManagerDialog(self.controller, parent=self)
        dialog.exec()
        self.refresh_all()

    # ---- Tree context menu ----------------------------------------------------
    def _show_tree_context_menu(self, position: QPoint) -> None:
        item = self.tree.itemAt(position)
        if item:
            self.tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("New Organization", self._create_root_organization)
        if self._selected_org_id:
            menu.addAction("New Sub-Organization", self._create_sub_organization)
            menu.addAction("Reparent / Move", self._reparent_selected)
            menu.addAction("Duplicate", self._duplicate_selected)
            menu.addSeparator()
            menu.addAction("Delete", self._delete_selected)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _reparent_selected(self) -> None:
        if not self._selected_org_id:
            return
        org = self.controller.get_organization(self._selected_org_id)
        if not org:
            return
        dlg = ReparentOrganizationDialog(self.controller, org, parent=self)
        if not dlg.exec():
            return
        payload = dict(org)
        payload["parent_organization_id"] = dlg.selected_parent_id()
        try:
            self.controller.update_organization(self._selected_org_id, payload)
            self.refresh_all()
        except ValueError as exc:
            QMessageBox.warning(self, "Reparent", str(exc))

    # ---- Utility --------------------------------------------------------------
    def _set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        for widget in (
            self.name_edit,
            self.short_name_edit,
            self.parent_combo,
            self.org_type_combo,
            self.rank_structure_combo,
            self.active_check,
            self.external_id_edit,
            self.callsign_prefix_edit,
            self.notes_edit,
        ):
            widget.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.btn_cancel.setEnabled(enabled)
        self.btn_edit.setEnabled(not enabled)

    @staticmethod
    def _set_combo_to_data(combo: QComboBox, data: Any) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)


__all__ = ["UnitsOrganizationsPanel"]
