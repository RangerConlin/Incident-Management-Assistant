from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .models import MeetingTemplate
from .repository import MeetingsRepository
from .services import MeetingsService


# ── New Meeting dialog ────────────────────────────────────────────────────────

class _NewMeetingDialog(QDialog):
    def __init__(self, templates: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Meeting")
        self.setMinimumWidth(380)
        self._result: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.template_combo = QComboBox()
        for t in templates:
            self.template_combo.addItem(t.name, t.slug)

        self.date_edit = QLineEdit(date.today().isoformat())
        self.time_edit = QLineEdit("08:00")
        self.location_edit = QLineEdit()
        self.owner_edit = QLineEdit()

        form.addRow("Template", self.template_combo)
        form.addRow("Date", self.date_edit)
        form.addRow("Start time", self.time_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Owner", self.owner_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        slug = self.template_combo.currentData()
        if not slug:
            QMessageBox.warning(self, "New Meeting", "Please select a template.")
            return
        self._result = {
            "slug": str(slug),
            "meeting_date": self.date_edit.text().strip(),
            "start_time": self.time_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "owner": self.owner_edit.text().strip(),
        }
        self.accept()

    def result_data(self) -> dict | None:
        return self._result


# ── Meeting detail window ─────────────────────────────────────────────────────

class _MeetingDetailWindow(QDialog):
    def __init__(self, meeting_id: int, repository: MeetingsRepository, service: MeetingsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(600, 640)
        self._meeting_id = meeting_id
        self._repository = repository
        self._service = service
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        root.addWidget(self.title_label)

        # Meeting Details group
        details_group = QGroupBox("Meeting Details")
        details_form = QFormLayout(details_group)
        details_form.setHorizontalSpacing(12)
        details_form.setVerticalSpacing(6)
        self.status_combo = QComboBox()
        self.status_combo.addItems(["draft", "scheduled", "ready", "completed", "canceled"])
        self.show_ics230_check = QCheckBox("Visible on ICS-230")
        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(80)
        save_btn.clicked.connect(self._save_detail)
        details_form.addRow("Status", self.status_combo)
        details_form.addRow("", self.show_ics230_check)
        details_form.addRow("", save_btn)

        # Attendees group
        attendees_group = QGroupBox("Attendees")
        att_layout = QVBoxLayout(attendees_group)
        att_layout.setContentsMargins(6, 6, 6, 6)
        self.attendees_table = QTableWidget(0, 3)
        self.attendees_table.setHorizontalHeaderLabels(["Attendee", "Requirement", "Status"])
        self.attendees_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.attendees_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.attendees_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.attendees_table.setAlternatingRowColors(True)
        att_layout.addWidget(self.attendees_table)

        # Checklist group
        checklist_group = QGroupBox("Checklist")
        chk_layout = QVBoxLayout(checklist_group)
        chk_layout.setContentsMargins(6, 6, 6, 6)
        self.checklist_table = QTableWidget(0, 4)
        self.checklist_table.setHorizontalHeaderLabels(["Done", "N/A", "Group", "Item"])
        hdr = self.checklist_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        self.checklist_table.setColumnWidth(0, 48)
        self.checklist_table.setColumnWidth(1, 48)
        self.checklist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.checklist_table.setAlternatingRowColors(True)
        self.checklist_table.itemChanged.connect(self._checklist_item_changed)
        chk_layout.addWidget(self.checklist_table)

        # Structured Notes group
        notes_group = QGroupBox("Structured Notes")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setContentsMargins(6, 6, 6, 6)
        note_bar = QHBoxLayout()
        self.note_category_combo = QComboBox()
        self.note_category_combo.addItems(
            ["decision", "action item", "issue/risk", "resource request",
             "safety item", "assignment", "notable event", "follow-up"]
        )
        self.note_text_edit = QLineEdit()
        self.note_text_edit.setPlaceholderText("Note text…")
        add_note_btn = QPushButton("Add Note")
        add_note_btn.clicked.connect(self._add_note)
        route_note_btn = QPushButton("Route to Log")
        route_note_btn.clicked.connect(self._route_selected_note)
        note_bar.addWidget(self.note_category_combo)
        note_bar.addWidget(self.note_text_edit, 2)
        note_bar.addWidget(add_note_btn)
        note_bar.addWidget(route_note_btn)
        self.notes_table = QTableWidget(0, 4)
        self.notes_table.setHorizontalHeaderLabels(["Category", "Text", "Author", "Routing"])
        self.notes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.notes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notes_table.setAlternatingRowColors(True)
        notes_layout.addLayout(note_bar)
        notes_layout.addWidget(self.notes_table)

        # Scroll area wrapping all groups
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(8)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        for group in (details_group, attendees_group, checklist_group, notes_group):
            inner_layout.addWidget(group)
        inner_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(scroll)

    def _load(self) -> None:
        meeting = self._repository.get_meeting(self._meeting_id)
        self.setWindowTitle(f"{meeting.title} — {meeting.meeting_date}")
        self.title_label.setText(f"{meeting.title} — {meeting.meeting_date} {meeting.start_time}")
        self.status_combo.setCurrentText(meeting.status)
        self.show_ics230_check.setChecked(meeting.show_on_ics230)

        attendees = self._repository.list_attendees(meeting.id or 0)
        self.attendees_table.setRowCount(len(attendees))
        for row, att in enumerate(attendees):
            for col, val in enumerate([att.display_name, att.requirement_status, att.attendance_status]):
                self.attendees_table.setItem(row, col, QTableWidgetItem(val))

        self.checklist_table.blockSignals(True)
        checklist = self._repository.list_checklist_items(meeting.id or 0)
        self.checklist_table.setRowCount(len(checklist))
        for row, item in enumerate(checklist):
            done = QTableWidgetItem()
            done.setFlags(done.flags() | Qt.ItemIsUserCheckable)
            done.setCheckState(Qt.Checked if item.is_complete else Qt.Unchecked)
            done.setData(Qt.UserRole, item.id)
            na = QTableWidgetItem()
            na.setFlags(na.flags() | Qt.ItemIsUserCheckable)
            na.setCheckState(Qt.Checked if item.is_not_applicable else Qt.Unchecked)
            na.setData(Qt.UserRole, item.id)
            self.checklist_table.setItem(row, 0, done)
            self.checklist_table.setItem(row, 1, na)
            self.checklist_table.setItem(row, 2, QTableWidgetItem(item.group_name))
            self.checklist_table.setItem(row, 3, QTableWidgetItem(item.text))
        self.checklist_table.blockSignals(False)

        notes = self._repository.list_structured_notes(meeting.id or 0)
        self.notes_table.setRowCount(len(notes))
        for row, note in enumerate(notes):
            for col, val in enumerate([note.category, note.text, note.author, note.routing_status]):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, note.id)
                self.notes_table.setItem(row, col, item)

    def _save_detail(self) -> None:
        self._repository.update_meeting(
            self._meeting_id,
            {"status": self.status_combo.currentText(), "show_on_ics230": self.show_ics230_check.isChecked()},
        )

    def _checklist_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() not in (0, 1):
            return
        item_id = item.data(Qt.UserRole)
        if item_id is None:
            return
        field = "is_complete" if item.column() == 0 else "is_not_applicable"
        self._repository.update_checklist_item(int(item_id), {field: item.checkState() == Qt.Checked})

    def _add_note(self) -> None:
        text = self.note_text_edit.text().strip()
        if not text:
            return
        self._service.add_structured_note(
            self._meeting_id,
            category=self.note_category_combo.currentText(),
            text=text,
            route_ready=True,
        )
        self.note_text_edit.clear()
        self._load()

    def _route_selected_note(self) -> None:
        items = self.notes_table.selectedItems()
        if not items:
            return
        note_id = items[0].data(Qt.UserRole)
        if note_id is None:
            return
        meeting = self._repository.get_meeting(self._meeting_id)
        self._service.route_note_to_log(int(note_id), entered_by=meeting.owner)
        self._load()


# ── Template manager window ───────────────────────────────────────────────────

class _TemplateManagerWindow(QDialog):
    def __init__(self, repository: MeetingsRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Meeting Templates")
        self.setMinimumSize(760, 560)
        self._repository = repository
        self._templates: list[MeetingTemplate] = []
        self._build_ui()
        self._load_list()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)

        # Left: template list + New button
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self._on_selection_changed)
        new_btn = QPushButton("New Template")
        new_btn.clicked.connect(self._new_template)
        left_layout.addWidget(QLabel("Templates"))
        left_layout.addWidget(self.template_list, 1)
        left_layout.addWidget(new_btn)
        left.setFixedWidth(200)
        root.addWidget(left)

        # Right: edit form in a scroll area
        form_inner = QWidget()
        form_layout = QVBoxLayout(form_inner)
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(8, 0, 0, 0)

        basics_group = QGroupBox("Basic Info")
        basics_form = QFormLayout(basics_group)
        basics_form.setHorizontalSpacing(12)
        basics_form.setVerticalSpacing(6)
        self.name_edit = QLineEdit()
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 480)
        self.duration_spin.setSuffix(" min")
        self.ics230_check = QCheckBox("Appears on ICS-230 by default")
        basics_form.addRow("Name", self.name_edit)
        basics_form.addRow("Duration", self.duration_spin)
        basics_form.addRow("", self.ics230_check)
        form_layout.addWidget(basics_group)

        roles_group = QGroupBox("Attendee Roles")
        roles_form = QFormLayout(roles_group)
        roles_form.setHorizontalSpacing(12)
        roles_form.setVerticalSpacing(6)
        self.required_roles_edit = QPlainTextEdit()
        self.required_roles_edit.setPlaceholderText("One role per line…")
        self.required_roles_edit.setFixedHeight(80)
        self.optional_roles_edit = QPlainTextEdit()
        self.optional_roles_edit.setPlaceholderText("One role per line…")
        self.optional_roles_edit.setFixedHeight(60)
        roles_form.addRow("Required", self.required_roles_edit)
        roles_form.addRow("Optional", self.optional_roles_edit)
        form_layout.addWidget(roles_group)

        checklist_group = QGroupBox("Checklist Items")
        checklist_form = QFormLayout(checklist_group)
        checklist_form.setHorizontalSpacing(12)
        checklist_form.setVerticalSpacing(6)
        self.prep_edit = QPlainTextEdit()
        self.prep_edit.setPlaceholderText("One item per line…")
        self.prep_edit.setFixedHeight(80)
        self.agenda_edit = QPlainTextEdit()
        self.agenda_edit.setPlaceholderText("One item per line…")
        self.agenda_edit.setFixedHeight(80)
        self.closeout_edit = QPlainTextEdit()
        self.closeout_edit.setPlaceholderText("One item per line…")
        self.closeout_edit.setFixedHeight(80)
        checklist_form.addRow("Prep", self.prep_edit)
        checklist_form.addRow("Agenda", self.agenda_edit)
        checklist_form.addRow("Closeout", self.closeout_edit)
        form_layout.addWidget(checklist_group)

        save_btn = QPushButton("Save Template")
        save_btn.clicked.connect(self._save_template)
        form_layout.addWidget(save_btn)
        form_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_inner)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(scroll, 1)

        self._set_form_enabled(False)

    def _set_form_enabled(self, enabled: bool) -> None:
        for w in (self.name_edit, self.duration_spin, self.ics230_check,
                  self.required_roles_edit, self.optional_roles_edit,
                  self.prep_edit, self.agenda_edit, self.closeout_edit):
            w.setEnabled(enabled)

    def _load_list(self) -> None:
        self._templates = self._repository.list_templates(active_only=False)
        self.template_list.clear()
        for t in self._templates:
            self.template_list.addItem(t.name)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._templates):
            self._set_form_enabled(False)
            return
        t = self._templates[row]
        self._set_form_enabled(True)
        self.name_edit.setText(t.name)
        self.duration_spin.setValue(t.default_duration_minutes)
        self.ics230_check.setChecked(t.appears_on_ics230_default)
        self.required_roles_edit.setPlainText("\n".join(t.required_attendee_roles))
        self.optional_roles_edit.setPlainText("\n".join(t.optional_attendee_roles))
        self.prep_edit.setPlainText("\n".join(t.prep_checklist_items))
        self.agenda_edit.setPlainText("\n".join(t.agenda_checklist_items))
        self.closeout_edit.setPlainText("\n".join(t.closeout_checklist_items))

    def _new_template(self) -> None:
        self._set_form_enabled(True)
        self.template_list.clearSelection()
        self.name_edit.clear()
        self.duration_spin.setValue(60)
        self.ics230_check.setChecked(True)
        self.required_roles_edit.clear()
        self.optional_roles_edit.clear()
        self.prep_edit.clear()
        self.agenda_edit.clear()
        self.closeout_edit.clear()
        self.name_edit.setFocus()

    def _lines(self, widget: QPlainTextEdit) -> list[str]:
        return [ln.strip() for ln in widget.toPlainText().splitlines() if ln.strip()]

    def _save_template(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Save Template", "Template name is required.")
            return

        # Determine slug: use existing template's slug if one is selected
        row = self.template_list.currentRow()
        slug = self._templates[row].slug if 0 <= row < len(self._templates) else ""

        template = MeetingTemplate(
            name=name,
            slug=slug,
            default_duration_minutes=self.duration_spin.value(),
            appears_on_ics230_default=self.ics230_check.isChecked(),
            required_attendee_roles=self._lines(self.required_roles_edit),
            optional_attendee_roles=self._lines(self.optional_roles_edit),
            prep_checklist_items=self._lines(self.prep_edit),
            agenda_checklist_items=self._lines(self.agenda_edit),
            closeout_checklist_items=self._lines(self.closeout_edit),
        )
        self._repository.save_template(template)
        self._load_list()


# ── ICS-230 preview dialog ────────────────────────────────────────────────────

class _ICS230Dialog(QDialog):
    def __init__(self, service: MeetingsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ICS-230 — Meeting Schedule")
        self.setMinimumSize(560, 480)
        self._service = service

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.prepared_by_edit = QLineEdit()
        self.prepared_by_edit.setPlaceholderText("Name…")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        bar.addWidget(QLabel("Prepared by"))
        bar.addWidget(self.prepared_by_edit)
        bar.addWidget(refresh_btn)
        layout.addLayout(bar)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview)
        self._refresh()

    def _refresh(self) -> None:
        schedule = self._service.generate_ics230(prepared_by=self.prepared_by_edit.text().strip())
        self.preview.setPlainText(self._service.render_ics230_text(schedule))


# ── Main panel ────────────────────────────────────────────────────────────────

class MeetingsPanel(QWidget):
    def __init__(self, incident_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = MeetingsRepository(incident_id=incident_id)
        self.service = MeetingsService(self.repository)
        self.setObjectName("PlanningMeetingsPanel")
        self.setWindowTitle("Planning - Meetings")
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Meetings")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton("New Meeting…")
        new_btn.clicked.connect(self._open_new_meeting_dialog)
        templates_btn = QPushButton("Manage Templates…")
        templates_btn.clicked.connect(self._open_template_manager)
        ics230_btn = QPushButton("Print ICS-230")
        ics230_btn.clicked.connect(self._open_ics230)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_all)

        for btn in (new_btn, templates_btn, ics230_btn, refresh_btn):
            header.addWidget(btn)
        root.addLayout(header)

        self.schedule_table = QTableWidget(0, 8)
        self.schedule_table.setHorizontalHeaderLabels(
            ["Date", "Time", "Title", "Status", "Owner", "Location", "Checklist", "ICS-230"]
        )
        self.schedule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.schedule_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.schedule_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.itemDoubleClicked.connect(self._open_meeting_detail)
        root.addWidget(self.schedule_table)

    def refresh_all(self) -> None:
        self._load_schedule()

    def _load_schedule(self) -> None:
        meetings = self.repository.list_meetings()
        self.schedule_table.setRowCount(len(meetings))
        for row, meeting in enumerate(meetings):
            complete = total = 0
            if meeting.id is not None:
                complete, total = self.repository.checklist_progress(meeting.id)
            values = [
                meeting.meeting_date,
                f"{meeting.start_time}–{meeting.end_time}",
                meeting.title,
                meeting.status,
                meeting.owner,
                meeting.virtual_link or meeting.location,
                f"{complete}/{total}",
                "Yes" if meeting.show_on_ics230 else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, meeting.id)
                self.schedule_table.setItem(row, col, item)

    def _open_new_meeting_dialog(self) -> None:
        templates = self.repository.list_templates()
        dlg = _NewMeetingDialog(templates, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        try:
            self.service.create_meeting_from_template(
                data["slug"],
                meeting_date=data["meeting_date"],
                start_time=data["start_time"],
                location=data["location"],
                owner=data["owner"],
            )
        except Exception as exc:
            QMessageBox.warning(self, "New Meeting", str(exc))
            return
        self._load_schedule()

    def _open_meeting_detail(self, item: QTableWidgetItem) -> None:
        meeting_id = item.data(Qt.UserRole)
        if meeting_id is None:
            return
        dlg = _MeetingDetailWindow(int(meeting_id), self.repository, self.service, parent=self)
        dlg.exec()
        self._load_schedule()

    def _open_template_manager(self) -> None:
        dlg = _TemplateManagerWindow(self.repository, parent=self)
        dlg.exec()

    def _open_ics230(self) -> None:
        dlg = _ICS230Dialog(self.service, parent=self)
        dlg.exec()


def make_meetings_panel(incident_id: str | None = None, parent: QWidget | None = None) -> MeetingsPanel:
    return MeetingsPanel(incident_id=incident_id, parent=parent)


__all__ = ["MeetingsPanel", "make_meetings_panel"]
