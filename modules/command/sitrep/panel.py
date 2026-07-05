"""Situation Report (ICS-209) panel — 5-tab interface."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    QTimer,
)
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from utils import incident_context
from utils.app_signals import app_signals

from .models import (
    AUDIENCES,
    EVENT_TYPES,
    IMPACT_LEVELS,
    MVP_SECTION_TYPES,
    SECTION_TITLES,
    SITREP_STATUSES,
    TEMPOS,
    VISIBILITIES,
    Sitrep,
    SitrepApiClient,
    SitrepEvent,
    SitrepSection,
    SitrepSummary,
)

logger = logging.getLogger(__name__)

_STATUS_COLORS = {
    "draft": "#888888",
    "ready_for_review": "#d4a017",
    "needs_revision": "#c0392b",
    "approved": "#27ae60",
    "distributed": "#2980b9",
    "archived": "#7f8c8d",
}

_VISIBILITY_COLORS = {
    "internal": "#2c3e50",
    "agency": "#8e44ad",
    "public": "#27ae60",
    "sensitive": "#c0392b",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _current_op_period_id() -> Optional[str]:
    """Return the active operational period id/number from app state, if any."""
    from utils.state import AppState

    op = AppState.get_active_op_period()
    if isinstance(op, dict):
        val = op.get("id") or op.get("number")
    else:
        val = op
    return str(val) if val not in (None, "") else None


def _op_payload() -> dict:
    """Payload fragment carrying the active OP; empty when none is set so
    duplication keeps the source SITREP's operational period."""
    op = _current_op_period_id()
    return {"operational_period_id": op} if op else {}


def _apply_table_standards(table: QTableView, stretch_column: int) -> None:
    """User-resizable columns + outlined selected row, per repo table standards."""
    hdr = table.horizontalHeader()
    hdr.setStretchLastSection(False)
    hdr.setSectionResizeMode(QHeaderView.Interactive)
    hdr.setSectionResizeMode(stretch_column, QHeaderView.Stretch)
    hdr.setSectionsMovable(True)
    table.setStyleSheet("QTableView { selection-background-color: transparent; }")
    try:
        from utils.itemview_delegates import RowOutlineSelectionDelegate
        from utils.styles import get_palette

        pal = get_palette()
        color = pal.get("ctrl_focus", pal.get("accent"))
        table.setItemDelegate(RowOutlineSelectionDelegate(table, color))
    except Exception:
        logger.exception("Failed to install row outline delegate")


def _label_pill(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background:{color};color:#fff;border-radius:3px;padding:1px 6px;font-size:11px;font-weight:600;"
    )
    lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lbl


# ---------------------------------------------------------------------------
# Event table model
# ---------------------------------------------------------------------------

_EVENT_COLS = ["Time", "Type", "Summary", "Source", "Impact", "Visibility", "In SITREP"]


class EventTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._events: list[SitrepEvent] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_EVENT_COLS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _EVENT_COLS[section] if 0 <= section < len(_EVENT_COLS) else None
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        ev = self._events[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return ev.timestamp[:16].replace("T", " ") if ev.timestamp else ""
            if col == 1:
                return ev.event_type
            if col == 2:
                return ev.summary
            if col == 3:
                return ev.source
            if col == 4:
                return ev.impact.title()
            if col == 5:
                return ev.visibility.title()
            if col == 6:
                return "Yes" if ev.include_in_sitrep else "No"
        if role == Qt.ForegroundRole and col == 5:
            color = _VISIBILITY_COLORS.get(ev.visibility, "#000")
            return QColor(color)
        if role == Qt.UserRole:
            return ev.id
        return None

    def set_events(self, events: list[SitrepEvent]) -> None:
        self.beginResetModel()
        self._events = list(events)
        self.endResetModel()

    def event_for_row(self, row: int) -> Optional[SitrepEvent]:
        if 0 <= row < len(self._events):
            return self._events[row]
        return None


# ---------------------------------------------------------------------------
# Archive table model
# ---------------------------------------------------------------------------

_ARCHIVE_COLS = ["#", "Prepared", "OP", "By", "Status", "Audience", "Summary"]


class ArchiveTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[SitrepSummary] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_ARCHIVE_COLS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return _ARCHIVE_COLS[section] if 0 <= section < len(_ARCHIVE_COLS) else None
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return str(row.sitrep_number).zfill(3)
            if col == 1:
                return row.created_at[:16].replace("T", " ") if row.created_at else ""
            if col == 2:
                return row.operational_period_id or ""
            if col == 3:
                return row.prepared_by
            if col == 4:
                return dict(SITREP_STATUSES).get(row.status, row.status)
            if col == 5:
                return dict(AUDIENCES).get(row.audience, row.audience)
            if col == 6:
                return row.summary[:80] + "…" if len(row.summary) > 80 else row.summary
        if role == Qt.ForegroundRole and col == 4:
            return QColor(_STATUS_COLORS.get(row.status, "#000"))
        if role == Qt.UserRole:
            return row.id
        return None

    def set_rows(self, rows: list[SitrepSummary]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def summary_for_row(self, row: int) -> Optional[SitrepSummary]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


# ---------------------------------------------------------------------------
# Event Dialog
# ---------------------------------------------------------------------------

class EventDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, event: Optional[SitrepEvent] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Significant Event" if event is None else "Edit Event")
        self.setMinimumWidth(480)
        self._result_payload: Optional[dict] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._timestamp = QLineEdit(_now_iso()[:16])
        form.addRow("Time (ISO):", self._timestamp)

        self._event_type = QComboBox()
        self._event_type.addItems(EVENT_TYPES)
        form.addRow("Event Type:", self._event_type)

        self._summary = QLineEdit()
        self._summary.setPlaceholderText("Brief summary")
        form.addRow("Summary:", self._summary)

        self._source = QLineEdit()
        self._source.setPlaceholderText("e.g. Operations, Weather, Intel")
        form.addRow("Source:", self._source)

        self._impact = QComboBox()
        self._impact.addItems([i.title() for i in IMPACT_LEVELS])
        form.addRow("Impact:", self._impact)

        self._visibility = QComboBox()
        for val, label in VISIBILITIES:
            self._visibility.addItem(label, val)
        form.addRow("Visibility:", self._visibility)

        self._in_sitrep = QCheckBox("Include in SITREP")
        self._in_sitrep.setChecked(True)
        self._in_214 = QCheckBox("Include in ICS-214")
        h = QHBoxLayout()
        h.addWidget(self._in_sitrep)
        h.addWidget(self._in_214)
        form.addRow("", h)

        self._notes = QTextEdit()
        self._notes.setMaximumHeight(80)
        self._notes.setPlaceholderText("Additional notes…")
        form.addRow("Notes:", self._notes)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if event:
            self._timestamp.setText(event.timestamp[:16])
            idx = EVENT_TYPES.index(event.event_type) if event.event_type in EVENT_TYPES else 0
            self._event_type.setCurrentIndex(idx)
            self._summary.setText(event.summary)
            self._source.setText(event.source)
            impact_idx = IMPACT_LEVELS.index(event.impact) if event.impact in IMPACT_LEVELS else 0
            self._impact.setCurrentIndex(impact_idx)
            for i in range(self._visibility.count()):
                if self._visibility.itemData(i) == event.visibility:
                    self._visibility.setCurrentIndex(i)
                    break
            self._in_sitrep.setChecked(event.include_in_sitrep)
            self._in_214.setChecked(event.include_in_214)
            self._notes.setPlainText(event.notes)

    def _accept(self) -> None:
        if not self._summary.text().strip():
            QMessageBox.warning(self, "Validation", "Summary is required.")
            return
        ts = self._timestamp.text().strip()
        if len(ts) == 16:
            ts = ts + ":00+00:00"
        self._result_payload = {
            "timestamp": ts,
            "event_type": self._event_type.currentText(),
            "summary": self._summary.text().strip(),
            "source": self._source.text().strip(),
            "impact": IMPACT_LEVELS[self._impact.currentIndex()],
            "visibility": self._visibility.currentData(),
            "include_in_sitrep": self._in_sitrep.isChecked(),
            "include_in_214": self._in_214.isChecked(),
            "notes": self._notes.toPlainText().strip(),
        }
        self.accept()

    def payload(self) -> Optional[dict]:
        return self._result_payload


# ---------------------------------------------------------------------------
# Section editor (used in Current SITREP center pane)
# ---------------------------------------------------------------------------

class SectionEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self._title_lbl = QLabel()
        f = self._title_lbl.font()
        f.setPointSize(12)
        f.setBold(True)
        self._title_lbl.setFont(f)
        header.addWidget(self._title_lbl)
        header.addStretch()

        self._visibility_combo = QComboBox()
        for val, label in VISIBILITIES:
            self._visibility_combo.addItem(label, val)
        header.addWidget(QLabel("Visibility:"))
        header.addWidget(self._visibility_combo)

        self._review_lbl = QLabel()
        self._review_lbl.setStyleSheet("color:#888;font-size:11px;")
        header.addWidget(self._review_lbl)
        layout.addLayout(header)

        auto_lbl = QLabel("Auto-filled content:")
        auto_lbl.setStyleSheet("color:#666;font-size:11px;")
        layout.addWidget(auto_lbl)

        self._auto_text = QTextEdit()
        self._auto_text.setReadOnly(True)
        self._auto_text.setMaximumHeight(100)
        self._auto_text.setPlaceholderText("(no auto content — click Refresh From Modules)")
        self._auto_text.setStyleSheet("background:#f5f5f5;color:#555;font-size:11px;")
        layout.addWidget(self._auto_text)

        insert_btn = QPushButton("Insert Auto-Content →")
        insert_btn.clicked.connect(self._insert_auto)
        layout.addWidget(insert_btn)

        edit_lbl = QLabel("Narrative / edited content:")
        edit_lbl.setStyleSheet("color:#666;font-size:11px;")
        layout.addWidget(edit_lbl)

        self._edit_text = QTextEdit()
        self._edit_text.setPlaceholderText("Enter or edit the section narrative here…")
        layout.addWidget(self._edit_text)

        self._section: Optional[SitrepSection] = None

    def load(self, section: SitrepSection) -> None:
        self._section = section
        self._title_lbl.setText(section.title)
        self._auto_text.setPlainText(section.auto_content)
        self._edit_text.setPlainText(section.edited_content)
        for i in range(self._visibility_combo.count()):
            if self._visibility_combo.itemData(i) == section.visibility:
                self._visibility_combo.setCurrentIndex(i)
                break
        self._review_lbl.setText(section.review_status.replace("_", " ").title())

    def collect(self) -> dict:
        return {
            "edited_content": self._edit_text.toPlainText(),
            "visibility": self._visibility_combo.currentData() or "internal",
            "review_status": "edited" if self._edit_text.toPlainText() else "auto_filled",
        }

    def set_auto(self, section: SitrepSection) -> None:
        """Update the auto-filled pane without touching the user's narrative edits."""
        self._section = section
        self._auto_text.setPlainText(section.auto_content)
        self._review_lbl.setText(section.review_status.replace("_", " ").title())

    def _insert_auto(self) -> None:
        auto = self._auto_text.toPlainText()
        if auto:
            self._edit_text.setPlainText(auto)


# ---------------------------------------------------------------------------
# Tab 1: Current SITREP
# ---------------------------------------------------------------------------

class CurrentSitrepTab(QWidget):
    def __init__(self, panel: "SitrepPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._sitrep: Optional[Sitrep] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Header bar ---
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_frame.setStyleSheet("QFrame{background:#1e2a38;}")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 6, 8, 6)

        self._sitrep_num_lbl = QLabel("SITREP —")
        self._sitrep_num_lbl.setStyleSheet("color:#fff;font-size:14px;font-weight:700;")
        header_layout.addWidget(self._sitrep_num_lbl)

        self._op_lbl = QLabel("OP —")
        self._op_lbl.setStyleSheet("color:#aaa;font-size:12px;")
        header_layout.addWidget(self._op_lbl)

        header_layout.addStretch()

        self._status_lbl = QLabel("Draft")
        self._status_lbl.setStyleSheet("color:#888;font-size:12px;font-weight:600;")
        header_layout.addWidget(QLabel("Status:"))
        header_layout.addWidget(self._status_lbl)

        self._audience_combo = QComboBox()
        for val, label in AUDIENCES:
            self._audience_combo.addItem(label, val)
        header_layout.addWidget(QLabel("Audience:"))
        header_layout.addWidget(self._audience_combo)

        refresh_btn = QPushButton("Refresh From Modules")
        refresh_btn.clicked.connect(self._refresh_from_modules)
        header_layout.addWidget(refresh_btn)

        root.addWidget(header_frame)

        # --- Metadata row ---
        meta_frame = QFrame()
        meta_frame.setStyleSheet("background:#263545;")
        meta_layout = QHBoxLayout(meta_frame)
        meta_layout.setContentsMargins(8, 4, 8, 4)

        self._priority_combo = QComboBox()
        self._priority_combo.addItems(["", "High", "Medium", "Low", "Life Safety"])
        meta_layout.addWidget(QLabel("Priority:"))
        meta_layout.addWidget(self._priority_combo)

        self._tempo_combo = QComboBox()
        for val, label in TEMPOS:
            self._tempo_combo.addItem(label, val)
        meta_layout.addWidget(QLabel("Tempo:"))
        meta_layout.addWidget(self._tempo_combo)

        self._prepared_by = QLineEdit()
        self._prepared_by.setPlaceholderText("Prepared by…")
        self._prepared_by.setMaximumWidth(200)
        meta_layout.addWidget(QLabel("By:"))
        meta_layout.addWidget(self._prepared_by)

        self._next_update = QLineEdit()
        self._next_update.setPlaceholderText("Next update (time or datetime)")
        self._next_update.setMaximumWidth(180)
        meta_layout.addWidget(QLabel("Next update:"))
        meta_layout.addWidget(self._next_update)

        for lbl in meta_frame.findChildren(QLabel):
            lbl.setStyleSheet("color:#bbb;font-size:11px;")

        root.addWidget(meta_frame)

        # --- Three-pane splitter ---
        splitter = QSplitter(Qt.Horizontal)

        # Left: section nav
        left = QWidget()
        left.setMaximumWidth(200)
        left.setMinimumWidth(140)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)
        nav_lbl = QLabel("Sections")
        nav_lbl.setStyleSheet("font-weight:700;font-size:11px;color:#888;")
        left_layout.addWidget(nav_lbl)
        self._section_list = QListWidget()
        self._section_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._section_list.currentRowChanged.connect(self._on_section_selected)
        left_layout.addWidget(self._section_list)
        splitter.addWidget(left)

        # Center: section editor stack
        self._editor_stack = QStackedWidget()
        self._editors: list[SectionEditor] = []
        for stype in MVP_SECTION_TYPES:
            editor = SectionEditor()
            self._editor_stack.addWidget(editor)
            self._editors.append(editor)
            item = QListWidgetItem(SECTION_TITLES[stype])
            self._section_list.addItem(item)
        splitter.addWidget(self._editor_stack)

        # Right: fact panel
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMaximumWidth(240)
        right_scroll.setMinimumWidth(180)
        right_inner = QWidget()
        right_layout = QVBoxLayout(right_inner)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(8)

        right_lbl = QLabel("Live Facts")
        right_lbl.setStyleSheet("font-weight:700;font-size:11px;color:#888;")
        right_layout.addWidget(right_lbl)

        self._teams_group = QGroupBox("Teams")
        tg = QVBoxLayout(self._teams_group)
        self._teams_labels: dict[str, QLabel] = {}
        for key in ("active", "available", "enroute", "returning"):
            lbl = QLabel(f"{key.title()}: —")
            lbl.setStyleSheet("font-size:11px;")
            tg.addWidget(lbl)
            self._teams_labels[key] = lbl
        right_layout.addWidget(self._teams_group)

        self._tasks_group = QGroupBox("Tasks")
        tk = QVBoxLayout(self._tasks_group)
        self._task_labels: dict[str, QLabel] = {}
        for key in ("in_progress", "complete", "blocked", "planned"):
            lbl = QLabel(f"{key.replace('_', ' ').title()}: —")
            lbl.setStyleSheet("font-size:11px;")
            tk.addWidget(lbl)
            self._task_labels[key] = lbl
        right_layout.addWidget(self._tasks_group)

        self._alerts_group = QGroupBox("Alerts")
        self._alerts_layout = QVBoxLayout(self._alerts_group)
        self._no_alerts_lbl = QLabel("None")
        self._no_alerts_lbl.setStyleSheet("color:#888;font-size:11px;")
        self._alerts_layout.addWidget(self._no_alerts_lbl)
        right_layout.addWidget(self._alerts_group)

        right_layout.addStretch()
        right_scroll.setWidget(right_inner)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter, 1)

        # --- Action bar ---
        action_frame = QFrame()
        action_frame.setFrameStyle(QFrame.StyledPanel)
        action_layout = QHBoxLayout(action_frame)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(self._save)
        action_layout.addWidget(save_btn)

        review_btn = QPushButton("Ready for Review")
        review_btn.clicked.connect(lambda: self._set_status("ready_for_review"))
        action_layout.addWidget(review_btn)

        approve_btn = QPushButton("Approve")
        approve_btn.clicked.connect(lambda: self._set_status("approved"))
        action_layout.addWidget(approve_btn)

        action_layout.addStretch()

        export_btn = QPushButton("Export Text")
        export_btn.clicked.connect(self._export_text)
        action_layout.addWidget(export_btn)

        archive_btn = QPushButton("Archive")
        archive_btn.clicked.connect(lambda: self._set_status("archived"))
        action_layout.addWidget(archive_btn)

        root.addWidget(action_frame)

        self._section_list.setCurrentRow(0)

    def load_sitrep(self, sitrep: Optional[Sitrep]) -> None:
        self._sitrep = sitrep
        if sitrep is None:
            self._sitrep_num_lbl.setText("SITREP — (none)")
            self._op_lbl.setText("OP —")
            self._status_lbl.setText("—")
            for editor in self._editors:
                editor.load(SitrepSection(section_type="", title=""))
            return

        self._sitrep_num_lbl.setText(f"SITREP #{str(sitrep.sitrep_number).zfill(3)}")
        self._op_lbl.setText(f"OP {sitrep.operational_period_id or '—'}")

        status_text = dict(SITREP_STATUSES).get(sitrep.status, sitrep.status)
        color = _STATUS_COLORS.get(sitrep.status, "#888")
        self._status_lbl.setText(status_text)
        self._status_lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:600;")

        for i, val in enumerate([a[0] for a in AUDIENCES]):
            if val == sitrep.audience:
                self._audience_combo.setCurrentIndex(i)
                break

        self._prepared_by.setText(sitrep.prepared_by)
        self._next_update.setText(sitrep.next_update_due or "")

        for i, val in enumerate([a[0] for a in TEMPOS]):
            if val == sitrep.current_tempo:
                self._tempo_combo.setCurrentIndex(i)
                break

        self._priority_combo.setCurrentText(sitrep.current_priority)

        for i, stype in enumerate(MVP_SECTION_TYPES):
            section = sitrep.section(stype)
            if section is None:
                from .models import SitrepSection as _Sec
                section = _Sec(section_type=stype, title=SECTION_TITLES[stype])
            self._editors[i].load(section)

    def _on_section_selected(self, row: int) -> None:
        if 0 <= row < len(self._editors):
            self._editor_stack.setCurrentIndex(row)

    def _collect_payload(self) -> dict:
        sections = []
        for i, stype in enumerate(MVP_SECTION_TYPES):
            if self._sitrep:
                existing = self._sitrep.section(stype)
            else:
                existing = None
            editor_data = self._editors[i].collect()
            from .models import SitrepSection as _Sec
            sec = _Sec(
                section_type=stype,
                title=SECTION_TITLES[stype],
                auto_content=existing.auto_content if existing else "",
                edited_content=editor_data["edited_content"],
                visibility=editor_data["visibility"],
                review_status=editor_data["review_status"],
            )
            sections.append(sec.to_dict())

        return {
            "prepared_by": self._prepared_by.text().strip(),
            "audience": self._audience_combo.currentData() or "internal",
            "current_priority": self._priority_combo.currentText().strip(),
            "current_tempo": self._tempo_combo.currentData() or "stable",
            "next_update_due": self._next_update.text().strip() or None,
            "sections": sections,
        }

    def _save(self) -> None:
        self._panel._save_current(self._collect_payload())

    def _set_status(self, status: str) -> None:
        payload = self._collect_payload()
        payload["status"] = status
        self._panel._save_current(payload)

    def _export_text(self) -> None:
        if not self._sitrep:
            QMessageBox.warning(self, "Export", "No SITREP loaded.")
            return
        lines = [
            f"SITREP {str(self._sitrep.sitrep_number).zfill(3)}",
            f"Incident: {self._sitrep.incident_id}",
            f"Prepared: {self._sitrep.created_at[:16].replace('T', ' ')}",
            f"By: {self._sitrep.prepared_by}",
            f"Audience: {dict(AUDIENCES).get(self._sitrep.audience, self._sitrep.audience)}",
            f"Status: {dict(SITREP_STATUSES).get(self._sitrep.status, self._sitrep.status)}",
            "",
        ]
        for stype in MVP_SECTION_TYPES:
            section = self._sitrep.section(stype)
            if not section:
                continue
            content = section.display_content.strip()
            if not content:
                continue
            lines.append(f"--- {section.title} ---")
            lines.append(content)
            lines.append("")

        text = "\n".join(lines)
        dialog = QDialog(self)
        dialog.setWindowTitle("SITREP Text Export")
        dialog.setMinimumSize(600, 400)
        dlayout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(text)
        text_edit.setReadOnly(True)
        dlayout.addWidget(text_edit)
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(text))
        dlayout.addWidget(copy_btn)
        dialog.exec()

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def update_auto_contents(self, sitrep: Sitrep) -> None:
        """Refresh header/auto panes from a re-pulled SITREP, preserving edits in progress."""
        self._sitrep = sitrep
        for i, stype in enumerate(MVP_SECTION_TYPES):
            section = sitrep.section(stype)
            if section:
                self._editors[i].set_auto(section)

    def _refresh_from_modules(self) -> None:
        self._panel._refresh_from_modules()


# ---------------------------------------------------------------------------
# Tab 2: Changes / Significant Events
# ---------------------------------------------------------------------------

class EventsTab(QWidget):
    def __init__(self, panel: "SitrepPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel

        layout = QVBoxLayout(self)

        toolbar = QToolBar("Events")
        toolbar.setMovable(False)
        add_action = QAction("New Event", self)
        add_action.triggered.connect(self._add_event)
        toolbar.addAction(add_action)
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._edit_event)
        toolbar.addAction(edit_action)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_event)
        toolbar.addAction(delete_action)
        layout.addWidget(toolbar)

        self._model = EventTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.setAlternatingRowColors(True)
        _apply_table_standards(self._table, stretch_column=2)
        self._table.doubleClicked.connect(self._edit_event)
        layout.addWidget(self._table)

    def load_events(self, events: list[SitrepEvent]) -> None:
        self._model.set_events(events)

    def _current_event(self) -> Optional[SitrepEvent]:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return None
        return self._model.event_for_row(idx.row())

    def _add_event(self) -> None:
        dialog = EventDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.payload():
            self._panel._create_event(dialog.payload())

    def _edit_event(self) -> None:
        ev = self._current_event()
        if not ev:
            return
        dialog = EventDialog(self, event=ev)
        if dialog.exec() == QDialog.Accepted and dialog.payload():
            self._panel._update_event(ev.id, dialog.payload())

    def _delete_event(self) -> None:
        ev = self._current_event()
        if not ev:
            return
        if QMessageBox.question(self, "Delete Event", "Delete this significant event?") == QMessageBox.Yes:
            self._panel._delete_event(ev.id)


# ---------------------------------------------------------------------------
# Tab 3: Operational Summary
# ---------------------------------------------------------------------------

class OperationalSummaryTab(QWidget):
    def __init__(self, panel: "SitrepPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel

        layout = QVBoxLayout(self)

        refresh_btn = QPushButton("Refresh From Modules")
        refresh_btn.clicked.connect(panel._refresh_live_facts)
        layout.addWidget(refresh_btn)

        cols = QHBoxLayout()

        # Resources
        res_group = QGroupBox("Resource Counts")
        rg = QFormLayout(res_group)
        self._stat_labels: dict[str, QLabel] = {}
        for key, label in [
            ("total_checked_in", "Total Checked In"),
            ("teams_active", "Teams Active"),
            ("teams_available", "Teams Available"),
            ("teams_enroute", "Teams Enroute"),
        ]:
            lbl = QLabel("—")
            rg.addRow(label + ":", lbl)
            self._stat_labels[key] = lbl
        cols.addWidget(res_group)

        # Tasks
        task_group = QGroupBox("Task Status")
        tg = QFormLayout(task_group)
        for key, label in [
            ("tasks_planned", "Planned"),
            ("tasks_assigned", "Assigned"),
            ("tasks_in_progress", "In Progress"),
            ("tasks_complete", "Complete"),
            ("tasks_blocked", "Blocked"),
            ("tasks_suspended", "Suspended"),
        ]:
            lbl = QLabel("—")
            tg.addRow(label + ":", lbl)
            self._stat_labels[key] = lbl
        cols.addWidget(task_group)

        # Alerts
        alert_group = QGroupBox("Active Alerts")
        self._alert_vbox = QVBoxLayout(alert_group)
        self._alert_no_lbl = QLabel("None")
        self._alert_no_lbl.setStyleSheet("color:#888;")
        self._alert_vbox.addWidget(self._alert_no_lbl)
        cols.addWidget(alert_group)

        layout.addLayout(cols)

        # Auto-generated summary
        sum_lbl = QLabel("Auto-Generated Summary")
        sum_lbl.setStyleSheet("font-weight:700;")
        layout.addWidget(sum_lbl)

        self._auto_summary = QTextEdit()
        self._auto_summary.setReadOnly(True)
        self._auto_summary.setMaximumHeight(120)
        self._auto_summary.setPlaceholderText("Click Refresh From Modules to generate…")
        layout.addWidget(self._auto_summary)

        insert_btn = QPushButton("Insert Into SITREP (Operational Status Section)")
        insert_btn.clicked.connect(self._insert_into_sitrep)
        layout.addWidget(insert_btn)
        layout.addStretch()

        self._summary_data: dict = {}

    def update_summary(self, data: dict) -> None:
        self._summary_data = data
        teams = data.get("teams", {})
        tasks = data.get("tasks", {})

        self._stat_labels["total_checked_in"].setText(str(data.get("total_checked_in", "—")))
        self._stat_labels["teams_active"].setText(str(teams.get("active", "—")))
        self._stat_labels["teams_available"].setText(str(teams.get("available", "—")))
        self._stat_labels["teams_enroute"].setText(str(teams.get("enroute", "—")))
        self._stat_labels["tasks_planned"].setText(str(tasks.get("planned", "—")))
        self._stat_labels["tasks_assigned"].setText(str(tasks.get("assigned", "—")))
        self._stat_labels["tasks_in_progress"].setText(str(tasks.get("in_progress", "—")))
        self._stat_labels["tasks_complete"].setText(str(tasks.get("complete", "—")))
        self._stat_labels["tasks_blocked"].setText(str(tasks.get("blocked", "—")))
        self._stat_labels["tasks_suspended"].setText(str(tasks.get("suspended", "—")))

        alerts = data.get("alerts", [])
        for i in reversed(range(self._alert_vbox.count())):
            w = self._alert_vbox.itemAt(i).widget()
            if w:
                w.setParent(None)

        if alerts:
            for a in alerts:
                albl = QLabel(f"⚠ {a['message']}  [{a.get('source','')}]")
                albl.setStyleSheet("color:#c0392b;font-size:11px;")
                self._alert_vbox.addWidget(albl)
        else:
            no_lbl = QLabel("None")
            no_lbl.setStyleSheet("color:#888;")
            self._alert_vbox.addWidget(no_lbl)

        active = teams.get("active", 0)
        available = teams.get("available", 0)
        in_prog = tasks.get("in_progress", 0)
        done = tasks.get("complete", 0)
        blocked_count = tasks.get("blocked", 0)
        alert_count = len(alerts)

        summary_parts = [
            f"As of {_now_iso()[:16].replace('T', ' ')},",
            f"{active} team(s) are active, {available} available.",
            f"{in_prog} task(s) in progress, {done} completed.",
        ]
        if blocked_count:
            summary_parts.append(f"{blocked_count} task(s) blocked.")
        if alert_count:
            summary_parts.append(f"{alert_count} active alert(s) require attention.")

        self._auto_summary.setPlainText(" ".join(summary_parts))

    def _insert_into_sitrep(self) -> None:
        text = self._auto_summary.toPlainText()
        if text:
            self._panel._insert_auto_content("operational_status", text)


# ---------------------------------------------------------------------------
# Tab 4: Distribution / Versions
# ---------------------------------------------------------------------------

class DistributionTab(QWidget):
    def __init__(self, panel: "SitrepPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel
        self._distributions: list[dict] = []

        layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        add_action = QAction("New Distribution Record", self)
        add_action.triggered.connect(self._add_distribution)
        toolbar.addAction(add_action)
        layout.addWidget(toolbar)

        self._list = QListWidget()
        layout.addWidget(self._list)

    def load_distributions(self, distributions: list[dict]) -> None:
        self._distributions = distributions
        self._list.clear()
        for d in distributions:
            ts = (d.get("distributed_at") or "")[:16].replace("T", " ")
            text = (
                f"{d.get('version_name','(unnamed)')} | "
                f"{d.get('audience','').title()} | "
                f"{d.get('delivery_method','').title()} | "
                f"{ts}"
            )
            self._list.addItem(text)

    def _add_distribution(self) -> None:
        if not self._panel._active_sitrep:
            QMessageBox.warning(self, "Distribution", "No SITREP active.")
            return
        dialog = _DistributionDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.payload():
            self._panel._create_distribution(dialog.payload())


class _DistributionDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Record Distribution")
        self.setMinimumWidth(400)
        self._payload: Optional[dict] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._version_name = QLineEdit()
        self._version_name.setPlaceholderText("e.g. SITREP 004 - Agency")
        form.addRow("Version Name:", self._version_name)

        self._audience = QComboBox()
        for val, label in AUDIENCES:
            self._audience.addItem(label, val)
        form.addRow("Audience:", self._audience)

        self._recipient_group = QLineEdit()
        form.addRow("Recipients:", self._recipient_group)

        self._delivery = QComboBox()
        for m in ("print", "pdf", "email", "copied_text", "radio"):
            self._delivery.addItem(m.title().replace("_", " "), m)
        form.addRow("Delivery Method:", self._delivery)

        self._approved_by = QLineEdit()
        form.addRow("Approved By:", self._approved_by)

        self._distributed_by = QLineEdit()
        form.addRow("Distributed By:", self._distributed_by)

        self._notes = QLineEdit()
        form.addRow("Notes:", self._notes)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self) -> None:
        self._payload = {
            "version_name": self._version_name.text().strip(),
            "audience": self._audience.currentData(),
            "recipient_group": self._recipient_group.text().strip(),
            "delivery_method": self._delivery.currentData(),
            "approved_by": self._approved_by.text().strip() or None,
            "distributed_by": self._distributed_by.text().strip(),
            "notes": self._notes.text().strip(),
        }
        self.accept()

    def payload(self) -> Optional[dict]:
        return self._payload


# ---------------------------------------------------------------------------
# Tab 5: Archive
# ---------------------------------------------------------------------------

class ArchiveTab(QWidget):
    def __init__(self, panel: "SitrepPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._panel = panel

        layout = QVBoxLayout(self)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        view_action = QAction("Open", self)
        view_action.triggered.connect(self._open_selected)
        toolbar.addAction(view_action)
        dup_action = QAction("Duplicate as Next SITREP", self)
        dup_action.triggered.connect(self._duplicate_selected)
        toolbar.addAction(dup_action)
        layout.addWidget(toolbar)

        self._model = ArchiveTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.setAlternatingRowColors(True)
        _apply_table_standards(self._table, stretch_column=6)
        self._table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self._table)

    def load_archive(self, summaries: list[SitrepSummary]) -> None:
        self._model.set_rows(summaries)

    def _current_summary(self) -> Optional[SitrepSummary]:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return None
        return self._model.summary_for_row(idx.row())

    def _open_selected(self) -> None:
        summary = self._current_summary()
        if summary:
            self._panel._load_sitrep_by_id(summary.id)

    def _duplicate_selected(self) -> None:
        summary = self._current_summary()
        if summary:
            self._panel._duplicate_sitrep(summary.id)


# ---------------------------------------------------------------------------
# Main SitrepPanel
# ---------------------------------------------------------------------------

class SitrepPanel(QWidget):
    """Situation Report (ICS-209) panel — 5-tab SITREP management interface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SitrepPanel")

        self._incident_id: Optional[str] = None
        self._client: Optional[SitrepApiClient] = None
        self._active_sitrep: Optional[Sitrep] = None
        self._all_summaries: list[SitrepSummary] = []
        self._all_events: list[SitrepEvent] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top toolbar
        top_bar = QToolBar("SITREP")
        top_bar.setMovable(False)
        new_action = QAction("New SITREP", self)
        new_action.triggered.connect(self._new_sitrep)
        top_bar.addAction(new_action)
        quick_action = QAction("Quick SITREP", self)
        quick_action.triggered.connect(self._quick_sitrep)
        top_bar.addAction(quick_action)
        top_bar.addSeparator()
        root.addWidget(top_bar)

        self._tabs = QTabWidget()
        self._tab_current = CurrentSitrepTab(self)
        self._tab_events = EventsTab(self)
        self._tab_ops = OperationalSummaryTab(self)
        self._tab_dist = DistributionTab(self)
        self._tab_archive = ArchiveTab(self)

        self._tabs.addTab(self._tab_current, "Current SITREP")
        self._tabs.addTab(self._tab_events, "Changes / Events")
        self._tabs.addTab(self._tab_ops, "Operational Summary")
        self._tabs.addTab(self._tab_dist, "Distribution")
        self._tabs.addTab(self._tab_archive, "Archive")
        root.addWidget(self._tabs)

        self._tabs.currentChanged.connect(self._on_tab_changed)

        app_signals.incidentChanged.connect(self._on_incident_changed)
        app_signals.opPeriodChanged.connect(self._soft_reload)

        self.load(incident_context.get_active_incident_id())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, incident_id: str | None) -> None:
        self._incident_id = incident_id
        self._client = SitrepApiClient(incident_id) if incident_id else None
        self._active_sitrep = None
        self._all_summaries = []
        self._all_events = []
        self._tab_current.load_sitrep(None)
        self._tab_archive.load_archive([])
        self._tab_events.load_events([])

        if incident_id and self._client:
            self._reload()

    # ------------------------------------------------------------------
    # Internal reload helpers
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        if not self._client:
            return
        try:
            self._all_summaries = self._client.list_sitreps()
        except Exception:
            logger.exception("Failed to list sitreps")
            self._all_summaries = []

        self._tab_archive.load_archive(self._all_summaries)

        # Load the most recent non-archived sitrep as the active one
        active = next(
            (s for s in self._all_summaries if s.status not in ("archived",)),
            self._all_summaries[0] if self._all_summaries else None,
        )
        if active:
            self._load_sitrep_by_id(active.id)
        else:
            self._tab_current.load_sitrep(None)

        self._reload_events()

    def _reload_events(self) -> None:
        if not self._client:
            return
        try:
            self._all_events = self._client.list_events()
        except Exception:
            logger.exception("Failed to list sitrep events")
            self._all_events = []
        self._tab_events.load_events(self._all_events)

    def _load_sitrep_by_id(self, sitrep_id: str) -> None:
        if not self._client:
            return
        try:
            sitrep = self._client.get_sitrep(sitrep_id)
        except Exception:
            logger.exception("Failed to load sitrep %s", sitrep_id)
            return
        self._active_sitrep = sitrep
        self._tab_current.load_sitrep(sitrep)

        try:
            distributions = self._client.list_distributions(sitrep_id)
            self._tab_dist.load_distributions(distributions)
        except Exception:
            logger.exception("Failed to load distributions for %s", sitrep_id)

    def _soft_reload(self, *_args) -> None:
        if self._incident_id:
            self._reload()

    # ------------------------------------------------------------------
    # SITREP actions
    # ------------------------------------------------------------------

    def _new_sitrep(self) -> None:
        if not self._client:
            QMessageBox.warning(self, "New SITREP", "Select an incident first.")
            return
        try:
            sitrep = self._client.create_sitrep(_op_payload())
        except Exception as exc:
            QMessageBox.critical(self, "New SITREP", f"Failed to create SITREP:\n{exc}")
            return
        self._reload()
        self._load_sitrep_by_id(sitrep.id)
        self._tabs.setCurrentIndex(0)

    def _quick_sitrep(self) -> None:
        if not self._client:
            QMessageBox.warning(self, "Quick SITREP", "Select an incident first.")
            return
        op_payload = _op_payload()
        if self._active_sitrep:
            try:
                sitrep = self._client.duplicate_sitrep(self._active_sitrep.id, op_payload)
            except Exception as exc:
                QMessageBox.critical(self, "Quick SITREP", f"Failed:\n{exc}")
                return
        else:
            try:
                sitrep = self._client.create_sitrep(op_payload)
            except Exception as exc:
                QMessageBox.critical(self, "Quick SITREP", f"Failed:\n{exc}")
                return
        self._reload()
        self._load_sitrep_by_id(sitrep.id)
        self._tabs.setCurrentIndex(0)

    def _save_current(self, payload: dict) -> None:
        if not self._client:
            return
        if not self._active_sitrep:
            QMessageBox.warning(self, "Save", "No SITREP loaded.")
            return
        try:
            updated = self._client.update_sitrep(self._active_sitrep.id, payload)
        except Exception as exc:
            QMessageBox.critical(self, "Save", f"Failed to save:\n{exc}")
            return
        self._active_sitrep = updated
        self._tab_current.load_sitrep(updated)
        self._reload_archive_row(updated)

    def _reload_archive_row(self, sitrep: Sitrep) -> None:
        for i, s in enumerate(self._all_summaries):
            if s.id == sitrep.id:
                self._all_summaries[i] = sitrep  # Sitrep IS-A SitrepSummary
                break
        self._tab_archive.load_archive(self._all_summaries)

    def _duplicate_sitrep(self, sitrep_id: str) -> None:
        if not self._client:
            return
        try:
            new_sitrep = self._client.duplicate_sitrep(sitrep_id, _op_payload())
        except Exception as exc:
            QMessageBox.critical(self, "Duplicate SITREP", f"Failed:\n{exc}")
            return
        self._reload()
        self._load_sitrep_by_id(new_sitrep.id)
        self._tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Event actions
    # ------------------------------------------------------------------

    def _create_event(self, payload: dict) -> None:
        if not self._client:
            return
        try:
            self._client.create_event(payload)
        except Exception as exc:
            QMessageBox.critical(self, "New Event", f"Failed:\n{exc}")
            return
        self._reload_events()

    def _update_event(self, event_id: str, payload: dict) -> None:
        if not self._client:
            return
        try:
            self._client.update_event(event_id, payload)
        except Exception as exc:
            QMessageBox.critical(self, "Update Event", f"Failed:\n{exc}")
            return
        self._reload_events()

    def _delete_event(self, event_id: str) -> None:
        if not self._client:
            return
        try:
            self._client.delete_event(event_id)
        except Exception as exc:
            QMessageBox.critical(self, "Delete Event", f"Failed:\n{exc}")
            return
        self._reload_events()

    # ------------------------------------------------------------------
    # Distribution actions
    # ------------------------------------------------------------------

    def _create_distribution(self, payload: dict) -> None:
        if not self._client or not self._active_sitrep:
            return
        try:
            self._client.create_distribution(self._active_sitrep.id, payload)
            distributions = self._client.list_distributions(self._active_sitrep.id)
            self._tab_dist.load_distributions(distributions)
        except Exception as exc:
            QMessageBox.critical(self, "Distribution", f"Failed:\n{exc}")

    # ------------------------------------------------------------------
    # Live facts / operational summary
    # ------------------------------------------------------------------

    def _refresh_from_modules(self) -> None:
        """Refresh live facts and re-pull auto-filled section content from the server."""
        self._refresh_live_facts()
        if not self._client or not self._active_sitrep:
            return
        try:
            updated = self._client.refresh_sitrep(self._active_sitrep.id)
        except Exception:
            logger.exception("Failed to refresh sitrep sections")
            return
        self._active_sitrep = updated
        self._tab_current.update_auto_contents(updated)

    def _refresh_live_facts(self) -> None:
        if not self._client:
            return
        try:
            data = self._client.get_operational_summary()
        except Exception:
            logger.exception("Failed to fetch operational summary")
            return
        self._tab_ops.update_summary(data)

        teams = data.get("teams", {})
        tasks = data.get("tasks", {})
        for key, lbl in self._tab_current._teams_labels.items():
            lbl.setText(f"{key.title()}: {teams.get(key, '—')}")
        for key, lbl in self._tab_current._task_labels.items():
            count = tasks.get(key, "—")
            lbl.setText(f"{key.replace('_',' ').title()}: {count}")

        alerts = data.get("alerts", [])
        for i in reversed(range(self._tab_current._alerts_layout.count())):
            w = self._tab_current._alerts_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        if alerts:
            for a in alerts:
                albl = QLabel(f"⚠ {a['message']}")
                albl.setStyleSheet("color:#c0392b;font-size:11px;")
                self._tab_current._alerts_layout.addWidget(albl)
        else:
            no_lbl = QLabel("None")
            no_lbl.setStyleSheet("color:#888;font-size:11px;")
            self._tab_current._alerts_layout.addWidget(no_lbl)

    def _insert_auto_content(self, section_type: str, text: str) -> None:
        """Inject auto-generated text into a specific section of the current SITREP editor."""
        try:
            idx = MVP_SECTION_TYPES.index(section_type)
        except ValueError:
            return
        editor = self._tab_current._editors[idx]
        if not editor._edit_text.toPlainText().strip():
            editor._edit_text.setPlainText(text)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_incident_changed(self, incident_id: str) -> None:
        self.load(incident_id if incident_id else None)

    def _on_tab_changed(self, index: int) -> None:
        if index == 2:
            self._refresh_live_facts()
