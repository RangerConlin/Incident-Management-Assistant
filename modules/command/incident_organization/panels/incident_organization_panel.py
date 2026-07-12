from __future__ import annotations
from collections import defaultdict
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from styles.colors import MUTED_TEXT
from utils.app_signals import app_signals
from utils.state import AppState

from ..controller import IncidentOrganizationController
from ..models import (
    ASSIGNMENT_TYPE_ASSISTANT,
    ASSIGNMENT_TYPE_DEPUTY,
    ASSIGNMENT_TYPE_PRIMARY,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT,
    ASSIGNMENT_TYPE_TRAINEE,
    OrganizationPosition,
    OrganizationTemplate,
    PositionAssignment,
    normalize_assignment_type,
)
from ..windows.ops_section_window import OperationsSectionWindow


# ── ICS Classification → Position Title Mapping ──────────────────────────
# Based on the ICS organizational structure standard:
#   Organizational Element   | Leadership Position Title | Support Positions
#   ────────────────────────┼───────────────────────────┼──────────────────────
#   Incident Command        | Incident Commander        | Deputy
#   Command Staff           | Officer                   | Assistant
#   Section                 | Chief                     | Deputy, Assistant
#   Branch                  | Director                  | Deputy
#   Division/Group          | Supervisor                | N/A
#   Unit                    | Unit Leader               | Manager, Coordinator
#   Strike Team/Task Force  | Leader                    | Single Resource Boss
#   Single Resource         | Boss/Leader               | N/A
#   Technical Specialist    | Specialist                | N/A

_ICS_SUPPORT_TITLES: dict[str, dict[str, str]] = {
    "command": {
        "deputy": "Deputy",
        "trainee": "Trainee",
    },
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
    "division": {
        "trainee": "Trainee",
    },
    "group": {
        "trainee": "Trainee",
    },
    "unit": {
        "trainee": "Trainee",
    },
    "position": {
        "assistant": "Assistant",
        "staff_assistant": "Staff Assistant",
        "trainee": "Trainee",
    },
}

def _classification_support_title(classification: str, assignment_type: str) -> str | None:
    """Return the ICS-standard title for a support assignment on this classification."""
    cls_titles = _ICS_SUPPORT_TITLES.get(classification, _ICS_SUPPORT_TITLES["position"])
    return cls_titles.get(assignment_type)

# ── Color/label helpers for assignment types ──────────────────────────────

_ASSIGNMENT_COLORS: dict[str, QColor] = {
    "primary":  QColor("#2e7d32"),
    "deputy":   QColor("#1565c0"),
    "assistant": QColor("#8e24aa"),
    "staff_assistant": QColor("#6a1b9a"),
    "trainee":  QColor("#e65100"),
}

_ASSIGNMENT_ORDER = {
    ASSIGNMENT_TYPE_PRIMARY: 0,
    ASSIGNMENT_TYPE_DEPUTY: 1,
    ASSIGNMENT_TYPE_ASSISTANT: 2,
    ASSIGNMENT_TYPE_STAFF_ASSISTANT: 3,
    ASSIGNMENT_TYPE_TRAINEE: 4,
}

_ASSIGNMENT_LABELS = {
    ASSIGNMENT_TYPE_PRIMARY: "Primary",
    ASSIGNMENT_TYPE_DEPUTY: "Deputy",
    ASSIGNMENT_TYPE_ASSISTANT: "Assistant",
    ASSIGNMENT_TYPE_STAFF_ASSISTANT: "Staff Assistant",
    ASSIGNMENT_TYPE_TRAINEE: "Trainee",
}


def _assignment_display_text(at: str, name: str, classification: str = "position") -> str:

    if at == "primary":
        return name
    title = _classification_support_title(classification, at)
    if title:
        return f"{title}: {name}"
    return name


def _assignment_color(at: str) -> QColor:
    return _ASSIGNMENT_COLORS.get(at, QColor("#757575"))


# ── Dialogs ──────────────────────────────────────────────────────────────


class PositionDialog(QDialog):
    """Small editor for custom AHJ-defined organization positions."""

    CLASSIFICATIONS = ["command", "section", "branch", "division", "group", "unit", "position"]
    _TOP_LEVEL_SENTINEL = -1

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        position: OrganizationPosition | None = None,
        parent_position_id: int | None = None,
        existing_positions: list[OrganizationPosition] | None = None,
        exclude_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Position")
        layout = QFormLayout(self)
        self.title_edit = QLineEdit(position.title if position else "", self)
        layout.addRow("Title", self.title_edit)
        self.classification_combo = QComboBox(self)
        self.classification_combo.addItems(self.CLASSIFICATIONS)
        selected = position.classification if position else "position"
        self.classification_combo.setCurrentText(selected if selected in self.CLASSIFICATIONS else "position")
        layout.addRow("Classification", self.classification_combo)

        self.parent_combo = QComboBox(self)
        self.parent_combo.addItem("— Top Level (no parent) —", self._TOP_LEVEL_SENTINEL)
        preselect_id = (position.parent_position_id if position else parent_position_id) or self._TOP_LEVEL_SENTINEL
        self._populate_parent_combo(existing_positions or [], exclude_id, preselect_id)
        layout.addRow("Parent position", self.parent_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate_parent_combo(
        self,
        positions: list[OrganizationPosition],
        exclude_id: int | None,
        preselect_id: int,
    ) -> None:
        """Add positions to the parent combo with depth-indented labels."""
        by_parent: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for pos in positions:
            if pos.id != exclude_id:
                by_parent[pos.parent_position_id].append(pos)

        def add_children(parent_id: int | None, depth: int) -> None:
            for pos in by_parent.get(parent_id, []):
                label = "    " * depth + pos.title + f"  ({pos.classification})"
                self.parent_combo.addItem(label, pos.id)
                if pos.id == preselect_id:
                    self.parent_combo.setCurrentIndex(self.parent_combo.count() - 1)
                add_children(pos.id, depth + 1)

        add_children(None, 0)

    def values(self) -> dict[str, object]:
        raw_id = self.parent_combo.currentData()
        parent_id = None if raw_id == self._TOP_LEVEL_SENTINEL else raw_id
        return {
            "title": self.title_edit.text().strip(),
            "classification": self.classification_combo.currentText(),
            "parent_position_id": parent_id,
        }


# ── Unified Assignment Dialog (3 tabs) ───────────────────────────────────


class _CheckedInTab(QWidget):
    """Tab 1: Personnel already checked into this incident."""

    def __init__(self, incident_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Filter checked-in personnel…")
        self.search_input.textChanged.connect(self._do_search)
        search_row.addWidget(self.search_input, stretch=1)
        layout.addLayout(search_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Callsign", "Role", "Status"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        self._load_roster()

    def _load_roster(self) -> None:
        try:
            from utils.api_client import api_client
            roster = api_client.get(
                f"/api/incidents/{self._incident_id}/checkin/roster"
            ) or []
            # Filter out NoShow / Demobilized by default
            self._all_rows = [
                r for r in roster
                if r.get("ci_status") not in ("NoShow", "Demobilized")
            ]
        except Exception:
            self._all_rows = []
        self._do_search()

    def _do_search(self) -> None:
        term = self.search_input.text().strip().lower()
        filtered = [
            r for r in self._all_rows
            if not term or term in (r.get("name") or "").lower()
            or term in (r.get("callsign") or "").lower()
        ] if term else self._all_rows
        self._rows = filtered
        self.table.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(str(p.get("name") or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(p.get("callsign") or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.get("role") or "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(p.get("ci_status") or "")))
        if self.table.rowCount():
            self.table.selectRow(0)

    def selected_person(self) -> dict | None:
        sel = self.table.selectedItems()
        if not sel:
            return None
        row = sel[0].row()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


class _SearchDBTab(QWidget):
    """Tab 2: Search master personnel database. Selecting = check in + assign."""

    def __init__(self, incident_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search all personnel (min 2 chars)…")
        self.search_input.textChanged.connect(self._schedule_search)
        search_row.addWidget(self.search_input, stretch=1)
        self.btn_search = QPushButton("Search", self)
        self.btn_search.clicked.connect(self._do_search)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Callsign", "Agency", "Phone"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        info = QLabel(
            "Select a person and they will be checked in to this incident "
            "and assigned to the position in one step.",
            self,
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {MUTED_TEXT}; font-style: italic;")
        layout.addWidget(info)

    def _schedule_search(self) -> None:
        term = self.search_input.text().strip()
        if len(term) >= 2:
            self._do_search()

    def _do_search(self) -> None:
        term = self.search_input.text().strip()
        if len(term) < 2:
            self._rows = []
            self.table.setRowCount(0)
            return
        try:
            from utils.api_client import api_client
            results = api_client.get(
                "/api/master/personnel",
                params={"search": term, "limit": 50},
            ) or []
            self._rows = results
        except Exception:
            self._rows = []
        self.table.setRowCount(len(self._rows))
        for row, p in enumerate(self._rows):
            self.table.setItem(row, 0, QTableWidgetItem(str(p.get("name") or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(p.get("callsign") or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.get("home_unit") or p.get("agency") or "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(p.get("phone") or "")))
        if self.table.rowCount():
            self.table.selectRow(0)

    def selected_person(self) -> dict | None:
        sel = self.table.selectedItems()
        if not sel:
            return None
        row = sel[0].row()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def check_in_selected(self) -> dict | None:
        """Check the selected person into this incident and return their info."""
        person = self.selected_person()
        if person is None:
            return None
        person_id = person.get("id") or person.get("person_id")
        if not person_id:
            return None
        try:
            from utils.api_client import api_client
            api_client.put(
                f"/api/incidents/{self._incident_id}/checkin/{person_id}",
                json={"ci_status": "CheckedIn"},
            )
            return person
        except Exception:
            QMessageBox.warning(self, "Check-In", f"Failed to check in {person.get('name', '')}.")
            return None


class _NewPersonTab(QWidget):
    """Tab 3: Create a new personnel record, check in, and assign."""

    def __init__(self, incident_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._created_person: dict | None = None

        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Full name (required)")
        layout.addRow("Name *", self.name_edit)

        self.callsign_edit = QLineEdit(self)
        self.callsign_edit.setPlaceholderText("Optional")
        layout.addRow("Callsign", self.callsign_edit)

        self.agency_edit = QLineEdit(self)
        self.agency_edit.setPlaceholderText("Agency / organization")
        layout.addRow("Agency", self.agency_edit)

        self.phone_edit = QLineEdit(self)
        self.phone_edit.setPlaceholderText("Contact phone")
        layout.addRow("Phone", self.phone_edit)

        self.role_edit = QLineEdit(self)
        self.role_edit.setPlaceholderText("Role / primary qualification")
        layout.addRow("Role", self.role_edit)

        info = QLabel(
            "A new personnel record will be created in the master database, "
            "checked in to this incident, and assigned to the position.",
            self,
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {MUTED_TEXT}; font-style: italic;")
        layout.addRow("", info)

    def validate_and_create(self) -> dict | None:
        """Create the person if validation passes. Returns person dict or None."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "New Person", "Name is required.")
            return None
        try:
            from utils.api_client import api_client
            person = api_client.post("/api/master/personnel", json={
                "name": name,
                "callsign": self.callsign_edit.text().strip(),
                "home_unit": self.agency_edit.text().strip(),
                "phone": self.phone_edit.text().strip(),
                "primary_role": self.role_edit.text().strip(),
            })
            if person:
                pid = person.get("id") or person.get("person_id")
                if pid:
                    api_client.put(
                        f"/api/incidents/{self._incident_id}/checkin/{pid}",
                        json={"ci_status": "CheckedIn"},
                    )
                self._created_person = person
                return person
        except Exception as exc:
            QMessageBox.warning(self, "New Person", f"Failed to create person: {exc}")
        return None


class UnifiedAssignmentDialog(QDialog):
    """Single dialog with three tabs for assigning personnel to a position."""

    def __init__(
        self,
        incident_id: str,
        position_title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Assign Personnel — {position_title}")
        self.setMinimumSize(650, 500)
        self._incident_id = incident_id
        self._result: dict | None = None

        layout = QVBoxLayout(self)

        header = QLabel(f"Assign someone to: <b>{position_title}</b>", self)
        header.setWordWrap(True)
        layout.addWidget(header)

        self.tabs = QTabWidget(self)
        self.checked_in_tab = _CheckedInTab(incident_id, self)
        self.search_db_tab = _SearchDBTab(incident_id, self)
        self.new_person_tab = _NewPersonTab(incident_id, self)
        self.tabs.addTab(self.checked_in_tab, "Checked-In")
        self.tabs.addTab(self.search_db_tab, "Search Database")
        self.tabs.addTab(self.new_person_tab, "New Person")
        layout.addWidget(self.tabs, stretch=1)

        # Assignment type selector
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Assignment type:", self))
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(
            [
                ASSIGNMENT_TYPE_PRIMARY,
                ASSIGNMENT_TYPE_DEPUTY,
                ASSIGNMENT_TYPE_ASSISTANT,
                ASSIGNMENT_TYPE_STAFF_ASSISTANT,
                ASSIGNMENT_TYPE_TRAINEE,
            ]
        )
        type_row.addWidget(self.type_combo)
        type_row.addStretch(1)
        layout.addLayout(type_row)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, self)
        self.btn_assign = QPushButton("Assign", self)
        self.btn_assign.clicked.connect(self._handle_assign)
        buttons.addButton(self.btn_assign, QDialogButtonBox.AcceptRole)
        layout.addWidget(buttons)

    def _resolve_person(self) -> dict | None:
        """Get person info from whichever tab is active."""
        tab = self.tabs.currentWidget()
        if isinstance(tab, _CheckedInTab):
            return tab.selected_person()
        elif isinstance(tab, _SearchDBTab):
            return tab.check_in_selected()
        elif isinstance(tab, _NewPersonTab):
            return tab.validate_and_create()
        return None

    def _handle_assign(self) -> None:
        person = self._resolve_person()
        if person is None:
            return
        pid = person.get("person_record") or person.get("id") or person.get("int_id")
        name = person.get("name") or " ".join(
            part for part in (str(person.get("first_name") or "").strip(), str(person.get("last_name") or "").strip()) if part
        )
        if not name:
            QMessageBox.warning(self, "Assign", "No person name available.")
            return
        self._result = {
            "person_record": int(pid) if pid is not None else None,
            "person_name": name,
            "assignment_type": normalize_assignment_type(self.type_combo.currentText()),
        }
        self.accept()

    def result_values(self) -> dict | None:
        return self._result


# ── Templates dialog ─────────────────────────────────────────────────────


class TemplatesDialog(QDialog):
    """Dialog for previewing and loading organization templates."""

    def __init__(
        self, templates: list[OrganizationTemplate], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Organization Templates")
        self._templates_by_name = {template.name: template for template in templates}
        self._selected_name: str | None = None

        layout = QVBoxLayout(self)
        self.lst_templates = QListWidget(self)
        for template in sorted(templates, key=lambda item: item.name.lower()):
            item = QListWidgetItem(template.name)
            item.setData(Qt.UserRole, template.name)
            if template.description:
                item.setToolTip(template.description)
            self.lst_templates.addItem(item)
        self.lst_templates.currentItemChanged.connect(self._update_preview)
        layout.addWidget(self.lst_templates)

        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            "Select a template to preview the positions that will be created."
        )
        layout.addWidget(self.preview, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok, self)
        buttons.button(QDialogButtonBox.Ok).setText("Load")
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.lst_templates.count():
            self.lst_templates.setCurrentRow(0)

    def _update_preview(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            self.preview.clear()
            return
        template = self._templates_by_name.get(str(current.data(Qt.UserRole)))
        if template is None:
            self.preview.clear()
            return
        lines: list[str] = []
        if template.description:
            lines.extend([template.description, ""])
        depths: dict[str, int] = {}
        for index, raw in enumerate(template.payload):
            key = str(raw.get("key") or f"item_{index}")
            parent_key = str(raw.get("parent_key") or "")
            depth = depths.get(parent_key, -1) + 1 if parent_key else 0
            depths[key] = depth
            title = str(raw.get("title") or "").strip() or "(Untitled)"
            classification = str(raw.get("classification") or "position")
            lines.append(f"{'  ' * depth}{title} ({classification})")
        self.preview.setPlainText("\n".join(lines) if lines else "Template is empty.")

    def _handle_accept(self) -> None:
        item = self.lst_templates.currentItem()
        if item is None:
            self.reject()
            return
        self._selected_name = str(item.data(Qt.UserRole))
        self.accept()

    def selected_template_name(self) -> str | None:
        return self._selected_name


# ── Move dialog ──────────────────────────────────────────────────────────


class _MoveUnderDialog(QDialog):
    """Prompt for choosing a new parent position (or top level) for a position."""

    _TOP_LEVEL_SENTINEL = -1

    def __init__(
        self,
        position_title: str,
        candidates: list[OrganizationPosition],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Move Position Under…")
        layout = QFormLayout(self)
        layout.addRow(QLabel(f'Move "{position_title}" under:', self))
        self.combo = QComboBox(self)
        self.combo.addItem("— Top Level (no parent) —", self._TOP_LEVEL_SENTINEL)
        by_parent: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for pos in candidates:
            by_parent[pos.parent_position_id].append(pos)

        def add_children(parent_id: int | None, depth: int) -> None:
            for pos in by_parent.get(parent_id, []):
                label = "    " * depth + pos.title + f"  ({pos.classification})"
                self.combo.addItem(label, pos.id)
                add_children(pos.id, depth + 1)

        add_children(None, 0)
        layout.addRow("New parent", self.combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_parent_id(self) -> int | None:
        raw = self.combo.currentData()
        return None if raw == self._TOP_LEVEL_SENTINEL else raw


# ── Main panel ───────────────────────────────────────────────────────────


class IncidentOrganizationPanel(QWidget):
    """Dual-pane organization manager.

    Left pane: tree with assignments shown inline, color-coded by type.
    Right pane: position detail and action buttons.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("IncidentOrganizationPanel")
        self.incident_id: Optional[str] = None
        self.controller: Optional[IncidentOrganizationController] = None
        self._positions_by_id: dict[int, OrganizationPosition] = {}
        self._assignments_by_position: dict[int, list[PositionAssignment]] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # ── Toolbar ────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        self.btn_ops_section = QPushButton("Operations Section…", self)
        self.btn_ops_section.clicked.connect(self._open_ops_section_window)
        toolbar.addWidget(self.btn_ops_section)
        self.btn_add_position = QPushButton("Add Position…", self)
        self.btn_add_position.clicked.connect(self._add_position)
        toolbar.addWidget(self.btn_add_position)
        self.btn_edit_position = QPushButton("Edit Position…", self)
        self.btn_edit_position.clicked.connect(self._edit_position)
        toolbar.addWidget(self.btn_edit_position)
        self.btn_deactivate_position = QPushButton("Deactivate", self)
        self.btn_deactivate_position.clicked.connect(self._deactivate_position)
        toolbar.addWidget(self.btn_deactivate_position)
        self.btn_templates = QPushButton("Templates…", self)
        self.btn_templates.clicked.connect(self._apply_template)
        toolbar.addWidget(self.btn_templates)
        toolbar.addStretch(1)
        self.btn_ics203 = QPushButton("Prepare ICS 203", self)
        self.btn_ics203.clicked.connect(lambda: self._prepare_form("ICS_203"))
        toolbar.addWidget(self.btn_ics203)
        self.btn_ics207 = QPushButton("Prepare ICS 207", self)
        self.btn_ics207.clicked.connect(lambda: self._prepare_form("ICS_207"))
        toolbar.addWidget(self.btn_ics207)
        root_layout.addLayout(toolbar)

        # ── Dual-pane splitter ─────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal, self)
        root_layout.addWidget(splitter, stretch=1)

        # Left: organization tree
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Organization", left_widget))
        self.tree = QTreeWidget(left_widget)
        self.tree.setHeaderLabels(["Position", "Assignment"])
        self.tree.header().setStretchLastSection(True)
        self.tree.itemSelectionChanged.connect(self._handle_tree_selection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        left_layout.addWidget(self.tree, stretch=1)
        splitter.addWidget(left_widget)

        # Right: position detail panel
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 0, 0)

        # Position header
        self.detail_title = QLabel("Select a position", right_widget)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.detail_title.setFont(title_font)
        right_layout.addWidget(self.detail_title)

        self.detail_meta = QLabel("", right_widget)
        self.detail_meta.setStyleSheet(f"color: {MUTED_TEXT};")
        self.detail_meta.setWordWrap(True)
        right_layout.addWidget(self.detail_meta)

        # Status + warnings
        self.status_label = QLabel("", right_widget)
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)
        self.warning_label = QLabel("", right_widget)
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #e65100;")
        right_layout.addWidget(self.warning_label)

        # Action buttons
        action_row = QHBoxLayout()
        self.btn_assign = QPushButton("Assign Personnel…", right_widget)
        self.btn_assign.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_assign.clicked.connect(self._assign_personnel)
        action_row.addWidget(self.btn_assign)

        self.btn_remove_assignment = QPushButton("Remove Selected", right_widget)
        self.btn_remove_assignment.clicked.connect(self._remove_selected_assignment)
        action_row.addWidget(self.btn_remove_assignment)

        action_row.addStretch(1)
        right_layout.addLayout(action_row)

        # ── Assignments table (grouped by type) ─────────────────────
        right_layout.addWidget(QLabel("Assigned Personnel", right_widget))
        self.assignments_table = QTableWidget(right_widget)
        self.assignments_table.setColumnCount(4)
        self.assignments_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Period", "Notes"]
        )
        self.assignments_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.assignments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.assignments_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.assignments_table.verticalHeader().setVisible(False)
        self.assignments_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.assignments_table, stretch=1)

        # ── Personnel pool (compact, below assignments) ─────────────
        pool_group = QGroupBox("Personnel Pool", right_widget)
        pool_layout = QVBoxLayout(pool_group)

        pool_search_row = QHBoxLayout()
        self.personnel_search = QLineEdit(pool_group)
        self.personnel_search.setPlaceholderText("Search available personnel…")
        pool_search_row.addWidget(self.personnel_search, stretch=1)
        self.btn_search_personnel = QPushButton("Search", pool_group)
        self.btn_search_personnel.clicked.connect(self._search_personnel)
        pool_search_row.addWidget(self.btn_search_personnel)
        pool_layout.addLayout(pool_search_row)

        self.pool_table = QTableWidget(pool_group)
        self.pool_table.setColumnCount(4)
        self.pool_table.setHorizontalHeaderLabels(["Name", "Callsign", "Agency", "Phone"])
        self.pool_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pool_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pool_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pool_table.verticalHeader().setVisible(False)
        self.pool_table.horizontalHeader().setStretchLastSection(True)
        pool_layout.addWidget(self.pool_table, stretch=1)

        pool_assign_row = QHBoxLayout()
        self.btn_pool_assign = QPushButton("Assign Selected", pool_group)
        self.btn_pool_assign.clicked.connect(self._pool_assign)
        pool_assign_row.addWidget(self.btn_pool_assign)
        pool_assign_row.addStretch(1)
        pool_layout.addLayout(pool_assign_row)

        right_layout.addWidget(pool_group)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        # ── State ──────────────────────────────────────────────────
        self._ops_section_window: Optional[OperationsSectionWindow] = None
        self._pool_rows: list[dict] = []
        self._set_enabled(False)
        self._init_incident_tracking()

    # ------------------------------------------------------------------
    def load(self, incident_id: str) -> None:
        self.incident_id = str(incident_id)
        self.controller = IncidentOrganizationController(self.incident_id)
        self._refresh()
        self._set_enabled(True)

    def _ensure_controller(self) -> IncidentOrganizationController:
        if self.controller is None:
            if not self.incident_id:
                raise RuntimeError("Incident must be loaded before managing organization")
            self.controller = IncidentOrganizationController(self.incident_id)
        return self.controller

    def _init_incident_tracking(self) -> None:
        active = self._active_incident_from_state()
        if active:
            self.load(active)
        app_signals.incidentChanged.connect(self._handle_incident_changed)

    @staticmethod
    def _active_incident_from_state() -> str | None:
        active = AppState.get_active_incident()
        return str(active) if active else None

    def _handle_incident_changed(self, incident_id: str) -> None:
        if incident_id:
            self.load(str(incident_id))

    def _open_ops_section_window(self) -> None:
        if not self.incident_id:
            QMessageBox.warning(self, "Incident Required", "Load an incident first.")
            return
        if self._ops_section_window is None or not self._ops_section_window.isVisible():
            self._ops_section_window = OperationsSectionWindow(self.incident_id, self)
            self._ops_section_window.structure_changed.connect(self._refresh)
        self._ops_section_window.show()
        self._ops_section_window.raise_()
        self._ops_section_window.activateWindow()

    def _set_enabled(self, enabled: bool) -> None:
        for button in (
            self.btn_ops_section,
            self.btn_add_position,
            self.btn_edit_position,
            self.btn_deactivate_position,
            self.btn_templates,
            self.btn_ics203,
            self.btn_ics207,
            self.btn_assign,
            self.btn_remove_assignment,
            self.btn_search_personnel,
            self.btn_pool_assign,
        ):
            button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._refresh_tree()
        self._handle_tree_selection()

    def _refresh_tree(self) -> None:
        controller = self._ensure_controller()
        positions = controller.list_positions()
        active_assignments = controller.list_assignments(active_only=True)
        summary = controller.staffing_summary()

        self._positions_by_id = {position.id or 0: position for position in positions}
        self._assignments_by_position = defaultdict(list)
        for asgn in active_assignments:
            self._assignments_by_position[asgn.position_id].append(asgn)

        children: dict[int | None, list[OrganizationPosition]] = defaultdict(list)
        for position in positions:
            children[position.parent_position_id].append(position)

        self.tree.clear()

        def add_items(parent_item: QTreeWidget | QTreeWidgetItem, parent_id: int | None) -> None:
            for position in children.get(parent_id, []):
                pos_id = position.id or 0
                pos_assignments = self._assignments_by_position.get(pos_id, [])

                # Build summary of assignments for display
                def _assignment_piece(a: PositionAssignment) -> str | None:
                    assignment_type = normalize_assignment_type(a.assignment_type)
                    if position.classification in {"division", "group"} and assignment_type in {
                        ASSIGNMENT_TYPE_DEPUTY,
                        ASSIGNMENT_TYPE_ASSISTANT,
                        ASSIGNMENT_TYPE_STAFF_ASSISTANT,
                    }:
                        return None
                    return _assignment_display_text(
                        assignment_type,
                        a.person_name,
                        classification=position.classification,
                    )

                assignment_display = ", ".join(
                    piece for piece in (_assignment_piece(a) for a in pos_assignments) if piece
                )

                item_summary = summary.get(pos_id)
                status = item_summary.staffing_status if item_summary else "unknown"
                title = position.title

                item = QTreeWidgetItem([title, assignment_display])

                # Color-code status
                if status == "vacant":
                    item.setForeground(0, QColor("#bdbdbd"))
                elif status == "partially filled":
                    item.setForeground(0, QColor("#e65100"))

                item.setData(0, Qt.UserRole, position.id)
                if item_summary and item_summary.warnings:
                    item.setToolTip(0, "\n".join(w.message for w in item_summary.warnings))
                parent_item.addChild(item)
                add_items(item, position.id)

        add_items(self.tree.invisibleRootItem(), None)
        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)

    def _selected_position_id(self) -> int | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value = items[0].data(0, Qt.UserRole)
        return int(value) if value else None

    def _handle_tree_selection(self) -> None:
        position_id = self._selected_position_id()
        has_selection = bool(position_id and self.incident_id)
        self.btn_edit_position.setEnabled(has_selection)
        self.btn_deactivate_position.setEnabled(has_selection)
        self.btn_assign.setEnabled(has_selection)
        self.btn_remove_assignment.setEnabled(has_selection)

        if not position_id or self.controller is None:
            self.detail_title.setText("Select a position")
            self.detail_meta.setText("")
            self.status_label.setText("")
            self.warning_label.setText("")
            self.assignments_table.setRowCount(0)
            return

        position = self.controller.get_position(position_id)
        if position is None:
            return

        assignments = self.controller.list_assignments(position_id)
        summary = self.controller.staffing_summary().get(position_id)

        self.detail_title.setText(position.title)

        parent_label = "top level"
        if position.parent_position_id and position.parent_position_id in self._positions_by_id:
            parent_label = self._positions_by_id[position.parent_position_id].title
        primary_count = sum(
            1
            for assignment in assignments
            if normalize_assignment_type(assignment.assignment_type) == ASSIGNMENT_TYPE_PRIMARY
        )
        command_mode_tag = (
            " | Unified Command"
            if position.classification == "command"
            and position.title.strip().casefold() == "incident commander"
            and primary_count > 1
            else ""
        )
        self.detail_meta.setText(
            f"{position.classification} | Parent: {parent_label} | "
            f"{len(assignments)} assigned{command_mode_tag}"
        )

        self.status_label.setText(
            f"Staffing: {(summary.staffing_status if summary else 'unknown')}"
        )
        warnings = summary.warnings if summary else []
        self.warning_label.setText("\n".join(w.message for w in warnings) if warnings else "")

        self._populate_assignments(assignments)

    def _populate_assignments(self, assignments: list[PositionAssignment]) -> None:
        sorted_assignments = sorted(
            assignments,
            key=lambda a: (
                _ASSIGNMENT_ORDER.get(normalize_assignment_type(a.assignment_type), 99),
                a.person_name.lower(),
            ),
        )

        self.assignments_table.setRowCount(len(sorted_assignments))
        for row, assignment in enumerate(sorted_assignments):
            assignment_type = normalize_assignment_type(assignment.assignment_type)
            values = [
                assignment.person_name,
                _ASSIGNMENT_LABELS.get(assignment_type, assignment_type.replace("_", " ").title()),
                assignment.start_time or "",
                assignment.end_time or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, assignment.id)
                if col == 1 and assignment_type != ASSIGNMENT_TYPE_PRIMARY:
                    color = _assignment_color(assignment_type)
                    item.setForeground(color)
                self.assignments_table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_tree_context_menu(self, point) -> None:
        if not self.incident_id:
            return
        menu = QMenu(self)
        action_assign = QAction("Assign Personnel…", self)
        action_assign.triggered.connect(self._assign_personnel)
        menu.addAction(action_assign)
        menu.addSeparator()

        action_add_child = QAction("Add Child Position…", self)
        action_add_child.triggered.connect(self._add_child_position)
        menu.addAction(action_add_child)

        action_add_sibling = QAction("Add Sibling Position…", self)
        action_add_sibling.triggered.connect(self._add_sibling_position)
        menu.addAction(action_add_sibling)

        action_add_top = QAction("Add Top-Level Position…", self)
        action_add_top.triggered.connect(self._add_position)
        menu.addAction(action_add_top)
        menu.addSeparator()

        position_id = self._selected_position_id()
        action_move = QAction("Move Under…", self)
        action_move.triggered.connect(self._move_position)
        action_move.setEnabled(bool(position_id))
        menu.addAction(action_move)

        menu.exec(self.tree.mapToGlobal(point))

    # ------------------------------------------------------------------
    # Position CRUD
    # ------------------------------------------------------------------

    def _add_position(self) -> None:
        self._open_add_dialog(preset_parent_id=None)

    def _add_child_position(self) -> None:
        self._open_add_dialog(preset_parent_id=self._selected_position_id())

    def _add_sibling_position(self) -> None:
        position_id = self._selected_position_id()
        sibling_parent: int | None = None
        if position_id and position_id in self._positions_by_id:
            sibling_parent = self._positions_by_id[position_id].parent_position_id
        self._open_add_dialog(preset_parent_id=sibling_parent)

    def _open_add_dialog(self, *, preset_parent_id: int | None) -> None:
        if not self.incident_id:
            QMessageBox.warning(self, "Incident Required", "Load an incident before managing organization.")
            return
        positions = list(self._positions_by_id.values())
        dialog = PositionDialog(
            self,
            parent_position_id=preset_parent_id,
            existing_positions=positions,
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                self._ensure_controller().add_position(dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Position", str(exc))
                return
            self._refresh()

    def _edit_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id:
            return
        position = self._ensure_controller().get_position(position_id)
        if position is None:
            return
        positions = list(self._positions_by_id.values())
        dialog = PositionDialog(
            self,
            position=position,
            existing_positions=positions,
            exclude_id=position_id,
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                self._ensure_controller().update_position(position_id, dialog.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Position", str(exc))
                return
            self._refresh()

    def _move_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id or not self.incident_id:
            return
        position = self._positions_by_id.get(position_id)
        if position is None:
            return
        positions = [p for p in self._positions_by_id.values() if p.id != position_id]
        dialog = _MoveUnderDialog(position.title, positions, self)
        if dialog.exec() == QDialog.Accepted:
            new_parent = dialog.selected_parent_id()
            self._ensure_controller().move_position(position_id, new_parent)
            self._refresh()

    def _deactivate_position(self) -> None:
        position_id = self._selected_position_id()
        if not position_id:
            return
        self._ensure_controller().deactivate_position(position_id)
        self._refresh()

    def _apply_template(self) -> None:
        if not self.incident_id:
            active = self._active_incident_from_state()
            if active:
                self.load(active)
            else:
                QMessageBox.warning(self, "Incident Required", "Load an incident before managing organization.")
                return
        controller = self._ensure_controller()
        templates = controller.list_templates()
        if not templates:
            QMessageBox.information(self, "Organization Templates", "No organization templates are available.")
            return
        dialog = TemplatesDialog(templates, self)
        if dialog.exec() != QDialog.Accepted:
            return
        template_name = dialog.selected_template_name()
        if not template_name:
            return
        try:
            applied_ids = controller.apply_template(template_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Organization Template", str(exc))
            return
        self._refresh()
        QMessageBox.information(
            self,
            "Template Loaded",
            f"Loaded {len(applied_ids)} organization positions from {template_name}.",
        )

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def _assign_personnel(self) -> None:
        """Open the unified assignment dialog for the selected position."""
        position_id = self._selected_position_id()
        if not position_id or not self.incident_id:
            return
        position = self._positions_by_id.get(position_id)
        if position is None:
            return

        dialog = UnifiedAssignmentDialog(
            self.incident_id,
            position.title,
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.result_values()
        if values is None:
            return

        try:
            _, warnings = self._ensure_controller().assign_person(position_id, values)
        except ValueError as exc:
            QMessageBox.warning(self, "Assignment", str(exc))
            return
        if warnings:
            QMessageBox.warning(self, "Qualification Review", "\n".join(w.message for w in warnings))
        self._refresh()

    def _remove_selected_assignment(self) -> None:
        selected = self.assignments_table.selectedItems()
        if not selected:
            return
        assignment_id = selected[0].data(Qt.UserRole)
        if assignment_id:
            self._ensure_controller().remove_assignment(str(assignment_id))
            self._refresh()

    # ------------------------------------------------------------------
    # Personnel pool (legacy quick search)
    # ------------------------------------------------------------------

    def _search_personnel(self) -> None:
        if self.controller is None:
            return
        self._pool_rows = self.controller.personnel_pool(self.personnel_search.text())
        self.pool_table.setRowCount(len(self._pool_rows))
        for row, person in enumerate(self._pool_rows):
            values = [
                str(person.get("name") or ""),
                str(person.get("callsign") or ""),
                str(person.get("agency") or ""),
                str(person.get("phone") or ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, person.get("id"))
                self.pool_table.setItem(row, col, item)

    def _pool_assign(self) -> None:
        """Quick assign from the legacy personnel pool (avoids the unified dialog)."""
        position_id = self._selected_position_id()
        if not position_id:
            return
        selected = self.pool_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Assign", "Search and select someone from the pool first.")
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._pool_rows):
            return
        person = self._pool_rows[row]
        try:
            _, warnings = self._ensure_controller().assign_person(position_id, {
                "person_record": int(person.get("person_record") or 0) or None,
                "person_name": str(
                    person.get("name")
                    or " ".join(
                        part for part in (
                            str(person.get("first_name") or "").strip(),
                            str(person.get("last_name") or "").strip(),
                        )
                        if part
                    )
                ),
                "assignment_type": ASSIGNMENT_TYPE_PRIMARY,
            })
        except ValueError as exc:
            QMessageBox.warning(self, "Assignment", str(exc))
            return
        if warnings:
            QMessageBox.warning(self, "Qualification Review", "\n".join(w.message for w in warnings))
        self._refresh()

    # ------------------------------------------------------------------
    # ICS form generation
    # ------------------------------------------------------------------

    def _prepare_form(self, form_type: str) -> None:
        controller = self._ensure_controller()
        payload = (
            controller.build_ics207_payload()
            if form_type == "ICS_207"
            else controller.build_ics203_payload()
        )
        QMessageBox.information(
            self,
            "Generated Output Prepared",
            f"{form_type.replace('_', ' ')} data was prepared from the incident organization "
            f"for IAP assembly ({len(payload.get('positions', []))} positions).",
        )
