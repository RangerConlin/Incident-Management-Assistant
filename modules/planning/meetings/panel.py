from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from utils.table_view_styles import apply_statusboard_table_behavior

logger = logging.getLogger(__name__)

_REMINDER_CHECK_INTERVAL_MS = 5 * 60_000
_REMINDER_SETTINGS_KEY = "planning/meetings/reminder_lead_minutes"
_REMINDER_LEAD_DEFAULT = 15

from .models import MeetingTemplate
from ..operational_periods.repository import OperationalPeriodRepository
from modules.common.models.ics_positions import IcsPosition, all_position_names, position_names_by_group
from .repository import MeetingsRepository
from .services import MeetingsService

_OP_TEMPLATE_SETTINGS_KEY = "planning/meetings/op_template_sets"


def _copy_op_template_sets(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {name: [dict(entry) for entry in entries] for name, entries in data.items()}


def _calculate_time_from_offset(anchor_time: str, offset_minutes: int) -> str:
    base = datetime.fromisoformat(f"2000-01-01T{anchor_time}")
    calculated = base + timedelta(minutes=offset_minutes)
    return calculated.time().isoformat(timespec="minutes")


def _load_operational_period_template_sets(settings: QSettings) -> dict[str, list[dict]]:
    raw = settings.value(_OP_TEMPLATE_SETTINGS_KEY)
    if isinstance(raw, dict) and raw:
        loaded: dict[str, list[dict]] = {}
        for set_name, entries in raw.items():
            if not isinstance(entries, list):
                continue
            normalized_entries: list[dict] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                template_name = str(entry.get("template_name") or "").strip()
                if not template_name:
                    continue
                selected = bool(entry.get("selected", True))
                start_time = str(entry.get("start_time") or "").strip()
                if not start_time:
                    start_time = _calculate_time_from_offset("07:00", int(entry.get("offset_minutes") or 0))
                normalized_entries.append(
                    {
                        "template_name": template_name,
                        "selected": selected,
                        "start_time": start_time,
                    }
                )
            if normalized_entries:
                loaded[str(set_name)] = normalized_entries
        if loaded:
            return loaded
    return MeetingsService.default_operational_period_template_sets()


def _save_operational_period_template_sets(settings: QSettings, data: dict[str, list[dict]]) -> None:
    settings.setValue(_OP_TEMPLATE_SETTINGS_KEY, _copy_op_template_sets(data))


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


class _OperationalPeriodTemplateDialog(QDialog):
    def __init__(
        self,
        period_repo: OperationalPeriodRepository,
        template_sets: dict[str, list[dict]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Operational Period Meeting Set")
        self.setMinimumWidth(420)
        self._period_repo = period_repo
        self._template_sets = _copy_op_template_sets(template_sets)
        self._result: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.set_combo = QComboBox()
        for set_name in self._template_sets:
            self.set_combo.addItem(set_name, set_name)
        self.set_combo.currentTextChanged.connect(self._refresh_included_meetings)

        self.period_combo = QComboBox()
        for period_id, label in self._period_repo.list_period_choices():
            self.period_combo.addItem(label, period_id)

        active_period = self._period_repo.get_active_period()
        if active_period is not None and active_period.id is not None:
            active_index = self.period_combo.findData(active_period.id)
            if active_index >= 0:
                self.period_combo.setCurrentIndex(active_index)
            default_date, default_time = self._period_start_defaults(active_period)
        else:
            default_date = date.today().isoformat()
            default_time = "07:00"

        self.date_edit = QLineEdit(default_date)
        self.time_edit = QLineEdit(default_time)
        self.time_edit.textChanged.connect(self._recalculate_display_times)
        self.location_edit = QLineEdit()
        self.owner_edit = QLineEdit()
        self.included_meetings = QTableWidget(0, 3)
        self.included_meetings.setHorizontalHeaderLabels(["Use", "Meeting", "Time"])
        apply_statusboard_table_behavior(self.included_meetings, stretch_last_section=False)
        self.included_meetings.setAlternatingRowColors(True)
        self.included_meetings.verticalHeader().setVisible(False)
        self.included_meetings.setColumnWidth(0, 56)
        self.included_meetings.setColumnWidth(1, 220)
        self.included_meetings.setColumnWidth(2, 90)
        self.included_meetings.setMinimumHeight(220)

        form.addRow("Meeting Set", self.set_combo)
        form.addRow("Operational Period", self.period_combo)
        form.addRow("First Meeting Date", self.date_edit)
        form.addRow("First Meeting Time", self.time_edit)
        form.addRow("Location", self.location_edit)
        form.addRow("Owner", self.owner_edit)
        layout.addLayout(form)
        layout.addWidget(QLabel("Meetings Included By Default"))
        layout.addWidget(self.included_meetings)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_included_meetings()

    @staticmethod
    def _period_start_defaults(period) -> tuple[str, str]:
        if period.start_time:
            normalized = period.start_time.strip().replace("Z", "+00:00")
            for candidate in (normalized, normalized.replace(" ", "T")):
                try:
                    parsed = datetime.fromisoformat(candidate)
                    return parsed.date().isoformat(), parsed.time().isoformat(timespec="minutes")
                except ValueError:
                    continue
        return date.today().isoformat(), "07:00"

    def _on_accept(self) -> None:
        period_id = self.period_combo.currentData()
        if period_id is None:
            QMessageBox.warning(self, "Operational Period Meeting Set", "Please select an operational period.")
            return
        self._result = {
            "entries": [
                self._entry_from_row(row)
                for row in range(self.included_meetings.rowCount())
            ],
            "operational_period_id": int(period_id),
            "meeting_date": self.date_edit.text().strip(),
            "anchor_time": self.time_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "owner": self.owner_edit.text().strip(),
        }
        self.accept()

    def result_data(self) -> dict | None:
        return self._result

    def _refresh_included_meetings(self) -> None:
        self.included_meetings.setRowCount(0)
        set_name = self.set_combo.currentText()
        anchor_time = self.time_edit.text().strip() or "07:00"
        for entry in self._template_sets.get(set_name, []):
            row = self.included_meetings.rowCount()
            self.included_meetings.insertRow(row)
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(enabled_item.flags() | Qt.ItemIsUserCheckable)
            enabled_item.setCheckState(Qt.Checked if bool(entry.get("selected", True)) else Qt.Unchecked)
            self.included_meetings.setItem(row, 0, enabled_item)
            self.included_meetings.setItem(
                row, 1, QTableWidgetItem(str(entry.get("template_name") or "").strip())
            )
            start_time = str(entry.get("start_time") or "").strip()
            if not start_time:
                start_time = anchor_time
            self.included_meetings.setItem(row, 2, QTableWidgetItem(start_time))

    def _entry_from_row(self, row: int) -> dict:
        use_item = self.included_meetings.item(row, 0)
        name_item = self.included_meetings.item(row, 1)
        time_item = self.included_meetings.item(row, 2)
        return {
            "selected": use_item is not None and use_item.checkState() == Qt.Checked,
            "template_name": name_item.text().strip() if name_item else "",
            "start_time": time_item.text().strip() if time_item else "",
        }

    def _recalculate_display_times(self) -> None:
        anchor_time = self.time_edit.text().strip()
        try:
            base_time = datetime.fromisoformat(f"2000-01-01T{anchor_time}")
        except ValueError:
            return
        entries = self._template_sets.get(self.set_combo.currentText(), [])
        if not entries:
            return
        previous_time: datetime | None = None
        for row, entry in enumerate(entries):
            item = self.included_meetings.item(row, 2)
            if item is None:
                continue
            if row == 0:
                calculated = base_time
            else:
                prior_entry = entries[row - 1]
                prior_time = str(prior_entry.get("start_time") or "").strip()
                current_time = str(entry.get("start_time") or "").strip()
                try:
                    prior_dt = datetime.fromisoformat(f"2000-01-01T{prior_time}")
                    current_dt = datetime.fromisoformat(f"2000-01-01T{current_time}")
                    gap_minutes = int((current_dt - prior_dt).total_seconds() / 60)
                except ValueError:
                    gap_minutes = 60
                calculated = (previous_time or base_time) + timedelta(minutes=gap_minutes)
            item.setText(calculated.time().isoformat(timespec="minutes"))
            previous_time = calculated


# ── Meeting detail window ─────────────────────────────────────────────────────

class _MeetingDetailWindow(QDialog):
    def __init__(self, meeting_id: int, repository: MeetingsRepository, service: MeetingsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resize(850, 640)
        self.setMinimumSize(700, 520)
        self._meeting_id = meeting_id
        self._repository = repository
        self._service = service
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        details_group = QGroupBox("Meeting Details")
        details_layout = QGridLayout(details_group)
        details_layout.setHorizontalSpacing(14)
        details_layout.setVerticalSpacing(4)
        self.title_value = QLabel()
        self.date_value = QLabel()
        self.time_value = QLabel()
        self.location_value = QLabel()
        self.owner_value = QLabel()
        self.title_value.setWordWrap(True)
        self.location_value.setWordWrap(True)
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Draft", "Scheduled", "Ready", "Completed", "Canceled"])
        self.show_ics230_check = QCheckBox("On ICS-230")
        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(96)
        save_btn.clicked.connect(self._save_detail)

        details_layout.addWidget(QLabel("Meeting"), 0, 0)
        details_layout.addWidget(self.title_value, 0, 1)
        details_layout.addWidget(QLabel("Date"), 0, 2)
        details_layout.addWidget(self.date_value, 0, 3)
        details_layout.addWidget(QLabel("Time"), 1, 0)
        details_layout.addWidget(self.time_value, 1, 1)
        details_layout.addWidget(QLabel("Owner"), 1, 2)
        details_layout.addWidget(self.owner_value, 1, 3)
        details_layout.addWidget(QLabel("Location"), 2, 0)
        details_layout.addWidget(self.location_value, 2, 1, 1, 3)
        details_layout.addWidget(QLabel("Status"), 3, 0)
        details_layout.addWidget(self.status_combo, 3, 1)
        details_layout.addWidget(self.show_ics230_check, 3, 2)
        details_layout.addWidget(save_btn, 3, 3, alignment=Qt.AlignRight)
        details_layout.setColumnStretch(1, 1)
        details_layout.setColumnStretch(3, 1)

        # Attendees group
        attendees_group = QGroupBox("Attendees")
        att_layout = QVBoxLayout(attendees_group)
        att_layout.setContentsMargins(6, 6, 6, 6)
        self.attendees_table = QTableWidget(0, 3)
        self.attendees_table.setHorizontalHeaderLabels(["Attendee", "Requirement", "Status"])
        apply_statusboard_table_behavior(self.attendees_table, stretch_last_section=True)
        self.attendees_table.setAlternatingRowColors(True)
        self.attendees_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.attendees_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.attendees_table.verticalHeader().setVisible(False)
        att_layout.addWidget(self.attendees_table)

        # Checklist group
        checklist_group = QGroupBox("Checklist")
        chk_layout = QVBoxLayout(checklist_group)
        chk_layout.setContentsMargins(6, 6, 6, 6)
        self.checklist_table = QTableWidget(0, 4)
        self.checklist_table.setHorizontalHeaderLabels(["Done", "N/A", "Group", "Item"])
        apply_statusboard_table_behavior(self.checklist_table, stretch_last_section=True)
        self.checklist_table.setColumnWidth(0, 48)
        self.checklist_table.setColumnWidth(1, 48)
        self.checklist_table.setAlternatingRowColors(True)
        self.checklist_table.verticalHeader().setVisible(False)
        self.checklist_table.itemChanged.connect(self._checklist_item_changed)
        chk_layout.addWidget(self.checklist_table)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(attendees_group)
        splitter.addWidget(checklist_group)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # Notes group
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setContentsMargins(6, 6, 6, 6)
        note_bar = QHBoxLayout()
        self.note_category_combo = QComboBox()
        self.note_category_combo.addItems(
            ["Comment", "Decision", "Action Item", "Issue/Risk", "Resource Request",
             "Safety Item", "Assignment", "Notable Event", "Follow-Up"]
        )
        self.note_text_edit = QLineEdit()
        self.note_text_edit.setPlaceholderText("Add a note…")
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
        apply_statusboard_table_behavior(self.notes_table, stretch_last_section=True)
        self.notes_table.setAlternatingRowColors(True)
        self.notes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.notes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.notes_table.verticalHeader().setVisible(False)
        notes_layout.addLayout(note_bar)
        notes_layout.addWidget(self.notes_table)

        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.addWidget(details_group)
        vertical_splitter.addWidget(splitter)
        vertical_splitter.addWidget(notes_group)
        vertical_splitter.setChildrenCollapsible(False)
        vertical_splitter.setStretchFactor(0, 0)
        vertical_splitter.setStretchFactor(1, 1)
        vertical_splitter.setStretchFactor(2, 1)
        vertical_splitter.setSizes([130, 280, 180])
        root.addWidget(vertical_splitter)

    def _load(self) -> None:
        meeting = self._repository.get_meeting(self._meeting_id)
        self.setWindowTitle(f"{meeting.title} — {meeting.meeting_date}")
        self.title_value.setText(meeting.title)
        self.date_value.setText(meeting.meeting_date)
        self.time_value.setText(f"{meeting.start_time} - {meeting.end_time}")
        self.location_value.setText(meeting.virtual_link or meeting.location or "Not set")
        self.owner_value.setText(meeting.owner or "Not set")
        self.status_combo.setCurrentText(meeting.status.title())
        self.show_ics230_check.setChecked(meeting.show_on_ics230)

        attendees = self._repository.list_attendees(meeting.id or 0)
        self.attendees_table.setRowCount(len(attendees))
        for row, att in enumerate(attendees):
            attendee_item = QTableWidgetItem(att.display_name)
            attendee_item.setData(Qt.UserRole, att.id)
            self.attendees_table.setItem(row, 0, attendee_item)
            self.attendees_table.setItem(row, 1, QTableWidgetItem(att.requirement_status.title()))

            status_combo = QComboBox()
            status_combo.addItems(["Invited", "Confirmed", "Tentative", "Declined", "Attended"])
            status_combo.setCurrentText(att.attendance_status.title())
            status_combo.currentTextChanged.connect(
                lambda value, attendee_id=att.id: self._update_attendee_status(attendee_id, value)
            )
            self.attendees_table.setCellWidget(row, 2, status_combo)

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
            for col, val in enumerate(
                [note.category.title(), note.text, note.author, note.routing_status.title()]
            ):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, note.id)
                self.notes_table.setItem(row, col, item)

    def _save_detail(self) -> None:
        self._repository.update_meeting(
            self._meeting_id,
            {
                "status": self.status_combo.currentText().lower(),
                "show_on_ics230": self.show_ics230_check.isChecked(),
            },
        )
        self._load()

    def _checklist_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() not in (0, 1):
            return
        item_id = item.data(Qt.UserRole)
        if item_id is None:
            return
        field = "is_complete" if item.column() == 0 else "is_not_applicable"
        self._repository.update_checklist_item_for_meeting(
            self._meeting_id,
            int(item_id),
            {field: item.checkState() == Qt.Checked},
        )

    def _update_attendee_status(self, attendee_id: int | None, value: str) -> None:
        if attendee_id is None:
            return
        self._repository.update_attendee(
            self._meeting_id,
            int(attendee_id),
            {"attendance_status": value.lower()},
        )

    def _add_note(self) -> None:
        text = self.note_text_edit.text().strip()
        if not text:
            return
        self._service.add_structured_note(
            self._meeting_id,
            category=self.note_category_combo.currentText().lower(),
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
        self._service.route_note_to_log(int(note_id), meeting_id=self._meeting_id, entered_by=meeting.owner)
        self._load()


# ── Attendee role picker dialog ──────────────────────────────────────────────

class _AttendeeRolePickerDialog(QDialog):
    """Modal dialog for selecting required/optional attendee roles from a
    canonical ICS position catalog.

    Displays all known positions grouped by section, each with checkboxes
    for Required and Optional. A position cannot be both — checking one
    column unchecks the other.
    """

    def __init__(
        self,
        current_required: list[str],
        current_optional: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Attendee Roles")
        self.setMinimumSize(520, 480)
        self.setModal(True)

        # Track which positions are checked and in which column
        self._required: set[str] = set(current_required)
        self._optional: set[str] = set(current_optional)
        self._positions_by_group = position_names_by_group()
        self._all_groups = list(self._positions_by_group.keys())
        self._all_position_names = all_position_names()

        layout = QVBoxLayout(self)

        # ── Filter bar ────────────────────────────────────────────────────
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter positions…")
        self.filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_edit)

        # ── Table ─────────────────────────────────────────────────────────
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Position", "Required", "Optional"])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        layout.addWidget(self.table)

        # ── Buttons ───────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_table()

    # ── Table building ──────────────────────────────────────────────────

    def _populate_table(self, filter_text: str = "") -> None:
        """Fill the table with all positions, optionally filtered."""
        self.table.setRowCount(0)
        for group_name, positions in self._positions_by_group.items():
            sorted_positions = sorted(positions)
            # Add group header row
            group_row = self.table.rowCount()
            self.table.insertRow(group_row)
            group_item = QTableWidgetItem(f"  {group_name}")
            group_font = group_item.font()
            group_font.setBold(True)
            group_item.setFont(group_font)
            group_item.setFlags(group_item.flags() & ~Qt.ItemIsSelectable)
            self.table.setItem(group_row, 0, group_item)
            self.table.setSpan(group_row, 0, 1, 3)
            # Store metadata so we know this is a group row
            group_item.setData(Qt.UserRole, "__group__")

            for pos_name in sorted_positions:
                if filter_text and filter_text.lower() not in pos_name.lower():
                    continue
                row = self.table.rowCount()
                self.table.insertRow(row)

                # Position name
                name_item = QTableWidgetItem(pos_name)
                name_item.setData(Qt.UserRole, pos_name)
                self.table.setItem(row, 0, name_item)

                # Required checkbox
                required_item = QTableWidgetItem()
                required_item.setFlags(required_item.flags() | Qt.ItemIsUserCheckable)
                required_item.setCheckState(Qt.Checked if pos_name in self._required else Qt.Unchecked)
                required_item.setData(Qt.UserRole, pos_name)
                self.table.setItem(row, 1, required_item)

                # Optional checkbox
                optional_item = QTableWidgetItem()
                optional_item.setFlags(optional_item.flags() | Qt.ItemIsUserCheckable)
                optional_item.setCheckState(Qt.Checked if pos_name in self._optional else Qt.Unchecked)
                optional_item.setData(Qt.UserRole, pos_name)
                self.table.setItem(row, 2, optional_item)

        # Connect item changed signal for mutual exclusion
        self.table.itemChanged.connect(self._on_item_changed)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() not in (1, 2):
            return
        pos_name = item.data(Qt.UserRole)
        if not pos_name or pos_name == "__group__":
            return
        is_checked = item.checkState() == Qt.Checked
        if not is_checked:
            # Just unchecking — remove from the appropriate set
            if item.column() == 1:
                self._required.discard(pos_name)
            else:
                self._optional.discard(pos_name)
            return

        # Preventing the signal from re-entering
        self.table.blockSignals(True)

        # Uncheck the other column for this position
        if item.column() == 1:
            # Checked "Required" — uncheck "Optional"
            self._required.add(pos_name)
            self._optional.discard(pos_name)
            other = self.table.item(item.row(), 2)
            if other is not None:
                other.setCheckState(Qt.Unchecked)
        else:
            # Checked "Optional" — uncheck "Required"
            self._optional.add(pos_name)
            self._required.discard(pos_name)
            other = self.table.item(item.row(), 1)
            if other is not None:
                other.setCheckState(Qt.Unchecked)

        self.table.blockSignals(False)

    def _apply_filter(self, text: str) -> None:
        self.table.itemChanged.disconnect(self._on_item_changed)
        self._populate_table(filter_text=text)

    def _on_accept(self) -> None:
        self.accept()

    # ── Result ──────────────────────────────────────────────────────────

    def selected_roles(self) -> tuple[list[str], list[str]]:
        """Return (required_roles, optional_roles) as sorted lists."""
        return sorted(self._required), sorted(self._optional)


# ── Template manager window ───────────────────────────────────────────────────

class _TemplateManagerWindow(QDialog):
    def __init__(self, repository: MeetingsRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Meeting Templates")
        self.setMinimumSize(760, 560)
        self._repository = repository
        self._settings = QSettings()
        self._templates: list[MeetingTemplate] = []
        self._required_roles: list[str] = []
        self._optional_roles: list[str] = []
        self._op_template_sets: dict[str, list[dict]] = _load_operational_period_template_sets(self._settings)
        self._build_ui()
        self._load_list()
        self._load_op_template_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        meeting_tab = QWidget()
        op_tab = QWidget()
        tabs.addTab(meeting_tab, "Meeting Templates")
        tabs.addTab(op_tab, "Operational Period Templates")

        meeting_root = QHBoxLayout(meeting_tab)

        # Left: template list + New button
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self._on_selection_changed)
        new_btn = QPushButton("New Template")
        new_btn.clicked.connect(self._new_template)
        delete_btn = QPushButton("Delete Template")
        delete_btn.clicked.connect(self._delete_template)
        left_layout.addWidget(QLabel("Templates"))
        left_layout.addWidget(self.template_list, 1)
        left_layout.addWidget(new_btn)
        left_layout.addWidget(delete_btn)
        left.setFixedWidth(200)
        meeting_root.addWidget(left)

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
        roles_layout = QVBoxLayout(roles_group)
        roles_layout.setSpacing(6)
        self.roles_summary = QLabel("No roles configured")
        self.roles_summary.setWordWrap(True)
        self.configure_roles_btn = QPushButton("Configure Attendee Roles…")
        self.configure_roles_btn.clicked.connect(self._open_role_picker)
        roles_layout.addWidget(self.roles_summary)
        roles_layout.addWidget(self.configure_roles_btn)
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
        meeting_root.addWidget(scroll, 1)

        op_root = QHBoxLayout(op_tab)
        op_left = QWidget()
        op_left_layout = QVBoxLayout(op_left)
        op_left_layout.setContentsMargins(0, 0, 0, 0)
        op_left_layout.setSpacing(6)
        self.op_template_list = QListWidget()
        self.op_template_list.currentRowChanged.connect(self._on_op_template_selection_changed)
        new_op_btn = QPushButton("New OP Template")
        new_op_btn.clicked.connect(self._new_op_template)
        delete_op_btn = QPushButton("Delete OP Template")
        delete_op_btn.clicked.connect(self._delete_op_template)
        op_left_layout.addWidget(QLabel("Operational Period Templates"))
        op_left_layout.addWidget(self.op_template_list, 1)
        op_left_layout.addWidget(new_op_btn)
        op_left_layout.addWidget(delete_op_btn)
        op_left.setFixedWidth(230)
        op_root.addWidget(op_left)

        op_editor = QWidget()
        op_editor_layout = QVBoxLayout(op_editor)
        op_editor_layout.setContentsMargins(8, 0, 0, 0)
        op_editor_layout.setSpacing(10)

        op_details_group = QGroupBox("Template Details")
        op_details_form = QFormLayout(op_details_group)
        self.op_template_name_edit = QLineEdit()
        self.op_anchor_time_edit = QLineEdit("07:00")
        op_details_form.addRow("Name", self.op_template_name_edit)
        op_details_form.addRow("First Meeting Time", self.op_anchor_time_edit)
        op_editor_layout.addWidget(op_details_group)

        included_group = QGroupBox("Included Meetings")
        included_layout = QVBoxLayout(included_group)
        self.op_meetings_table = QTableWidget(0, 3)
        self.op_meetings_table.setHorizontalHeaderLabels(["Use", "Meeting Template", "Time"])
        apply_statusboard_table_behavior(self.op_meetings_table, stretch_last_section=False)
        self.op_meetings_table.setAlternatingRowColors(True)
        self.op_meetings_table.verticalHeader().setVisible(False)
        self.op_meetings_table.setColumnWidth(0, 56)
        self.op_meetings_table.setColumnWidth(1, 260)
        self.op_meetings_table.setColumnWidth(2, 90)
        included_layout.addWidget(self.op_meetings_table)
        included_buttons = QHBoxLayout()
        add_meeting_btn = QPushButton("Add Meeting")
        add_meeting_btn.clicked.connect(self._add_op_template_meeting)
        remove_meeting_btn = QPushButton("Remove Selected")
        remove_meeting_btn.clicked.connect(self._remove_op_template_meeting)
        included_buttons.addWidget(add_meeting_btn)
        included_buttons.addWidget(remove_meeting_btn)
        included_buttons.addStretch()
        included_layout.addLayout(included_buttons)
        op_editor_layout.addWidget(included_group, 1)

        save_op_btn = QPushButton("Save OP Template")
        save_op_btn.clicked.connect(self._save_op_template)
        op_editor_layout.addWidget(save_op_btn)
        op_root.addWidget(op_editor, 1)

        self._set_form_enabled(False)
        self._set_op_form_enabled(False)

    def _set_form_enabled(self, enabled: bool) -> None:
        for w in (self.name_edit, self.duration_spin, self.ics230_check,
                  self.roles_summary, self.configure_roles_btn,
                  self.prep_edit, self.agenda_edit, self.closeout_edit):
            w.setEnabled(enabled)

    def _load_list(self) -> None:
        self._templates = self._repository.list_templates(active_only=False)
        self.template_list.clear()
        for t in self._templates:
            suffix = "" if t.active else " (Inactive)"
            self.template_list.addItem(f"{t.name}{suffix}")

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._templates):
            self._set_form_enabled(False)
            return
        t = self._templates[row]
        self._set_form_enabled(True)
        self.name_edit.setText(t.name)
        self.duration_spin.setValue(t.default_duration_minutes)
        self.ics230_check.setChecked(t.appears_on_ics230_default)
        self._required_roles = list(t.required_attendee_roles)
        self._optional_roles = list(t.optional_attendee_roles)
        self._update_roles_summary()
        self.prep_edit.setPlainText("\n".join(t.prep_checklist_items))
        self.agenda_edit.setPlainText("\n".join(t.agenda_checklist_items))
        self.closeout_edit.setPlainText("\n".join(t.closeout_checklist_items))

    def _new_template(self) -> None:
        self._set_form_enabled(True)
        self.template_list.clearSelection()
        self.name_edit.clear()
        self.duration_spin.setValue(60)
        self.ics230_check.setChecked(True)
        self._required_roles = []
        self._optional_roles = []
        self._update_roles_summary()
        self.prep_edit.clear()
        self.agenda_edit.clear()
        self.closeout_edit.clear()
        self.name_edit.setFocus()

    def _delete_template(self) -> None:
        row = self.template_list.currentRow()
        if row < 0 or row >= len(self._templates):
            return
        template = self._templates[row]
        self._repository.save_template(
            MeetingTemplate(
                name=template.name,
                slug=template.slug,
                default_duration_minutes=template.default_duration_minutes,
                agenda_sections=list(template.agenda_sections),
                required_attendee_roles=list(template.required_attendee_roles),
                optional_attendee_roles=list(template.optional_attendee_roles),
                prep_checklist_items=list(template.prep_checklist_items),
                agenda_checklist_items=list(template.agenda_checklist_items),
                closeout_checklist_items=list(template.closeout_checklist_items),
                appears_on_ics230_default=template.appears_on_ics230_default,
                active=False,
            )
        )
        self._load_list()
        self.template_list.clearSelection()
        self._set_form_enabled(False)

    def _update_roles_summary(self) -> None:
        parts = []
        if self._required_roles:
            parts.append(f"{len(self._required_roles)} required")
        if self._optional_roles:
            parts.append(f"{len(self._optional_roles)} optional")
        if parts:
            self.roles_summary.setText(f"{', '.join(parts)} role(s) selected")
        else:
            self.roles_summary.setText("No roles configured")

    def _open_role_picker(self) -> None:
        dlg = _AttendeeRolePickerDialog(self._required_roles, self._optional_roles, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        self._required_roles, self._optional_roles = dlg.selected_roles()
        self._update_roles_summary()

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
            required_attendee_roles=list(self._required_roles),
            optional_attendee_roles=list(self._optional_roles),
            prep_checklist_items=[ln.strip() for ln in self.prep_edit.toPlainText().splitlines() if ln.strip()],
            agenda_checklist_items=[ln.strip() for ln in self.agenda_edit.toPlainText().splitlines() if ln.strip()],
            closeout_checklist_items=[ln.strip() for ln in self.closeout_edit.toPlainText().splitlines() if ln.strip()],
        )
        self._repository.save_template(template)
        self._load_list()

    def _set_op_form_enabled(self, enabled: bool) -> None:
        for widget in (self.op_template_name_edit, self.op_anchor_time_edit, self.op_meetings_table):
            widget.setEnabled(enabled)

    def _load_op_template_list(self) -> None:
        self.op_template_list.clear()
        for name in self._op_template_sets:
            self.op_template_list.addItem(name)

    def _on_op_template_selection_changed(self, row: int) -> None:
        names = list(self._op_template_sets.keys())
        if row < 0 or row >= len(names):
            self._set_op_form_enabled(False)
            self.op_template_name_edit.clear()
            self.op_meetings_table.setRowCount(0)
            return
        set_name = names[row]
        self._set_op_form_enabled(True)
        self.op_template_name_edit.setText(set_name)
        entries = self._op_template_sets[set_name]
        self.op_anchor_time_edit.setText(str(entries[0].get("start_time") or "07:00") if entries else "07:00")
        available_templates = [template.name for template in self._repository.list_templates(active_only=False)]
        self.op_meetings_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(enabled_item.flags() | Qt.ItemIsUserCheckable)
            enabled_item.setCheckState(Qt.Checked if bool(entry.get("selected", True)) else Qt.Unchecked)
            self.op_meetings_table.setItem(row_index, 0, enabled_item)
            combo = QComboBox()
            combo.addItems(available_templates)
            combo.setEditable(True)
            combo.setCurrentText(str(entry.get("template_name") or ""))
            self.op_meetings_table.setCellWidget(row_index, 1, combo)
            self.op_meetings_table.setItem(
                row_index,
                2,
                QTableWidgetItem(str(entry.get("start_time") or "")),
            )

    def _new_op_template(self) -> None:
        self.op_template_list.clearSelection()
        self._set_op_form_enabled(True)
        self.op_template_name_edit.setText("New Operational Period Template")
        self.op_anchor_time_edit.setText("07:00")
        self.op_meetings_table.setRowCount(0)
        self._add_op_template_meeting()

    def _delete_op_template(self) -> None:
        row = self.op_template_list.currentRow()
        names = list(self._op_template_sets.keys())
        if row < 0 or row >= len(names):
            return
        del self._op_template_sets[names[row]]
        _save_operational_period_template_sets(self._settings, self._op_template_sets)
        self._load_op_template_list()
        self.op_template_list.clearSelection()
        self._on_op_template_selection_changed(-1)

    def _add_op_template_meeting(self) -> None:
        row = self.op_meetings_table.rowCount()
        self.op_meetings_table.insertRow(row)
        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(enabled_item.flags() | Qt.ItemIsUserCheckable)
        enabled_item.setCheckState(Qt.Checked)
        self.op_meetings_table.setItem(row, 0, enabled_item)
        combo = QComboBox()
        combo.addItems([template.name for template in self._repository.list_templates(active_only=False)])
        combo.setEditable(True)
        self.op_meetings_table.setCellWidget(row, 1, combo)
        self.op_meetings_table.setItem(row, 2, QTableWidgetItem(self._default_op_meeting_time(row)))

    def _remove_op_template_meeting(self) -> None:
        row = self.op_meetings_table.currentRow()
        if row >= 0:
            self.op_meetings_table.removeRow(row)

    def _save_op_template(self) -> None:
        set_name = self.op_template_name_edit.text().strip()
        if not set_name:
            QMessageBox.warning(self, "Save OP Template", "Template name is required.")
            return
        entries: list[dict] = []
        for row in range(self.op_meetings_table.rowCount()):
            enabled_item = self.op_meetings_table.item(row, 0)
            combo = self.op_meetings_table.cellWidget(row, 1)
            template_name = combo.currentText().strip() if isinstance(combo, QComboBox) else ""
            if not template_name:
                continue
            time_item = self.op_meetings_table.item(row, 2)
            meeting_time = time_item.text().strip() if time_item else ""
            try:
                datetime.strptime(meeting_time, "%H:%M")
            except ValueError:
                QMessageBox.warning(self, "Save OP Template", "Meeting times must use HH:MM.")
                return
            entries.append(
                {
                    "selected": enabled_item is not None and enabled_item.checkState() == Qt.Checked,
                    "template_name": template_name,
                    "start_time": meeting_time,
                }
            )
        if not entries:
            QMessageBox.warning(self, "Save OP Template", "Add at least one meeting to the template.")
            return

        existing_names = list(self._op_template_sets.keys())
        selected_row = self.op_template_list.currentRow()
        if 0 <= selected_row < len(existing_names):
            previous_name = existing_names[selected_row]
            if previous_name != set_name and previous_name in self._op_template_sets:
                del self._op_template_sets[previous_name]
        self._op_template_sets[set_name] = entries
        _save_operational_period_template_sets(self._settings, self._op_template_sets)
        self._load_op_template_list()
        matching_items = self.op_template_list.findItems(set_name, Qt.MatchExactly)
        if matching_items:
            self.op_template_list.setCurrentItem(matching_items[0])

    def _default_op_meeting_time(self, row: int) -> str:
        anchor_time = self.op_anchor_time_edit.text().strip() or "07:00"
        try:
            base = datetime.fromisoformat(f"2000-01-01T{anchor_time}")
        except ValueError:
            base = datetime.fromisoformat("2000-01-01T07:00")
        return (base + timedelta(minutes=row * 60)).time().isoformat(timespec="minutes")


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
        self._notified_meeting_ids: set[int] = set()
        self._settings = QSettings()
        self._op_template_sets = _load_operational_period_template_sets(self._settings)
        self._build_ui()
        self.refresh_all()

        self._reminder_timer = QTimer(self)
        self._reminder_timer.setInterval(_REMINDER_CHECK_INTERVAL_MS)
        self._reminder_timer.timeout.connect(self._check_upcoming_meeting_reminders)
        self._reminder_timer.start()
        self._check_upcoming_meeting_reminders()

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
        op_set_btn = QPushButton("Add OP Meeting Set…")
        op_set_btn.clicked.connect(self._open_operational_period_template_dialog)
        ics230_btn = QPushButton("Print ICS-230")
        ics230_btn.clicked.connect(self._open_ics230)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_all)

        for btn in (new_btn, templates_btn, op_set_btn, ics230_btn, refresh_btn):
            header.addWidget(btn)
        root.addLayout(header)

        reminder_bar = QHBoxLayout()
        reminder_bar.addStretch()
        reminder_bar.addWidget(QLabel("Remind attendees"))
        self.reminder_lead_spin = QSpinBox()
        self.reminder_lead_spin.setRange(0, 180)
        self.reminder_lead_spin.setSuffix(" min before start")
        self.reminder_lead_spin.setValue(
            int(self._settings.value(_REMINDER_SETTINGS_KEY, _REMINDER_LEAD_DEFAULT))
        )
        self.reminder_lead_spin.valueChanged.connect(self._on_reminder_lead_changed)
        reminder_bar.addWidget(self.reminder_lead_spin)
        root.addLayout(reminder_bar)

        self.schedule_table = QTableWidget(0, 8)
        self.schedule_table.setHorizontalHeaderLabels(
            ["Date", "Time", "Title", "Status", "Owner", "Location", "Checklist", "ICS-230"]
        )
        apply_statusboard_table_behavior(self.schedule_table, stretch_last_section=False)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.setColumnWidth(0, 96)
        self.schedule_table.setColumnWidth(1, 112)
        self.schedule_table.setColumnWidth(2, 220)
        self.schedule_table.setColumnWidth(3, 96)
        self.schedule_table.setColumnWidth(4, 120)
        self.schedule_table.setColumnWidth(5, 180)
        self.schedule_table.setColumnWidth(6, 80)
        self.schedule_table.setColumnWidth(7, 64)
        self.schedule_table.setSortingEnabled(True)
        self.schedule_table.itemDoubleClicked.connect(self._open_meeting_detail)
        root.addWidget(self.schedule_table)

    def refresh_all(self) -> None:
        self._load_schedule()

    def _load_schedule(self) -> None:
        self.schedule_table.setSortingEnabled(False)
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
                meeting.status.title(),
                meeting.owner or "",
                meeting.virtual_link or meeting.location or "",
                f"{complete}/{total}",
                "Yes" if meeting.show_on_ics230 else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, meeting.id)
                self.schedule_table.setItem(row, col, item)
        self.schedule_table.setSortingEnabled(True)

    def _on_reminder_lead_changed(self, minutes: int) -> None:
        self._settings.setValue(_REMINDER_SETTINGS_KEY, minutes)
        # Lead time changed — re-evaluate so a longer window can re-arm reminders.
        self._notified_meeting_ids.clear()

    def _check_upcoming_meeting_reminders(self) -> None:
        lead_minutes = self.reminder_lead_spin.value()
        if lead_minutes <= 0:
            return
        now = datetime.now()
        try:
            meetings = self.repository.list_meetings(include_canceled=False)
        except Exception:
            logger.exception("Failed to list meetings for reminder check")
            return
        for meeting in meetings:
            if meeting.id is None or meeting.id in self._notified_meeting_ids:
                continue
            if meeting.status in ("canceled", "completed"):
                continue
            start = self._parse_meeting_start(meeting.meeting_date, meeting.start_time)
            if start is None:
                continue
            minutes_until = (start - now).total_seconds() / 60
            if minutes_until < 0 or minutes_until > lead_minutes:
                continue
            self._notified_meeting_ids.add(meeting.id)
            if self._current_user_is_attendee(meeting.id):
                self._send_meeting_reminder(meeting)

    @staticmethod
    def _parse_meeting_start(meeting_date: str, start_time: str) -> datetime | None:
        try:
            return datetime.strptime(f"{meeting_date} {start_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _current_user_is_attendee(self, meeting_id: int) -> bool:
        from utils.state import AppState

        active_user_id = str(AppState.get_active_user_id() or "").strip()
        if not active_user_id:
            return False
        try:
            attendees = self.repository.list_attendees(meeting_id)
        except Exception:
            logger.exception("Failed to list attendees for meeting %s", meeting_id)
            return False
        for attendee in attendees:
            if attendee.attendee_type == "role" and attendee.role:
                if self._resolve_role_actor_id(attendee.role) == active_user_id:
                    return True
            elif attendee.display_name.strip().lower() == active_user_id.lower():
                return True
        return False

    def _resolve_role_actor_id(self, role: str) -> str | None:
        try:
            from modules.command.incident_organization.controller import (
                IncidentOrganizationController,
            )

            org = IncidentOrganizationController(self.repository.incident_id)
            positions = org.list_positions()
            match = next((p for p in positions if p.title == role and p.status == "active"), None)
            if match is None:
                return None
            assignments = org.list_assignments(match.id, active_only=True)
            return str(assignments[0].personnel_id) if assignments else None
        except Exception:
            logger.exception("Failed to resolve role %r to an actor", role)
            return None

    def _send_meeting_reminder(self, meeting) -> None:
        from notifications.models import Notification
        from notifications.services import get_notifier

        get_notifier().notify(
            Notification(
                title="Upcoming meeting",
                message=f"{meeting.title} starts at {meeting.start_time} ({meeting.location or meeting.virtual_link}).",
                severity="priority",
                category="planning",
                source="Meetings",
                entity_type="meeting",
                entity_id=str(meeting.id),
            )
        )

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
        self._op_template_sets = _load_operational_period_template_sets(self._settings)

    def _open_operational_period_template_dialog(self) -> None:
        try:
            period_repo = OperationalPeriodRepository(self.repository.incident_id)
        except Exception as exc:
            QMessageBox.warning(self, "Operational Period Meeting Set", str(exc))
            return
        dlg = _OperationalPeriodTemplateDialog(period_repo, self._op_template_sets, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.result_data()
        if not data:
            return
        try:
            created = self.service.create_operational_period_template_set(**data)
        except Exception as exc:
            QMessageBox.warning(self, "Operational Period Meeting Set", str(exc))
            return
        self._load_schedule()
        QMessageBox.information(
            self,
            "Operational Period Meeting Set",
            f"Created {len(created)} meetings for the selected operational period.",
        )

    def _open_ics230(self) -> None:
        dlg = _ICS230Dialog(self.service, parent=self)
        dlg.exec()


def make_meetings_panel(incident_id: str | None = None, parent: QWidget | None = None) -> MeetingsPanel:
    return MeetingsPanel(incident_id=incident_id, parent=parent)


__all__ = ["MeetingsPanel", "make_meetings_panel"]
