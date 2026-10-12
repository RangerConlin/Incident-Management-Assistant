"""Agency Requests board — every outside-agency ask or offer, grouped as one
Request (e.g. "AFRCC-1: find the aircraft", "OEM-2: help with POD setup").

Each Request can link to multiple Objectives/Tasks/Resource Requests and
carries its own LOFR-owned narrative thread (Feedback is a narrative
category, not a separate top-level record). Replaces the separate Agency
Requests / Resource Offers / Feedback boards as the single place the LOFR
triages everything coming in from outside agencies — general, not-tied-to-
any-request contact logging stays on the Agency Directory's own Interaction
Log. Kept as its own window for now, alongside (not instead of) the
existing Agency Directory / Reporting Board / Customer Requests & Feedback
windows.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.liaison import repository as liaison_repo
from modules.liaison.models import (
    LIAISON_REQUEST_NARRATIVE_CATEGORIES,
    LIAISON_REQUEST_STATUSES,
    LIAISON_REQUEST_TYPES,
    PRIORITIES,
)
from utils.styles import get_palette, liaison_priority_colors, liaison_request_status_colors, subscribe_theme

_OBJECTIVE_PRIORITY_MAP = {"Low": "low", "Medium": "normal", "High": "high", "Critical": "urgent"}
_ATTENTION_PRIORITIES = {"High", "Critical"}
_OPEN_STATUSES = {"Open", "In Progress"}


def _linked_label(request: dict[str, Any]) -> str:
    parts = []
    objective_ids = request.get("objective_ids") or []
    task_ids = request.get("task_ids") or []
    resource_request_ids = request.get("resource_request_ids") or []
    if objective_ids:
        parts.append(f"{len(objective_ids)} Objective(s)")
    if task_ids:
        parts.append(f"{len(task_ids)} Task(s)")
    if resource_request_ids:
        parts.append(f"{len(resource_request_ids)} Resource Request(s)")
    return ", ".join(parts)


def _parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            continue
    return None


def _is_overdue(request: dict[str, Any]) -> bool:
    if str(request.get("status") or "") not in _OPEN_STATUSES:
        return False
    due = _parse_date(str(request.get("due_date") or ""))
    return due is not None and due < date.today()


def _needs_attention(request: dict[str, Any]) -> bool:
    """Naive first pass: overdue, or open + High/Critical priority.

    TODO: revisit this — needs real criteria (e.g. staleness/no recent
    narrative activity) rather than just priority + due date.
    """
    if str(request.get("status") or "") not in _OPEN_STATUSES:
        return False
    if _is_overdue(request):
        return True
    return str(request.get("priority") or "") in _ATTENTION_PRIORITIES


def _last_narrative_line(request: dict[str, Any]) -> str:
    narrative = request.get("narrative") or []
    if not narrative:
        return "No narrative entries yet."
    entry = narrative[-1]
    category = entry.get("category", "")
    text = entry.get("text", "")
    return f"({category}) {text}" if category else text


def _stat_card(title: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setAttribute(Qt.WA_StyledBackground, True)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    frame.setFixedHeight(72)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(6, 8, 6, 8)
    lay.setSpacing(2)
    count = QLabel("0")
    count.setStyleSheet("font-size:24px; font-weight:700; background:transparent;")
    count.setAlignment(Qt.AlignCenter)
    name = QLabel(title)
    name.setStyleSheet("font-size:11px; font-weight:600; background:transparent;")
    name.setAlignment(Qt.AlignCenter)
    name.setWordWrap(True)
    lay.addWidget(count)
    lay.addWidget(name)
    return frame, count


def _tint_stat_card(frame: QFrame, count_label: QLabel, brushes: dict | None) -> None:
    """Color a stat card so it's visually distinct instead of blending
    into its neighbors, and match its color to what it represents."""
    if not brushes:
        frame.setStyleSheet("QFrame { border: 1px solid palette(mid); border-radius: 6px; }")
        return
    bg = brushes["bg"].color().name()
    fg = brushes["fg"].color().name()
    frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 6px; }}")
    count_label.setStyleSheet(f"font-size:24px; font-weight:700; background:transparent; color:{fg};")


class _LinkPicker(QWidget):
    """Add/remove Objective/Task/Resource Request links, shown in both create and detail dialogs."""

    def __init__(self, incident_id: object | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        self.link_type_combo = QComboBox(self)
        self.link_type_combo.addItems(["Objective", "Task", "Resource Request"])
        self.link_type_combo.currentTextChanged.connect(self._reload_sources)
        row.addWidget(self.link_type_combo)
        self.source_combo = QComboBox(self)
        row.addWidget(self.source_combo, 1)
        add_btn = QPushButton("Add Link", self)
        add_btn.clicked.connect(self._add_link)
        row.addWidget(add_btn)
        layout.addLayout(row)

        layout.addWidget(QLabel("Linked Objectives/Tasks/Resource Requests (double-click to remove):"))
        self.link_list = QListWidget(self)
        self.link_list.itemDoubleClicked.connect(self._remove_link)
        layout.addWidget(self.link_list)

        self._reload_sources(self.link_type_combo.currentText())

    def _reload_sources(self, link_type: str) -> None:
        self.source_combo.clear()
        try:
            if link_type == "Objective":
                from modules.command.models.objectives import ApiObjectiveRepository

                repo = ApiObjectiveRepository(str(self.incident_id))
                for obj in repo.list_objectives():
                    self.source_combo.addItem(f"{obj.code} — {obj.text}", obj.id)
            elif link_type == "Task":
                from modules.operations.taskings.repository import list_tasks

                for task in list_tasks():
                    label = f"{task.get('task_id') or task.get('int_id')} — {task.get('title', '')}"
                    self.source_combo.addItem(label, task.get("int_id"))
            else:
                from modules.logistics.resource_requests import get_service

                service = get_service(str(self.incident_id) if self.incident_id is not None else None)
                for req in service.list_requests({}):
                    label = f"{req.get('id')} — {req.get('title') or req.get('justification') or ''}"
                    self.source_combo.addItem(label, req.get("id"))
        except Exception as exc:
            QMessageBox.warning(self, "Load Sources", f"Failed to load sources:\n{exc}")

    def _add_link(self) -> None:
        link_type = self.link_type_combo.currentText()
        link_id = self.source_combo.currentData()
        if link_id is None:
            return
        for row in range(self.link_list.count()):
            existing = self.link_list.item(row)
            if existing.data(Qt.UserRole) == (link_type, link_id):
                return
        item = QListWidgetItem(f"{link_type}: {self.source_combo.currentText()}")
        item.setData(Qt.UserRole, (link_type, link_id))
        self.link_list.addItem(item)

    def _remove_link(self, item: QListWidgetItem) -> None:
        self.link_list.takeItem(self.link_list.row(item))

    def set_links(self, objective_ids: list[str], task_ids: list[int], resource_request_ids: list[str] | None = None) -> None:
        for obj_id in objective_ids:
            item = QListWidgetItem(f"Objective: {obj_id}")
            item.setData(Qt.UserRole, ("Objective", obj_id))
            self.link_list.addItem(item)
        for task_id in task_ids:
            item = QListWidgetItem(f"Task: {task_id}")
            item.setData(Qt.UserRole, ("Task", task_id))
            self.link_list.addItem(item)
        for rr_id in resource_request_ids or []:
            item = QListWidgetItem(f"Resource Request: {rr_id}")
            item.setData(Qt.UserRole, ("Resource Request", rr_id))
            self.link_list.addItem(item)

    def _ids_for(self, link_type: str) -> list:
        return [
            self.link_list.item(row).data(Qt.UserRole)[1]
            for row in range(self.link_list.count())
            if self.link_list.item(row).data(Qt.UserRole)[0] == link_type
        ]

    def objective_ids(self) -> list[str]:
        return [str(v) for v in self._ids_for("Objective")]

    def task_ids(self) -> list[int]:
        return [int(v) for v in self._ids_for("Task")]

    def resource_request_ids(self) -> list[str]:
        return [str(v) for v in self._ids_for("Resource Request")]


class CreateRequestDialog(QDialog):
    """Add a new Request: an outside agency's ask or offer."""

    def __init__(self, incident_id: object | None, agencies: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.setWindowTitle("New Agency Request")
        self.resize(520, 560)
        layout = QVBoxLayout(self)

        agency_row = QHBoxLayout()
        agency_row.addWidget(QLabel("Agency:"))
        self.agency_combo = QComboBox(self)
        for agency in agencies:
            self.agency_combo.addItem(str(agency.get("agency_name") or "Unnamed Agency"), agency.get("id"))
        agency_row.addWidget(self.agency_combo, 1)
        layout.addLayout(agency_row)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox(self)
        self.type_combo.addItems(LIAISON_REQUEST_TYPES)
        type_row.addWidget(self.type_combo)
        type_row.addWidget(QLabel("Priority:"))
        self.priority_combo = QComboBox(self)
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText("Medium")
        type_row.addWidget(self.priority_combo)
        layout.addLayout(type_row)

        layout.addWidget(QLabel("Summary:"))
        self.summary_edit = QLineEdit(self)
        layout.addWidget(self.summary_edit)

        who_row = QHBoxLayout()
        who_row.addWidget(QLabel("Requested By:"))
        self.requested_by_edit = QLineEdit(self)
        who_row.addWidget(self.requested_by_edit, 1)
        who_row.addWidget(QLabel("Due Date:"))
        self.due_date_edit = QLineEdit(self)
        self.due_date_edit.setPlaceholderText("YYYY-MM-DD")
        who_row.addWidget(self.due_date_edit)
        layout.addLayout(who_row)

        self.link_picker = _LinkPicker(incident_id, self)
        layout.addWidget(self.link_picker, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:  # type: ignore[override]
        if self.agency_combo.currentData() is None:
            QMessageBox.warning(self, "Agency Required", "Select an agency.")
            return
        if not self.summary_edit.text().strip():
            QMessageBox.warning(self, "Summary Required", "Enter a summary.")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "agency_id": self.agency_combo.currentData(),
            "request_type": self.type_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "summary": self.summary_edit.text().strip(),
            "requested_by": self.requested_by_edit.text().strip(),
            "due_date": self.due_date_edit.text().strip(),
            "status": "Open",
            "objective_ids": self.link_picker.objective_ids(),
            "task_ids": self.link_picker.task_ids(),
            "resource_request_ids": self.link_picker.resource_request_ids(),
        }


class ConvertDialog(QDialog):
    """Confirm/edit the text and priority before creating an Objective or Task."""

    def __init__(self, kind: str, initial_text: str, initial_priority: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(f"Convert to {kind}")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"{kind} Text:"))
        self.text_edit = QLineEdit(self)
        self.text_edit.setText(initial_text)
        layout.addWidget(self.text_edit)

        row = QHBoxLayout()
        row.addWidget(QLabel("Priority:"))
        self.priority_combo = QComboBox(self)
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText(initial_priority)
        row.addWidget(self.priority_combo)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:  # type: ignore[override]
        if not self.text_edit.text().strip():
            QMessageBox.warning(self, "Text Required", f"Enter the {self.kind} text.")
            return
        super().accept()

    def values(self) -> tuple[str, str]:
        return self.text_edit.text().strip(), self.priority_combo.currentText()


class RequestDetailDialog(QDialog):
    """Status/priority/links editor plus the LOFR's narrative thread for one Request."""

    def __init__(self, request: dict[str, Any], incident_id: object | None, agency_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.request = request
        self.incident_id = incident_id
        code = request.get("code") or f"Request #{request.get('int_id')}"
        self.setWindowTitle(f"{code} — {agency_name}")
        self.resize(680, 760)
        layout = QVBoxLayout(self)

        # Demographics: kept compact (form-style, tight rows) so the
        # narrative thread below gets most of the dialog's vertical space —
        # that thread is where the LOFR spends most of their time.
        header = QLabel(f"{code} — {agency_name}  •  Type: {request.get('request_type', '')}")
        header.setStyleSheet("font-weight:700;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 4)
        form.setVerticalSpacing(4)

        self.summary_edit = QLineEdit(self)
        self.summary_edit.setText(str(request.get("summary") or ""))
        form.addRow("Summary:", self.summary_edit)

        who_row = QHBoxLayout()
        self.requested_by_edit = QLineEdit(self)
        self.requested_by_edit.setText(str(request.get("requested_by") or ""))
        self.requested_by_edit.setPlaceholderText("Requested by")
        who_row.addWidget(self.requested_by_edit, 1)
        self.due_date_edit = QLineEdit(self)
        self.due_date_edit.setText(str(request.get("due_date") or ""))
        self.due_date_edit.setPlaceholderText("Due date (YYYY-MM-DD)")
        who_row.addWidget(self.due_date_edit, 1)
        form.addRow("Requested by / Due:", who_row)

        status_row = QHBoxLayout()
        self.priority_combo = QComboBox(self)
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText(str(request.get("priority") or "Medium"))
        status_row.addWidget(self.priority_combo, 1)
        self.status_combo = QComboBox(self)
        self.status_combo.addItems(LIAISON_REQUEST_STATUSES)
        self.status_combo.setCurrentText(str(request.get("status") or "Open"))
        status_row.addWidget(self.status_combo, 1)
        convert_obj_btn = QPushButton("Convert to Objective", self)
        convert_obj_btn.clicked.connect(self._convert_to_objective)
        status_row.addWidget(convert_obj_btn)
        convert_task_btn = QPushButton("Convert to Task", self)
        convert_task_btn.clicked.connect(self._convert_to_task)
        status_row.addWidget(convert_task_btn)
        form.addRow("Priority / Status:", status_row)
        layout.addLayout(form)

        self.link_picker = _LinkPicker(incident_id, self)
        self.link_picker.link_list.setMaximumHeight(64)
        self.link_picker.set_links(
            request.get("objective_ids") or [],
            request.get("task_ids") or [],
            request.get("resource_request_ids") or [],
        )
        layout.addWidget(self.link_picker)

        layout.addWidget(QLabel("Narrative:"))
        self.narrative_list = QListWidget(self)
        self.narrative_list.setMinimumHeight(260)
        self._reload_narrative()
        layout.addWidget(self.narrative_list, 1)

        entry_row = QHBoxLayout()
        self.entry_category = QComboBox(self)
        self.entry_category.addItems(LIAISON_REQUEST_NARRATIVE_CATEGORIES)
        entry_row.addWidget(self.entry_category)
        self.entry_text = QLineEdit(self)
        self.entry_text.setPlaceholderText("Add a narrative entry...")
        entry_row.addWidget(self.entry_text, 1)
        add_btn = QPushButton("Add", self)
        add_btn.clicked.connect(self._add_entry)
        entry_row.addWidget(add_btn)
        layout.addLayout(entry_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close, self)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _reload_narrative(self) -> None:
        self.narrative_list.clear()
        for entry in self.request.get("narrative") or []:
            text = f"[{entry.get('ts', '')}] ({entry.get('category', '')}) {entry.get('author', '')}: {entry.get('text', '')}"
            QListWidgetItem(text, self.narrative_list)

    def _current_author(self) -> str:
        try:
            from utils.state import AppState

            return str(AppState.get_active_user_display() or "")
        except Exception:
            return ""

    def _log_narrative(self, category: str, text: str) -> None:
        try:
            self.request = liaison_repo.add_request_narrative_entry(
                self.request["int_id"], text, category=category, author=self._current_author(),
                incident_id=self.incident_id,
            )
            self._reload_narrative()
        except Exception:
            pass

    def _convert_to_objective(self) -> None:
        dialog = ConvertDialog("Objective", self.summary_edit.text().strip(), self.priority_combo.currentText(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        text, priority = dialog.values()
        try:
            from modules.command.models.objectives import ApiObjectiveRepository

            repo = ApiObjectiveRepository(str(self.incident_id))
            detail = repo.create_objective(
                {
                    "text": text,
                    "priority": _OBJECTIVE_PRIORITY_MAP.get(priority, "normal"),
                    "origin_module": "liaison",
                    "origin_id": str(self.request["int_id"]),
                }
            )
            objective_id = detail.summary.id
            self.link_picker.set_links([objective_id], [], [])
            self._log_narrative("Auto", f"Converted to Objective {objective_id}: {text}")
            QMessageBox.information(self, "Convert to Objective", f"Created Objective {objective_id} and linked it.")
        except Exception as exc:
            QMessageBox.critical(self, "Convert to Objective", f"Failed to create Objective:\n{exc}")

    def _convert_to_task(self) -> None:
        dialog = ConvertDialog("Task", self.summary_edit.text().strip(), self.priority_combo.currentText(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        title, priority = dialog.values()
        try:
            from modules.operations.taskings.repository import create_task

            task_int_id = create_task(
                title=title,
                priority=priority,
                origin_module="liaison",
                origin_id=str(self.request["int_id"]),
            )
            self.link_picker.set_links([], [task_int_id], [])
            self._log_narrative("Auto", f"Converted to Task {task_int_id}: {title}")
            QMessageBox.information(self, "Convert to Task", f"Created Task {task_int_id} and linked it.")
        except Exception as exc:
            QMessageBox.critical(self, "Convert to Task", f"Failed to create Task:\n{exc}")

    def _add_entry(self) -> None:
        text = self.entry_text.text().strip()
        if not text:
            return
        self._log_narrative(self.entry_category.currentText(), text)
        if text:
            self.entry_text.clear()

    def _save(self) -> None:
        try:
            liaison_repo.update_request(
                self.request["int_id"],
                {
                    "summary": self.summary_edit.text().strip(),
                    "priority": self.priority_combo.currentText(),
                    "status": self.status_combo.currentText(),
                    "requested_by": self.requested_by_edit.text().strip(),
                    "due_date": self.due_date_edit.text().strip(),
                    "objective_ids": self.link_picker.objective_ids(),
                    "task_ids": self.link_picker.task_ids(),
                    "resource_request_ids": self.link_picker.resource_request_ids(),
                },
                self.incident_id,
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Request", f"Failed to save:\n{exc}")


class _RequestCard(QFrame):
    """One bordered card per Request — code, agency, badges, summary, and
    a footer with requested-by/due-date/links plus the last narrative entry.
    """

    opened = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, request: dict[str, Any], agency_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.request_id = int(request["int_id"])
        self.setFrameShape(QFrame.StyledPanel)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        status_colors = liaison_request_status_colors()
        priority_colors = liaison_priority_colors()
        status = str(request.get("status") or "Open")
        priority = str(request.get("priority") or "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = QHBoxLayout()
        code_label = QLabel(str(request.get("code") or f"#{self.request_id}"))
        code_label.setStyleSheet("font-weight:700;")
        header.addWidget(code_label)
        agency_label = QLabel(agency_name)
        agency_label.setStyleSheet("color:palette(mid);")
        header.addWidget(agency_label)
        header.addStretch(1)

        priority_badge = QLabel(priority)
        priority_brushes = priority_colors.get(priority)
        if priority_brushes:
            priority_badge.setStyleSheet(
                f"background:{priority_brushes['bg'].color().name()};"
                f"color:{priority_brushes['fg'].color().name()};"
                "padding:2px 8px; border-radius:4px; font-weight:700;"
            )
        header.addWidget(priority_badge)

        status_badge = QLabel(status)
        status_brushes = status_colors.get(status)
        if status_brushes:
            status_badge.setStyleSheet(
                f"background:{status_brushes['bg'].color().name()};"
                f"color:{status_brushes['fg'].color().name()};"
                "padding:2px 8px; border-radius:4px; font-weight:700;"
            )
        header.addWidget(status_badge)
        layout.addLayout(header)

        summary = QLabel(str(request.get("summary") or ""))
        summary.setWordWrap(True)
        layout.addWidget(summary)

        footer_bits = []
        if request.get("requested_by"):
            footer_bits.append(f"Requested by {request['requested_by']}")
        if request.get("due_date"):
            footer_bits.append(f"Due {request['due_date']}")
        linked = _linked_label(request)
        if linked:
            footer_bits.append(linked)
        if footer_bits:
            footer = QLabel("  •  ".join(footer_bits))
            footer.setStyleSheet("color:palette(mid); font-size:11px;")
            layout.addWidget(footer)

        narrative_line = QLabel(_last_narrative_line(request))
        narrative_line.setWordWrap(True)
        narrative_line.setStyleSheet("color:palette(mid); font-size:11px; font-style:italic;")
        layout.addWidget(narrative_line)

        if _is_overdue(request):
            border_color = (priority_colors.get("Critical") or {}).get("bg")
        elif _needs_attention(request):
            border_color = (priority_colors.get("High") or {}).get("bg")
        else:
            border_color = None
        card_bg = get_palette().get("bg_raised")
        rules = [f"background-color: {card_bg.name()};", "border-radius: 8px;"]
        if border_color:
            rules.append(f"border-left: 3px solid {border_color.color().name()};")
        self.setStyleSheet("_RequestCard { " + " ".join(rules) + " }")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.opened.emit(self.request_id)
        super().mousePressEvent(event)

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        menu.addAction("Open / Edit", lambda: self.opened.emit(self.request_id))
        menu.addAction("Remove Request", lambda: self.remove_requested.emit(self.request_id))
        menu.exec(self.mapToGlobal(position))


class RequestsBoard(QWidget):
    """Every outside-agency ask or offer, one card per Request, grouped
    under stat cards and a "Needing attention" strip.
    """

    def __init__(self, incident_id: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self._requests_cache: list[dict[str, Any]] = []
        self._agency_names: dict[int, str] = {}

        root = QVBoxLayout(self)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self._stat_cards: dict[str, tuple[QFrame, QLabel]] = {}
        for key, title in [
            ("open", "OPEN"),
            ("in_progress", "IN PROGRESS"),
            ("overdue", "OVERDUE"),
            ("resolved_week", "RESOLVED\nTHIS WEEK"),
        ]:
            card, count_label = _stat_card(title)
            stats_row.addWidget(card)
            self._stat_cards[key] = (card, count_label)
        root.addLayout(stats_row)

        attention_label = QLabel("NEEDING ATTENTION")
        attention_label.setStyleSheet("font-size:11px; font-weight:700; letter-spacing:0.05em; color:palette(mid); margin-top:8px;")
        root.addWidget(attention_label)
        self._attention_lay = QVBoxLayout()
        self._attention_lay.setSpacing(4)
        root.addLayout(self._attention_lay)

        toolbar = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search Agency Requests...")
        self.search.textChanged.connect(lambda _t: self._render_cards())
        self.status_filter = QComboBox(self)
        self.status_filter.addItems(["All", *LIAISON_REQUEST_STATUSES])
        self.status_filter.currentTextChanged.connect(lambda _t: self._render_cards())
        self.priority_filter = QComboBox(self)
        self.priority_filter.addItems(["All", *PRIORITIES])
        self.priority_filter.currentTextChanged.connect(lambda _t: self._render_cards())
        create_btn = QPushButton("+ New Request", self)
        create_btn.clicked.connect(self._create_request)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(QLabel("Status:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Priority:"))
        toolbar.addWidget(self.priority_filter)
        toolbar.addWidget(create_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.setContentsMargins(0, 8, 0, 0)
        root.addLayout(toolbar)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._card_container = QWidget()
        self._card_lay = QVBoxLayout(self._card_container)
        self._card_lay.setSpacing(8)
        self._card_lay.addStretch(1)
        self._scroll.setWidget(self._card_container)
        root.addWidget(self._scroll, 1)

        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass
        self.reload()

    def _on_theme_changed(self, _name: str) -> None:
        self._render_stats()
        self._render_cards()
        self._render_attention()

    def _filtered_requests(self) -> list[dict[str, Any]]:
        needle = self.search.text().strip().lower()
        status = self.status_filter.currentText()
        priority = self.priority_filter.currentText()
        result = []
        for request in self._requests_cache:
            if status != "All" and str(request.get("status") or "") != status:
                continue
            if priority != "All" and str(request.get("priority") or "") != priority:
                continue
            if needle:
                agency_name = self._agency_names.get(int(request.get("agency_id") or -1), "")
                haystack = " ".join([
                    str(request.get("code") or ""), agency_name,
                    str(request.get("summary") or ""), str(request.get("requested_by") or ""),
                ]).lower()
                if needle not in haystack:
                    continue
            result.append(request)
        return result

    def reload(self) -> None:
        try:
            agencies = liaison_repo.fetch_agency_rows(self.incident_id)
            self._agency_names = {int(a["id"]): str(a.get("agency_name") or "") for a in agencies}
        except Exception:
            self._agency_names = {}
        try:
            self._requests_cache = liaison_repo.fetch_requests(self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Agency Requests", f"Failed to load requests:\n{exc}")
            self._requests_cache = []
        self._render_stats()
        self._render_attention()
        self._render_cards()

    def _render_stats(self) -> None:
        today = date.today()
        open_count = sum(1 for r in self._requests_cache if r.get("status") == "Open")
        in_progress_count = sum(1 for r in self._requests_cache if r.get("status") == "In Progress")
        overdue_count = sum(1 for r in self._requests_cache if _is_overdue(r))
        resolved_week = 0
        for r in self._requests_cache:
            if r.get("status") != "Resolved":
                continue
            updated = _parse_date(str(r.get("updated_at") or ""))
            if updated and (today - updated).days <= 7:
                resolved_week += 1
        self._stat_cards["open"][1].setText(str(open_count))
        self._stat_cards["in_progress"][1].setText(str(in_progress_count))
        self._stat_cards["overdue"][1].setText(str(overdue_count))
        self._stat_cards["resolved_week"][1].setText(str(resolved_week))

        status_colors = liaison_request_status_colors()
        priority_colors = liaison_priority_colors()
        _tint_stat_card(*self._stat_cards["open"], status_colors.get("Open"))
        _tint_stat_card(*self._stat_cards["in_progress"], status_colors.get("In Progress"))
        _tint_stat_card(*self._stat_cards["overdue"], priority_colors.get("Critical"))
        _tint_stat_card(*self._stat_cards["resolved_week"], status_colors.get("Resolved"))

    def _render_attention(self) -> None:
        lay = self._attention_lay
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        flagged = [r for r in self._requests_cache if _needs_attention(r)][:6]
        if not flagged:
            lay.addWidget(QLabel("Nothing currently flagged for attention."))
            return
        priority_colors = liaison_priority_colors()
        for request in flagged:
            row = QHBoxLayout()
            code = QLabel(str(request.get("code") or ""))
            code.setStyleSheet("font-weight:700;")
            row.addWidget(code)
            summary = QLabel(str(request.get("summary") or ""))
            row.addWidget(summary, 1)
            priority = str(request.get("priority") or "")
            badge = QLabel(priority)
            brushes = priority_colors.get(priority)
            if brushes:
                badge.setStyleSheet(
                    f"background:{brushes['bg'].color().name()};"
                    f"color:{brushes['fg'].color().name()};"
                    "padding:2px 8px; border-radius:4px; font-weight:700;"
                )
            row.addWidget(badge)
            if _is_overdue(request):
                overdue_label = QLabel(f"Due {request.get('due_date')} — overdue")
                overdue_label.setStyleSheet("color:palette(mid); font-size:11px;")
                row.addWidget(overdue_label)
            wrapper = QWidget()
            wrapper.setLayout(row)
            lay.addWidget(wrapper)

    def _render_cards(self) -> None:
        while self._card_lay.count() > 1:
            item = self._card_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for request in self._filtered_requests():
            agency_name = self._agency_names.get(int(request.get("agency_id") or -1), "")
            card = _RequestCard(request, agency_name)
            card.opened.connect(self._open_request)
            card.remove_requested.connect(self._delete_request)
            self._card_lay.insertWidget(self._card_lay.count() - 1, card)

    def _open_request(self, request_id: int) -> None:
        request = next((r for r in self._requests_cache if r.get("int_id") == request_id), None)
        if request is None:
            return
        agency_name = self._agency_names.get(int(request.get("agency_id") or -1), "Unknown Agency")
        dialog = RequestDetailDialog(request, self.incident_id, agency_name, self)
        dialog.exec()
        self.reload()

    def _create_request(self) -> None:
        try:
            agencies = liaison_repo.fetch_agency_rows(self.incident_id)
        except Exception as exc:
            QMessageBox.critical(self, "Agency Requests", f"Failed to load agencies:\n{exc}")
            return
        if not agencies:
            QMessageBox.information(self, "Agency Requests", "Add an agency before creating a request.")
            return
        dialog = CreateRequestDialog(self.incident_id, agencies, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            from utils.state import AppState

            created_by = str(AppState.get_active_user_display() or "")
        except Exception:
            created_by = ""
        values = dialog.values()
        values["created_by"] = created_by
        try:
            liaison_repo.create_request(values, incident_id=self.incident_id)
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "New Agency Request", f"Failed to create request:\n{exc}")

    def _delete_request(self, request_id: int) -> None:
        if QMessageBox.question(
            self,
            "Remove Request",
            "Remove this request? This cannot be undone.",
        ) != QMessageBox.Yes:
            return
        try:
            liaison_repo.delete_request(request_id, self.incident_id)
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Remove Request", f"Failed to remove:\n{exc}")


def get_requests_panel(incident_id: object | None = None) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Liaison Agency Requests")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(RequestsBoard(incident_id, panel))
    return panel
