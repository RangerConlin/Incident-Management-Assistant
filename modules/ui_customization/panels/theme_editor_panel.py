from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QColorDialog,
    QMessageBox,
    QInputDialog,
)

from styles.palette import THEMES

from ..models import ThemeProfile
from ..repository import UICustomizationRepository
from ..services import apply_theme_profile


class ThemeEditorPanel(QWidget):
    """Advanced theme editing panel allowing token overrides."""

    def __init__(
        self,
        main_window,
        repo: Optional[UICustomizationRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._repo = repo or UICustomizationRepository()
        self._current_theme_id: Optional[str] = None

        self.setWindowTitle("Theme Designer")
        root = QVBoxLayout(self)

        row = QHBoxLayout()
        self._theme_list = QListWidget(self)
        self._theme_list.currentItemChanged.connect(lambda current, _: self._load_theme(current))
        row.addWidget(self._theme_list, 1)

        editor_col = QVBoxLayout()
        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("Theme Name:"))
        self._name_edit = QLineEdit(self)
        meta_row.addWidget(self._name_edit)
        editor_col.addLayout(meta_row)

        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("Base Theme:"))
        self._base_label = QLabel("light", self)
        base_row.addWidget(self._base_label)
        editor_col.addLayout(base_row)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("Description:"))
        self._description_edit = QLineEdit(self)
        desc_row.addWidget(self._description_edit)
        editor_col.addLayout(desc_row)

        self._table = QTableWidget(self)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Token", "Value", "Preview"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._handle_table_change)
        editor_col.addWidget(self._table, 1)

        editor_buttons = QHBoxLayout()
        self._btn_pick = QPushButton("Pick Color…")
        self._btn_add_token = QPushButton("Add Token…")
        self._btn_remove_token = QPushButton("Remove Token")
        editor_buttons.addWidget(self._btn_pick)
        editor_buttons.addWidget(self._btn_add_token)
        editor_buttons.addWidget(self._btn_remove_token)
        editor_buttons.addStretch(1)
        editor_col.addLayout(editor_buttons)

        row.addLayout(editor_col, 2)
        root.addLayout(row, 1)

        action_row = QHBoxLayout()
        self._btn_new = QPushButton("New Theme…")
        self._btn_duplicate = QPushButton("Duplicate")
        self._btn_delete = QPushButton("Delete")
        self._btn_save = QPushButton("Save")
        self._btn_apply = QPushButton("Apply")
        action_row.addWidget(self._btn_new)
        action_row.addWidget(self._btn_duplicate)
        action_row.addWidget(self._btn_delete)
        action_row.addStretch(1)
        action_row.addWidget(self._btn_save)
        action_row.addWidget(self._btn_apply)
        root.addLayout(action_row)

        self._btn_pick.clicked.connect(self._pick_color)
        self._btn_add_token.clicked.connect(self._add_token)
        self._btn_remove_token.clicked.connect(self._remove_token)
        self._btn_new.clicked.connect(self._create_theme)
        self._btn_duplicate.clicked.connect(self._duplicate_theme)
        self._btn_delete.clicked.connect(self._delete_theme)
        self._btn_save.clicked.connect(self._save_theme)
        self._btn_apply.clicked.connect(self._apply_theme)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._theme_list.clear()
        for theme in self._repo.list_themes():
            label = theme.name or theme.id
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, theme.id)
            if getattr(theme, "is_default", False):
                item.setText(f"{label} (Active)")
            self._theme_list.addItem(item)
        if self._theme_list.count() > 0:
            self._theme_list.setCurrentRow(0)

    def _load_theme(self, item: QListWidgetItem | None) -> None:
        if not item:
            self._current_theme_id = None
            self._table.setRowCount(0)
            self._name_edit.setText("")
            self._description_edit.setText("")
            self._base_label.setText("-")
            return
        theme_id = item.data(Qt.UserRole)
        theme = self._repo.get_theme(str(theme_id))
        if not theme:
            return
        self._current_theme_id = theme.id
        self._name_edit.setText(theme.name)
        self._description_edit.setText(theme.description)
        self._base_label.setText(theme.base_theme)
        self._table.setRowCount(0)
        for row_idx, (token, value) in enumerate(sorted(theme.tokens.items())):
            self._table.insertRow(row_idx)
            key_item = QTableWidgetItem(token)
            key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            value_item = QTableWidgetItem(value)
            preview_item = QTableWidgetItem("")
            preview_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            color = QColor(value)
            preview_item.setBackground(color if color.isValid() else Qt.transparent)
            self._table.setItem(row_idx, 0, key_item)
            self._table.setItem(row_idx, 1, value_item)
            self._table.setItem(row_idx, 2, preview_item)

    def _pick_color(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        value_item = self._table.item(row, 1)
        current_value = value_item.text() if value_item else "#FFFFFF"
        color = QColorDialog.getColor(QColor(current_value), self, "Select Color")
        if color.isValid():
            value_item.setText(color.name())
            preview_item = self._table.item(row, 2)
            if preview_item:
                preview_item.setBackground(color)

    def _add_token(self) -> None:
        token, ok = QInputDialog.getText(self, "Add Token", "Token name:")
        if not ok or not str(token).strip():
            return
        value, ok_val = QInputDialog.getText(self, "Token Value", "Hex value:", text="#FFFFFF")
        if not ok_val:
            return
        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)
        key_item = QTableWidgetItem(str(token).strip())
        key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        value_item = QTableWidgetItem(str(value).strip())
        preview_item = QTableWidgetItem("")
        preview_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        preview_item.setBackground(QColor(str(value).strip()))
        self._table.setItem(row_idx, 0, key_item)
        self._table.setItem(row_idx, 1, value_item)
        self._table.setItem(row_idx, 2, preview_item)

    def _remove_token(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def _handle_table_change(self, item: QTableWidgetItem) -> None:
        if item.column() == 1:
            color = QColor(item.text())
            preview_item = self._table.item(item.row(), 2)
            if preview_item:
                preview_item.setBackground(color if color.isValid() else Qt.transparent)

    def _collect_tokens(self) -> dict[str, str]:
        tokens: dict[str, str] = {}
        for row in range(self._table.rowCount()):
            key_item = self._table.item(row, 0)
            value_item = self._table.item(row, 1)
            if not key_item or not value_item:
                continue
            key = key_item.text().strip()
            value = value_item.text().strip()
            if key:
                tokens[key] = value
        return tokens

    def _create_theme(self) -> None:
        name, ok = QInputDialog.getText(self, "New Theme", "Theme name:")
        if not ok or not str(name).strip():
            return
        base_theme, ok_base = QInputDialog.getItem(
            self,
            "Base Theme",
            "Start from theme:",
            list(THEMES.keys()),
            0,
            False,
        )
        if not ok_base:
            return
        tokens = dict(THEMES.get(base_theme, {}))
        theme = ThemeProfile(id="", name=str(name).strip(), base_theme=str(base_theme), description="", tokens=tokens)
        theme = self._repo.upsert_theme(theme)
        self.refresh()
        self._select_theme(theme.id)

    def _duplicate_theme(self) -> None:
        if not self._current_theme_id:
            return
        theme = self._repo.get_theme(self._current_theme_id)
        if not theme:
            return
        duplicate_name, ok = QInputDialog.getText(self, "Duplicate Theme", "New theme name:", text=f"{theme.name} Copy")
        if not ok or not str(duplicate_name).strip():
            return
        dup = ThemeProfile(
            id="",
            name=str(duplicate_name).strip(),
            base_theme=theme.base_theme,
            description=theme.description,
            tokens=dict(theme.tokens),
        )
        dup = self._repo.upsert_theme(dup)
        self.refresh()
        self._select_theme(dup.id)

    def _delete_theme(self) -> None:
        if not self._current_theme_id:
            return
        if QMessageBox.question(self, "Delete Theme", "Delete selected theme?") != QMessageBox.Yes:
            return
        self._repo.delete_theme(self._current_theme_id)
        self.refresh()

    def _save_theme(self) -> None:
        if not self._current_theme_id:
            QMessageBox.warning(self, "Theme", "No theme selected.")
            return
        theme = ThemeProfile(
            id=self._current_theme_id,
            name=self._name_edit.text().strip(),
            base_theme=self._base_label.text(),
            description=self._description_edit.text().strip(),
            tokens=self._collect_tokens(),
        )
        self._repo.upsert_theme(theme)
        QMessageBox.information(self, "Theme", "Theme saved.")
        self.refresh()
        self._select_theme(theme.id)

    def _apply_theme(self) -> None:
        if not self._current_theme_id:
            return
        theme = self._repo.get_theme(self._current_theme_id)
        if not theme:
            return
        self._repo.set_active_theme(theme.id)
        apply_theme_profile(theme, getattr(self._main_window, "theme_manager", None), getattr(self._main_window, "settings_bridge", None))
        QMessageBox.information(self, "Theme", "Theme applied.")
        self.refresh()
        self._select_theme(theme.id)

    def _select_theme(self, theme_id: str) -> None:
        for row in range(self._theme_list.count()):
            item = self._theme_list.item(row)
            if item.data(Qt.UserRole) == theme_id:
                self._theme_list.setCurrentRow(row)
                break


def get_theme_editor_panel(main_window) -> ThemeEditorPanel:
    repo = getattr(main_window, "customization_repo", None)
    return ThemeEditorPanel(main_window, repo=repo)
