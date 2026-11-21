"""Operational Timeline — Planned Events Toolkit (Phase 1C).

A chronological run-of-show for one event date: each activity shown with
planned vs. actual timing, responsibility, location, status, and a
computed (never stored) delay/attention indicator. Reads and mutates
through the same `ScheduleController` the Phase 1A/1B activity list uses —
this file adds no new scheduling model, validation, or status-changing
logic of its own.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import services
from .reminder_dialog import ReminderDialog
from .schedule_dialogs import ScheduleItemDialog, prompt_cancellation_reason, prompt_delay_reason
from .schedule_time_utils import friendly_dt, friendly_time, is_overdue, parse_dt, planned_vs_actual_text
from ..record_resolvers import resolve_gis_feature, resolve_meeting
from ..records import ScheduledItem
from ..schedule_controller import ScheduleController
from utils.styles import event_schedule_status_colors, subscribe_theme

_ALL = "All"
STATUSES = ("Scheduled", "In Progress", "Completed", "Delayed", "Cancelled")
_OPEN_STATUSES = ("Scheduled", "In Progress", "Delayed")

_COLUMNS = (
    "Time", "Activity", "Type", "Responsible", "Location", "Status",
    "Actual Start", "Actual End", "Planned vs. Actual", "Attention",
)
_NOW_MARKER_TEXT = "— NOW —"


def _item_date(item: ScheduledItem) -> date | None:
    dt = parse_dt(item.starts_at)
    return dt.date() if dt else None


def _pick_default_date(items: list[ScheduledItem], *, today: date) -> date:
    """"Most relevant" date per the brief: today if anything's scheduled
    today, else the nearest upcoming activity's date, else the most recent
    past activity's date, else just today."""
    dates = sorted({d for d in (_item_date(item) for item in items) if d is not None})
    if not dates:
        return today
    if today in dates:
        return today
    upcoming = [d for d in dates if d > today]
    if upcoming:
        return min(upcoming)
    return max(dates)


class ActivityDetailDialog(QDialog):
    """Read-oriented detail panel with the five event-day actions + Edit.

    Every action here calls the shared `ScheduleController` -- the same
    validated backend endpoints Phase 1A/1B built -- never a local status
    change.
    """

    def __init__(self, item: ScheduledItem, controller: ScheduleController, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self.controller = controller
        self.setWindowTitle(item.name or "Activity")
        self.setMinimumWidth(480)
        self._build_ui()
        self.controller.statusMessage.connect(self._set_status)
        self._refresh_related_records()
        self._refresh_reminders()

    def _set_status(self, message: str, is_error: bool) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(f"color: {'#b00020' if is_error else '#375a2b'};")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        item = self.item

        form.addRow("Activity Type", QLabel(item.kind))
        form.addRow("Status", QLabel(item.status))
        form.addRow("Planned Start", QLabel(friendly_dt(item.starts_at)))
        form.addRow("Planned End", QLabel(friendly_dt(item.ends_at)))
        form.addRow("Actual Start", QLabel(friendly_dt(item.actual_start_at) or "—"))
        form.addRow("Actual End", QLabel(friendly_dt(item.actual_end_at) or "—"))
        pva = planned_vs_actual_text(item.starts_at, item.ends_at, item.actual_start_at, item.actual_end_at)
        form.addRow("Planned vs. Actual", QLabel(pva or "—"))
        form.addRow("Responsible", QLabel(item.assigned_to or "—"))
        form.addRow("Location", QLabel(item.location or "—"))
        if item.meeting_id:
            form.addRow("Linked Meeting", QLabel(item.meeting_id))
        if item.status == "Delayed" and item.delay_reason:
            form.addRow("Delay Reason", QLabel(item.delay_reason))
        if item.status == "Cancelled" and item.cancellation_reason:
            form.addRow("Cancellation Reason", QLabel(item.cancellation_reason))
        notes_label = QTextEdit(item.notes)
        notes_label.setReadOnly(True)
        notes_label.setFixedHeight(60)
        form.addRow("Notes", notes_label)
        layout.addLayout(form)

        layout.addWidget(self._build_related_records_group())
        layout.addWidget(self._build_reminders_group())

        actions = QHBoxLayout()
        self._edit_btn = QPushButton("Edit")
        self._start_btn = QPushButton("Start")
        self._resume_btn = QPushButton("Resume")
        self._complete_btn = QPushButton("Complete")
        self._delay_btn = QPushButton("Delay")
        self._cancel_btn = QPushButton("Cancel")
        self._correct_btn = QPushButton("Correct...")
        self._edit_btn.clicked.connect(self._edit)
        self._start_btn.clicked.connect(lambda: self._act(self.controller.start))
        self._resume_btn.clicked.connect(lambda: self._act(self.controller.resume))
        self._complete_btn.clicked.connect(lambda: self._act(self.controller.complete))
        self._delay_btn.clicked.connect(self._delay)
        self._cancel_btn.clicked.connect(self._cancel)
        self._correct_btn.clicked.connect(self._correct)
        self._edit_btn.setEnabled(item.status not in ("Completed", "Cancelled"))
        self._start_btn.setEnabled(item.status == "Scheduled")
        self._resume_btn.setEnabled(item.status == "Delayed")
        # Complete now requires In Progress -- resume a Delayed activity
        # first (Phase 1E: Delayed can no longer skip straight to Completed).
        self._complete_btn.setEnabled(item.status == "In Progress")
        self._delay_btn.setEnabled(item.status in ("Scheduled", "In Progress"))
        self._cancel_btn.setEnabled(item.status in ("Scheduled", "In Progress", "Delayed"))
        for button in (self._edit_btn, self._start_btn, self._resume_btn, self._complete_btn, self._delay_btn, self._cancel_btn, self._correct_btn):
            actions.addWidget(button)
        layout.addLayout(actions)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    # -- Related Records (Meeting / Quick Assignment / GIS) ---------------

    def _build_related_records_group(self) -> QGroupBox:
        group = QGroupBox("Related Records")
        form = QFormLayout(group)

        meeting_row = QHBoxLayout()
        self._meeting_label = QLabel("—")
        self._meeting_open_btn = QPushButton("Open")
        self._meeting_unlink_btn = QPushButton("Unlink")
        self._meeting_open_btn.clicked.connect(self._open_meeting)
        self._meeting_unlink_btn.clicked.connect(self._unlink_meeting)
        meeting_row.addWidget(self._meeting_label, 1)
        meeting_row.addWidget(self._meeting_open_btn)
        meeting_row.addWidget(self._meeting_unlink_btn)
        form.addRow("Meeting", meeting_row)

        qa_row = QHBoxLayout()
        self._qa_label = QLabel("—")
        self._qa_open_btn = QPushButton("Open Quick Assignments")
        self._qa_create_btn = QPushButton("Create Quick Assignment")
        self._qa_unlink_btn = QPushButton("Unlink")
        self._qa_open_btn.clicked.connect(self._open_quick_assignments)
        self._qa_create_btn.clicked.connect(self._create_quick_assignment)
        self._qa_unlink_btn.clicked.connect(self._unlink_quick_assignment)
        qa_row.addWidget(self._qa_label, 1)
        qa_row.addWidget(self._qa_open_btn)
        qa_row.addWidget(self._qa_create_btn)
        qa_row.addWidget(self._qa_unlink_btn)
        form.addRow("Quick Assignment", qa_row)

        gis_row = QHBoxLayout()
        self._gis_label = QLabel("—")
        self._gis_unlink_btn = QPushButton("Unlink")
        self._gis_unlink_btn.clicked.connect(self._unlink_gis_feature)
        gis_row.addWidget(self._gis_label, 1)
        gis_row.addWidget(self._gis_unlink_btn)
        form.addRow("GIS Location", gis_row)
        # No "Open"/focus action for GIS yet -- no existing desktop entry
        # point opens the map centered on a specific feature (checked
        # before building this; see the Phase 1D audit notes). Linking,
        # display, and unlink work; deep navigation is a documented gap.

        return group

    def _refresh_related_records(self) -> None:
        item = self.item
        incident_id = self.controller.incident_id or ""

        if item.meeting_id:
            meeting = resolve_meeting(incident_id, item.meeting_id)
            self._meeting_label.setText(
                f"{meeting.get('title', '')} ({meeting.get('meeting_date', '')})" if meeting else "(meeting not found)"
            )
            self._meeting_open_btn.setEnabled(meeting is not None)
        else:
            self._meeting_label.setText("—")
            self._meeting_open_btn.setEnabled(False)
        self._meeting_unlink_btn.setEnabled(bool(item.meeting_id))

        if item.quick_assignment_id:
            self._qa_label.setText(item.quick_assignment_id)
            self._qa_create_btn.setEnabled(False)
            self._qa_unlink_btn.setEnabled(True)
        else:
            self._qa_label.setText("—")
            self._qa_create_btn.setEnabled(True)
            self._qa_unlink_btn.setEnabled(False)

        if item.gis_feature_id:
            feature = resolve_gis_feature(incident_id, item.gis_feature_id)
            self._gis_label.setText(
                f"{feature.get('label', '')} ({feature.get('feature_type', '')})" if feature else "(location not found)"
            )
        else:
            self._gis_label.setText("—")
        self._gis_unlink_btn.setEnabled(bool(item.gis_feature_id))

    def _open_meeting(self) -> None:
        if not self.item.meeting_id:
            return
        try:
            from modules.planning.meetings.panel import open_meeting_detail
            open_meeting_detail(int(self.item.meeting_id), self.controller.incident_id, parent=self)
        except Exception as exc:
            QMessageBox.warning(self, "Meeting", f"Could not open the linked meeting: {exc}")

    def _unlink_meeting(self) -> None:
        if self.item.id is not None and self.controller.update(
            self.item.id, {"meeting_id": ""}, expected_revision=self.item.revision
        ):
            self.accept()

    def _open_quick_assignments(self) -> None:
        try:
            from .. import windows as plannedtoolkit_windows
            panel = plannedtoolkit_windows.get_tasking_panel(self.controller.incident_id)
            panel.setParent(None)
            panel.setWindowTitle("Quick Assignments")
            panel.show()
            self._qa_panel_ref = panel  # keep a reference so it isn't garbage-collected
        except Exception as exc:
            QMessageBox.warning(self, "Quick Assignments", f"Could not open Quick Assignments: {exc}")

    def _create_quick_assignment(self) -> None:
        if self.item.id is not None and self.controller.create_quick_assignment(self.item.id):
            self.accept()

    def _unlink_quick_assignment(self) -> None:
        """Clears the schedule item's own reference only -- the Quick
        Assignment record itself (and its independent lifecycle) is
        untouched, per the brief."""
        if self.item.id is not None and self.controller.update(
            self.item.id, {"quick_assignment_id": ""}, expected_revision=self.item.revision
        ):
            self.accept()

    def _unlink_gis_feature(self) -> None:
        if self.item.id is not None and self.controller.update(
            self.item.id, {"gis_feature_id": ""}, expected_revision=self.item.revision
        ):
            self.accept()

    # -- Reminders (ScheduleTrigger) ---------------------------------------

    def _build_reminders_group(self) -> QGroupBox:
        group = QGroupBox("Reminders")
        layout = QVBoxLayout(group)

        self._reminders_table = QTableWidget(0, 4)
        self._reminders_table.setHorizontalHeaderLabels(["When", "Title", "Severity", "Delivered"])
        self._reminders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._reminders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._reminders_table.setMaximumHeight(120)
        layout.addWidget(self._reminders_table)

        actions = QHBoxLayout()
        add_btn = QPushButton("Add Reminder")
        edit_btn = QPushButton("Edit")
        delete_btn = QPushButton("Delete")
        add_btn.clicked.connect(self._add_reminder)
        edit_btn.clicked.connect(self._edit_reminder)
        delete_btn.clicked.connect(self._delete_reminder)
        for button in (add_btn, edit_btn, delete_btn):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        return group

    def _refresh_reminders(self) -> None:
        try:
            triggers = services.list_schedule_triggers(self.controller.incident_id, self.item.record_id)
        except Exception:
            triggers = []
        self._reminders = list(triggers)
        self._reminders_table.setRowCount(len(self._reminders))
        for row, trigger in enumerate(self._reminders):
            when = friendly_dt(trigger.trigger_at) or "—"
            delivered = "Delivered" if trigger.fired_at else ("Enabled" if trigger.enabled else "Cancelled")
            for col, value in enumerate([when, trigger.title or trigger.label, trigger.severity or "routine", delivered]):
                self._reminders_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _selected_reminder(self):
        row = self._reminders_table.currentRow()
        if row < 0 or row >= len(self._reminders):
            return None
        return self._reminders[row]

    def _add_reminder(self) -> None:
        dialog = ReminderDialog(self.item, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            services.create_schedule_trigger(self.controller.incident_id, **dialog.values())
        except Exception as exc:
            QMessageBox.warning(self, "Reminder", f"Could not create reminder: {exc}")
            return
        self._refresh_reminders()

    def _edit_reminder(self) -> None:
        trigger = self._selected_reminder()
        if trigger is None:
            return
        if trigger.fired_at:
            QMessageBox.information(self, "Reminder", "This reminder already fired and can no longer be edited.")
            return
        dialog = ReminderDialog(self.item, trigger=trigger, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            # Edit updates the existing trigger in place -- never creates a
            # second one, per the brief's "do not silently duplicate a
            # reminder when editing an activity."
            services.update_schedule_trigger(trigger.id, dialog.values(), self.controller.incident_id)
        except Exception as exc:
            QMessageBox.warning(self, "Reminder", f"Could not update reminder: {exc}")
            return
        self._refresh_reminders()

    def _delete_reminder(self) -> None:
        trigger = self._selected_reminder()
        if trigger is None:
            return
        if QMessageBox.question(self, "Delete Reminder", "Cancel this reminder?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.delete_schedule_trigger(trigger.id, self.controller.incident_id)
        except Exception as exc:
            QMessageBox.warning(self, "Reminder", f"Could not cancel reminder: {exc}")
            return
        self._refresh_reminders()

    def _act(self, fn) -> None:
        if self.item.id is not None and fn(self.item.id, expected_revision=self.item.revision):
            self.accept()

    def _edit(self) -> None:
        dialog = ScheduleItemDialog(self.item, incident_id=self.controller.incident_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self.item.id is not None and self.controller.update(
            self.item.id, dialog.values(), expected_revision=self.item.revision
        ):
            self.accept()

    def _delay(self) -> None:
        reason = prompt_delay_reason(self)
        if reason is None or self.item.id is None:
            return
        if self.controller.delay(self.item.id, delay_reason=reason, expected_revision=self.item.revision):
            self.accept()

    def _cancel(self) -> None:
        reason = prompt_cancellation_reason(self)
        if reason is None or self.item.id is None:
            return
        if self.controller.cancel(self.item.id, cancellation_reason=reason, expected_revision=self.item.revision):
            self.accept()

    def _correct(self) -> None:
        from .schedule_dialogs import CorrectionDialog

        dialog = CorrectionDialog(self.item, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or self.item.id is None:
            return
        if self.controller.correct(self.item.id, expected_revision=self.item.revision, **dialog.values()):
            self.accept()


class OperationalTimelineWidget(QWidget):
    def __init__(self, controller: ScheduleController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._selected_date: date = date.today()
        self._build_ui()
        self.controller.itemsChanged.connect(self._on_items_changed)
        self.controller.statusMessage.connect(self._set_status)
        subscribe_theme(self, self._on_theme_changed)
        self._on_items_changed(initial=True)

    def _on_theme_changed(self, _name: str) -> None:
        self._populate()

    # -- UI ---------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        summary = QHBoxLayout()
        self.in_progress_label = QLabel()
        self.next_label = QLabel()
        self.delayed_label = QLabel()
        self.attention_label = QLabel()
        for label in (self.in_progress_label, self.next_label, self.delayed_label, self.attention_label):
            label.setStyleSheet("font-weight: 600;")
            summary.addWidget(label)
        summary.addStretch(1)
        self.status_label = QLabel("")
        summary.addWidget(self.status_label)
        layout.addLayout(summary)

        nav = QHBoxLayout()
        prev_btn = QPushButton("◀ Prev Day")
        next_btn = QPushButton("Next Day ▶")
        today_btn = QPushButton("Today")
        now_btn = QPushButton("Scroll to Now")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("MM/dd/yyyy")
        prev_btn.clicked.connect(lambda: self._go_to(self._selected_date - timedelta(days=1)))
        next_btn.clicked.connect(lambda: self._go_to(self._selected_date + timedelta(days=1)))
        today_btn.clicked.connect(lambda: self._go_to(date.today()))
        now_btn.clicked.connect(self._scroll_to_now)
        self.date_edit.dateChanged.connect(self._on_date_edit_changed)
        for widget in (prev_btn, self.date_edit, next_btn, today_btn, now_btn):
            nav.addWidget(widget)
        nav.addStretch(1)
        layout.addLayout(nav)

        filters = QHBoxLayout()
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems([_ALL, *STATUSES])
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems([_ALL])
        self.type_filter_combo.setEditable(True)
        self.responsible_filter_combo = QComboBox()
        self.responsible_filter_combo.addItems([_ALL])
        self.responsible_filter_combo.setEditable(True)
        self.status_filter_combo.currentTextChanged.connect(self._populate)
        self.type_filter_combo.currentTextChanged.connect(self._populate)
        self.responsible_filter_combo.currentTextChanged.connect(self._populate)
        for label, widget in (
            ("Status", self.status_filter_combo),
            ("Type", self.type_filter_combo),
            ("Responsible", self.responsible_filter_combo),
        ):
            filters.addWidget(QLabel(label))
            filters.addWidget(widget)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        from utils.table_view_styles import apply_statusboard_table_behavior
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
        self.table.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)

        open_row = QHBoxLayout()
        open_btn = QPushButton("Open Activity")
        open_btn.clicked.connect(self._open_selected)
        open_row.addWidget(open_btn)
        open_row.addStretch(1)
        layout.addLayout(open_row)

    def _set_status(self, message: str, is_error: bool) -> None:
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {'#b00020' if is_error else '#375a2b'};")

    # -- navigation ---------------------------------------------------------

    def _go_to(self, target: date) -> None:
        self._selected_date = target
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(QDate(target.year, target.month, target.day))
        self.date_edit.blockSignals(False)
        self._populate()

    def _on_date_edit_changed(self, qdate: QDate) -> None:
        self._selected_date = date(qdate.year(), qdate.month(), qdate.day())
        self._populate()

    def _scroll_to_now(self) -> None:
        if self._selected_date != date.today():
            self._go_to(date.today())
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == "now_marker":
                self.table.scrollToItem(item)
                return
        if self.table.rowCount():
            self.table.scrollToBottom()

    # -- data ---------------------------------------------------------------

    def _on_items_changed(self, *, initial: bool = False) -> None:
        if initial:
            self._selected_date = _pick_default_date(self.controller.items(), today=date.today())
            self.date_edit.setDate(QDate(self._selected_date.year, self._selected_date.month, self._selected_date.day))
        self._refresh_filter_choices()
        self._populate()

    def _refresh_filter_choices(self) -> None:
        types = sorted({item.kind for item in self.controller.items() if item.kind})
        responsibles = sorted({item.assigned_to for item in self.controller.items() if item.assigned_to})
        self._reload_combo(self.type_filter_combo, types)
        self._reload_combo(self.responsible_filter_combo, responsibles)

    def _reload_combo(self, combo: QComboBox, values: list[str]) -> None:
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems([_ALL, *values])
        if current and combo.findText(current) >= 0:
            combo.setCurrentText(current)
        else:
            combo.setCurrentText(_ALL)
        combo.blockSignals(False)

    def _items_for_selected_date(self) -> list[ScheduledItem]:
        return [item for item in self.controller.items() if _item_date(item) == self._selected_date]

    def _filtered_items(self) -> list[ScheduledItem]:
        status_text = self.status_filter_combo.currentText()
        type_text = self.type_filter_combo.currentText().strip()
        responsible_text = self.responsible_filter_combo.currentText().strip()

        def matches(item: ScheduledItem) -> bool:
            if status_text != _ALL and item.status != status_text:
                return False
            if type_text and type_text != _ALL and item.kind != type_text:
                return False
            if responsible_text and responsible_text != _ALL and item.assigned_to != responsible_text:
                return False
            return True

        return [item for item in self._items_for_selected_date() if matches(item)]

    # -- summary (always "now", independent of the navigated date) --------

    def _update_summary(self) -> None:
        all_items = self.controller.items()
        now = datetime.now()

        in_progress = [item for item in all_items if item.status == "In Progress"]
        delayed = [item for item in all_items if item.status == "Delayed"]
        attention = [
            item for item in all_items
            if item.status in _OPEN_STATUSES and is_overdue(item.status, item.starts_at, item.ends_at, now=now)
        ]
        upcoming = sorted(
            (item for item in all_items if item.status == "Scheduled" and parse_dt(item.starts_at) and parse_dt(item.starts_at) >= now),
            key=lambda item: item.starts_at,
        )

        self.in_progress_label.setText(f"In Progress: {len(in_progress)}")
        self.next_label.setText(
            f"Next: {upcoming[0].name} @ {friendly_time(upcoming[0].starts_at)}" if upcoming else "Next: —"
        )
        self.delayed_label.setText(f"Delayed: {len(delayed)}")
        self.attention_label.setText(f"Needs Attention: {len(attention)}")

    # -- rendering ------------------------------------------------------------

    def _populate(self, *_args: Any) -> None:
        self._update_summary()
        items = sorted(self._filtered_items(), key=lambda item: item.starts_at or "")
        colors = event_schedule_status_colors()
        now = datetime.now()
        is_today = self._selected_date == date.today()

        rows: list[tuple[str, ScheduledItem | None]] = []
        inserted_now = False
        for item in items:
            if is_today and not inserted_now:
                start_dt = parse_dt(item.starts_at)
                if start_dt and start_dt > now:
                    rows.append((_NOW_MARKER_TEXT, None))
                    inserted_now = True
            rows.append(("item", item))
        if is_today and not inserted_now:
            rows.append((_NOW_MARKER_TEXT, None))

        # clearSpans() first: the NOW-marker row's column span from a
        # previous render otherwise lingers when a filter change shrinks
        # the row count, corrupting which cells later setItem calls land
        # on (a real, reproducible QTableWidget interaction, not specific
        # to this filter).
        self.table.clearSpans()
        self.table.setRowCount(len(rows))
        for row_idx, (kind, item) in enumerate(rows):
            if kind == _NOW_MARKER_TEXT:
                marker = QTableWidgetItem(_NOW_MARKER_TEXT)
                marker.setData(Qt.ItemDataRole.UserRole, "now_marker")
                marker.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, 0, marker)
                # The span visually hides columns 1+, but row indices are
                # reused across renders (e.g. a filter change shrinking the
                # row count), so whatever QTableWidgetItem previously
                # occupied this row at those columns otherwise lingers in
                # the model -- invisible, but still returned by a direct
                # table.item(row, col) read.
                for col_idx in range(1, len(_COLUMNS)):
                    self.table.setItem(row_idx, col_idx, QTableWidgetItem(""))
                self.table.setSpan(row_idx, 0, 1, len(_COLUMNS))
                continue

            overdue = item.status in _OPEN_STATUSES and is_overdue(item.status, item.starts_at, item.ends_at, now=now)
            attention_text = item.delay_reason if item.status == "Delayed" else ("Overdue" if overdue else "")
            values = [
                friendly_time(item.starts_at),
                item.name,
                item.kind,
                item.assigned_to,
                item.location,
                item.status,
                friendly_time(item.actual_start_at),
                friendly_time(item.actual_end_at),
                planned_vs_actual_text(item.starts_at, item.ends_at, item.actual_start_at, item.actual_end_at),
                attention_text,
            ]
            badge = colors.get(item.status)
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem("" if value is None else str(value))
                if badge is not None:
                    cell.setBackground(badge["bg"])
                    cell.setForeground(badge["fg"])
                if item.status == "In Progress":
                    font = cell.font()
                    font.setBold(True)
                    cell.setFont(font)
                cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self.table.setItem(row_idx, col_idx, cell)

    # -- selection ------------------------------------------------------------

    def _selected_item(self) -> ScheduledItem | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        id_item = self.table.item(row, 0)
        if id_item is None:
            return None
        item_id = id_item.data(Qt.ItemDataRole.UserRole)
        if item_id in (None, "now_marker"):
            return None
        return next((item for item in self.controller.items() if item.id == item_id), None)

    def _open_selected(self, *_args: Any) -> None:
        item = self._selected_item()
        if item is None:
            return
        dialog = ActivityDetailDialog(item, self.controller, parent=self)
        dialog.exec()
