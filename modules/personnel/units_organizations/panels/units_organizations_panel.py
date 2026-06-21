"""Modeless QMainWindow for master-data Units and Organizations management."""
from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.itemview_delegates import RowOutlineSelectionDelegate
from ..controller import TreeNode, UnitsOrganizationsController
from ..widgets.dialogs import (
    NewOrganizationDialog,
    OrganizationTypeManagerDialog,
    RankTemplateManagerDialog,
    ReparentOrganizationDialog,
)


_CHILD_COLS: list[tuple[str, str]] = [
    ("name",                   "Name"),
    ("short_name",             "Short Name"),
    ("parent_name",            "Parent"),
    ("organization_type_name", "Type"),
    ("rank_structure_name",    "Rank Structure"),
    ("status",                 "Status"),
    ("notes",                  "Notes"),
]


class _ChildTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: List[dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_CHILD_COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _CHILD_COLS[section][1]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key, _ = _CHILD_COLS[index.column()]
        if role == Qt.DisplayRole:
            if key == "status":
                return "Active" if row.get("is_active") else "Inactive"
            return str(row.get(key) or "")
        if role == Qt.UserRole:
            return row.get("id")
        return None

    def load(self, rows: List[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, row: int) -> Optional[dict[str, Any]]:
        return self._rows[row] if 0 <= row < len(self._rows) else None


class UnitsOrganizationsPanel(QMainWindow):
    """Modeless three-pane editor for units and organizations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Units and Organizations")
        self.resize(1150, 680)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self.controller = UnitsOrganizationsController()
        self._selected_org_id: int | None = None
        self._dirty = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)

        self._build_toolbar()
        self._build_splitter(root)
        self._build_status_bar()

        self.refresh_all()

    # ---- Toolbar -------------------------------------------------------------
    def _build_toolbar(self) -> None:
        tb = QToolBar("Actions", self)
        tb.setMovable(False)

        self.btn_new     = QPushButton("New Org")
        self.btn_new_sub = QPushButton("New Sub-Org")
        self.btn_dup     = QPushButton("Duplicate")
        self.btn_delete  = QPushButton("Delete")
        self.btn_up      = QPushButton("↑")
        self.btn_down    = QPushButton("↓")
        self.btn_up.setFixedWidth(32)
        self.btn_down.setFixedWidth(32)
        self.btn_up.setToolTip("Move Up")
        self.btn_down.setToolTip("Move Down")

        for btn in (self.btn_new, self.btn_new_sub, self.btn_dup, self.btn_delete, self.btn_up, self.btn_down):
            tb.addWidget(btn)

        tb.addSeparator()

        self.btn_types          = QPushButton("Manage Types")
        self.btn_rank_templates = QPushButton("Rank Templates")
        self.btn_expand         = QPushButton("Expand All")
        self.btn_collapse       = QPushButton("Collapse All")
        for btn in (self.btn_types, self.btn_rank_templates, self.btn_expand, self.btn_collapse):
            tb.addWidget(btn)

        tb.addSeparator()

        self.btn_import = QPushButton("Import CSV...")
        self.btn_import.clicked.connect(self._on_import_csv)
        self.btn_export = QPushButton("Export CSV...")
        self.btn_export.clicked.connect(self._on_export_csv)
        tb.addWidget(self.btn_import)
        tb.addWidget(self.btn_export)

        self.addToolBar(tb)

        self.btn_new.clicked.connect(self._create_root_organization)
        self.btn_new_sub.clicked.connect(self._create_sub_organization)
        self.btn_dup.clicked.connect(self._duplicate_selected)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_down.clicked.connect(lambda: self._move_selected(1))
        self.btn_types.clicked.connect(self._open_type_manager)
        self.btn_rank_templates.clicked.connect(self._open_rank_templates)
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())

    # ---- Three-pane splitter -------------------------------------------------
    def _build_splitter(self, root: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Horizontal)

        splitter.addWidget(self._build_left_pane())
        splitter.addWidget(self._build_center_pane())
        splitter.addWidget(self._build_right_pane())

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 3)
        root.addWidget(splitter, 1)

    def _build_left_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(4)

        hdr = QLabel("<b>Organization Tree</b>")
        self.tree_search = QLineEdit()
        self.tree_search.setPlaceholderText("Filter tree…")
        self.tree_search.textChanged.connect(self._filter_tree)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        layout.addWidget(hdr)
        layout.addWidget(self.tree_search)
        layout.addWidget(self.tree)
        return pane

    def _build_center_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        self.center_label = QLabel("<b>All Organizations</b>")
        self._child_model = _ChildTableModel()
        self._child_proxy = QSortFilterProxyModel()
        self._child_proxy.setSourceModel(self._child_model)

        self.children_table = QTableView()
        self.children_table.setModel(self._child_proxy)
        self.children_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.children_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.children_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.children_table.setSortingEnabled(True)
        self.children_table.horizontalHeader().setStretchLastSection(True)
        self.children_table.setAlternatingRowColors(False)
        self.children_table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        self.children_table.setItemDelegate(RowOutlineSelectionDelegate(self.children_table, QColor("#FFFFFF")))
        self.children_table.selectionModel().selectionChanged.connect(self._on_children_table_selected)
        self.children_table.doubleClicked.connect(self._on_children_table_double_clicked)

        layout.addWidget(self.center_label)
        layout.addWidget(self.children_table)
        return pane

    def _build_right_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(6)

        box = QGroupBox("Organization Details")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignRight)

        self.name_edit            = QLineEdit()
        self.short_name_edit      = QLineEdit()
        self.parent_combo         = QComboBox()
        self.org_type_combo       = QComboBox()
        self.rank_structure_combo = QComboBox()
        self.active_check         = QCheckBox("Active")
        self.external_id_edit     = QLineEdit()
        self.callsign_prefix_edit = QLineEdit()
        self.notes_edit           = QTextEdit()
        self.notes_edit.setMaximumHeight(80)

        form.addRow("Name:", self.name_edit)
        form.addRow("Short Name:", self.short_name_edit)
        form.addRow("Parent:", self.parent_combo)
        form.addRow("Type:", self.org_type_combo)
        form.addRow("Rank Structure:", self.rank_structure_combo)
        form.addRow("", self.active_check)
        form.addRow("External ID:", self.external_id_edit)
        form.addRow("Callsign Prefix:", self.callsign_prefix_edit)
        form.addRow("Notes:", self.notes_edit)

        self.btn_save   = QPushButton("Save Changes")
        self.btn_revert = QPushButton("Revert")
        self.btn_save.setEnabled(False)
        self.btn_revert.setEnabled(False)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self.btn_revert)
        save_row.addWidget(self.btn_save)

        layout.addWidget(box)
        layout.addLayout(save_row)
        layout.addStretch(1)

        # Wire dirty tracking
        for widget in (self.name_edit, self.short_name_edit, self.external_id_edit, self.callsign_prefix_edit):
            widget.textChanged.connect(self._on_detail_changed)
        self.notes_edit.textChanged.connect(self._on_detail_changed)
        self.parent_combo.currentIndexChanged.connect(self._on_detail_changed)
        self.org_type_combo.currentIndexChanged.connect(self._on_detail_changed)
        self.rank_structure_combo.currentIndexChanged.connect(self._on_detail_changed)
        self.active_check.toggled.connect(self._on_detail_changed)

        self.btn_save.clicked.connect(self._save_detail)
        self.btn_revert.clicked.connect(self._revert_detail)

        self._set_detail_enabled(False)
        return pane

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("No organization selected")
        sb.addWidget(self._status_label)

    # ---- Refresh -------------------------------------------------------------
    def refresh_all(self) -> None:
        self._load_reference_options()
        self._refresh_tree()
        self._refresh_center_table()
        self._reload_detail_form()

    def _load_reference_options(self) -> None:
        current_parent = self.parent_combo.currentData()
        current_type   = self.org_type_combo.currentData()
        current_rank   = self.rank_structure_combo.currentData()

        self.parent_combo.blockSignals(True)
        self.org_type_combo.blockSignals(True)
        self.rank_structure_combo.blockSignals(True)

        self.parent_combo.clear()
        self.parent_combo.addItem("(Root)", None)
        for row in self.controller.list_organizations(include_inactive=True):
            self.parent_combo.addItem(row["name"], int(row["id"]))

        self.org_type_combo.clear()
        self.org_type_combo.addItem("(Select type)", None)
        for row in self.controller.list_organization_types(include_inactive=True):
            self.org_type_combo.addItem(row["name"], int(row["id"]))

        self.rank_structure_combo.clear()
        self.rank_structure_combo.addItem("(None)", None)
        for row in self.controller.list_rank_structures(include_inactive=True):
            self.rank_structure_combo.addItem(row["name"], int(row["id"]))

        self._set_combo_to_data(self.parent_combo, current_parent)
        self._set_combo_to_data(self.org_type_combo, current_type)
        self._set_combo_to_data(self.rank_structure_combo, current_rank)

        self.parent_combo.blockSignals(False)
        self.org_type_combo.blockSignals(False)
        self.rank_structure_combo.blockSignals(False)

    def _refresh_tree(self) -> None:
        selected = self._selected_org_id
        self.tree.clear()
        self._all_nodes: list[dict[str, Any]] = []
        for node in self.controller.build_tree(include_inactive=True):
            self.tree.addTopLevelItem(self._make_tree_item(node))
        self.tree.expandAll()
        filter_text = self.tree_search.text()
        if filter_text:
            self._apply_tree_filter(filter_text)
        if selected is not None:
            self._select_tree_item(selected)

    def _make_tree_item(self, node: TreeNode) -> QTreeWidgetItem:
        org = node.organization
        name = org.get("name") or "(Unnamed)"
        short = org.get("short_name") or ""
        label = f"{name}  [{short}]" if short else name
        if not org.get("is_active", 1):
            label = f"{label}  ·  Inactive"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.UserRole, int(org["id"]))
        if not org.get("is_active", 1):
            from PySide6.QtGui import QColor
            item.setForeground(0, QColor("#888888"))
        for child in node.children:
            item.addChild(self._make_tree_item(child))
        return item

    def _filter_tree(self, text: str) -> None:
        self._apply_tree_filter(text)

    def _apply_tree_filter(self, text: str) -> None:
        t = text.lower()

        def _walk(item: QTreeWidgetItem) -> bool:
            match = not t or t in item.text(0).lower()
            child_visible = False
            for i in range(item.childCount()):
                if _walk(item.child(i)):
                    child_visible = True
            visible = match or child_visible
            item.setHidden(not visible)
            if child_visible:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            _walk(self.tree.topLevelItem(i))

    def _select_tree_item(self, org_id: int) -> None:
        def _walk(item: QTreeWidgetItem):
            if int(item.data(0, Qt.UserRole)) == org_id:
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
        if self._dirty:
            if QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.Discard | QMessageBox.Cancel,
            ) != QMessageBox.Discard:
                if self._selected_org_id:
                    self.tree.blockSignals(True)
                    self._select_tree_item(self._selected_org_id)
                    self.tree.blockSignals(False)
                return
            self._dirty = False

        item = self.tree.currentItem()
        if not item:
            self._selected_org_id = None
        else:
            self._selected_org_id = int(item.data(0, Qt.UserRole))
        self._refresh_center_table()
        self._reload_detail_form()
        self._update_status()

    def _refresh_center_table(self) -> None:
        rows = self.controller.list_children(self._selected_org_id)
        self._child_model.load(rows)
        self.children_table.resizeColumnsToContents()

        if self._selected_org_id:
            org = self.controller.get_organization(self._selected_org_id)
            name = org.get("name", "") if org else ""
            self.center_label.setText(f"<b>Children of: {name}</b>")
        else:
            self.center_label.setText("<b>All Top-Level Organizations</b>")

    def _on_children_table_selected(self) -> None:
        idx = self.children_table.currentIndex()
        if not idx.isValid():
            return
        src = self._child_proxy.mapToSource(idx)
        row = self._child_model.row_at(src.row())
        if not row:
            return
        org_id = int(row["id"])
        if org_id != self._selected_org_id:
            # Let _on_tree_selection_changed own the _selected_org_id update and
            # dirty-check; don't write _selected_org_id here or Cancel can't restore it.
            self._select_tree_item(org_id)

    def _on_children_table_double_clicked(self, index) -> None:
        src = self._child_proxy.mapToSource(index)
        row = self._child_model.row_at(src.row())
        if row:
            # _select_tree_item fires itemSelectionChanged → _on_tree_selection_changed
            # which already calls _refresh_center_table + _reload_detail_form.
            self._select_tree_item(int(row["id"]))

    def _reload_detail_form(self) -> None:
        org = self.controller.get_organization(self._selected_org_id) if self._selected_org_id else None

        self._block_detail_signals(True)
        if not org:
            self.name_edit.clear()
            self.short_name_edit.clear()
            self.external_id_edit.clear()
            self.callsign_prefix_edit.clear()
            self.notes_edit.clear()
            self.active_check.setChecked(True)
            self._set_combo_to_data(self.parent_combo, None)
            self._set_combo_to_data(self.org_type_combo, None)
            self._set_combo_to_data(self.rank_structure_combo, None)
            self._set_detail_enabled(False)
        else:
            self.name_edit.setText(org.get("name") or "")
            self.short_name_edit.setText(org.get("short_name") or "")
            self.external_id_edit.setText(org.get("external_id") or "")
            self.callsign_prefix_edit.setText(org.get("callsign_prefix") or "")
            self.notes_edit.setPlainText(org.get("notes") or "")
            self.active_check.setChecked(bool(org.get("is_active", 1)))
            self._set_combo_to_data(self.parent_combo, org.get("parent_organization_id"))
            self._set_combo_to_data(self.org_type_combo, org.get("organization_type_id"))
            self._set_combo_to_data(self.rank_structure_combo, org.get("default_rank_structure_id"))
            self._set_detail_enabled(True)
        self._block_detail_signals(False)
        self._set_dirty(False)

    def _on_detail_changed(self) -> None:
        if self._selected_org_id:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self.btn_save.setEnabled(dirty)
        self.btn_revert.setEnabled(dirty)

    def _set_detail_enabled(self, enabled: bool) -> None:
        for w in (self.name_edit, self.short_name_edit, self.parent_combo,
                  self.org_type_combo, self.rank_structure_combo, self.active_check,
                  self.external_id_edit, self.callsign_prefix_edit, self.notes_edit):
            w.setEnabled(enabled)

    def _block_detail_signals(self, block: bool) -> None:
        for w in (self.name_edit, self.short_name_edit, self.external_id_edit,
                  self.callsign_prefix_edit, self.notes_edit, self.parent_combo,
                  self.org_type_combo, self.rank_structure_combo, self.active_check):
            w.blockSignals(block)

    def _update_status(self) -> None:
        if not self._selected_org_id:
            self._status_label.setText("No organization selected")
            return
        org = self.controller.get_organization(self._selected_org_id)
        if org:
            children = self.controller.list_children(self._selected_org_id)
            self._status_label.setText(
                f"{org.get('name', '')}  ·  {len(children)} child org(s)"
            )

    # ---- CRUD ----------------------------------------------------------------
    def _save_detail(self) -> None:
        if not self._selected_org_id:
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Organization Name is required.")
            return
        if self.org_type_combo.currentData() is None:
            QMessageBox.warning(self, "Validation", "Organization Type is required.")
            return
        existing = self.controller.get_organization(self._selected_org_id) or {}
        payload: dict[str, Any] = {
            "name":                      self.name_edit.text().strip(),
            "short_name":                self.short_name_edit.text().strip(),
            "parent_organization_id":    self.parent_combo.currentData(),
            "organization_type_id":      self.org_type_combo.currentData(),
            "default_rank_structure_id": self.rank_structure_combo.currentData(),
            "is_active":                 1 if self.active_check.isChecked() else 0,
            "notes":                     self.notes_edit.toPlainText().strip(),
            "external_id":               self.external_id_edit.text().strip() or None,
            "callsign_prefix":           self.callsign_prefix_edit.text().strip() or None,
            "sort_order":                existing.get("sort_order", 0),
        }
        try:
            self.controller.update_organization(self._selected_org_id, payload)
        except ValueError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
            return
        self.refresh_all()

    def _revert_detail(self) -> None:
        self._reload_detail_form()

    def _create_root_organization(self) -> None:
        dlg = NewOrganizationDialog(self.controller, parent=self, parent_id=None)
        if dlg.exec():
            org_id = self.controller.create_organization(dlg.payload())
            self._selected_org_id = org_id
            self.refresh_all()

    def _create_sub_organization(self) -> None:
        if not self._selected_org_id:
            QMessageBox.information(self, "Select Parent", "Select a parent organization first.")
            return
        dlg = NewOrganizationDialog(self.controller, parent=self, parent_id=self._selected_org_id)
        if dlg.exec():
            org_id = self.controller.create_organization(dlg.payload())
            self._selected_org_id = org_id
            self.refresh_all()

    def _delete_selected(self) -> None:
        if not self._selected_org_id:
            QMessageBox.warning(self, "Units and Organizations", "Select an organization first.")
            return
        if QMessageBox.question(
            self, "Delete", "Delete this organization? Cannot be undone.",
        ) != QMessageBox.Yes:
            return
        result = self.controller.delete_organization(self._selected_org_id)
        if not result.deleted:
            QMessageBox.warning(self, "Delete Failed", result.message)
        self._selected_org_id = None
        self.refresh_all()

    def _move_selected(self, direction: int) -> None:
        if not self._selected_org_id:
            return
        self.controller.move_organization(self._selected_org_id, direction)
        self.refresh_all()

    def _duplicate_selected(self) -> None:
        if not self._selected_org_id:
            return
        org = self.controller.get_organization(self._selected_org_id)
        if not org:
            return
        payload = {
            "name":                      f"{org['name']} Copy",
            "short_name":                org.get("short_name") or "",
            "parent_organization_id":    org.get("parent_organization_id"),
            "organization_type_id":      org.get("organization_type_id"),
            "default_rank_structure_id": org.get("default_rank_structure_id"),
            "is_active":                 org.get("is_active", 1),
            "notes":                     org.get("notes") or "",
            "external_id":               None,
            "callsign_prefix":           org.get("callsign_prefix"),
            "sort_order":                int(org.get("sort_order", 0)) + 1,
        }
        new_id = self.controller.create_organization(payload)
        self._selected_org_id = new_id
        self.refresh_all()

    def _open_type_manager(self) -> None:
        OrganizationTypeManagerDialog(self.controller, parent=self).exec()
        self.refresh_all()

    def _open_rank_templates(self) -> None:
        RankTemplateManagerDialog(self.controller, parent=self).exec()
        self.refresh_all()

    def _on_import_csv(self) -> None:
        from utils.edit_menu_io import UnitsOrganizationsIO, do_import_csv
        do_import_csv(UnitsOrganizationsIO(), self)
        self.refresh_all()

    def _on_export_csv(self) -> None:
        from utils.edit_menu_io import UnitsOrganizationsIO, do_export_csv
        do_export_csv(UnitsOrganizationsIO(), self)

    # ---- Context menu --------------------------------------------------------
    def _show_tree_context_menu(self, position: QPoint) -> None:
        item = self.tree.itemAt(position)
        if item:
            self.tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("New Organization", self._create_root_organization)
        if self._selected_org_id:
            menu.addAction("New Sub-Organization", self._create_sub_organization)
            menu.addAction("Reparent…", self._reparent_selected)
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

    # ---- Utility -------------------------------------------------------------
    @staticmethod
    def _set_combo_to_data(combo: QComboBox, data: Any) -> None:
        idx = combo.findData(data)
        combo.setCurrentIndex(idx if idx >= 0 else 0)


__all__ = ["UnitsOrganizationsPanel"]
