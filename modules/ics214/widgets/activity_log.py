"""QtWidgets implementation for the redesigned ICS-214 Activity Log module."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Sequence
from uuid import uuid4

from PySide6.QtCore import QDateTime, QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def _now_local() -> QDateTime:
    dt = QDateTime.currentDateTime()
    dt.setTimeSpec(Qt.LocalTime)
    return dt


@dataclass
class EntryData:
    """Container for editable ICS-214 entry attributes."""

    timestamp: QDateTime = field(default_factory=_now_local)
    author: str = "Jane Smith"
    source: str = "manual"
    activity: str = ""
    location: str = ""
    links: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)

    def clone(self) -> "EntryData":
        return replace(
            self,
            links=list(self.links),
            attachments=list(self.attachments),
        )


@dataclass
class LogEntry:
    """Saved entry rendered in the main log table."""

    entry_id: int
    data: EntryData


@dataclass
class DraftEntry:
    """Auto-generated draft awaiting review."""

    draft_id: int
    data: EntryData
    selected: bool = True


@dataclass
class LogHeader:
    """Metadata describing the active ICS-214 log."""

    log_for_type: str
    log_for_label: str
    unit_or_resource: str = ""
    operational_period: str = ""
    status: str = "OPEN"
    version: int = 1
    prepared_by_name: str | None = None
    prepared_by_position: str | None = None
    start: QDateTime = field(default_factory=_now_local)
    end: QDateTime | None = None
    notes: str = ""
    identifier: str = field(default_factory=lambda: uuid4().hex)

    def clone(self) -> "LogHeader":
        cp = replace(self)
        if self.end is not None:
            cp.end = QDateTime(self.end)
        cp.start = QDateTime(self.start)
        return cp

    def is_prepared(self) -> bool:
        return bool(self.prepared_by_name and self.prepared_by_position)


def format_local_time(dt: QDateTime) -> str:
    if not dt.isValid():
        return "—"
    return dt.toLocalTime().toString("HH:mm MM/dd")


def format_header_time(dt: QDateTime | None) -> str:
    if dt is None or not dt.isValid():
        return "—"
    return dt.toLocalTime().toString("yyyy-MM-dd HH:mm")


class EntryEditorDialog(QDialog):
    """Rich editor dialog for ICS-214 entries."""

    def __init__(
        self,
        entry: EntryData | None = None,
        parent: QWidget | None = None,
        *,
        title: str | None = None,
        read_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self._original = entry.clone() if entry else EntryData()
        self._result = self._original.clone()
        self._read_only = read_only
        self.save_and_new_requested = False
        self.setWindowTitle(title or "Edit Entry")
        self._build_ui()
        self._apply_entry(self._original)

    @property
    def result(self) -> EntryData:
        return self._result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.time_edit = QDateTimeEdit(self)
        self.time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.time_edit.setCalendarPopup(True)

        self.author_combo = QComboBox(self)
        self.author_combo.addItems([
            "Jane Smith",
            "Alex Kim",
            "Priya Patel",
            "Miguel Torres",
        ])

        self.source_combo = QComboBox(self)
        self.source_combo.addItems([
            "manual",
            "auto_task",
            "auto_status",
            "auto_comms",
            "import",
        ])

        self.location_edit = QLineEdit(self)
        self.activity_edit = QTextEdit(self)
        self.activity_edit.setPlaceholderText("Describe the activity…")
        self.activity_edit.setMinimumHeight(120)

        links_row = QHBoxLayout()
        self.link_task_btn = QPushButton("Link Task", self)
        self.link_status_btn = QPushButton("Link Status", self)
        self.link_comms_btn = QPushButton("Link Comms", self)
        self.linked_label = QLabel("Linked: —", self)
        links_row.addWidget(self.link_task_btn)
        links_row.addWidget(self.link_status_btn)
        links_row.addWidget(self.link_comms_btn)
        links_row.addStretch(1)
        links_row.addWidget(self.linked_label)

        attach_row = QHBoxLayout()
        self.attach_btn = QPushButton("+ Add File", self)
        self.attach_count = QLabel("Attachments: 0", self)
        attach_row.addWidget(self.attach_btn)
        attach_row.addStretch(1)
        attach_row.addWidget(self.attach_count)

        form.addRow("Time:", self.time_edit)
        form.addRow("Author:", self.author_combo)
        form.addRow("Source:", self.source_combo)
        form.addRow("Location:", self.location_edit)
        form.addRow("Activity:", self.activity_edit)
        form.addRow("Links:", links_row)
        form.addRow("Attachments:", attach_row)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
        )
        self.save_new_btn = QPushButton("Save && New", self)
        self.button_box.addButton(self.save_new_btn, QDialogButtonBox.ActionRole)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        self.save_new_btn.clicked.connect(self._on_save_new)

        if self._read_only:
            for widget in (
                self.time_edit,
                self.author_combo,
                self.source_combo,
                self.location_edit,
                self.activity_edit,
                self.link_task_btn,
                self.link_status_btn,
                self.link_comms_btn,
                self.attach_btn,
            ):
                widget.setEnabled(False)
            self.save_new_btn.setEnabled(False)
            ok_btn = self.button_box.button(QDialogButtonBox.Save)
            if ok_btn:
                ok_btn.setText("Close")

    def _apply_entry(self, entry: EntryData) -> None:
        self.time_edit.setDateTime(entry.timestamp)
        idx = self.author_combo.findText(entry.author)
        self.author_combo.setCurrentIndex(max(0, idx))
        src_idx = self.source_combo.findText(entry.source)
        self.source_combo.setCurrentIndex(max(0, src_idx))
        self.location_edit.setText(entry.location)
        self.activity_edit.setPlainText(entry.activity)
        self._update_links_label(entry.links)
        self.attach_count.setText(f"Attachments: {len(entry.attachments)}")

    def _update_links_label(self, links: Sequence[str]) -> None:
        if links:
            self.linked_label.setText("Linked: " + ", ".join(links))
        else:
            self.linked_label.setText("Linked: —")

    def _collect(self) -> bool:
        text = self.activity_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Validation", "Activity description is required.")
            return False
        self._result = EntryData(
            timestamp=self.time_edit.dateTime(),
            author=self.author_combo.currentText(),
            source=self.source_combo.currentText(),
            activity=text,
            location=self.location_edit.text().strip(),
            links=self._original.links.copy(),
            attachments=self._original.attachments.copy(),
        )
        return True

    def _on_accept(self) -> None:
        if not self._read_only and not self._collect():
            return
        self.accept()

    def _on_save_new(self) -> None:
        if self._read_only:
            return
        if self._collect():
            self.save_and_new_requested = True
            self.accept()


class PreparedByDialog(QDialog):
    """Dialog capturing Prepared-By signature details."""

    def __init__(
        self,
        name: str | None,
        position: str | None,
        parent: QWidget | None = None,
        *,
        position_hint: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prepared-By / Sign")
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(name or "", self)
        self.position_edit = QLineEdit(position or "", self)
        if position_hint and not position:
            self.position_edit.setPlaceholderText(position_hint)
        layout.addRow("Name:", self.name_edit)
        layout.addRow("Position:", self.position_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        layout.addWidget(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        self.result: tuple[str, str] | None = None

    def _on_accept(self) -> None:
        name = self.name_edit.text().strip()
        position = self.position_edit.text().strip()
        if not name or not position:
            QMessageBox.warning(self, "Validation", "Name and position are required.")
            return
        self.result = (name, position)
        self.accept()


class DraftRowWidget(QWidget):
    """Widget representing a single draft entry in the review tray."""

    viewRequested = Signal()
    acceptRequested = Signal()
    discardRequested = Signal()
    selectionChanged = Signal(bool)

    def __init__(self, draft: DraftEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.draft = draft
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.checkbox = QCheckBox(self)
        self.checkbox.setChecked(draft.selected)
        self.checkbox.toggled.connect(self.selectionChanged)
        self.time_label = QLabel(format_local_time(draft.data.timestamp), self)
        self.time_label.setMinimumWidth(110)
        self.source_label = QLabel(draft.data.source, self)
        self.source_label.setMinimumWidth(90)
        self.summary_label = QLabel(f"“{draft.data.activity}”", self)
        self.summary_label.setWordWrap(True)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.view_btn = QPushButton("View", self)
        self.accept_btn = QPushButton("Accept", self)
        self.discard_btn = QPushButton("Discard", self)

        for widget in (
            self.checkbox,
            self.time_label,
            self.source_label,
            self.summary_label,
            self.view_btn,
            self.accept_btn,
            self.discard_btn,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)

        self.view_btn.clicked.connect(self.viewRequested)
        self.accept_btn.clicked.connect(self.acceptRequested)
        self.discard_btn.clicked.connect(self.discardRequested)

    def refresh(self) -> None:
        self.checkbox.setChecked(self.draft.selected)
        self.time_label.setText(format_local_time(self.draft.data.timestamp))
        self.source_label.setText(self.draft.data.source)
        self.summary_label.setText(f"“{self.draft.data.activity}”")


class DraftsTrayDialog(QDialog):
    """Review tray dialog for pending drafts."""

    entryAccepted = Signal(DraftEntry)
    entryDiscarded = Signal(DraftEntry)
    acceptAllRequested = Signal(list)

    def __init__(
        self,
        drafts: list[DraftEntry],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Review Drafts ({len(drafts)})")
        self._drafts: list[DraftEntry] = [d for d in drafts]
        self._rows: list[DraftRowWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        container = QWidget(self.scroll)
        self.scroll.setWidget(container)
        self.rows_layout = QVBoxLayout(container)

        for draft in self._drafts:
            self._add_row(draft)

        root.addWidget(self.scroll)

        controls = QHBoxLayout()
        controls.addStretch(1)
        self.accept_all_btn = QPushButton("Accept All", self)
        self.close_btn = QPushButton("Close", self)
        controls.addWidget(self.accept_all_btn)
        controls.addWidget(self.close_btn)
        root.addLayout(controls)

        self.accept_all_btn.clicked.connect(self._on_accept_all)
        self.close_btn.clicked.connect(self.reject)

    def _add_row(self, draft: DraftEntry) -> None:
        row = DraftRowWidget(draft, self)
        row.viewRequested.connect(lambda d=draft, w=row: self._on_view(d, w))
        row.acceptRequested.connect(lambda d=draft: self._on_accept(d))
        row.discardRequested.connect(lambda d=draft: self._on_discard(d))
        row.selectionChanged.connect(lambda state, d=draft: self._on_select(d, state))
        self.rows_layout.addWidget(row)
        self._rows.append(row)

    def _on_view(self, draft: DraftEntry, row: DraftRowWidget) -> None:
        dialog = EntryEditorDialog(draft.data, self, title=f"Review Draft #{draft.draft_id}")
        if dialog.exec() == QDialog.Accepted:
            draft.data = dialog.result.clone()
            row.refresh()

    def _on_accept(self, draft: DraftEntry) -> None:
        self.entryAccepted.emit(draft)
        self._remove_draft(draft)

    def _on_discard(self, draft: DraftEntry) -> None:
        self.entryDiscarded.emit(draft)
        self._remove_draft(draft)

    def _on_select(self, draft: DraftEntry, state: bool) -> None:
        draft.selected = state

    def _on_accept_all(self) -> None:
        selected = [d for d in self._drafts if d.selected]
        if not selected:
            QMessageBox.information(self, "Drafts", "Select drafts to accept.")
            return
        self.acceptAllRequested.emit(selected)
        for draft in list(selected):
            self._remove_draft(draft)

    def _remove_draft(self, draft: DraftEntry) -> None:
        if draft in self._drafts:
            idx = self._drafts.index(draft)
            self._drafts.pop(idx)
            row = self._rows.pop(idx)
            row.setParent(None)
            row.deleteLater()
        self.setWindowTitle(f"Review Drafts ({len(self._drafts)})")
        if not self._drafts:
            self.accept()


class NewLogDialog(QDialog):
    """Dialog for creating or editing an ICS-214 log header."""

    def __init__(
        self,
        header: LogHeader | None,
        subject_options: dict[str, list[str]],
        operational_periods: Sequence[str],
        parent: QWidget | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New / Select ICS 214 Log")
        self._subject_options = subject_options
        self._context = context or {}
        self._result: LogHeader | None = None
        self._build_ui()
        self._populate_options(operational_periods)
        self._load_header(header)

    @property
    def result(self) -> LogHeader | None:
        return self._result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        type_group_box = QGroupBox("Log For", self)
        type_layout = QHBoxLayout(type_group_box)
        self.type_group = QButtonGroup(self)
        self.individual_btn = QRadioButton("Individual", self)
        self.team_btn = QRadioButton("Team", self)
        self.section_btn = QRadioButton("Section", self)
        self.facility_btn = QRadioButton("Facility", self)
        for btn in (
            self.individual_btn,
            self.team_btn,
            self.section_btn,
            self.facility_btn,
        ):
            self.type_group.addButton(btn)
            type_layout.addWidget(btn)
        layout.addWidget(type_group_box)

        form = QFormLayout()
        self.subject_combo = QComboBox(self)
        self.subject_combo.setEditable(False)
        self.subject_combo.setInsertPolicy(QComboBox.NoInsert)
        form.addRow("Subject:", self.subject_combo)

        self.op_combo = QComboBox(self)
        form.addRow("Operational Period:", self.op_combo)

        self.start_edit = QDateTimeEdit(self)
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setCalendarPopup(True)
        form.addRow("Start Time:", self.start_edit)

        self.unit_edit = QLineEdit(self)
        form.addRow("Unit / Resource:", self.unit_edit)

        self.notes_edit = QLineEdit(self)
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("Create Log")
        layout.addWidget(buttons)

        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        self.type_group.buttonClicked.connect(self._on_type_changed)

    def _populate_options(self, operational_periods: Sequence[str]) -> None:
        self.op_combo.addItems(list(operational_periods))

    def _load_header(self, header: LogHeader | None) -> None:
        default_type = (self._context.get("default_log_for_type") or "team").lower()
        btn_map = {
            "individual": self.individual_btn,
            "team": self.team_btn,
            "section": self.section_btn,
            "facility": self.facility_btn,
        }
        btn = btn_map.get(default_type, self.team_btn)
        btn.setChecked(True)
        self._on_type_changed(btn)

        if header:
            btn_map.get(header.log_for_type, self.team_btn).setChecked(True)
            self._on_type_changed(btn_map.get(header.log_for_type, self.team_btn))
            idx = self.subject_combo.findText(header.log_for_label)
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)
            self.unit_edit.setText(header.unit_or_resource)
            self.notes_edit.setText(header.notes)
            self.start_edit.setDateTime(header.start)
            op_idx = self.op_combo.findText(header.operational_period)
            if op_idx >= 0:
                self.op_combo.setCurrentIndex(op_idx)
            self.setWindowTitle("Edit Log Header")
            button_box = self.findChild(QDialogButtonBox)
            if button_box:
                ok_btn = button_box.button(QDialogButtonBox.Ok)
                if ok_btn:
                    ok_btn.setText("Save")
        else:
            if self._context.get("default_log_for_ref"):
                default_ref = str(self._context["default_log_for_ref"])
                idx = self.subject_combo.findText(default_ref)
                if idx >= 0:
                    self.subject_combo.setCurrentIndex(idx)
            if isinstance(self._context.get("op_start"), QDateTime):
                self.start_edit.setDateTime(self._context["op_start"])
            else:
                self.start_edit.setDateTime(_now_local())

    def _on_type_changed(self, btn: QWidget | None) -> None:
        if btn is None:
            return
        type_name = btn.text().split()[0].lower()
        options = self._subject_options.get(type_name, [])
        self.subject_combo.clear()
        if options:
            self.subject_combo.addItems(options)
        else:
            self.subject_combo.addItem("(Select)")

    def _on_accept(self) -> None:
        subject = self.subject_combo.currentText().strip()
        if not subject or subject == "(Select)":
            QMessageBox.warning(self, "Validation", "Select who the log is for.")
            return
        log_type = "team"
        if self.individual_btn.isChecked():
            log_type = "individual"
        elif self.section_btn.isChecked():
            log_type = "section"
        elif self.facility_btn.isChecked():
            log_type = "facility"
        self._result = LogHeader(
            log_for_type=log_type,
            log_for_label=subject,
            unit_or_resource=self.unit_edit.text().strip(),
            operational_period=self.op_combo.currentText(),
            start=self.start_edit.dateTime(),
            notes=self.notes_edit.text().strip(),
        )
        self.accept()


class Ics214ActivityLogPanel(QWidget):
    """Main QWidget implementing the ICS-214 Activity Log workspace."""

    def __init__(
        self,
        incident_id: Any | None = None,
        parent: QWidget | None = None,
        *,
        services: Any | None = None,
        styles: Any | None = None,
        launch_context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.services = services
        self.styles = styles
        self.launch_context = launch_context or {}
        self.prepared_by_hint: str | None = self.launch_context.get(
            "default_prepared_by_position"
        )
        self.header = LogHeader(
            log_for_type="team",
            log_for_label="Team — G-12 (Ground)",
            unit_or_resource="Team G-12",
            operational_period="2025-09-21 (Day)",
            status="OPEN",
            version=4,
            prepared_by_name="Jane Smith",
            prepared_by_position="Ops",
            start=QDateTime.fromString("2025-09-21T06:00:00", Qt.ISODate),
            notes="Operational period day shift.",
        )
        self._current_log_id = self.header.identifier
        self.entries: list[LogEntry] = []
        self.drafts: list[DraftEntry] = []
        self.subject_options: dict[str, list[str]] = {}
        self.known_logs: dict[str, dict[str, Any]] = {}
        self._last_saved: QDateTime | None = None
        self._build_ui()
        self._load_demo_data()
        if self.launch_context:
            self.apply_launch_context(self.launch_context)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        self.title_label = QLabel("ICS 214 — Activity Log", self)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search")
        self.search_edit.textChanged.connect(self._apply_search_filter)
        title_row.addWidget(self.search_edit)
        layout.addLayout(title_row)

        selector_row = QHBoxLayout()
        self.incident_combo = QComboBox(self)
        self.op_combo = QComboBox(self)
        self.op_combo.currentTextChanged.connect(self._on_operational_period_changed)
        self.log_combo = QComboBox(self)
        self.log_combo.currentIndexChanged.connect(self._on_log_changed)
        self.new_log_btn = QPushButton("New Log", self)
        self.new_log_btn.clicked.connect(self._open_new_log_dialog)
        selector_row.addWidget(QLabel("Incident:", self))
        selector_row.addWidget(self.incident_combo)
        selector_row.addWidget(QLabel("OP:", self))
        selector_row.addWidget(self.op_combo)
        selector_row.addWidget(QLabel("Log:", self))
        selector_row.addWidget(self.log_combo)
        selector_row.addWidget(self.new_log_btn)
        layout.addLayout(selector_row)

        actions_row = QHBoxLayout()
        self.review_btn = QPushButton("Review Drafts • 0", self)
        self.review_btn.clicked.connect(self._open_drafts_tray)
        self.export_btn = QPushButton("Export", self)
        self.export_menu = self._build_export_menu()
        self.export_btn.setMenu(self.export_menu)
        self.print_btn = QPushButton("Print", self)
        self.print_btn.clicked.connect(self._on_print)
        self.filters_btn = QPushButton("Filters", self)
        self.filters_btn.clicked.connect(self._on_filters)
        actions_row.addWidget(self.review_btn)
        actions_row.addWidget(self.export_btn)
        actions_row.addWidget(self.print_btn)
        actions_row.addStretch(1)
        actions_row.addWidget(self.filters_btn)
        layout.addLayout(actions_row)

        self.header_frame = self._build_header_card()
        layout.addWidget(self.header_frame)

        entries_label = QLabel("Entries", self)
        entries_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(entries_label)

        self.entries_table = QTableWidget(self)
        self.entries_table.setColumnCount(6)
        self.entries_table.setHorizontalHeaderLabels(
            ["#", "Time (Local)", "Activity", "Source", "Links", "⋯"]
        )
        header = self.entries_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.entries_table.verticalHeader().setVisible(False)
        self.entries_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.entries_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.entries_table.cellDoubleClicked.connect(self._open_editor_for_row)
        self.entries_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.entries_table.customContextMenuRequested.connect(self._show_table_menu)
        layout.addWidget(self.entries_table)

        self.quick_frame = QFrame(self)
        quick_layout = QHBoxLayout(self.quick_frame)
        quick_layout.setContentsMargins(4, 4, 4, 4)
        quick_layout.addWidget(QLabel("+ Add entry…", self.quick_frame))
        self.quick_time = QDateTimeEdit(self.quick_frame)
        self.quick_time.setDisplayFormat("MM/dd HH:mm")
        self.quick_time.setDateTime(_now_local())
        self.quick_location = QLineEdit(self.quick_frame)
        self.quick_location.setPlaceholderText("Location")
        self.quick_activity = QLineEdit(self.quick_frame)
        self.quick_activity.setPlaceholderText("Activity summary")
        self.quick_add_btn = QPushButton("Add", self.quick_frame)
        self.quick_add_btn.clicked.connect(self._on_quick_add)
        for widget in (
            self.quick_time,
            self.quick_location,
            self.quick_activity,
            self.quick_add_btn,
        ):
            quick_layout.addWidget(widget)
        layout.addWidget(self.quick_frame)

        footer = QHBoxLayout()
        self.rows_label = QLabel("Rows: 0", self)
        footer.addWidget(self.rows_label)
        footer.addStretch(1)
        self.edit_header_btn = QPushButton("Edit Header", self)
        self.edit_header_btn.clicked.connect(self._edit_header)
        self.close_log_btn = QPushButton("Close Log", self)
        self.close_log_btn.clicked.connect(self._close_log)
        self.reopen_btn = QPushButton("Re-open", self)
        self.reopen_btn.clicked.connect(self._reopen_log)
        self.last_saved_label = QLabel("Last saved —", self)
        footer.addWidget(self.edit_header_btn)
        footer.addWidget(self.close_log_btn)
        footer.addWidget(self.reopen_btn)
        footer.addWidget(self.last_saved_label)
        layout.addLayout(footer)

    def _build_header_card(self) -> QWidget:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        grid = QGridLayout(frame)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(16)
        self.header_log_for = QLabel(frame)
        self.header_status = QLabel(frame)
        self.header_version = QLabel(frame)
        self.header_prepared = QLabel(frame)
        self.header_start = QLabel(frame)
        self.header_end = QLabel(frame)
        self.header_notes = QLabel(frame)
        self.header_notes.setWordWrap(True)

        grid.addWidget(self.header_log_for, 0, 0)
        grid.addWidget(self.header_status, 0, 1)
        grid.addWidget(self.header_version, 0, 2)
        grid.addWidget(self.header_prepared, 1, 0)
        grid.addWidget(self.header_start, 1, 1)
        grid.addWidget(self.header_end, 1, 2)
        grid.addWidget(self.header_notes, 2, 0, 1, 3)
        return frame

    def _build_export_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Export CSV", lambda: self._on_export("CSV"))
        menu.addAction("Export JSON", lambda: self._on_export("JSON"))
        return menu

    def _load_demo_data(self) -> None:
        incidents = ["Fall Creek SAR", "Elk River Fire", "Rescue Drill 2025"]
        self.incident_combo.addItems(incidents)
        if incidents:
            self.incident_combo.setCurrentIndex(0)
        ops = [
            "2025-09-21 (Day)",
            "2025-09-21 (Night)",
            "2025-09-22 (Day)",
        ]
        self.op_combo.addItems(ops)
        self.op_combo.setCurrentText(self.header.operational_period)

        subjects = {
            "individual": ["Jane Smith", "Alex Kim"],
            "team": ["Team G-12", "Team M-21"],
            "section": [
                "Command",
                "Planning",
                "Operations",
                "Logistics",
                "Communications",
            ],
            "facility": ["ICP", "Base Camp"],
        }
        self.subject_options = subjects

        self.known_logs.clear()
        self.known_logs[self.header.identifier] = {
            "header": self.header.clone(),
            "entries": [],
            "drafts": [],
        }
        self.log_combo.addItem(self._log_display_text(self.header), self.header.identifier)

        self.entries = [
            LogEntry(
                entry_id=12,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T07:14:00", Qt.ISODate),
                    activity="Departed ICP enroute to Search Area 2",
                    source="auto_task",
                    links=["Task G-21"],
                ),
            ),
            LogEntry(
                entry_id=13,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T07:45:00", Qt.ISODate),
                    activity="Arrived AO; begin hasty search along creek trail",
                    source="auto_status",
                ),
            ),
            LogEntry(
                entry_id=14,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T08:02:00", Qt.ISODate),
                    activity="Radio: brief comms check",
                    source="auto_comms",
                    links=["CH: TAC-2"],
                ),
            ),
            LogEntry(
                entry_id=15,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T08:27:00", Qt.ISODate),
                    activity="Located footprints E of bridge; shift search grid",
                    source="manual",
                    links=["Task G-21"],
                    location="East of bridge, S bank",
                ),
            ),
            LogEntry(
                entry_id=16,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T08:59:00", Qt.ISODate),
                    activity="Water crossing; safety pause 5 min",
                    source="manual",
                ),
            ),
        ]

        self.drafts = [
            DraftEntry(
                draft_id=1,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T09:14:00", Qt.ISODate),
                    activity="Departed ICP enroute to Search Area 3",
                    source="auto_task",
                    links=["Task G-22"],
                ),
            ),
            DraftEntry(
                draft_id=2,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T09:45:00", Qt.ISODate),
                    activity="Status update: arrived search block B",
                    source="auto_status",
                ),
            ),
            DraftEntry(
                draft_id=3,
                data=EntryData(
                    timestamp=QDateTime.fromString("2025-09-21T09:52:00", Qt.ISODate),
                    activity="Radio: comms check",
                    source="auto_comms",
                    links=["CH: TAC-2"],
                ),
            ),
        ]
        self._update_header_card()
        self._refresh_table()
        self._update_review_button()
        self._update_footer()

    def _apply_search_filter(self, _: str) -> None:
        search = self.search_edit.text().strip().lower()
        for row in range(self.entries_table.rowCount()):
            activity_item = self.entries_table.item(row, 2)
            links_item = self.entries_table.item(row, 4)
            haystack = ""
            if activity_item:
                haystack += activity_item.text()
            if links_item:
                haystack += " " + links_item.text()
            visible = search in haystack.lower()
            self.entries_table.setRowHidden(row, not visible)
        self._update_rows_label()

    def _refresh_table(self) -> None:
        self.entries.sort(key=lambda e: e.data.timestamp)
        self.entries_table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            self._populate_row(row, entry)
        self._apply_search_filter(self.search_edit.text())
        self._update_rows_label()

    def _populate_row(self, row: int, entry: LogEntry) -> None:
        data = entry.data
        num_item = QTableWidgetItem(str(entry.entry_id))
        time_item = QTableWidgetItem(format_local_time(data.timestamp))
        activity_lines = [data.activity]
        if data.location:
            activity_lines.append(data.location)
        activity_item = QTableWidgetItem("\n".join(activity_lines))
        source_item = QTableWidgetItem(data.source)
        links_item = QTableWidgetItem(", ".join(data.links) if data.links else "—")
        gear_item = QTableWidgetItem("⋯")
        gear_item.setTextAlignment(Qt.AlignCenter)
        for col, item in enumerate(
            [num_item, time_item, activity_item, source_item, links_item, gear_item]
        ):
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            self.entries_table.setItem(row, col, item)

    def _update_header_card(self) -> None:
        header = self.header
        self.header_log_for.setText(
            f"Log For: {header.log_for_type.title()} — {header.log_for_label}"
        )
        self.header_status.setText(f"Status: {header.status}")
        self.header_version.setText(f"Version: {header.version}")
        prepared = (
            f"Prepared By: {header.prepared_by_name} ({header.prepared_by_position})"
            if header.is_prepared()
            else "Prepared By: —"
        )
        self.header_prepared.setText(prepared)
        self.header_start.setText(f"Start: {format_header_time(header.start)}")
        self.header_end.setText(f"End: {format_header_time(header.end)}")
        notes = header.notes or "—"
        self.header_notes.setText(f"Notes: {notes}")
        editable = header.status != "CLOSED"
        self.reopen_btn.setEnabled(not editable)
        self.close_log_btn.setEnabled(editable)
        self.quick_frame.setEnabled(editable)
        self._update_print_button_state()

    def _update_print_button_state(self) -> None:
        self.print_btn.setEnabled(self.header.is_prepared())

    def _update_review_button(self) -> None:
        count = len(self.drafts)
        self.review_btn.setText(f"Review Drafts • {count}")
        self.review_btn.setEnabled(count > 0)

    def _update_footer(self) -> None:
        self._update_rows_label()
        if self._last_saved and self._last_saved.isValid():
            self.last_saved_label.setText(
                f"Last saved {self._last_saved.toString('HH:mm')}"
            )
        else:
            self.last_saved_label.setText("Last saved —")

    def _update_rows_label(self) -> None:
        visible = sum(
            not self.entries_table.isRowHidden(row)
            for row in range(self.entries_table.rowCount())
        )
        total = self.entries_table.rowCount()
        if visible == total:
            self.rows_label.setText(f"Rows: {total}")
        else:
            self.rows_label.setText(f"Rows: {visible} / {total}")

    def _touch(self) -> None:
        self._last_saved = _now_local()
        self._update_footer()

    def _next_entry_id(self) -> int:
        return max((entry.entry_id for entry in self.entries), default=0) + 1

    def _open_editor_for_row(self, row: int, column: int) -> None:
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        dialog = EntryEditorDialog(entry.data, self, title=f"Edit Entry #{entry.entry_id}")
        if dialog.exec() == QDialog.Accepted:
            entry.data = dialog.result.clone()
            self._populate_row(row, entry)
            self._bump_version()

    def _show_table_menu(self, pos: QPoint) -> None:
        if not self.entries:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit")
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.entries_table.viewport().mapToGlobal(pos))
        if action == edit_action:
            rows = {index.row() for index in self.entries_table.selectedIndexes()}
            if not rows:
                row = self.entries_table.rowAt(pos.y())
                rows = {row} if row >= 0 else set()
            for row in rows:
                self._open_editor_for_row(row, 0)
        elif action == duplicate_action:
            self._duplicate_selected()
        elif action == delete_action:
            self._delete_selected()

    def _duplicate_selected(self) -> None:
        rows = sorted({index.row() for index in self.entries_table.selectedIndexes()})
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self.entries):
                entry = self.entries[row]
                clone = LogEntry(
                    entry_id=self._next_entry_id(),
                    data=entry.data.clone(),
                )
                self.entries.append(clone)
        self._refresh_table()
        self._bump_version()

    def _delete_selected(self) -> None:
        rows = sorted({index.row() for index in self.entries_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self.entries):
                self.entries.pop(row)
        self._refresh_table()
        self._bump_version()

    def _on_quick_add(self) -> None:
        if self.header.status == "CLOSED":
            QMessageBox.information(self, "Log Closed", "Re-open the log to add entries.")
            return
        activity = self.quick_activity.text().strip()
        if not activity:
            QMessageBox.warning(self, "Validation", "Activity description is required.")
            return
        entry = LogEntry(
            entry_id=self._next_entry_id(),
            data=EntryData(
                timestamp=self.quick_time.dateTime(),
                activity=activity,
                location=self.quick_location.text().strip(),
            ),
        )
        self.entries.append(entry)
        self.quick_activity.clear()
        self.quick_location.clear()
        self.quick_time.setDateTime(_now_local())
        self._refresh_table()
        self._bump_version()

    def _on_operational_period_changed(self, text: str) -> None:
        self.header.operational_period = text
        self._bump_version(update_timestamp=False)
        self._update_known_log()

    def _open_drafts_tray(self) -> None:
        if not self.drafts:
            return
        dialog = DraftsTrayDialog([draft for draft in self.drafts], self)
        dialog.entryAccepted.connect(self._accept_draft)
        dialog.entryDiscarded.connect(self._discard_draft)
        dialog.acceptAllRequested.connect(self._accept_all_drafts)
        dialog.exec()

    def _accept_draft(self, draft: DraftEntry) -> None:
        draft_copy = draft.data.clone()
        entry = LogEntry(entry_id=self._next_entry_id(), data=draft_copy)
        self.entries.append(entry)
        self._remove_draft(draft)
        self._refresh_table()
        self._bump_version()

    def _discard_draft(self, draft: DraftEntry) -> None:
        self._remove_draft(draft)
        self._update_review_button()

    def _accept_all_drafts(self, drafts: list[DraftEntry]) -> None:
        added = False
        for draft in drafts:
            entry = LogEntry(entry_id=self._next_entry_id(), data=draft.data.clone())
            self.entries.append(entry)
            self._remove_draft(draft)
            added = True
        if added:
            self._refresh_table()
            self._bump_version()

    def _remove_draft(self, draft: DraftEntry) -> None:
        for existing in list(self.drafts):
            if existing.draft_id == draft.draft_id:
                self.drafts.remove(existing)
                break
        self._update_review_button()

    def _close_log(self) -> None:
        if self.header.status == "CLOSED":
            return
        self.header.status = "CLOSED"
        self.header.end = _now_local()
        self._bump_version()

    def _reopen_log(self) -> None:
        if self.header.status != "CLOSED":
            return
        self.header.status = "OPEN"
        self.header.end = None
        self._bump_version()

    def _edit_header(self) -> None:
        ops = [self.op_combo.itemText(i) for i in range(self.op_combo.count())]
        dialog = NewLogDialog(
            self.header.clone(),
            self.subject_options,
            ops,
            self,
            context=self.launch_context,
        )
        if dialog.exec() == QDialog.Accepted and dialog.result:
            updated = dialog.result.clone()
            updated.identifier = self.header.identifier
            updated.status = self.header.status
            updated.version = self.header.version
            updated.prepared_by_name = self.header.prepared_by_name
            updated.prepared_by_position = self.header.prepared_by_position
            updated.end = self.header.end
            self._set_header(updated)
            self._bump_version()

    def _open_new_log_dialog(self) -> None:
        ops = [self.op_combo.itemText(i) for i in range(self.op_combo.count())]
        context = dict(self.launch_context)
        context.setdefault("op_start", self.header.start)
        dialog = NewLogDialog(None, self.subject_options, ops, self, context=context)
        if dialog.exec() == QDialog.Accepted and dialog.result:
            self._update_known_log()
            new_header = dialog.result.clone()
            new_header.status = "OPEN"
            new_header.version = 1
            new_header.prepared_by_name = None
            new_header.prepared_by_position = None
            new_header.end = None
            self.header = new_header
            self.entries = []
            self.drafts = []
            self._last_saved = None
            display = self._log_display_text(new_header)
            self.log_combo.addItem(display, new_header.identifier)
            self.log_combo.setCurrentIndex(self.log_combo.count() - 1)
            self._current_log_id = new_header.identifier
            self._update_header_card()
            self._refresh_table()
            self._update_review_button()
            self._update_known_log()

    def _on_log_changed(self, index: int) -> None:
        if index < 0:
            return
        log_id = self.log_combo.itemData(index)
        if not log_id:
            return
        if getattr(self, "_current_log_id", None) == log_id:
            return
        self._update_known_log()
        self._current_log_id = log_id
        self._apply_log_state(log_id)

    def _apply_log_state(self, log_id: str) -> None:
        record = self.known_logs.get(log_id)
        if not record:
            return
        self.header = record["header"].clone()
        self.entries = [
            LogEntry(entry.entry_id, entry.data.clone())
            for entry in record["entries"]
        ]
        self.drafts = [
            DraftEntry(draft.draft_id, draft.data.clone(), draft.selected)
            for draft in record["drafts"]
        ]
        display = self._log_display_text(self.header)
        current_idx = self.log_combo.currentIndex()
        if current_idx >= 0:
            self.log_combo.setItemText(current_idx, display)
        self.op_combo.setCurrentText(self.header.operational_period)
        saved = record.get("last_saved")
        self._last_saved = QDateTime(saved) if isinstance(saved, QDateTime) else None
        self._update_header_card()
        self._refresh_table()
        self._update_review_button()
        self._update_footer()

    def _update_known_log(self) -> None:
        if not getattr(self, "_current_log_id", None):
            self._current_log_id = self.header.identifier
        self.known_logs[self.header.identifier] = {
            "header": self.header.clone(),
            "entries": [
                LogEntry(entry.entry_id, entry.data.clone()) for entry in self.entries
            ],
            "drafts": [
                DraftEntry(draft.draft_id, draft.data.clone(), draft.selected)
                for draft in self.drafts
            ],
            "last_saved": QDateTime(self._last_saved) if self._last_saved else None,
        }

    def _log_display_text(self, header: LogHeader) -> str:
        return f"{header.log_for_label} ({header.operational_period})"

    def _on_export(self, fmt: str) -> None:
        message = (
            f"{fmt} export queued for {self._log_display_text(self.header)}."
            "\n(Stub implementation)"
        )
        QMessageBox.information(self, "Export", message)

    def _on_print(self) -> None:
        if not self.header.is_prepared():
            if not self._open_prepared_by_dialog():
                return
        QMessageBox.information(
            self,
            "Print",
            "PDF rendering pipeline placeholder — will generate ICS-214 PDF.",
        )

    def _on_filters(self) -> None:
        QMessageBox.information(
            self,
            "Filters",
            "Filter dialog placeholder — source toggles and time range forthcoming.",
        )

    def _open_prepared_by_dialog(self) -> bool:
        dialog = PreparedByDialog(
            self.header.prepared_by_name,
            self.header.prepared_by_position,
            self,
            position_hint=self.prepared_by_hint,
        )
        if dialog.exec() == QDialog.Accepted and dialog.result:
            name, position = dialog.result
            self.header.prepared_by_name = name
            self.header.prepared_by_position = position
            self._bump_version()
            return True
        return False

    def _set_header(self, header: LogHeader) -> None:
        self.header = header
        self._update_header_card()
        display = self._log_display_text(header)
        index = self.log_combo.currentIndex()
        if index >= 0:
            self.log_combo.setItemText(index, display)
        self._update_known_log()

    def _bump_version(self, update_timestamp: bool = True) -> None:
        self.header.version += 1
        if update_timestamp:
            self._touch()
        self._update_header_card()
        self._update_known_log()

    def apply_launch_context(self, context: dict[str, Any]) -> None:
        self.launch_context = context
        self.prepared_by_hint = context.get("default_prepared_by_position", self.prepared_by_hint)
        log_type = context.get("default_log_for_type")
        if log_type:
            self.header.log_for_type = log_type.lower()
        ref = context.get("default_log_for_ref")
        if ref:
            self.header.log_for_label = str(ref)
        op = context.get("default_operational_period")
        if op:
            self.header.operational_period = str(op)
            self.op_combo.setCurrentText(self.header.operational_period)
        filters = context.get("default_filters")
        if filters and not self.search_edit.text():
            sources = ", ".join(filters.get("source", []))
            if sources:
                self.header.notes = f"Filters applied: {sources}"
        idx = self.log_combo.currentIndex()
        if idx >= 0:
            self.log_combo.setItemText(idx, self._log_display_text(self.header))
        self._update_header_card()
        self._refresh_table()
        self._update_review_button()
        self._update_known_log()
