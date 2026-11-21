"""Compact create/edit modal for a single Assignment (quick-assignments)."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import services
from ..records import PlannedRecord
from .assignee_picker_dialog import AssigneePickerDialog
from .schedule_time_utils import friendly_dt

STATUSES = ["Draft", "Planned", "In Progress", "Completed", "Cancelled"]
PRIORITIES = ["Low", "Medium", "High"]
_NONE_LABEL = "— None —"


class AssignmentDetailDialog(QDialog):
    """Create or edit a single Assignment.

    Pass ``record`` to edit an existing assignment, or leave it ``None`` to
    create a new one. After ``exec() == QDialog.Accepted``, read
    ``result_payload()`` for the fields to save.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        incident_id: str | None = None,
        record: PlannedRecord | None = None,
        default_schedule_item_id: str = "",
    ) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._record = record
        self._assigned_team_id = record.assigned_team_id if record else ""
        self._assigned_person_id = record.assigned_person_id if record else ""
        read_only = bool(record and record.promoted_read_only)

        self.setWindowTitle("Assignment" if not record else "Edit Assignment")
        self.resize(460, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(record.title if record else "")
        form.addRow("Assignment", self.title_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUSES)
        self.status_combo.setCurrentText(record.status if record and record.status in STATUSES else "Planned")
        form.addRow("Status", self.status_combo)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText(record.priority if record and record.priority in PRIORITIES else "Medium")
        form.addRow("Priority", self.priority_combo)

        assignee_row = QHBoxLayout()
        self.assignee_edit = QLineEdit(record.assigned_to if record else "")
        self.assignee_edit.setPlaceholderText("Free-text assignee, or choose a resource")
        self.assignee_edit.textEdited.connect(self._on_assignee_text_edited)
        choose_btn = QPushButton("Choose…")
        choose_btn.clicked.connect(self._choose_assignee)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_assignee)
        assignee_row.addWidget(self.assignee_edit, 1)
        assignee_row.addWidget(choose_btn)
        assignee_row.addWidget(clear_btn)
        form.addRow("Assigned To", assignee_row)

        self.assignee_kind_label = QLabel("")
        form.addRow("", self.assignee_kind_label)
        self._refresh_assignee_kind_label()

        self.due_edit = QLineEdit(record.due_at if record else "")
        self.due_edit.setPlaceholderText("Optional due date/time")
        form.addRow("Due", self.due_edit)

        self.location_edit = QLineEdit(record.location if record else "")
        self.location_edit.setPlaceholderText("Optional location")
        form.addRow("Location", self.location_edit)

        schedule_row = QHBoxLayout()
        self.schedule_combo = QComboBox()
        self.schedule_combo.setEditable(True)
        self.schedule_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self.schedule_combo.completer()
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        clear_schedule_btn = QPushButton("Clear")
        clear_schedule_btn.clicked.connect(self._clear_schedule_item)
        schedule_row.addWidget(self.schedule_combo, 1)
        schedule_row.addWidget(clear_schedule_btn)
        form.addRow("Related Schedule Activity", schedule_row)
        self._populate_schedule_combo(record.schedule_item_id if record else default_schedule_item_id)

        self.notes_edit = QTextEdit(record.summary if record else "")
        self.notes_edit.setFixedHeight(90)
        self.notes_edit.setPlaceholderText("Optional notes")
        form.addRow("Notes", self.notes_edit)

        layout.addLayout(form)

        if read_only:
            notice = QLabel("Promoted to formal Operations Tasking — read-only here.")
            notice.setWordWrap(True)
            layout.addWidget(notice)
            for widget in (
                self.title_edit,
                self.status_combo,
                self.priority_combo,
                self.assignee_edit,
                choose_btn,
                clear_btn,
                self.due_edit,
                self.location_edit,
                self.schedule_combo,
                clear_schedule_btn,
                self.notes_edit,
            ):
                widget.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        if read_only:
            buttons.button(QDialogButtonBox.Save).setEnabled(False)
        layout.addWidget(buttons)

        self._payload: dict[str, Any] | None = None

    def _populate_schedule_combo(self, selected_schedule_item_id: str) -> None:
        self.schedule_combo.clear()
        self.schedule_combo.addItem(_NONE_LABEL, "")
        try:
            items = services.list_schedule_items(self._incident_id)
        except Exception:
            items = []
        for item in items:
            when = friendly_dt(item.starts_at)
            label = f"{item.name} ({when})" if when else item.name
            self.schedule_combo.addItem(label, item.record_id)
        if selected_schedule_item_id:
            index = self.schedule_combo.findData(selected_schedule_item_id)
            if index < 0:
                # Linked activity no longer resolves -- keep the stored id
                # selectable rather than silently dropping a link the user
                # didn't ask to remove.
                self.schedule_combo.addItem(f"(unavailable) {selected_schedule_item_id}", selected_schedule_item_id)
                index = self.schedule_combo.count() - 1
            self.schedule_combo.setCurrentIndex(index)
        else:
            self.schedule_combo.setCurrentIndex(0)

    def _clear_schedule_item(self) -> None:
        self.schedule_combo.setCurrentIndex(0)

    def _refresh_assignee_kind_label(self) -> None:
        if self._assigned_person_id:
            self.assignee_kind_label.setText("Linked to Personnel record")
        elif self._assigned_team_id:
            self.assignee_kind_label.setText("Linked to Operations Team record")
        else:
            self.assignee_kind_label.setText("")

    def _on_assignee_text_edited(self, _text: str) -> None:
        # Typing a free-text assignee clears any stale resource link so the
        # record never references two conflicting assignees at once.
        self._assigned_person_id = ""
        self._assigned_team_id = ""
        self._refresh_assignee_kind_label()

    def _choose_assignee(self) -> None:
        dialog = AssigneePickerDialog(self, incident_id=self._incident_id)
        if dialog.exec() != QDialog.Accepted:
            return
        self._assigned_person_id = str(dialog.selected_id) if dialog.selected_kind == "personnel" else ""
        self._assigned_team_id = str(dialog.selected_id) if dialog.selected_kind == "team" else ""
        self.assignee_edit.setText(dialog.selected_label)
        self._refresh_assignee_kind_label()

    def _clear_assignee(self) -> None:
        self.assignee_edit.clear()
        self._assigned_person_id = ""
        self._assigned_team_id = ""
        self._refresh_assignee_kind_label()

    def _on_save(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Assignment", "Assignment title is required.")
            return
        self._payload = {
            "title": title,
            "summary": self.notes_edit.toPlainText().strip(),
            "status": self.status_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "assigned_to": self.assignee_edit.text().strip(),
            "assigned_person_id": self._assigned_person_id,
            "assigned_team_id": self._assigned_team_id,
            "due_at": self.due_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "schedule_item_id": self.schedule_combo.currentData() or "",
        }
        self.accept()

    def result_payload(self) -> dict[str, Any] | None:
        return self._payload
