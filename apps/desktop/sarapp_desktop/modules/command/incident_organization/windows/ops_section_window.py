from __future__ import annotations

"""Operations Section Organization window.

Provides a persistent floating window for managing the Operations Section
structure: branches, divisions, groups, and their assigned resources.
Resources are currently treated as single resources (teams); task force
and strike team scaffolding is present for future expansion.

Deputies, staff assistants, and trainees are shown as secondary assignments
(assignment_type field) on the parent position rather than as separate
position nodes.
"""

from collections import defaultdict
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
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

from utils import incident_context
from ..controller import IncidentOrganizationController
from ..models import (
    ASSIGNMENT_TYPE_ASSISTANT,
    ASSIGNMENT_TYPE_DEPUTY,
    ASSIGNMENT_TYPE_PRIMARY,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
    ASSIGNMENT_TYPE_TRAINEE,
    OrganizationPosition,
    PositionAssignment,
    normalize_assignment_type,
)

# Fallback resource kind options when the master resource type library is empty
_DEFAULT_RESOURCE_KINDS: list[str] = [
    "Ground Team",
    "Hasty Team",
    "K9 Team",
    "Dive Team",
    "Swift Water Team",
    "Technical Rescue Team",
    "Medical Unit",
    "Helicopter",
    "Fixed Wing",
    "UAS / Drone",
    "ATV / UTV",
    "Vehicle",
    "Boat",
    "Equipment Cache",
    "Communications Unit",
    "Other",
]


def _load_resource_kind_options() -> list[str]:
    """Return resource type names from the master library, falling back to defaults."""
    try:
        from utils.api_client import api_client
        rows = api_client.get("/api/resource-types") or []
        names = [r.get("name", "") for r in rows if r.get("name") and r.get("is_active", True)]
        return names if names else _DEFAULT_RESOURCE_KINDS
    except Exception:
        return _DEFAULT_RESOURCE_KINDS


# Classifications rendered as structural nodes in this window's tree
_UNIT_CLASSIFICATIONS = {"branch", "division", "group"}

# Position classifications that are shown as leaf children under unit nodes
_STAFF_CLASSIFICATIONS = {"position"}

# Resource type labels
_RESOURCE_TYPE_LABELS = {
    "task_force": "Task Force",
    "strike_team": "Strike Team",
    "single_resource": "Single Resource",
}

# ICS support role titles by classification (mirrors incident_organization_panel.py)
# Division/Group have no deputies, assistants, or staff assistants (N/A).
# Incident Commander (command) has a Deputy only.
# Command Staff positions can have assistants and staff assistants.
# Section Chiefs have deputies, assistants, and staff assistants.
_ICS_SUPPORT_TITLES: dict[str, dict[str, str]] = {
    "command": {"deputy": "Deputy", "trainee": "Trainee"},
    "section": {
        "deputy": "Deputy",
        "assistant": "Assistant",
        "staff_assistant": "Staff Assistant",
        "trainee": "Trainee",
    },
    "branch": {
        "deputy": "Deputy Director",
        "assistant": "Assistant Director",
        "staff_assistant": "Staff Assistant",
        "trainee": "Trainee",
    },
    "division": {"trainee": "Trainee"},
    "group": {"trainee": "Trainee"},
    "unit":    {"trainee": "Trainee"},
    "position": {
        "assistant": "Assistant",
        "staff_assistant": "Staff Assistant",
        "trainee": "Trainee",
    },
}

def _assignment_display_text(at: str, name: str, classification: str = "position") -> str:
    """Format assignment text with ICS-standard role titles."""
    if at == "primary":
        return name
    cls_titles = _ICS_SUPPORT_TITLES.get(classification, _ICS_SUPPORT_TITLES["position"])
    title = cls_titles.get(at)
    return f"{title}: {name}" if title else name


# ---------------------------------------------------------------------------
# Teams access helper
# ---------------------------------------------------------------------------

class _TeamsAccess:
    """Thin query layer for teams via the SARApp API."""

    def _incident_id(self) -> str | None:
        iid = incident_context.get_active_incident_id()
        return str(iid) if iid else None

    def list_all_teams(self) -> list[dict]:
        try:
            from utils.api_client import api_client
            iid = self._incident_id()
            if not iid:
                return []
            return api_client.get(f"/api/incidents/{iid}/operations/teams") or []
        except Exception:
            return []

    def list_teams_for_unit(self, unit_id: int) -> list[dict]:
        try:
            teams = self.list_all_teams()
            return [t for t in teams if t.get("operational_unit_id") == unit_id]
        except Exception:
            return []

    def assign_to_unit(
        self,
        team_id: int,
        unit_id: int,
        ics_resource_kind: str,
        resource_kind: str,
    ) -> None:
        from utils.api_client import api_client
        iid = self._incident_id()
        if not iid:
            return
        api_client.patch(
            f"/api/incidents/{iid}/operations/teams/{team_id}",
            json={"operational_unit_id": unit_id, "ics_resource_kind": ics_resource_kind, "resource_kind": resource_kind or None},
        )

    def unassign_from_unit(self, team_id: int) -> None:
        from utils.api_client import api_client
        iid = self._incident_id()
        if not iid:
            return
        api_client.patch(
            f"/api/incidents/{iid}/operations/teams/{team_id}",
            json={"operational_unit_id": None},
        )


# ---------------------------------------------------------------------------
# Private dialogs
# ---------------------------------------------------------------------------

class _AddBranchDialog(QDialog):
    def __init__(
        self,
        parent_candidates: list[OrganizationPosition],
        ops_section_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Branch")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("e.g. Branch A, Alpha Branch")
        layout.addRow("Branch name *", self.name_edit)

        self.parent_combo = QComboBox(self)
        self._parent_ids: list[int | None] = []
        self._populate_parents(parent_candidates, ops_section_id)
        layout.addRow("Parent section", self.parent_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate_parents(
        self,
        candidates: list[OrganizationPosition],
        ops_section_id: int | None,
    ) -> None:
        for pos in candidates:
            self.parent_combo.addItem(pos.title, pos.id)
            self._parent_ids.append(pos.id)
            if pos.id == ops_section_id:
                self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)
        if not candidates:
            self.parent_combo.addItem("(no sections found)", None)
            self._parent_ids.append(None)

    def _handle_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Branch", "Branch name is required.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "parent_id": self.parent_combo.currentData(),
        }


class _AddAirOpsBranchDialog(QDialog):
    """Dedicated dialog for the one-per-incident Air Operations Branch.

    Deliberately has no name field (always titled "Air Operations Branch")
    and no parent picker (always directly under the Operations Section) -
    the only choices left are who's running it. Callers must check
    uniqueness before opening this.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Air Operations Branch")
        self.setMinimumWidth(360)
        layout = QFormLayout(self)

        info = QLabel(
            "Creates the Air Operations Branch directly under the "
            "Operations Section. There can only be one per incident - it "
            "populates the dedicated Air Ops field on ICS 203/207 instead "
            "of a numbered branch slot.",
            self,
        )
        info.setWordWrap(True)
        layout.addRow(info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict:
        return {
        }


class _AddDivisionGroupDialog(QDialog):
    def __init__(
        self,
        branch_candidates: list[OrganizationPosition],
        preset_parent_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Division / Group")
        self.setMinimumWidth(380)
        layout = QFormLayout(self)

        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["Division", "Group"])
        layout.addRow("Type *", self.type_combo)

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("e.g. Division A, Group 1, Hasty Group")
        layout.addRow("Identifier *", self.name_edit)

        self.parent_combo = QComboBox(self)
        self._populate_parents(branch_candidates, preset_parent_id)
        layout.addRow("Parent branch / section", self.parent_combo)

        info = QLabel(
            "Note: Division/Group Supervisors do not have deputies or "
            "assistants per ICS standards (N/A).",
            self,
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #757575; font-style: italic;")
        layout.addRow("", info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate_parents(
        self,
        candidates: list[OrganizationPosition],
        preset_parent_id: int | None,
    ) -> None:
        self.parent_combo.addItem("— Directly under Operations Section —", None)
        for pos in candidates:
            label = pos.title + ("  (branch)" if pos.classification == "branch" else "")
            self.parent_combo.addItem(label, pos.id)
            if pos.id == preset_parent_id:
                self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)

    def _handle_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Division / Group", "Identifier is required.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "classification": self.type_combo.currentText().lower(),
            "parent_id": self.parent_combo.currentData(),
        }


class _AddPositionDialog(QDialog):
    def __init__(
        self,
        parent_candidates: list[OrganizationPosition],
        preset_parent_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Position")
        self.setMinimumWidth(380)
        layout = QFormLayout(self)

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("e.g. Branch Director, Assistant, Trainee")
        layout.addRow("Title *", self.title_edit)

        self.parent_combo = QComboBox(self)
        self._populate_parents(parent_candidates, preset_parent_id)
        layout.addRow("Parent position / unit", self.parent_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate_parents(
        self,
        candidates: list[OrganizationPosition],
        preset_parent_id: int | None,
    ) -> None:
        self.parent_combo.addItem("— Top level / under Operations Section —", None)
        for pos in candidates:
            label = f"{pos.title}  ({pos.classification})"
            self.parent_combo.addItem(label, pos.id)
            if pos.id == preset_parent_id:
                self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)

    def _handle_accept(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Position", "Title is required.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "parent_id": self.parent_combo.currentData(),
        }


class _AssignResourceDialog(QDialog):
    """Pick a team and set its ICS resource kind for assignment to a division/group."""

    RESOURCE_KINDS: list[tuple[str, str]] = [
        ("Single Resource", "single_resource"),
        ("Task Force", "task_force"),
        ("Strike Team", "strike_team"),
    ]

    def __init__(
        self,
        teams: list[dict],
        current_unit_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Resource")
        self.setMinimumSize(520, 400)
        self._selected_team_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a resource to assign to this division/group:"))

        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Name", "Status"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        unassigned = [
            t for t in teams
            if t.get("operational_unit_id") != current_unit_id
        ]
        self.table.setRowCount(len(unassigned))
        self._team_ids: list[int] = []
        for row, team in enumerate(unassigned):
            self._team_ids.append(int(team["int_id"]))
            self.table.setItem(row, 0, QTableWidgetItem(str(team.get("name") or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(team.get("status") or "")))

        type_row = QFormLayout()

        self.kind_combo = QComboBox(self)
        for label, _ in self.RESOURCE_KINDS:
            self.kind_combo.addItem(label)
        type_row.addRow("ICS resource type:", self.kind_combo)

        self.resource_kind_combo = QComboBox(self)
        self.resource_kind_combo.addItem("")
        for name in _load_resource_kind_options():
            self.resource_kind_combo.addItem(name)
        type_row.addRow("Resource kind:", self.resource_kind_combo)

        layout.addLayout(type_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.table.rowCount():
            self.table.selectRow(0)

    def _handle_accept(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Assign Resource", "Select a resource first.")
            return
        row = selected[0].row()
        if 0 <= row < len(self._team_ids):
            self._selected_team_id = self._team_ids[row]
        self.accept()

    def selected_team_id(self) -> int | None:
        return self._selected_team_id

    def selected_ics_resource_kind(self) -> str:
        idx = self.kind_combo.currentIndex()
        return self.RESOURCE_KINDS[max(0, idx)][1]

    def selected_resource_kind(self) -> str:
        return self.resource_kind_combo.currentText()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class OperationsSectionWindow(QDialog):
    """Floating window for managing Operations Section structure and resources.

    The tree on the left shows branches and their divisions/groups with
    assignments (including deputies) shown inline on the position node
    rather than as separate child positions.

    Emits ``structure_changed`` when the org structure is modified so the
    main org panel can refresh its own tree.
    """

    structure_changed = Signal()

    def __init__(self, incident_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = str(incident_id)
        self.controller = IncidentOrganizationController(self.incident_id)
        self._teams = _TeamsAccess()

        self.setWindowTitle("Operations Section Organization")
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.resize(1200, 700)

        self._positions_by_id: dict[int, OrganizationPosition] = {}
        self._assignments_by_position: dict[int, list[PositionAssignment]] = {}
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_add_branch = QPushButton("Add Branch…", self)
        self.btn_add_branch.clicked.connect(self._add_branch)
        toolbar.addWidget(self.btn_add_branch)

        self.btn_add_air_ops_branch = QPushButton("Add Air Operations Branch…", self)
        self.btn_add_air_ops_branch.setToolTip(
            "Disabled once an Air Operations Branch exists for this "
            "incident - there can only be one."
        )
        self.btn_add_air_ops_branch.clicked.connect(self._add_air_ops_branch)
        toolbar.addWidget(self.btn_add_air_ops_branch)

        self.btn_add_div_group = QPushButton("Add Division / Group…", self)
        self.btn_add_div_group.clicked.connect(lambda: self._add_division_group(None))
        toolbar.addWidget(self.btn_add_div_group)

        self.btn_add_position = QPushButton("Add Position…", self)
        self.btn_add_position.clicked.connect(lambda: self._add_position(None))
        toolbar.addWidget(self.btn_add_position)

        self.btn_edit = QPushButton("Edit…", self)
        self.btn_edit.clicked.connect(self._edit_selected)
        toolbar.addWidget(self.btn_edit)

        self.btn_deactivate = QPushButton("Deactivate", self)
        self.btn_deactivate.clicked.connect(self._deactivate_selected)
        toolbar.addWidget(self.btn_deactivate)

        toolbar.addStretch(1)

        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(self.btn_refresh)

        root.addLayout(toolbar)

        # Splitter
        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, stretch=1)

        # Left: unit tree
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Operations Section Structure", left))

        self.tree = QTreeWidget(left)
        self.tree.setHeaderLabels(["Unit", "Assignments"])
        self.tree.header().setStretchLastSection(True)
        self.tree.itemSelectionChanged.connect(self._handle_unit_selected)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        left_layout.addWidget(self.tree, stretch=1)
        splitter.addWidget(left)

        # Right: resource panel
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.unit_header = QLabel("Select a unit", right)
        bold = QFont()
        bold.setPointSize(13)
        bold.setBold(True)
        self.unit_header.setFont(bold)
        right_layout.addWidget(self.unit_header)

        self.unit_meta = QLabel("", right)
        right_layout.addWidget(self.unit_meta)

        # Show personnel assignments on this unit
        self.unit_staffing = QLabel("", right)
        self.unit_staffing.setWordWrap(True)
        right_layout.addWidget(self.unit_staffing)

        staff_buttons = QHBoxLayout()
        self.btn_assign_personnel = QPushButton("Assign Personnel…", right)
        self.btn_assign_personnel.clicked.connect(self._assign_personnel)
        staff_buttons.addWidget(self.btn_assign_personnel)
        self.btn_remove_personnel = QPushButton("Remove Assignment…", right)
        self.btn_remove_personnel.clicked.connect(self._remove_personnel)
        staff_buttons.addWidget(self.btn_remove_personnel)
        staff_buttons.addStretch(1)
        right_layout.addLayout(staff_buttons)

        right_layout.addWidget(QLabel("Assigned Resources", right))

        self.resources_table = QTableWidget(right)
        self.resources_table.setColumnCount(4)
        self.resources_table.setHorizontalHeaderLabels(
            ["Name", "ICS Type", "Resource Kind", "Status"]
        )
        self.resources_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.resources_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resources_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.resources_table.verticalHeader().setVisible(False)
        self.resources_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.resources_table, stretch=1)

        res_buttons = QHBoxLayout()
        self.btn_assign_resource = QPushButton("Assign Resource…", right)
        self.btn_assign_resource.clicked.connect(self._assign_resource)
        res_buttons.addWidget(self.btn_assign_resource)

        self.btn_remove_resource = QPushButton("Remove from Unit", right)
        self.btn_remove_resource.clicked.connect(self._remove_resource)
        res_buttons.addWidget(self.btn_remove_resource)

        res_buttons.addStretch(1)
        right_layout.addLayout(res_buttons)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self._set_resource_panel_enabled(False)
        self.btn_assign_personnel.setEnabled(False)
        self.btn_remove_personnel.setEnabled(False)

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._refresh_tree()
        self._handle_unit_selected()
        self.btn_add_air_ops_branch.setEnabled(not self._has_air_ops_branch())

    def _has_air_ops_branch(self) -> bool:
        return any("air operations" in p.title.casefold() for p in self._positions_by_id.values())

    def _refresh_tree(self) -> None:
        positions = self.controller.list_positions()
        self._positions_by_id = {p.id or 0: p for p in positions}

        assignments = self.controller.list_assignments(active_only=True)
        self._assignments_by_position = defaultdict(list)
        for asgn in assignments:
            self._assignments_by_position[asgn.position_id].append(asgn)

        ops_id = self.controller.get_ops_section_id()

        # Group positions by parent
        children: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for pos in positions:
            children[pos.parent_position_id].append(pos)

        self.tree.clear()

        # Root item: Operations Section
        ops_label = "Operations Section"
        if ops_id and ops_id in self._positions_by_id:
            ops_label = self._positions_by_id[ops_id].title

        root_item = QTreeWidgetItem([ops_label, ""])
        root_item.setData(0, Qt.UserRole, ops_id)
        bold = QFont()
        bold.setBold(True)
        bold.setItalic(True)
        root_item.setFont(0, bold)
        self.tree.addTopLevelItem(root_item)

        branch_font = QFont()
        branch_font.setBold(True)

        def _build_assignment_text(pos_id: int, classification: str) -> str:
            """Build inline assignment text for the position lead and support staff."""
            pos_assignments = self._assignments_by_position.get(pos_id, [])
            pieces: list[str] = []
            for assignment in pos_assignments:
                assignment_type = normalize_assignment_type(assignment.assignment_type)
                if assignment_type == ASSIGNMENT_TYPE_PRIMARY:
                    pieces.append(assignment.person_name)
                    continue
                if classification in {"division", "group"} and assignment_type in {
                    ASSIGNMENT_TYPE_DEPUTY,
                    ASSIGNMENT_TYPE_ASSISTANT,
                    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
                }:
                    continue
                label = _assignment_display_text(
                    assignment_type,
                    assignment.person_name,
                    classification=classification,
                )
                if label != assignment.person_name:
                    pieces.append(label)
            return ", ".join(pieces)

        staff_font = QFont()
        staff_font.setItalic(True)

        def _add_unit_children(parent_item: QTreeWidgetItem, parent_id: int | None) -> None:
            for pos in children.get(parent_id, []):
                assignment_text = _build_assignment_text(pos.id or 0, pos.classification)
                item = QTreeWidgetItem([pos.title, assignment_text])
                item.setData(0, Qt.UserRole, pos.id)
                item.setData(0, Qt.UserRole + 1, pos.classification)
                if pos.classification == "branch":
                    item.setFont(0, branch_font)
                    _add_unit_children(item, pos.id)
                elif pos.classification in _UNIT_CLASSIFICATIONS:
                    _add_unit_children(item, pos.id)
                elif pos.classification in _STAFF_CLASSIFICATIONS:
                    item.setFont(0, staff_font)
                else:
                    continue
                parent_item.addChild(item)

        _add_unit_children(root_item, ops_id)

        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)

    def _selected_unit_id(self) -> int | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        val = items[0].data(0, Qt.UserRole)
        return int(val) if val is not None else None

    def _selected_resource_team_id(self) -> int | None:
        items = self.resources_table.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)

    def _selected_classification(self) -> str | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.UserRole + 1)

    def _handle_unit_selected(self) -> None:
        unit_id = self._selected_unit_id()
        is_unit = unit_id is not None and unit_id in self._positions_by_id
        self.btn_edit.setEnabled(is_unit)
        self.btn_deactivate.setEnabled(is_unit)
        self.btn_assign_personnel.setEnabled(is_unit)
        self.btn_remove_personnel.setEnabled(is_unit)
        self._set_resource_panel_enabled(is_unit)

        if not is_unit:
            self.unit_header.setText("Select a unit")
            self.unit_meta.setText("")
            self.unit_staffing.setText("")
            self.resources_table.setRowCount(0)
            return

        pos = self._positions_by_id[unit_id]
        parent_label = ""
        if pos.parent_position_id and pos.parent_position_id in self._positions_by_id:
            parent_label = f"  ·  under {self._positions_by_id[pos.parent_position_id].title}"

        self.unit_header.setText(pos.title)
        self.unit_meta.setText(f"{pos.classification.title()}{parent_label}")

        # Show staffing inline
        assignments = self._assignments_by_position.get(unit_id, [])
        staff_lines = []
        role_labels = {
            ASSIGNMENT_TYPE_PRIMARY: "Primary",
            ASSIGNMENT_TYPE_DEPUTY: "Deputy",
            ASSIGNMENT_TYPE_ASSISTANT: "Assistant",
            ASSIGNMENT_TYPE_STAFF_ASSISTANT: "Staff Assistant",
            ASSIGNMENT_TYPE_TRAINEE: "Trainee",
        }
        for at in (
            ASSIGNMENT_TYPE_PRIMARY,
            ASSIGNMENT_TYPE_DEPUTY,
            ASSIGNMENT_TYPE_ASSISTANT,
            ASSIGNMENT_TYPE_STAFF_ASSISTANT,
            ASSIGNMENT_TYPE_TRAINEE,
        ):
            names = [
                a.person_name
                for a in assignments
                if normalize_assignment_type(a.assignment_type) == at
            ]
            if names:
                label = role_labels.get(at, at.replace("_", " ").title())
                staff_lines.append(f"{label}: {', '.join(names)}")
        self.unit_staffing.setText("\n".join(staff_lines) if staff_lines else "")

        self._refresh_resources(unit_id)

    def _refresh_resources(self, unit_id: int) -> None:
        teams = self._teams.list_teams_for_unit(unit_id)
        self.resources_table.setRowCount(len(teams))
        for row, team in enumerate(teams):
            team_id = team.get("int_id")
            kind_key = str(team.get("ics_resource_kind") or "single_resource").lower()
            resource_type = _RESOURCE_TYPE_LABELS.get(kind_key, "Single Resource")
            cells = [
                str(team.get("name") or ""),
                resource_type,
                str(team.get("resource_kind") or ""),
                str(team.get("status") or ""),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, team_id)
                self.resources_table.setItem(row, col, item)

    def _set_resource_panel_enabled(self, enabled: bool) -> None:
        self.btn_assign_resource.setEnabled(enabled)
        self.btn_remove_resource.setEnabled(enabled)

    # ------------------------------------------------------------------
    def _show_tree_context_menu(self, point) -> None:
        menu = QMenu(self)
        unit_id = self._selected_unit_id()
        pos = self._positions_by_id.get(unit_id or 0)

        action_assign_personnel = menu.addAction("Assign Personnel…")
        action_assign_personnel.setEnabled(unit_id is not None)
        action_assign_personnel.triggered.connect(self._assign_personnel)

        action_remove_personnel = menu.addAction("Remove Assignment…")
        action_remove_personnel.setEnabled(unit_id is not None)
        action_remove_personnel.triggered.connect(self._remove_personnel)

        menu.addSeparator()

        action_add_branch = menu.addAction("Add Branch…")
        action_add_branch.triggered.connect(self._add_branch)

        action_add_air_ops = menu.addAction("Add Air Operations Branch…")
        action_add_air_ops.setEnabled(not self._has_air_ops_branch())
        action_add_air_ops.triggered.connect(self._add_air_ops_branch)

        action_add_div = menu.addAction("Add Division / Group…")
        if pos and pos.classification == "branch":
            action_add_div.setText(f"Add Division / Group under {pos.title}…")
            action_add_div.triggered.connect(
                lambda: self._add_division_group(unit_id)
            )
        else:
            action_add_div.triggered.connect(
                lambda: self._add_division_group(None)
            )

        action_add_pos = menu.addAction("Add Position…")
        if pos:
            action_add_pos.setText(f"Add Position under {pos.title}…")
            action_add_pos.triggered.connect(lambda: self._add_position(unit_id))
        else:
            action_add_pos.triggered.connect(lambda: self._add_position(None))

        menu.exec(self.tree.mapToGlobal(point))

    # ------------------------------------------------------------------
    def _add_branch(self) -> None:
        sections = [
            p for p in self._positions_by_id.values()
            if p.classification == "section"
        ]
        ops_id = self.controller.get_ops_section_id()
        dialog = _AddBranchDialog(sections, ops_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        v = dialog.values()
        try:
            branch_id = self.controller.add_branch(
                v["name"],
                v["parent_id"],
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Add Branch", str(exc))
            return
        self._refresh()
        self.structure_changed.emit()

    def _add_air_ops_branch(self) -> None:
        if self._has_air_ops_branch():
            QMessageBox.information(
                self,
                "Add Air Operations Branch",
                "An Air Operations Branch already exists for this incident. "
                "There can only be one - edit the existing one instead of "
                "creating another.",
            )
            return
        dialog = _AddAirOpsBranchDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        v = dialog.values()
        ops_id = self.controller.get_ops_section_id()
        try:
            branch_id = self.controller.add_branch(
                "Air Operations Branch",
                ops_id,
                is_air_ops=True,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Add Air Operations Branch", str(exc))
            return
        self._refresh()
        self.structure_changed.emit()

    def _add_division_group(self, preset_parent_id: int | None) -> None:
        branches = [
            p for p in self._positions_by_id.values()
            if p.classification == "branch"
        ]
        dialog = _AddDivisionGroupDialog(branches, preset_parent_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        v = dialog.values()
        parent_id = v["parent_id"]
        if parent_id is None:
            parent_id = self.controller.get_ops_section_id()
        try:
            unit_id = self.controller.add_division_group(
                v["name"],
                v["classification"],
                parent_id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Add Division / Group", str(exc))
            return
        self._refresh()
        self.structure_changed.emit()

    def _add_position(self, preset_parent_id: int | None) -> None:
        candidates = [p for p in self._positions_by_id.values() if p.id is not None]
        dialog = _AddPositionDialog(candidates, preset_parent_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        v = dialog.values()
        parent_id = v["parent_id"]
        if parent_id is None:
            parent_id = self.controller.get_ops_section_id()
        try:
            self.controller.add_position({
                "title": v["title"],
                "classification": "position",
                "parent_position_id": parent_id,
            })
        except ValueError as exc:
            QMessageBox.warning(self, "Add Position", str(exc))
            return
        self._refresh()
        self.structure_changed.emit()

    def _edit_selected(self) -> None:
        unit_id = self._selected_unit_id()
        if not unit_id:
            return
        pos = self._positions_by_id.get(unit_id)
        if pos is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit {pos.classification.title()}")
        layout = QFormLayout(dialog)
        name_edit = QLineEdit(pos.title, dialog)
        layout.addRow("Name", name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() != QDialog.Accepted:
            return
        new_name = name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Edit", "Name is required.")
            return
        try:
            self.controller.update_position(unit_id, {
                "title": new_name,
            })
        except ValueError as exc:
            QMessageBox.warning(self, "Edit", str(exc))
            return
        self._refresh()
        self.structure_changed.emit()

    def _deactivate_selected(self) -> None:
        unit_id = self._selected_unit_id()
        if not unit_id:
            return
        pos = self._positions_by_id.get(unit_id)
        if pos is None:
            return
        confirm = QMessageBox.question(
            self,
            "Deactivate Unit",
            f"Deactivate \"{pos.title}\"? Resources assigned to it will need to be reassigned.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.controller.deactivate_position(unit_id)
        self._refresh()
        self.structure_changed.emit()

    def _assign_personnel(self) -> None:
        unit_id = self._selected_unit_id()
        if not unit_id or unit_id not in self._positions_by_id:
            return
        from ..panels.incident_organization_panel import UnifiedAssignmentDialog
        pos = self._positions_by_id[unit_id]
        dialog = UnifiedAssignmentDialog(self.incident_id, pos.title, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.result_values()
        if values is None:
            return
        try:
            self.controller.assign_person(unit_id, values)
        except ValueError as exc:
            QMessageBox.warning(self, "Assign Personnel", str(exc))
            return
        self._refresh()
        self.structure_changed.emit()

    def _remove_personnel(self) -> None:
        unit_id = self._selected_unit_id()
        if not unit_id or unit_id not in self._positions_by_id:
            return
        assignments = self._assignments_by_position.get(unit_id, [])
        if not assignments:
            QMessageBox.information(self, "Remove Assignment", "No active assignments on this position.")
            return
        if len(assignments) == 1:
            asgn = assignments[0]
        else:
            items = [
                f"{a.person_name} ({a.assignment_type})" for a in assignments
            ]
            choice, ok = QInputDialog.getItem(
                self, "Remove Assignment", "Select assignment to remove:", items, 0, False
            )
            if not ok:
                return
            idx = items.index(choice)
            asgn = assignments[idx]
        confirm = QMessageBox.question(
            self,
            "Remove Assignment",
            f"Remove {asgn.person_name} from this position?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.controller.remove_assignment(asgn.id)
        self._refresh()
        self.structure_changed.emit()

    def _assign_resource(self) -> None:
        unit_id = self._selected_unit_id()
        if not unit_id:
            return
        all_teams = self._teams.list_all_teams()
        if not all_teams:
            QMessageBox.information(
                self, "Assign Resource",
                "No teams are available. Add teams in the Operations module first."
            )
            return
        dialog = _AssignResourceDialog(all_teams, unit_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        team_id = dialog.selected_team_id()
        if team_id is None:
            return
        try:
            self._teams.assign_to_unit(
                team_id,
                unit_id,
                dialog.selected_ics_resource_kind(),
                dialog.selected_resource_kind(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Assign Resource", str(exc))
            return
        self._refresh_resources(unit_id)

    def _remove_resource(self) -> None:
        unit_id = self._selected_unit_id()
        team_id = self._selected_resource_team_id()
        if not unit_id or team_id is None:
            return
        try:
            self._teams.unassign_from_unit(team_id)
        except Exception as exc:
            QMessageBox.warning(self, "Remove Resource", str(exc))
            return
        self._refresh_resources(unit_id)
