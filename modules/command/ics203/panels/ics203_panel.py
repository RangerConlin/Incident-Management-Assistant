from __future__ import annotations

"""QtWidgets panel providing ICS-203 organization editing."""

from collections import defaultdict
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..controller import ICS203Controller
from ..models import OrgUnit, Position
from styles.colors import MUTED_TEXT
from utils.app_signals import app_signals
from utils.state import AppState
from .dialogs import AddPositionDialog, AddUnitDialog, AssignPersonDialog
from .templates_dialog import TemplatesDialog


class ICS203Panel(QWidget):
    """Main widget used by the Command module for ICS-203."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ICS203Panel")
        self.incident_id: Optional[str] = None
        self.controller: Optional[ICS203Controller] = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # Toolbar -----------------------------------------------------------------
        toolbar = QHBoxLayout()
        self.btn_add_unit = QPushButton("Add Unit…", self)
        self.btn_add_unit.setShortcut("Ctrl+U")
        self.btn_add_unit.clicked.connect(self._add_unit)
        toolbar.addWidget(self.btn_add_unit)

        self.btn_add_position = QPushButton("Add Position…", self)
        self.btn_add_position.setShortcut("Ctrl+P")
        self.btn_add_position.clicked.connect(self._add_position)
        toolbar.addWidget(self.btn_add_position)

        self.btn_assign_person = QPushButton("Assign Person…", self)
        self.btn_assign_person.setShortcut("Ctrl+A")
        self.btn_assign_person.setEnabled(False)
        self.btn_assign_person.clicked.connect(self._assign_person)
        toolbar.addWidget(self.btn_assign_person)

        toolbar.addStretch(1)

        self.btn_seed = QPushButton("Seed", self)
        self.btn_seed.clicked.connect(self._seed_structure)
        toolbar.addWidget(self.btn_seed)

        self.btn_templates = QPushButton("Templates…", self)
        self.btn_templates.setShortcut("Ctrl+T")
        self.btn_templates.clicked.connect(self._apply_template)
        toolbar.addWidget(self.btn_templates)

        self.btn_export = QPushButton("Export", self)
        self.btn_export.setShortcut("Ctrl+E")
        self.btn_export.clicked.connect(self._export)
        toolbar.addWidget(self.btn_export)

        root_layout.addLayout(toolbar)

        # Splitter ----------------------------------------------------------------
        splitter = QSplitter(Qt.Horizontal, self)
        root_layout.addWidget(splitter, stretch=1)

        # Left: tree --------------------------------------------------------------
        tree_container = QWidget(self)
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget(tree_container)
        self.tree.setHeaderLabel("Units and Positions")
        self.tree.setSelectionBehavior(QTreeWidget.SelectItems)
        self.tree.itemSelectionChanged.connect(self._handle_tree_selection)
        tree_layout.addWidget(self.tree)
        splitter.addWidget(tree_container)

        # Right: assignments table ------------------------------------------------
        assignments_container = QWidget(self)
        assignments_layout = QVBoxLayout(assignments_container)
        assignments_layout.setContentsMargins(0, 0, 0, 0)
        assignments_layout.addWidget(QLabel("Assignments", assignments_container))
        self.tbl_assignments = QTableWidget(assignments_container)
        self.tbl_assignments.setColumnCount(6)
        self.tbl_assignments.setHorizontalHeaderLabels(
            ["Name", "Callsign", "Phone", "Agency", "Start", "End"]
        )
        self.tbl_assignments.horizontalHeader().setStretchLastSection(True)
        self.tbl_assignments.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_assignments.setSelectionBehavior(QAbstractItemView.SelectRows)
        assignments_layout.addWidget(self.tbl_assignments)
        splitter.addWidget(assignments_container)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self._set_toolbar_enabled(False)
        self._init_incident_tracking()

    # ------------------------------------------------------------------
    def load(self, incident_id: str) -> None:
        self.incident_id = str(incident_id)
        self.controller = ICS203Controller(self.incident_id)
        self._refresh_tree()
        self._clear_assignments()
        self._set_toolbar_enabled(True)

    # ------------------------------------------------------------------
    def _ensure_controller(self) -> ICS203Controller:
        if not self.controller:
            if not self.incident_id:
                raise RuntimeError("Incident must be loaded before using the panel")
            self.controller = ICS203Controller(self.incident_id)
        return self.controller

    def _controller_for_user_action(self) -> Optional[ICS203Controller]:
        if not self.incident_id:
            active = self._active_incident_from_state()
            if active:
                self.load(active)
            else:
                QMessageBox.warning(
                    self,
                    "Incident Required",
                    "Load an incident before managing the ICS-203 organization.",
                )
                return None
        return self._ensure_controller()

    def _refresh_tree(self) -> None:
        controller = self._ensure_controller()
        units = controller.load_units()
        positions = controller.load_positions()

        by_parent: Dict[Optional[int], List[OrgUnit]] = defaultdict(list)
        for unit in units:
            by_parent[unit.parent_unit_id].append(unit)
        for key in by_parent:
            by_parent[key].sort(key=lambda u: (u.sort_order, u.name.lower()))

        positions_by_unit: Dict[Optional[int], List[Position]] = defaultdict(list)
        for pos in positions:
            positions_by_unit[pos.unit_id].append(pos)
        for key in positions_by_unit:
            positions_by_unit[key].sort(key=lambda p: (p.sort_order, p.title.lower()))

        self.tree.clear()
        root = self.tree.invisibleRootItem()

        # Command-level positions first
        for pos in positions_by_unit.get(None, []):
            root.addChild(self._make_position_item(pos))

        for unit in by_parent.get(None, []):
            root.addChild(self._build_unit_item(unit, by_parent, positions_by_unit))

        self.tree.expandAll()

    def _build_unit_item(
        self,
        unit: OrgUnit,
        by_parent: Dict[Optional[int], List[OrgUnit]],
        positions_by_unit: Dict[Optional[int], List[Position]],
    ) -> QTreeWidgetItem:
        label = f"{unit.name} ({unit.unit_type})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.UserRole, {"kind": "unit", "id": unit.id})
        for pos in positions_by_unit.get(unit.id, []):
            item.addChild(self._make_position_item(pos))
        for child in by_parent.get(unit.id, []):
            item.addChild(self._build_unit_item(child, by_parent, positions_by_unit))
        return item

    def _make_position_item(self, position: Position) -> QTreeWidgetItem:
        label = f"Position: {position.title}"
        item = QTreeWidgetItem([label])
        item.setData(
            0,
            Qt.UserRole,
            {"kind": "position", "id": position.id, "unit_id": position.unit_id},
        )
        item.setForeground(0, QBrush(MUTED_TEXT))
        return item

    # ------------------------------------------------------------------
    def _handle_tree_selection(self) -> None:
        info = self._selected_tree_info()
        if info and info.get("kind") == "position":
            self.btn_assign_person.setEnabled(True)
            position_id = int(info["id"])
            self._load_assignments(position_id)
        else:
            self.btn_assign_person.setEnabled(False)
            self._clear_assignments()

    def _selected_tree_info(self) -> Optional[dict]:
        item = self.tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict):
            return data
        return None

    def _selected_unit_id(self) -> Optional[int]:
        info = self._selected_tree_info()
        if not info:
            return None
        if info.get("kind") == "unit":
            return int(info["id"])
        if info.get("kind") == "position":
            unit_id = info.get("unit_id")
            return int(unit_id) if unit_id not in (None, "") else None
        return None

    def _selected_position_id(self) -> Optional[int]:
        info = self._selected_tree_info()
        if info and info.get("kind") == "position":
            return int(info["id"])
        return None

    # ------------------------------------------------------------------
    def _load_assignments(self, position_id: int) -> None:
        controller = self._ensure_controller()
        assignments = controller.list_assignments(position_id)
        self.tbl_assignments.setRowCount(0)
        for row, assignment in enumerate(assignments):
            self.tbl_assignments.insertRow(row)
            self.tbl_assignments.setItem(row, 0, QTableWidgetItem(assignment.display_name or ""))
            self.tbl_assignments.setItem(row, 1, QTableWidgetItem(assignment.callsign or ""))
            self.tbl_assignments.setItem(row, 2, QTableWidgetItem(assignment.phone or ""))
            self.tbl_assignments.setItem(row, 3, QTableWidgetItem(assignment.agency or ""))
            self.tbl_assignments.setItem(row, 4, QTableWidgetItem(assignment.start_utc or ""))
            self.tbl_assignments.setItem(row, 5, QTableWidgetItem(assignment.end_utc or ""))

    def _clear_assignments(self) -> None:
        self.tbl_assignments.setRowCount(0)

    # ------------------------------------------------------------------
    def _add_unit(self) -> None:
        controller = self._controller_for_user_action()
        if controller is None:
            return
        preset_parent = self._selected_unit_id()
        dialog = AddUnitDialog(controller.repo, self.incident_id or "", self, preset_parent)
        if dialog.exec() == dialog.Accepted:
            values = dialog.values()
            controller.add_unit(values)
            self._refresh_tree()

    def _add_position(self) -> None:
        controller = self._controller_for_user_action()
        if controller is None:
            return
        preset_unit = self._selected_unit_id()
        dialog = AddPositionDialog(controller.repo, self.incident_id or "", self, preset_unit)
        if dialog.exec() == dialog.Accepted:
            values = dialog.values()
            controller.add_position(values)
            self._refresh_tree()

    def _assign_person(self) -> None:
        position_id = self._selected_position_id()
        if position_id is None:
            return
        controller = self._controller_for_user_action()
        if controller is None:
            return
        dialog = AssignPersonDialog(controller.master_repo, self)
        if dialog.exec() == dialog.Accepted:
            controller.add_assignment(position_id, dialog.values())
            self._load_assignments(position_id)

    def _seed_structure(self) -> None:
        controller = self._controller_for_user_action()
        if controller is None:
            return
        controller.seed_defaults()
        self._refresh_tree()

    def _apply_template(self) -> None:
        controller = self._controller_for_user_action()
        if controller is None:
            return
        dialog = TemplatesDialog(self.incident_id or "", self)
        if dialog.exec() == dialog.Accepted:
            controller.apply_items(dialog.selected_items())
            self._refresh_tree()

    def _export(self) -> None:
        controller = self._controller_for_user_action()
        if controller is None:
            return
        try:
            path = controller.export_snapshot()
        except Exception as exc:  # pragma: no cover - user notification
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"Saved to {path}")

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        for button in (
            self.btn_add_unit,
            self.btn_add_position,
            self.btn_seed,
            self.btn_templates,
            self.btn_export,
        ):
            button.setEnabled(enabled)
        # Always gate Assign Person on the current tree selection.
        self.btn_assign_person.setEnabled(False)

    # ------------------------------------------------------------------
    def _init_incident_tracking(self) -> None:
        try:
            app_signals.incidentChanged.connect(self._handle_active_incident_changed)
        except Exception:
            pass
        active = self._active_incident_from_state()
        if active:
            self.load(active)

    def _handle_active_incident_changed(self, incident_id: str) -> None:
        normalized = str(incident_id).strip() if incident_id is not None else ""
        if not normalized:
            self.incident_id = None
            self.controller = None
            self.tree.clear()
            self._clear_assignments()
            self._set_toolbar_enabled(False)
            return
        if normalized == self.incident_id:
            return
        self.load(normalized)

    def _active_incident_from_state(self) -> Optional[str]:
        try:
            value = AppState.get_active_incident()
        except Exception:
            return None
        if not value:
            return None
        return str(value)
