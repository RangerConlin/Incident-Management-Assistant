"""Reusable checklist execution/editor widget.

Given an incident id + checklist id, renders the checklist's sections and
items in order, lets an authenticated user record responses through the
shared Checklist API, and exposes the Phase 4B lifecycle actions
(complete/reopen/archive). This widget depends only on checklist identity
(`incident_id`, `checklist_id`) and the generic checklist JSON shape — it
has no Planned-Events-specific model or import, so another module can
embed it later (`load_checklist`/`clear` is the whole public surface a
container needs).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import APIError
from utils.styles import subscribe_theme
from utils.timefmt import format_display_datetime

from .. import api
from .. import record_links
from ..async_call import BackgroundCall
from ..progress_utils import summarize
from ..styles_support import checklist_status_brush
from .lifecycle_dialogs import CompletionDialog, ReopenDialog
from .response_history_dialog import ResponseHistoryDialog

_DEBOUNCE_MS = 600


class ChecklistExecutionWidget(QWidget):
    checklistChanged = Signal(dict)  # emitted whenever the loaded checklist is (re)loaded or updated

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.incident_id: Optional[str] = None
        self.checklist_id: Optional[str] = None
        self._checklist: Optional[dict[str, Any]] = None
        self._rows: dict[str, "_ItemRow"] = {}
        self._load_call: Optional[BackgroundCall] = None
        self._build_ui()
        self._render_empty_state("Select a checklist to view its details.")
        subscribe_theme(self, lambda _name: self._restyle_status())

    # -- public API -----------------------------------------------------------

    def load_checklist(self, incident_id: str, checklist_id: str) -> None:
        self.incident_id = incident_id
        self.checklist_id = checklist_id
        self.refresh()

    def clear(self) -> None:
        self.incident_id = None
        self.checklist_id = None
        self._checklist = None
        self._render_empty_state("Select a checklist to view its details.")

    def refresh(self) -> None:
        if not (self.incident_id and self.checklist_id):
            return
        self._set_busy(True, "Loading…")
        self._load_call = BackgroundCall(api.get_checklist, self.incident_id, self.checklist_id)
        self._load_call.succeeded.connect(self._on_loaded)
        self._load_call.failed.connect(self._on_load_failed)
        self._load_call.start()

    def _on_loaded(self, checklist: dict[str, Any]) -> None:
        self._set_busy(False)
        self._checklist = checklist
        self._render(checklist)
        self.checklistChanged.emit(checklist)

    def _on_load_failed(self, exc: Exception) -> None:
        self._set_busy(False)
        self._render_empty_state(self._describe_error(exc))

    # -- construction -----------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        self.header_name_label = QLabel("")
        self.header_name_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.header_status_label = QLabel("")
        header_row = QHBoxLayout()
        header_row.addWidget(self.header_name_label)
        header_row.addStretch(1)
        header_row.addWidget(self.header_status_label)
        outer.addLayout(header_row)

        self.header_description_label = QLabel("")
        self.header_description_label.setWordWrap(True)
        outer.addWidget(self.header_description_label)

        self.header_meta_label = QLabel("")
        self.header_meta_label.setWordWrap(True)
        outer.addWidget(self.header_meta_label)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel("")
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.progress_label)
        outer.addLayout(progress_row)

        self.failures_label = QLabel("")
        self.failures_label.setWordWrap(True)
        outer.addWidget(self.failures_label)

        links_header = QHBoxLayout()
        links_header.addWidget(QLabel("Associated Records:"))
        links_header.addStretch(1)
        outer.addLayout(links_header)
        self.links_container = QWidget()
        self.links_layout = QVBoxLayout(self.links_container)
        self.links_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.links_container)

        actions_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.complete_button = QPushButton("Complete Checklist")
        self.complete_button.clicked.connect(self._on_complete_clicked)
        self.reopen_button = QPushButton("Reopen")
        self.reopen_button.clicked.connect(self._on_reopen_clicked)
        self.archive_button = QPushButton("Archive")
        self.archive_button.clicked.connect(self._on_archive_clicked)
        for button in (self.refresh_button, self.complete_button, self.reopen_button, self.archive_button):
            actions_row.addWidget(button)
        actions_row.addStretch(1)
        outer.addLayout(actions_row)

        self.status_label = QLabel("")
        outer.addWidget(self.status_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_container)
        self.sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.sections_container)
        outer.addWidget(self.scroll_area, 1)

    # -- rendering ----------------------------------------------------------

    def _render_empty_state(self, message: str) -> None:
        self.header_name_label.setText("")
        self.header_status_label.setText("")
        self.header_description_label.setText("")
        self.header_meta_label.setText("")
        self.progress_bar.setValue(0)
        self.progress_label.setText("")
        self.failures_label.setText("")
        self._clear_links()
        self.status_label.setText(message)
        for button in (self.complete_button, self.reopen_button, self.archive_button, self.refresh_button):
            button.setEnabled(False)
        self._clear_sections()

    def _clear_sections(self) -> None:
        while self.sections_layout.count():
            child = self.sections_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = {}

    def _render(self, checklist: dict[str, Any]) -> None:
        scroll_value = self.scroll_area.verticalScrollBar().value()

        self.header_name_label.setText(checklist.get("name") or "")
        self.header_description_label.setText(checklist.get("description") or "")
        self.header_description_label.setVisible(bool(checklist.get("description")))

        status = str(checklist.get("status") or "not_started")
        self.header_status_label.setText(status.replace("_", " ").title())
        self._restyle_status()

        meta_parts: list[str] = []
        owner = checklist.get("owner_person_record")
        if owner is not None:
            meta_parts.append(f"Owner: {api.resolve_person_display(owner)}")
        if checklist.get("completed_at"):
            when = format_display_datetime(checklist["completed_at"], include_seconds=False)
            completed_by = api.resolve_person_display(checklist.get("completed_by"))
            meta_parts.append(f"Completed by {completed_by} — {when}")
        if checklist.get("archived_at"):
            when = format_display_datetime(checklist["archived_at"], include_seconds=False)
            archived_by = api.resolve_person_display(checklist.get("archived_by"))
            meta_parts.append(f"Archived by {archived_by} — {when}")
        self.header_meta_label.setText("  ·  ".join(meta_parts))

        summary = summarize(checklist.get("sections"))
        applicable = summary["applicable_items"] or 1
        percent = round((summary["answered_applicable_items"] / applicable) * 100) if summary["applicable_items"] else 0
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{summary['answered_applicable_items']}/{summary['applicable_items']} applicable items answered")

        if summary["failed_items"]:
            labels = ", ".join(f["label"] for f in summary["failed_items"])
            self.failures_label.setText(f"⚠ Unresolved failures ({len(summary['failed_items'])}): {labels}")
        else:
            self.failures_label.setText("No unresolved failures.")

        self._render_links(checklist)

        read_only = status in ("completed", "archived")
        self.refresh_button.setEnabled(True)
        self.complete_button.setEnabled(status in ("not_started", "in_progress") and bool(api.current_actor_id()))
        self.reopen_button.setEnabled(status == "completed" and bool(api.current_actor_id()))
        self.archive_button.setEnabled(status != "archived" and bool(api.current_actor_id()))
        if not api.current_actor_id():
            self.status_label.setText("Sign in to record responses or change this checklist's status.")
        else:
            self.status_label.setText("Read-only: this checklist is archived." if status == "archived" else "")

        self._clear_sections()
        sections = checklist.get("sections") or []
        if not sections:
            self.sections_layout.addWidget(QLabel("This checklist has no items."))
        for section in sections:
            self.sections_layout.addWidget(self._build_section_widget(section, read_only))

        self.scroll_area.verticalScrollBar().setValue(scroll_value)

    def _restyle_status(self) -> None:
        if not self._checklist:
            return
        status = str(self._checklist.get("status") or "not_started")
        brush = checklist_status_brush(status)
        if brush is None:
            self.header_status_label.setStyleSheet("")
            return
        bg = brush["bg"].color().name()
        fg = brush["fg"].color().name()
        self.header_status_label.setStyleSheet(
            f"background-color: {bg}; color: {fg}; padding: 2px 8px; border-radius: 4px; font-weight: 600;"
        )

    def _clear_links(self) -> None:
        while self.links_layout.count():
            child = self.links_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_links(self, checklist: dict[str, Any]) -> None:
        """Compact "manage supported associations" surface: one row per
        `linked_records` entry (resolved label + Open + Unlink). Adding a
        *new* link is initiated from the owning record's own "Checklists"
        section (e.g. `plannedtoolkit`'s Assignment/Schedule dialogs), not
        from here — this stays a simple display + removal affordance
        rather than a second place to pick records to link."""

        self._clear_links()
        links = checklist.get("linked_records") or []
        if not links:
            self.links_layout.addWidget(QLabel("None"))
            return
        incident_id = checklist.get("incident_id")
        for link in links:
            record_type = link.get("record_type", "")
            record_id = link.get("record_id", "")
            row = QHBoxLayout()
            label = record_links.describe(incident_id, record_type, record_id) if incident_id else f"{record_type}: {record_id}"
            row.addWidget(QLabel(label))
            row.addStretch(1)
            if incident_id and record_links.can_open(record_type):
                open_button = QPushButton("Open")
                open_button.clicked.connect(
                    lambda _checked=False, rt=record_type, rid=record_id: record_links.open_record(
                        incident_id, rt, rid, self
                    )
                )
                row.addWidget(open_button)
            unlink_button = QPushButton("Unlink")
            unlink_button.clicked.connect(
                lambda _checked=False, rt=record_type, rid=record_id: self._on_unlink_clicked(rt, rid)
            )
            row.addWidget(unlink_button)
            container = QWidget()
            container.setLayout(row)
            self.links_layout.addWidget(container)

    def _on_unlink_clicked(self, record_type: str, record_id: str) -> None:
        if not (self.incident_id and self.checklist_id):
            return
        confirm = QMessageBox.question(
            self,
            "Remove Association",
            "Remove this association? The checklist itself, its responses, and its other "
            "associations are preserved.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            api.remove_link(self.incident_id, self.checklist_id, record_type=record_type, record_id=record_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Remove Association", self._describe_error(exc))
            return
        self.refresh()

    def _build_section_widget(self, section: dict[str, Any], read_only: bool) -> QWidget:
        items = section.get("items") or []
        name = section.get("name") or ""
        if name:
            box = QGroupBox(name)
        else:
            box = QGroupBox()
            box.setFlat(True)
        layout = QVBoxLayout(box)
        for item in items:
            row = _ItemRow(self, item, read_only)
            self._rows[item["id"]] = row
            layout.addWidget(row.frame)
        return box

    # -- item response handling ---------------------------------------------

    def request_save(self, row: "_ItemRow", *, value: Any, na: bool, notes: str) -> None:
        """Start one item's save as a background call, tracked on ``row``.

        The row itself decides (in `_save_now`) whether a new save may
        start right now — this just performs it and routes the result
        back, so the duplicate-submission guard lives in one place.
        """

        if not (self.incident_id and self.checklist_id):
            return
        item_id = row.item["id"]
        row.set_saving()
        call = BackgroundCall(
            api.record_item_response,
            self.incident_id,
            self.checklist_id,
            item_id,
            value=value,
            na=na,
            notes=notes,
        )
        call.succeeded.connect(lambda result, row=row: self._on_response_saved(row, result))
        call.failed.connect(lambda exc, row=row: self._on_response_failed(row, exc))
        # Keep a reference on the row so the thread isn't garbage-collected
        # mid-flight, and so a concurrent save request for the same item
        # can tell one is already in flight (see `_ItemRow._save_now`).
        row.pending_call = call
        call.start()

    def _on_response_saved(self, row: "_ItemRow", result: dict[str, Any]) -> None:
        row.pending_call = None
        row.apply_saved_response(result.get("item") or {})
        updated_checklist = result.get("checklist")
        if updated_checklist:
            # The server's response already carries the full, current
            # checklist (same shape a fresh GET would return) — use it
            # as-is rather than re-fetching, so a quick status flip
            # (not-started -> in-progress) shows up without a full
            # re-render (preserves scroll position / other in-progress edits).
            self._checklist = updated_checklist
            self._refresh_header_only(updated_checklist)
        row.maybe_flush_pending_save()
        self.checklistChanged.emit(self._checklist or {})

    def _refresh_header_only(self, updated_checklist: dict[str, Any]) -> None:
        status = str(updated_checklist.get("status") or "not_started")
        self.header_status_label.setText(status.replace("_", " ").title())
        self._restyle_status()
        self.complete_button.setEnabled(status in ("not_started", "in_progress") and bool(api.current_actor_id()))

    def _on_response_failed(self, row: "_ItemRow", exc: Exception) -> None:
        row.pending_call = None
        row.show_error(self._describe_error(exc))
        row.maybe_flush_pending_save()

    def _open_history(self, item_id: str, label: str) -> None:
        if not (self.incident_id and self.checklist_id):
            return
        dialog = ResponseHistoryDialog(self.incident_id, self.checklist_id, item_id, label, self)
        dialog.exec()

    # -- lifecycle actions ----------------------------------------------------

    def _on_complete_clicked(self) -> None:
        if not (self.incident_id and self.checklist_id and self._checklist):
            return
        try:
            validation = api.validate_completion(self.incident_id, self.checklist_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Complete Checklist", self._describe_error(exc))
            return

        dialog = CompletionDialog(self._checklist, validation, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            result = api.complete_checklist(
                self.incident_id,
                self.checklist_id,
                acknowledge_failures=dialog.acknowledge_failures(),
                stream=dialog.selected_stream(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Complete Checklist", self._describe_error(exc))
            return

        checklist = result.get("checklist") or {}
        summary = result.get("summary") or {}
        actor_display = api.resolve_person_display(api.current_actor_id())
        stream_label = "the persisted incident stream"
        selected = dialog.selected_stream()
        if selected is not None:
            stream_label = next(
                (opt["label"] for opt in getattr(dialog, "_stream_options", []) if opt["stream"] == selected),
                "the selected stream",
            )
        message = (
            f"{checklist.get('name', '')} completed.\n\n"
            f"Answered: {summary.get('answered_applicable_items', '?')}/{summary.get('applicable_items', '?')} applicable items\n"
            f"Unresolved failures: {len(summary.get('unresolved_failures') or [])}\n"
            f"Completed by: {actor_display}\n"
            f"ICS-214 stream: {stream_label}"
        )
        if result.get("ics214_pending"):
            message += "\n\nNote: the ICS-214 entry could not be logged immediately and will need to be retried."
        QMessageBox.information(self, "Checklist Completed", message)
        self.refresh()

    def _on_reopen_clicked(self) -> None:
        if not (self.incident_id and self.checklist_id and self._checklist):
            return
        dialog = ReopenDialog(self._checklist, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            api.reopen_checklist(
                self.incident_id, self.checklist_id, reason=dialog.reason(), stream=dialog.selected_stream()
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Reopen Checklist", self._describe_error(exc))
            return
        self.refresh()

    def _on_archive_clicked(self) -> None:
        if not (self.incident_id and self.checklist_id and self._checklist):
            return
        confirm = QMessageBox.question(
            self,
            "Archive Checklist",
            "Archive this checklist? It will become read-only. Nothing is deleted, "
            "and it will remain visible through the checklist list's filters.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            api.archive_checklist(self.incident_id, self.checklist_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Archive Checklist", self._describe_error(exc))
            return
        self.refresh()

    # -- helpers --------------------------------------------------------------

    def _set_busy(self, busy: bool, message: str = "") -> None:
        # The widget stays interactive during a background load/save — only
        # the status label communicates "busy" — per the "do not block the
        # UI during network operations" requirement.
        if busy:
            self.status_label.setText(message)

    def _describe_error(self, exc: Exception) -> str:
        if isinstance(exc, APIError):
            if exc.status_code is None:
                return f"Checklists API unavailable: {exc}"
            if exc.status_code == 409:
                return f"This checklist was changed by someone else. Refresh and try again.\n({exc})"
            return f"Checklists API error {exc.status_code}: {exc}"
        return str(exc)


class _ItemRow:
    """One item's response controls + accountability caption.

    A thin controller object, not a `QWidget` subclass, so the widget tree
    stays plain Qt widgets laid out by the section's `QVBoxLayout` while
    this class owns the debounce timers and the "what do I currently show"
    state that doesn't belong on the execution widget itself.
    """

    def __init__(self, owner: ChecklistExecutionWidget, item: dict[str, Any], read_only: bool) -> None:
        self.owner = owner
        self.item = item
        self.read_only = read_only
        self.pending_call: Optional[BackgroundCall] = None
        self._dirty = False
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._save_now)
        self._suppress = False  # true while programmatically setting control values

        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self.frame)

        label_row = QHBoxLayout()
        label_text = item.get("label", "")
        if item.get("required"):
            label_text += "  *"
        label = QLabel(f"<b>{label_text}</b>")
        label_row.addWidget(label)
        label_row.addStretch(1)
        history_button = QPushButton("History")
        history_button.clicked.connect(lambda: owner._open_history(item["id"], item.get("label", "")))
        label_row.addWidget(history_button)
        layout.addLayout(label_row)

        if item.get("instructions"):
            instructions = QLabel(item["instructions"])
            instructions.setWordWrap(True)
            instructions.setStyleSheet("color: gray;")
            layout.addWidget(instructions)

        control_row = QHBoxLayout()
        self.control = self._build_control(item, control_row)
        if item.get("na_allowed"):
            self.na_check = QCheckBox("N/A")
            self.na_check.toggled.connect(self._on_na_toggled)
            control_row.addWidget(self.na_check)
        else:
            self.na_check = None
        layout.addLayout(control_row)

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes (optional)")
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        layout.addWidget(self.notes_edit)

        self.caption_label = QLabel("")
        self.caption_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.caption_label)

        response = item.get("response")
        self._apply_initial_response(response)
        self._set_enabled(not read_only)

    # -- control construction -------------------------------------------------

    def _build_control(self, item: dict[str, Any], control_row: QHBoxLayout) -> QWidget:
        item_type = item.get("item_type")
        if item_type == "checkbox":
            control = QCheckBox("Checked")
            control.toggled.connect(self._on_value_changed_immediate)
            control_row.addWidget(control)
            return control

        if item_type == "pass_fail_na":
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            self.pass_fail_group = QButtonGroup(container)
            self.pass_radio = QRadioButton("Pass")
            self.fail_radio = QRadioButton("FAIL")
            self.fail_radio.setStyleSheet("font-weight: 700;")
            self.pass_fail_group.addButton(self.pass_radio)
            self.pass_fail_group.addButton(self.fail_radio)
            row.addWidget(self.pass_radio)
            row.addWidget(self.fail_radio)
            self.pass_radio.toggled.connect(self._on_pass_fail_toggled)
            self.fail_radio.toggled.connect(self._on_pass_fail_toggled)
            control_row.addWidget(container)
            return container

        if item_type == "text":
            control = QPlainTextEdit()
            control.setFixedHeight(70)
            control.textChanged.connect(self._on_text_changed_debounced)
            control_row.addWidget(control, 1)
            return control

        if item_type == "numeric":
            control = QDoubleSpinBox()
            control.setDecimals(3)
            control.setRange(
                item.get("min_value") if item.get("min_value") is not None else -1_000_000.0,
                item.get("max_value") if item.get("max_value") is not None else 1_000_000.0,
            )
            if item.get("unit"):
                control.setSuffix(f" {item['unit']}")
            control.valueChanged.connect(self._on_numeric_changed_debounced)
            control_row.addWidget(control)
            return control

        if item_type == "selection":
            control = QComboBox()
            control.addItem("Select…", None)
            for option in item.get("options") or []:
                control.addItem(option.get("label", ""), option.get("id"))
            control.currentIndexChanged.connect(self._on_selection_changed)
            control_row.addWidget(control)
            return control

        return QLabel(f"Unsupported item type: {item_type}")

    def _apply_initial_response(self, response: Optional[dict[str, Any]]) -> None:
        self._suppress = True
        try:
            item_type = self.item.get("item_type")
            na = bool(response and response.get("na"))
            value = response.get("value") if response else None
            if self.na_check is not None:
                self.na_check.setChecked(na)
            if item_type == "checkbox":
                self.control.setChecked(bool(value) if not na else False)
            elif item_type == "pass_fail_na":
                if value == "pass":
                    self.pass_radio.setChecked(True)
                elif value == "fail":
                    self.fail_radio.setChecked(True)
                else:
                    self.pass_fail_group.setExclusive(False)
                    self.pass_radio.setChecked(False)
                    self.fail_radio.setChecked(False)
                    self.pass_fail_group.setExclusive(True)
            elif item_type == "text":
                self.control.setPlainText(value or "" if not na else "")
            elif item_type == "numeric":
                self.control.setValue(float(value) if value is not None and not na else self.control.minimum())
            elif item_type == "selection":
                index = self.control.findData(value) if value else -1
                self.control.setCurrentIndex(index if index >= 0 else 0)
            if response:
                self.notes_edit.setText(response.get("notes") or "")
            self._set_control_enabled(not na)
            self._update_caption(response)
        finally:
            self._suppress = False

    def _set_enabled(self, enabled: bool) -> None:
        self.control.setEnabled(enabled)
        if self.na_check is not None:
            self.na_check.setEnabled(enabled)
        self.notes_edit.setEnabled(enabled)

    def _set_control_enabled(self, enabled: bool) -> None:
        if not self.read_only:
            self.control.setEnabled(enabled)

    # -- control change handlers ----------------------------------------------

    def _on_na_toggled(self, checked: bool) -> None:
        if self._suppress:
            return
        self._set_control_enabled(not checked)
        if checked:
            self._save_now(na=True)
        else:
            self._save_now(na=False)

    def _on_value_changed_immediate(self, *_args: Any) -> None:
        if self._suppress:
            return
        self._save_now()

    def _on_pass_fail_toggled(self, checked: bool) -> None:
        if self._suppress or not checked:
            return
        self._save_now()

    def _on_selection_changed(self, *_args: Any) -> None:
        if self._suppress:
            return
        self._save_now()

    def _on_text_changed_debounced(self) -> None:
        if self._suppress:
            return
        self._debounce.start()

    def _on_numeric_changed_debounced(self, *_args: Any) -> None:
        if self._suppress:
            return
        self._debounce.start()

    def _on_notes_changed(self, *_args: Any) -> None:
        if self._suppress:
            return
        self._debounce.start()

    def _current_value_and_na(self) -> tuple[Any, bool]:
        na = bool(self.na_check and self.na_check.isChecked())
        item_type = self.item.get("item_type")
        if item_type == "checkbox":
            return bool(self.control.isChecked()), na
        if item_type == "pass_fail_na":
            if self.fail_radio.isChecked():
                return "fail", na
            if self.pass_radio.isChecked():
                return "pass", na
            return None, na
        if item_type == "text":
            return self.control.toPlainText(), na
        if item_type == "numeric":
            return self.control.value(), na
        if item_type == "selection":
            return self.control.currentData(), na
        return None, na

    def _save_now(self, na: Optional[bool] = None) -> None:
        if self.read_only:
            return
        if self.pending_call is not None:
            # A save for this item is already in flight — don't start a
            # second, concurrent request for the same item (duplicate
            # submission). Remember that the control changed again since;
            # the in-flight call's completion handler re-reads the
            # controls and saves once more, so nothing is lost.
            self._dirty = True
            return
        value, current_na = self._current_value_and_na()
        if na is not None:
            current_na = na
        if current_na is False and value is None and self.item.get("item_type") in ("pass_fail_na", "selection"):
            # Nothing chosen yet — don't submit an empty response.
            return
        self.owner.request_save(self, value=value, na=current_na, notes=self.notes_edit.text())

    def maybe_flush_pending_save(self) -> None:
        if self._dirty and not self.read_only:
            self._dirty = False
            self._save_now()

    # -- save result handling ---------------------------------------------

    def set_saving(self) -> None:
        self.caption_label.setText("Saving…")
        self.caption_label.setStyleSheet("color: gray; font-size: 11px;")

    def apply_saved_response(self, updated_item: dict[str, Any]) -> None:
        self.item = updated_item
        self._update_caption(updated_item.get("response"))

    def show_error(self, message: str) -> None:
        self.caption_label.setText(f"Save failed: {message}")
        self.caption_label.setStyleSheet("color: #b00020; font-size: 11px;")

    def _update_caption(self, response: Optional[dict[str, Any]]) -> None:
        if not response:
            self.caption_label.setText("Not yet answered.")
            self.caption_label.setStyleSheet("color: gray; font-size: 11px;")
            return
        actor = api.resolve_person_display(response.get("recorded_by"))
        when = format_display_datetime(response.get("recorded_at"), include_seconds=False)
        verb = "Marked N/A" if response.get("na") else "Completed"
        self.caption_label.setText(f"{verb} by {actor} — {when}")
        self.caption_label.setStyleSheet("color: gray; font-size: 11px;")


__all__ = ["ChecklistExecutionWidget"]
