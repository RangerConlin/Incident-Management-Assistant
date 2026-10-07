"""GAR Template Manager — admin editor for the master GAR scoring rubric library.

A GAR template is groups -> rows -> options (each option carrying a point
value and an optional hard No-Go flag), plus a list of score bands. This
window lists existing templates and lets an admin create, clone, edit, or
deactivate one. There is no demo/placeholder content shipped by this
window itself — the one starting "Default GAR" template is inserted by
``data/db/sarapp_db/migrations/seed_default_gar_template.py``; everything
else (e.g. an org's own paper ORM form) is authored here.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.admin.gar_templates.data import gar_template_repository as repo
from utils.edit_window_kit import make_sync_status_label, refresh_sync_status_label

_GROUP_LEVEL = 0
_ROW_LEVEL = 1
_OPTION_LEVEL = 2


def _item_level(item: QTreeWidgetItem) -> int:
    depth = 0
    node = item
    while node.parent() is not None:
        depth += 1
        node = node.parent()
    return depth


class GarTemplateManagerWindow(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GAR Template Manager")
        self.resize(1000, 700)
        self._templates: list[dict[str, Any]] = []
        self._current_id: Optional[int] = None
        self._loading = False

        root = QHBoxLayout(self)

        # ---- Left: template list ----
        left = QVBoxLayout()
        left_label = QLabel("Templates")
        left_label.setStyleSheet("font-weight: 600;")
        left.addWidget(left_label)
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_template_selected)
        left.addWidget(self._list, 1)

        list_btns = QHBoxLayout()
        self._new_btn = QPushButton("New")
        self._clone_btn = QPushButton("Clone")
        self._toggle_active_btn = QPushButton("Deactivate")
        self._new_btn.clicked.connect(self._new_template)
        self._clone_btn.clicked.connect(self._clone_template)
        self._toggle_active_btn.clicked.connect(self._toggle_active)
        list_btns.addWidget(self._new_btn)
        list_btns.addWidget(self._clone_btn)
        list_btns.addWidget(self._toggle_active_btn)
        left.addLayout(list_btns)

        self._sync_status_label = make_sync_status_label()
        left.addWidget(self._sync_status_label)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(240)
        left_widget.setMaximumWidth(320)

        # ---- Right: template editor ----
        right = QVBoxLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Template name")
        self._source_edit = QLineEdit()
        self._source_edit.setPlaceholderText("Source / organization (e.g. \"Generic\", \"CAP Michigan Wing\")")
        right.addWidget(QLabel("Name"))
        right.addWidget(self._name_edit)
        right.addWidget(QLabel("Source"))
        right.addWidget(self._source_edit)

        self._description_edit = QPlainTextEdit()
        self._description_edit.setPlaceholderText("Description")
        self._description_edit.setFixedHeight(50)
        right.addWidget(QLabel("Description"))
        right.addWidget(self._description_edit)

        right.addWidget(QLabel("Groups / Rows / Options"))
        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Label", "Points", "No-Go"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        right.addWidget(self._tree, 1)

        tree_btns = QHBoxLayout()
        add_group_btn = QPushButton("Add Group")
        add_row_btn = QPushButton("Add Row")
        add_option_btn = QPushButton("Add Option")
        remove_btn = QPushButton("Remove Selected")
        add_group_btn.clicked.connect(self._add_group)
        add_row_btn.clicked.connect(self._add_row)
        add_option_btn.clicked.connect(self._add_option)
        remove_btn.clicked.connect(self._remove_selected_tree_item)
        tree_btns.addWidget(add_group_btn)
        tree_btns.addWidget(add_row_btn)
        tree_btns.addWidget(add_option_btn)
        tree_btns.addWidget(remove_btn)
        right.addLayout(tree_btns)

        right.addWidget(QLabel("Bands (highest floor the score meets or exceeds wins)"))
        self._bands_table = QTableWidget(0, 3)
        self._bands_table.setHorizontalHeaderLabels(["Floor", "Label", "Required Reviewer"])
        self._bands_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._bands_table.setFixedHeight(140)
        right.addWidget(self._bands_table)

        band_btns = QHBoxLayout()
        add_band_btn = QPushButton("Add Band")
        remove_band_btn = QPushButton("Remove Band")
        add_band_btn.clicked.connect(self._add_band)
        remove_band_btn.clicked.connect(self._remove_band)
        band_btns.addWidget(add_band_btn)
        band_btns.addWidget(remove_band_btn)
        right.addLayout(band_btns)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self._save_btn = QPushButton("Save Template")
        self._save_btn.clicked.connect(self._save)
        save_row.addWidget(self._save_btn)
        right.addLayout(save_row)

        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        self._set_editor_enabled(False)
        self.reload()
        refresh_sync_status_label(self, self._sync_status_label, "gar_templates")

    # ---- Template list ----

    def reload(self) -> None:
        try:
            self._templates = repo.list_gar_templates(include_inactive=True)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Templates", f"Failed to load templates:\n{exc}")
            self._templates = []
        self._list.blockSignals(True)
        self._list.clear()
        for template in self._templates:
            label = template.get("name") or f"Template {template.get('id')}"
            if not template.get("active", True):
                label += "  (inactive)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, template.get("id"))
            self._list.addItem(item)
        self._list.blockSignals(False)
        if self._templates:
            self._list.setCurrentRow(0)
        else:
            self._current_id = None
            self._set_editor_enabled(False)

    def _on_template_selected(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            self._current_id = None
            self._set_editor_enabled(False)
            return
        template_id = current.data(Qt.UserRole)
        self._load_template(int(template_id))

    def _load_template(self, template_id: int) -> None:
        try:
            template = repo.get_gar_template(template_id)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Templates", f"Failed to load template:\n{exc}")
            return
        self._loading = True
        self._current_id = template_id
        self._name_edit.setText(template.get("name") or "")
        self._source_edit.setText(template.get("source") or "")
        self._description_edit.setPlainText(template.get("description") or "")
        self._populate_tree(template.get("groups") or [])
        self._populate_bands(template.get("bands") or [])
        self._toggle_active_btn.setText("Deactivate" if template.get("active", True) else "Activate")
        self._set_editor_enabled(True)
        self._loading = False

    def _set_editor_enabled(self, enabled: bool) -> None:
        for widget in (
            self._name_edit,
            self._source_edit,
            self._description_edit,
            self._tree,
            self._bands_table,
            self._save_btn,
            self._clone_btn,
            self._toggle_active_btn,
        ):
            widget.setEnabled(enabled)

    # ---- Tree population ----

    def _populate_tree(self, groups: list[dict[str, Any]]) -> None:
        self._tree.clear()
        for group in groups:
            group_item = QTreeWidgetItem([group.get("name") or "", "", ""])
            group_item.setFlags(group_item.flags() | Qt.ItemIsEditable)
            self._tree.addTopLevelItem(group_item)
            for row in group.get("rows") or []:
                row_item = QTreeWidgetItem([row.get("label") or "", "", ""])
                row_item.setFlags(row_item.flags() | Qt.ItemIsEditable)
                group_item.addChild(row_item)
                for option in row.get("options") or []:
                    option_item = QTreeWidgetItem(
                        [option.get("label") or "", str(option.get("points") or 0), ""]
                    )
                    option_item.setFlags(option_item.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
                    option_item.setCheckState(
                        2, Qt.Checked if option.get("no_go") else Qt.Unchecked
                    )
                    row_item.addChild(option_item)
        self._tree.expandAll()

    def _populate_bands(self, bands: list[dict[str, Any]]) -> None:
        self._bands_table.setRowCount(0)
        for band in bands:
            row = self._bands_table.rowCount()
            self._bands_table.insertRow(row)
            self._bands_table.setItem(row, 0, QTableWidgetItem(str(band.get("floor", 0))))
            self._bands_table.setItem(row, 1, QTableWidgetItem(band.get("label") or ""))
            self._bands_table.setItem(row, 2, QTableWidgetItem(band.get("required_reviewer") or ""))

    # ---- Tree editing ----

    def _add_group(self) -> None:
        item = QTreeWidgetItem(["New Group", "", ""])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._tree.addTopLevelItem(item)
        self._tree.setCurrentItem(item)
        self._tree.editItem(item, 0)

    def _add_row(self) -> None:
        group_item = self._selected_group_item()
        if group_item is None:
            QMessageBox.information(self, "Add Row", "Select a group first.")
            return
        item = QTreeWidgetItem(["New Row", "", ""])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        group_item.addChild(item)
        group_item.setExpanded(True)
        self._tree.setCurrentItem(item)
        self._tree.editItem(item, 0)

    def _add_option(self) -> None:
        row_item = self._selected_row_item()
        if row_item is None:
            QMessageBox.information(self, "Add Option", "Select a row first.")
            return
        item = QTreeWidgetItem(["New Option", "0", ""])
        item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
        item.setCheckState(2, Qt.Unchecked)
        row_item.addChild(item)
        row_item.setExpanded(True)
        self._tree.setCurrentItem(item)
        self._tree.editItem(item, 0)

    def _selected_group_item(self) -> Optional[QTreeWidgetItem]:
        item = self._tree.currentItem()
        if item is None:
            return None
        level = _item_level(item)
        while level > _GROUP_LEVEL:
            item = item.parent()
            level -= 1
        return item

    def _selected_row_item(self) -> Optional[QTreeWidgetItem]:
        item = self._tree.currentItem()
        if item is None:
            return None
        level = _item_level(item)
        if level == _GROUP_LEVEL:
            return None
        while level > _ROW_LEVEL:
            item = item.parent()
            level -= 1
        return item

    def _remove_selected_tree_item(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        parent = item.parent()
        if parent is None:
            index = self._tree.indexOfTopLevelItem(item)
            self._tree.takeTopLevelItem(index)
        else:
            parent.removeChild(item)

    # ---- Band editing ----

    def _add_band(self) -> None:
        row = self._bands_table.rowCount()
        self._bands_table.insertRow(row)
        self._bands_table.setItem(row, 0, QTableWidgetItem("0"))
        self._bands_table.setItem(row, 1, QTableWidgetItem("New Band"))
        self._bands_table.setItem(row, 2, QTableWidgetItem(""))

    def _remove_band(self) -> None:
        row = self._bands_table.currentRow()
        if row >= 0:
            self._bands_table.removeRow(row)

    # ---- Save / new / clone / activate ----

    def _collect_payload(self) -> Optional[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for gi in range(self._tree.topLevelItemCount()):
            group_item = self._tree.topLevelItem(gi)
            rows: list[dict[str, Any]] = []
            for ri in range(group_item.childCount()):
                row_item = group_item.child(ri)
                options: list[dict[str, Any]] = []
                for oi in range(row_item.childCount()):
                    option_item = row_item.child(oi)
                    try:
                        points = int(option_item.text(1) or 0)
                    except ValueError:
                        QMessageBox.warning(
                            self, "GAR Templates", f"Option '{option_item.text(0)}' has a non-numeric points value."
                        )
                        return None
                    options.append(
                        {
                            "id": f"o{oi + 1}",
                            "label": option_item.text(0).strip(),
                            "points": points,
                            "no_go": option_item.checkState(2) == Qt.Checked,
                        }
                    )
                if not options:
                    QMessageBox.warning(self, "GAR Templates", f"Row '{row_item.text(0)}' needs at least one option.")
                    return None
                rows.append({"id": f"r{ri + 1}", "label": row_item.text(0).strip(), "options": options})
            if not rows:
                QMessageBox.warning(self, "GAR Templates", f"Group '{group_item.text(0)}' needs at least one row.")
                return None
            groups.append({"id": f"g{gi + 1}", "name": group_item.text(0).strip(), "rows": rows})
        if not groups:
            QMessageBox.warning(self, "GAR Templates", "Template needs at least one group.")
            return None

        bands: list[dict[str, Any]] = []
        for row in range(self._bands_table.rowCount()):
            floor_item = self._bands_table.item(row, 0)
            label_item = self._bands_table.item(row, 1)
            reviewer_item = self._bands_table.item(row, 2)
            try:
                floor = int((floor_item.text() if floor_item else "0") or 0)
            except ValueError:
                QMessageBox.warning(self, "GAR Templates", f"Band row {row + 1} has a non-numeric floor.")
                return None
            bands.append(
                {
                    "floor": floor,
                    "label": (label_item.text() if label_item else "").strip(),
                    "required_reviewer": (reviewer_item.text() if reviewer_item else "").strip(),
                }
            )
        if not bands:
            QMessageBox.warning(self, "GAR Templates", "Template needs at least one band.")
            return None

        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "GAR Templates", "Template needs a name.")
            return None

        return {
            "name": name,
            "source": self._source_edit.text().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "groups": groups,
            "bands": bands,
            "active": True,
        }

    def _save(self) -> None:
        payload = self._collect_payload()
        if payload is None:
            return
        try:
            if self._current_id is None:
                repo.create_gar_template(payload)
            else:
                repo.save_gar_template(self._current_id, payload)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Templates", f"Failed to save template:\n{exc}")
            return
        self.reload()

    def _new_template(self) -> None:
        self._current_id = None
        self._name_edit.setText("New GAR Template")
        self._source_edit.clear()
        self._description_edit.clear()
        self._tree.clear()
        self._bands_table.setRowCount(0)
        self._add_band()
        self._set_editor_enabled(True)
        self._toggle_active_btn.setText("Deactivate")
        self._list.setCurrentItem(None)

    def _clone_template(self) -> None:
        if self._current_id is None:
            return
        try:
            repo.clone_gar_template(self._current_id)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Templates", f"Failed to clone template:\n{exc}")
            return
        self.reload()

    def _toggle_active(self) -> None:
        if self._current_id is None:
            return
        currently_active = self._toggle_active_btn.text() == "Deactivate"
        try:
            repo.set_gar_template_active(self._current_id, not currently_active)
        except Exception as exc:
            QMessageBox.critical(self, "GAR Templates", f"Failed to update template:\n{exc}")
            return
        self.reload()
