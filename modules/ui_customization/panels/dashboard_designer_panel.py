from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QComboBox,
    QMessageBox,
)

from ..repository import UICustomizationRepository
from ..services import register_dashboard_widgets, ensure_active_layout


class DashboardDesignerPanel(QWidget):
    """Simple drag-and-drop interface for dashboard widget ordering."""

    def __init__(
        self,
        main_window,
        repo: Optional[UICustomizationRepository] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._repo = repo or UICustomizationRepository()
        self._widget_catalog = self._load_widget_catalog()

        self.setWindowTitle("Dashboard Designer")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select Layout Template"))
        self._layout_combo = QComboBox(self)
        layout.addWidget(self._layout_combo)

        lists_row = QHBoxLayout()
        self._available = QListWidget(self)
        self._available.setSelectionMode(QListWidget.SingleSelection)
        self._available.setDragEnabled(True)
        self._available.setDragDropMode(QListWidget.DragOnly)
        self._available.setDefaultDropAction(Qt.CopyAction)
        lists_row.addWidget(self._available)

        self._selected = QListWidget(self)
        self._selected.setSelectionMode(QListWidget.SingleSelection)
        self._selected.setAcceptDrops(True)
        self._selected.setDragDropMode(QListWidget.InternalMove)
        self._selected.setDefaultDropAction(Qt.MoveAction)
        lists_row.addWidget(self._selected, 1)
        layout.addLayout(lists_row)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add →")
        self._btn_remove = QPushButton("← Remove")
        self._btn_save = QPushButton("Save Order")
        self._btn_apply = QPushButton("Apply To Dashboard")
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addStretch(1)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_apply)
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(self._handle_add)
        self._btn_remove.clicked.connect(self._handle_remove)
        self._btn_save.clicked.connect(self._save_order)
        self._btn_apply.clicked.connect(self._apply_dashboard)
        self._layout_combo.currentIndexChanged.connect(lambda _: self._load_selected_layout())

        self._populate_available()
        self._populate_layouts()

    # ------------------------------------------------------------------
    def _load_widget_catalog(self) -> Dict[str, str]:
        try:
            from ui.widgets import registry as W
        except Exception:
            return {}
        catalog: Dict[str, str] = {}
        for wid, spec in sorted(W.REGISTRY.items()):
            title = getattr(spec, "title", None) or getattr(spec, "label", None) or wid
            catalog[wid] = str(title)
        return catalog

    def _populate_available(self) -> None:
        self._available.clear()
        for wid, title in sorted(self._widget_catalog.items(), key=lambda pair: pair[1].lower()):
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, wid)
            self._available.addItem(item)

    def _populate_layouts(self) -> None:
        self._layout_combo.clear()
        self._layouts = self._repo.list_layouts()
        for layout in self._layouts:
            self._layout_combo.addItem(layout.name or layout.perspective_name or layout.id, layout.id)
        if self._layouts:
            self._layout_combo.setCurrentIndex(0)
            self._load_selected_layout()

    def _load_selected_layout(self) -> None:
        layout_id = self._layout_combo.currentData()
        self._selected.clear()
        if not layout_id:
            return
        layout = self._repo.get_layout(str(layout_id))
        widgets = list(layout.dashboard_widgets) if layout else []
        if not widgets:
            widgets = list(self._widget_catalog.keys())[:5]
        for wid in widgets:
            title = self._widget_catalog.get(wid, wid)
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, wid)
            self._selected.addItem(item)

    def _handle_add(self) -> None:
        item = self._available.currentItem()
        if not item:
            return
        clone = QListWidgetItem(item.text())
        clone.setData(Qt.UserRole, item.data(Qt.UserRole))
        self._selected.addItem(clone)

    def _handle_remove(self) -> None:
        row = self._selected.currentRow()
        if row >= 0:
            self._selected.takeItem(row)

    def _gather_selected_ids(self) -> list[str]:
        ids: list[str] = []
        for idx in range(self._selected.count()):
            item = self._selected.item(idx)
            wid = item.data(Qt.UserRole)
            if wid:
                ids.append(str(wid))
        return ids

    def _save_order(self) -> None:
        layout_id = self._layout_combo.currentData()
        if not layout_id:
            QMessageBox.warning(self, "Dashboard", "No layout selected.")
            return
        ids = self._gather_selected_ids()
        try:
            register_dashboard_widgets(self._repo, str(layout_id), ids)
            QMessageBox.information(self, "Dashboard", "Dashboard order saved.")
        except Exception as exc:
            QMessageBox.warning(self, "Dashboard", f"Failed to save: {exc}")

    def _apply_dashboard(self) -> None:
        layout_id = self._layout_combo.currentData()
        if not layout_id:
            return
        ids = self._gather_selected_ids()
        try:
            register_dashboard_widgets(self._repo, str(layout_id), ids)
            self._repo.set_active_layout(str(layout_id))
            dock_manager = getattr(self._main_window, "dock_manager", None)
            perspective_file = getattr(self._main_window, "_perspective_file", None)
            if dock_manager and perspective_file:
                ensure_active_layout(self._repo, dock_manager, perspective_file)
            QMessageBox.information(self, "Dashboard", "Dashboard applied. Re-open the Home Dashboard to view changes.")
        except Exception as exc:
            QMessageBox.warning(self, "Dashboard", f"Failed to apply: {exc}")


def get_dashboard_designer_panel(main_window) -> DashboardDesignerPanel:
    repo = getattr(main_window, "customization_repo", None)
    return DashboardDesignerPanel(main_window, repo=repo)
