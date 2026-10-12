from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QInputDialog,
    QFileDialog,
)

from ..models import LayoutTemplate
from ..repository import UICustomizationRepository
from ..services import capture_layout_state, apply_layout_state, ensure_active_layout


class LayoutManagerPanel(QWidget):
    """Panel that manages ADS layout templates with import/export helpers."""

    def __init__(
        self,
        main_window,
        repo: Optional[UICustomizationRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._repo = repo or UICustomizationRepository()

        self.setWindowTitle("Layout Templates")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Saved Layout Templates"))

        self._list = QListWidget(self)
        self._list.itemDoubleClicked.connect(lambda item: self._apply_selected())
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._btn_apply = QPushButton("Apply")
        self._btn_set_default = QPushButton("Set Active")
        self._btn_delete = QPushButton("Delete")
        btn_row.addWidget(self._btn_apply)
        btn_row.addWidget(self._btn_set_default)
        btn_row.addWidget(self._btn_delete)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        action_row = QHBoxLayout()
        self._btn_save_current = QPushButton("Save Current Layout…")
        self._btn_export = QPushButton("Export…")
        self._btn_import = QPushButton("Import…")
        action_row.addWidget(self._btn_save_current)
        action_row.addWidget(self._btn_export)
        action_row.addWidget(self._btn_import)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self._btn_apply.clicked.connect(self._apply_selected)
        self._btn_set_default.clicked.connect(self._set_default)
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_save_current.clicked.connect(self._save_current)
        self._btn_export.clicked.connect(self._export_bundle)
        self._btn_import.clicked.connect(self._import_bundle)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._list.clear()
        active_id = self._repo.active_layout_id()
        for layout in self._repo.list_layouts():
            item = QListWidgetItem(layout.name or layout.perspective_name or layout.id)
            item.setData(Qt.UserRole, layout.id)
            if layout.id == active_id:
                item.setText(f"{item.text()} (Active)")
            self._list.addItem(item)

    def _current_layout(self) -> Optional[LayoutTemplate]:
        item = self._list.currentItem()
        if not item:
            return None
        layout_id = item.data(Qt.UserRole)
        if not layout_id:
            return None
        return self._repo.get_layout(str(layout_id))

    def _apply_selected(self) -> None:
        layout = self._current_layout()
        if not layout:
            return
        dock_manager = getattr(self._main_window, "dock_manager", None)
        perspective_file = getattr(self._main_window, "_perspective_file", None)
        if not dock_manager or not perspective_file:
            QMessageBox.warning(self, "Apply Layout", "Dock manager not available.")
            return
        ok = apply_layout_state(dock_manager, perspective_file, layout.perspective_name, layout.ads_state)
        if not ok:
            QMessageBox.warning(self, "Apply Layout", "Failed to apply layout state.")
            return
        QMessageBox.information(self, "Layout Applied", f"Applied layout '{layout.name}'.")

    def _set_default(self) -> None:
        layout = self._current_layout()
        if not layout:
            return
        try:
            self._repo.set_active_layout(layout.id)
            dock_manager = getattr(self._main_window, "dock_manager", None)
            perspective_file = getattr(self._main_window, "_perspective_file", None)
            if dock_manager and perspective_file:
                ensure_active_layout(self._repo, dock_manager, perspective_file)
        except Exception as exc:
            QMessageBox.warning(self, "Set Active", f"Failed to set active layout: {exc}")
            return
        self.refresh()

    def _delete_selected(self) -> None:
        layout = self._current_layout()
        if not layout:
            return
        if QMessageBox.question(self, "Delete Layout", f"Delete layout '{layout.name}'?") != QMessageBox.Yes:
            return
        self._repo.delete_layout(layout.id)
        self.refresh()

    def _save_current(self) -> None:
        dock_manager = getattr(self._main_window, "dock_manager", None)
        perspective_file = getattr(self._main_window, "_perspective_file", None)
        if not dock_manager or not perspective_file:
            QMessageBox.warning(self, "Save Layout", "Dock manager not available.")
            return
        name, ok = QInputDialog.getText(self, "Save Layout", "Template name:")
        if not ok or not str(name).strip():
            return
        description, _ = QInputDialog.getText(self, "Description", "Optional description:")
        layout_id = uuid4().hex
        perspective_name = f"custom_layout_{layout_id}"
        ads_state = capture_layout_state(dock_manager, perspective_file, perspective_name)
        if not ads_state:
            QMessageBox.warning(self, "Save Layout", "Could not capture layout state.")
            return
        layout = LayoutTemplate(
            id=layout_id,
            name=str(name).strip(),
            perspective_name=perspective_name,
            description=str(description or ""),
            ads_state=ads_state,
            dashboard_widgets=[],
        )
        self._repo.upsert_layout(layout)
        self.refresh()

    def _export_bundle(self) -> None:
        bundle = self._repo.export_bundle()
        path, _ = QFileDialog.getSaveFileName(self, "Export Layouts", "customizations.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(bundle.to_dict(), fh, indent=2)
            QMessageBox.information(self, "Export", f"Exported to {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", f"Failed to export: {exc}")

    def _import_bundle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Layouts", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            from ..models import CustomizationBundle

            bundle = CustomizationBundle.from_dict(data)
            self._repo.import_bundle(bundle, replace=False)
            self.refresh()
            dock_manager = getattr(self._main_window, "dock_manager", None)
            perspective_file = getattr(self._main_window, "_perspective_file", None)
            if dock_manager and perspective_file:
                ensure_active_layout(self._repo, dock_manager, perspective_file)
            QMessageBox.information(self, "Import", "Import complete.")
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", f"Failed to import: {exc}")


def get_layout_manager_panel(main_window) -> LayoutManagerPanel:
    repo = getattr(main_window, "customization_repo", None)
    return LayoutManagerPanel(main_window, repo=repo)
