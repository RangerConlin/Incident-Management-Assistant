"""Forms Creator Hub — catalog browser, version matrix, and binding catalog."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.forms_creator.form_set_registry import FormSetRegistry
from modules.forms_creator.pdf_filler.pdf_filler import PDFFiller

from .dialogs.NewFormDialog import NewFormDialog
from .dialogs.CreateVersionDialog import CreateVersionDialog
from .dialogs.NewBindingDialog import NewBindingDialog
from .dialogs.NewFormSetDialog import NewFormSetDialog

_BINDING_CATALOG_PATH = Path(__file__).resolve().parents[3] / "forms" / "binding_catalog.json"


class HubWindow(QMainWindow):
    """Main entry point for form management: catalog, versions, and bindings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Forms Creator")
        self.resize(1100, 650)

        self._registry = FormSetRegistry()
        self._selected_form_id: str | None = None

        self._build_toolbar()
        self._build_central()
        self._populate_catalog_tree()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        self._new_form_btn = QPushButton("+ New Form Definition")
        self._new_form_btn.clicked.connect(self._on_new_form)
        tb.addWidget(self._new_form_btn)

        self._new_set_btn = QPushButton("+ New Form Set")
        self._new_set_btn.clicked.connect(self._on_new_form_set)
        tb.addWidget(self._new_set_btn)

        self._manage_sets_btn = QPushButton("Manage Form Sets…")
        self._manage_sets_btn.clicked.connect(self._on_manage_sets)
        tb.addWidget(self._manage_sets_btn)

    def _build_central(self) -> None:
        top_tabs = QTabWidget(self)
        self.setCentralWidget(top_tabs)

        # --- Tab 1: Forms ---
        forms_widget = QWidget()
        forms_layout = QVBoxLayout(forms_widget)
        forms_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        forms_layout.addWidget(splitter)

        # Left: catalog tree + edit/remove buttons
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.addWidget(QLabel("<b>Form Catalog</b>"))

        self._catalog_tree = QTreeWidget()
        self._catalog_tree.setHeaderHidden(True)
        self._catalog_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._catalog_tree.itemSelectionChanged.connect(self._on_form_selected)
        self._catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._catalog_tree.customContextMenuRequested.connect(self._catalog_context_menu)
        left_layout.addWidget(self._catalog_tree)

        catalog_btns = QHBoxLayout()
        self._edit_form_btn = QPushButton("Edit…")
        self._edit_form_btn.setEnabled(False)
        self._edit_form_btn.clicked.connect(self._on_edit_form)
        self._remove_form_btn = QPushButton("Remove…")
        self._remove_form_btn.setEnabled(False)
        self._remove_form_btn.setStyleSheet("color: #cc3333;")
        self._remove_form_btn.clicked.connect(self._on_remove_form)
        catalog_btns.addWidget(self._edit_form_btn)
        catalog_btns.addWidget(self._remove_form_btn)
        catalog_btns.addStretch()
        left_layout.addLayout(catalog_btns)

        left.setMinimumWidth(220)
        left.setMaximumWidth(300)
        splitter.addWidget(left)

        # Right: version matrix
        self._versions_widget = QWidget()
        splitter.addWidget(self._versions_widget)
        splitter.setStretchFactor(1, 1)

        top_tabs.addTab(forms_widget, "Forms")

        # --- Tab 2: Binding Catalog ---
        binding_widget = self._build_bindings_widget()
        top_tabs.addTab(binding_widget, "Binding Catalog")

        self._build_versions_panel()

    def _build_versions_panel(self) -> None:
        widget = self._versions_widget
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._form_header = QLabel("<i>Select a form from the catalog</i>")
        self._form_header.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._form_header)

        btn_row = QHBoxLayout()
        self._create_version_btn = QPushButton("+ Create Version for a Form Set…")
        self._create_version_btn.setEnabled(False)
        self._create_version_btn.clicked.connect(self._on_create_version)
        btn_row.addWidget(self._create_version_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._version_table = QTableWidget()
        self._version_table.setColumnCount(4)
        self._version_table.setHorizontalHeaderLabels(["Form Set", "Version", "Status", "Actions"])
        self._version_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._version_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._version_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._version_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._version_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._version_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._version_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._version_table.verticalHeader().setVisible(False)
        self._version_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._version_table.customContextMenuRequested.connect(self._version_context_menu)
        layout.addWidget(self._version_table)

    def _build_bindings_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("+ New Binding")
        new_btn.clicked.connect(self._on_new_binding)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._on_edit_binding)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete_binding)
        btn_row.addWidget(new_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._binding_tree = QTreeWidget()
        self._binding_tree.setColumnCount(3)
        self._binding_tree.setHeaderLabels(["Label", "Path", "Source Type"])
        self._binding_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._binding_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._binding_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._binding_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self._binding_tree)

        self._refresh_binding_tree()
        return widget

    # ------------------------------------------------------------------
    # Catalog tree
    # ------------------------------------------------------------------

    def _populate_catalog_tree(self) -> None:
        self._catalog_tree.clear()
        catalog = self._registry.list_catalog()
        categories: dict[str, QTreeWidgetItem] = {}
        for entry in catalog:
            cat = entry.category or "Other"
            if cat not in categories:
                cat_item = QTreeWidgetItem([cat])
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                font = cat_item.font(0)
                font.setBold(True)
                cat_item.setFont(0, font)
                self._catalog_tree.addTopLevelItem(cat_item)
                categories[cat] = cat_item
            form_item = QTreeWidgetItem([f"{entry.number}  —  {entry.title}"])
            form_item.setData(0, Qt.ItemDataRole.UserRole, entry.id)
            categories[cat].addChild(form_item)
        self._catalog_tree.expandAll()

    # ------------------------------------------------------------------
    # Form selection
    # ------------------------------------------------------------------

    def _catalog_context_menu(self, pos: QPoint) -> None:
        item = self._catalog_tree.itemAt(pos)
        if not item:
            return
        form_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not form_id:
            return
        menu = QMenu(self)
        menu.addAction("Edit Form Definition…", self._on_edit_form)
        sep = menu.addSeparator()
        remove_act = QAction("Remove Form Definition…", menu)
        remove_act.setEnabled(True)
        remove_act.triggered.connect(self._on_remove_form)
        menu.addAction(remove_act)
        menu.exec(self._catalog_tree.viewport().mapToGlobal(pos))

    def _version_context_menu(self, pos: QPoint) -> None:
        row = self._version_table.rowAt(pos.y())
        if row < 0 or not hasattr(self, "_version_row_meta"):
            return
        meta = self._version_row_meta.get(row)
        if not meta:
            return
        form_id, set_id, set_name, has_version = meta
        menu = QMenu(self)
        if has_version:
            menu.addAction("Open Mapper", lambda: self._open_mapper(form_id, set_id))
            menu.addSeparator()
            del_act = QAction("Delete Version…", menu)
            del_act.triggered.connect(lambda: self._on_delete_version(form_id, set_id, set_name))
            menu.addAction(del_act)
        else:
            menu.addAction("Create Version…", lambda: self._on_create_version(preselect_set=set_id))
        menu.exec(self._version_table.viewport().mapToGlobal(pos))

    def _on_form_selected(self) -> None:
        items = self._catalog_tree.selectedItems()
        if not items:
            self._edit_form_btn.setEnabled(False)
            self._remove_form_btn.setEnabled(False)
            return
        form_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not form_id:
            self._edit_form_btn.setEnabled(False)
            self._remove_form_btn.setEnabled(False)
            return
        self._selected_form_id = form_id
        self._edit_form_btn.setEnabled(True)
        self._remove_form_btn.setEnabled(True)
        self._refresh_versions_tab(form_id)

    def _refresh_versions_tab(self, form_id: str) -> None:
        entry = self._registry.get_form_definition(form_id)
        if not entry:
            return
        self._form_header.setText(f"<b>{entry.number}</b> — {entry.title}")
        self._create_version_btn.setEnabled(True)

        coverage = self._registry.coverage(form_id)
        sets = self._registry.list_sets()

        self._version_row_meta: dict[int, tuple] = {}
        self._version_table.setRowCount(len(sets))
        for row, set_meta in enumerate(sets):
            impl = coverage.implementations.get(set_meta.id, {})
            has_pdf = impl.get("has_pdf", False)
            has_mapping = impl.get("has_mapping", False)
            unmapped = impl.get("unmapped_count", 0)
            fallback = impl.get("fallback_set")
            version = impl.get("version") or ""
            has_version = has_pdf or has_mapping

            self._version_row_meta[row] = (form_id, set_meta.id, set_meta.display_name, has_version)

            self._version_table.setItem(row, 0, QTableWidgetItem(set_meta.display_name))
            self._version_table.setItem(row, 1, QTableWidgetItem(version or "—"))

            if has_pdf and has_mapping and unmapped == 0:
                status_text = "✓  Complete"
                status_color = "#2d7a2d"
            elif has_pdf and has_mapping and unmapped > 0:
                status_text = f"⚠  {unmapped} unmapped field{'s' if unmapped != 1 else ''}"
                status_color = "#9a6700"
            elif has_version:
                status_text = "⚠  Incomplete (missing PDF or mapping)"
                status_color = "#9a6700"
            elif fallback:
                status_text = f"—  Uses {fallback}"
                status_color = "#666666"
            else:
                status_text = "×  No implementation"
                status_color = "#aa3333"

            label = QLabel(status_text)
            label.setStyleSheet(f"color: {status_color}; padding: 2px 6px;")
            self._version_table.setCellWidget(row, 2, label)
            self._version_table.setItem(row, 2, QTableWidgetItem(""))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)

            if has_version:
                open_btn = QPushButton("Open Mapper")
                open_btn.setFixedHeight(24)
                open_btn.clicked.connect(
                    lambda checked=False, fid=form_id, sid=set_meta.id: self._open_mapper(fid, sid)
                )
                actions_layout.addWidget(open_btn)

                del_btn = QPushButton("Delete Version")
                del_btn.setFixedHeight(24)
                del_btn.setStyleSheet("color: #cc3333;")
                del_btn.clicked.connect(
                    lambda checked=False, fid=form_id, sid=set_meta.id,
                    sname=set_meta.display_name: self._on_delete_version(fid, sid, sname)
                )
                actions_layout.addWidget(del_btn)
            else:
                create_btn = QPushButton("Create Version")
                create_btn.setFixedHeight(24)
                create_btn.clicked.connect(
                    lambda checked=False, sid=set_meta.id: self._on_create_version(preselect_set=sid)
                )
                actions_layout.addWidget(create_btn)

            actions_layout.addStretch()
            self._version_table.setCellWidget(row, 3, actions_widget)

        self._version_table.resizeRowsToContents()

    # ------------------------------------------------------------------
    # New / Edit / Remove form definition
    # ------------------------------------------------------------------

    def _on_new_form(self) -> None:
        catalog = self._registry.list_catalog()
        existing_ids = {e.id for e in catalog}
        existing_cats = list(dict.fromkeys(e.category for e in catalog if e.category))
        dlg = NewFormDialog(existing_ids, existing_cats, parent=self)
        if dlg.exec() != NewFormDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        self._registry.add_form_definition(
            form_id=data["id"], number=data["number"],
            title=data["title"], category=data["category"],
        )
        self._populate_catalog_tree()
        self._select_form_in_tree(data["id"])

    def _on_edit_form(self) -> None:
        if not self._selected_form_id:
            return
        entry = self._registry.get_form_definition(self._selected_form_id)
        if not entry:
            return
        catalog = self._registry.list_catalog()
        existing_ids = {e.id for e in catalog}
        existing_cats = list(dict.fromkeys(e.category for e in catalog if e.category))
        existing = {"id": entry.id, "number": entry.number, "title": entry.title, "category": entry.category}
        dlg = NewFormDialog(existing_ids, existing_cats, existing=existing, parent=self)
        if dlg.exec() != NewFormDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        self._registry.update_form_definition(
            form_id=data["id"], number=data["number"],
            title=data["title"], category=data["category"],
        )
        self._populate_catalog_tree()
        self._select_form_in_tree(data["id"])

    def _on_remove_form(self) -> None:
        if not self._selected_form_id:
            return
        entry = self._registry.get_form_definition(self._selected_form_id)
        if not entry:
            return
        # Warn if any versions exist
        coverage = self._registry.coverage(self._selected_form_id)
        version_sets = [sid for sid, impl in coverage.implementations.items()
                        if impl.get("has_pdf") or impl.get("has_mapping")]
        warning = ""
        if version_sets:
            warning = (f"\n\n⚠ This form has versions in {len(version_sets)} form set(s). "
                       f"Those files will NOT be deleted — only the catalog entry is removed.")

        reply = QMessageBox.question(
            self, "Remove Form Definition",
            f"Remove '{entry.number} — {entry.title}' from the catalog?{warning}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._registry.remove_form_definition(self._selected_form_id)
        self._selected_form_id = None
        self._edit_form_btn.setEnabled(False)
        self._remove_form_btn.setEnabled(False)
        self._create_version_btn.setEnabled(False)
        self._form_header.setText("<i>Select a form from the catalog</i>")
        self._version_table.setRowCount(0)
        self._populate_catalog_tree()

    def _select_form_in_tree(self, form_id: str) -> None:
        it = self._catalog_tree.invisibleRootItem()
        for i in range(it.childCount()):
            cat_item = it.child(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == form_id:
                    self._catalog_tree.setCurrentItem(child)
                    return

    # ------------------------------------------------------------------
    # New / Edit / Remove form set
    # ------------------------------------------------------------------

    def _on_new_form_set(self) -> None:
        sets = self._registry.list_sets()
        existing_ids = {s.id for s in sets}
        existing_with_names = [(s.id, s.display_name) for s in sets]
        dlg = NewFormSetDialog(existing_ids, existing_with_names, parent=self)
        if dlg.exec() != NewFormSetDialog.DialogCode.Accepted:
            return
        self._registry = FormSetRegistry()
        if self._selected_form_id:
            self._refresh_versions_tab(self._selected_form_id)

    def _on_manage_sets(self) -> None:
        """Show a dialog listing all sets with Edit and Remove per row."""
        from .ManageSetsDialog import ManageSetsDialog
        dlg = ManageSetsDialog(self._registry, parent=self)
        dlg.exec()
        # Reload registry in case sets changed
        self._registry = FormSetRegistry()
        if self._selected_form_id:
            self._refresh_versions_tab(self._selected_form_id)

    # ------------------------------------------------------------------
    # Create / Delete version
    # ------------------------------------------------------------------

    def _on_create_version(self, checked=False, preselect_set: str | None = None) -> None:
        if not self._selected_form_id:
            QMessageBox.information(self, "Create Version", "Select a form first.")
            return
        entry = self._registry.get_form_definition(self._selected_form_id)
        sets = self._registry.list_sets()
        if preselect_set:
            sets = sorted(sets, key=lambda s: (s.id != preselect_set, s.id))

        dlg = CreateVersionDialog(
            self._selected_form_id,
            entry.title if entry else self._selected_form_id,
            sets, self,
        )
        if dlg.exec() != CreateVersionDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return

        set_meta = self._registry.get_set(data["set_id"])
        if not set_meta:
            return

        form_dir = set_meta.path / self._selected_form_id
        form_dir.mkdir(parents=True, exist_ok=True)

        dest_pdf = form_dir / "template.pdf"
        try:
            shutil.copy2(data["pdf_path"], dest_pdf)
        except Exception as exc:
            QMessageBox.critical(self, "Create Version", f"Could not copy PDF:\n{exc}")
            return

        mapping_path = form_dir / "mapping.json"
        try:
            PDFFiller.generate_mapping_scaffold(dest_pdf, mapping_path)
        except Exception as exc:
            QMessageBox.warning(
                self, "Create Version",
                f"Could not generate mapping scaffold:\n{exc}\nThe PDF was copied — edit mapping.json manually.",
            )

        self._open_mapper(self._selected_form_id, data["set_id"])
        self._registry = FormSetRegistry()
        self._refresh_versions_tab(self._selected_form_id)

    def _on_delete_version(self, form_id: str, set_id: str, set_name: str) -> None:
        entry = self._registry.get_form_definition(form_id)
        form_label = f"{entry.number} — {entry.title}" if entry else form_id
        reply = QMessageBox.question(
            self, "Delete Version",
            f"Delete the '{set_name}' version of {form_label}?\n\n"
            f"This will permanently delete template.pdf and mapping.json for this form/set combination.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._registry.remove_version(form_id, set_id)
        self._registry = FormSetRegistry()
        self._refresh_versions_tab(form_id)

    # ------------------------------------------------------------------
    # Open mapper
    # ------------------------------------------------------------------

    def _open_mapper(self, form_id: str, set_id: str) -> None:
        from .MapperWindow import MapperWindow
        w = MapperWindow(form_id, set_id, parent=self)
        w.show()

    # ------------------------------------------------------------------
    # Binding catalog
    # ------------------------------------------------------------------

    def _load_binding_catalog(self) -> list[dict]:
        try:
            return json.loads(_BINDING_CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_binding_catalog(self, entries: list[dict]) -> None:
        _BINDING_CATALOG_PATH.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _refresh_binding_tree(self) -> None:
        self._binding_tree.clear()
        entries = self._load_binding_catalog()
        categories: dict[str, QTreeWidgetItem] = {}
        for entry in entries:
            cat = entry.get("category", "Other")
            if cat not in categories:
                cat_item = QTreeWidgetItem([cat, "", ""])
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                font = cat_item.font(0)
                font.setBold(True)
                cat_item.setFont(0, font)
                self._binding_tree.addTopLevelItem(cat_item)
                categories[cat] = cat_item
            row = QTreeWidgetItem([
                entry.get("label", ""),
                entry.get("path", ""),
                entry.get("source_type", ""),
            ])
            row.setData(0, Qt.ItemDataRole.UserRole, entry)
            categories[cat].addChild(row)
        self._binding_tree.expandAll()

    def _selected_binding_item(self) -> QTreeWidgetItem | None:
        items = self._binding_tree.selectedItems()
        if not items:
            return None
        item = items[0]
        if not item.data(0, Qt.ItemDataRole.UserRole):
            return None
        return item

    def _on_new_binding(self) -> None:
        entries = self._load_binding_catalog()
        existing_paths = {e.get("path", "") for e in entries}
        dlg = NewBindingDialog(existing_paths=existing_paths, parent=self)
        if dlg.exec() != NewBindingDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        entries.append(data)
        self._save_binding_catalog(entries)
        self._refresh_binding_tree()

    def _on_edit_binding(self) -> None:
        item = self._selected_binding_item()
        if not item:
            QMessageBox.information(self, "Edit Binding", "Select a binding entry first.")
            return
        existing = item.data(0, Qt.ItemDataRole.UserRole)
        entries = self._load_binding_catalog()
        existing_paths = {e.get("path", "") for e in entries}
        dlg = NewBindingDialog(existing=existing, existing_paths=existing_paths, parent=self)
        if dlg.exec() != NewBindingDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        orig_path = existing.get("path", "")
        for i, e in enumerate(entries):
            if e.get("path") == orig_path:
                entries[i] = data
                break
        self._save_binding_catalog(entries)
        self._refresh_binding_tree()

    def _on_delete_binding(self) -> None:
        item = self._selected_binding_item()
        if not item:
            QMessageBox.information(self, "Delete Binding", "Select a binding entry first.")
            return
        existing = item.data(0, Qt.ItemDataRole.UserRole)
        label = existing.get("label", existing.get("path", "?"))
        reply = QMessageBox.question(
            self, "Delete Binding",
            f"Delete binding '{label}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        entries = self._load_binding_catalog()
        orig_path = existing.get("path", "")
        entries = [e for e in entries if e.get("path") != orig_path]
        self._save_binding_catalog(entries)
        self._refresh_binding_tree()
