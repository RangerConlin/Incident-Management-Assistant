"""Quick entry widget for rapid communications logging."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import QDateTime, Qt, Signal, QStringListModel
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    PRIORITY_EMERGENCY,
    PRIORITY_PRIORITY,
    PRIORITY_ROUTINE,
)
from .canned_picker import CannedCommPickerDialog
from utils.constants import TEAM_STATUSES

# First entry is the user-configurable "home base" label (e.g. "ECC", "Base", "Dispatch").
# TODO: make _BASE_LABEL user-configurable in Settings → Communications.
_BASE_LABEL = "Base"
_FIXED_CONTACTS_BOTTOM = ["ECC", "ICC", "Air Operations", "Logistics", "Staging"]


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("font-size: 11px; color: #90a4ae; font-weight: 600;")
    return l


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: #37474f;")
    return f


# ---------------------------------------------------------------------------
# Editable combo for Sender / Receiver
# ---------------------------------------------------------------------------

class _ContactCombo(QComboBox):
    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._populate([])

    def _populate(self, teams: List[Dict]) -> None:
        self.clear()
        self.addItem("", None)
        # Configurable home base label — top of list
        self.addItem(_BASE_LABEL, _BASE_LABEL)
        # Active teams
        if teams:
            self.insertSeparator(self.count())
            for t in teams:
                label = t.get("name") or t.get("callsign") or f"Team {t.get('int_id','?')}"
                self.addItem(label, t.get("int_id"))
        # Fixed standard positions at the bottom
        self.insertSeparator(self.count())
        for name in _FIXED_CONTACTS_BOTTOM:
            self.addItem(name, name)

    def populate_teams(self, teams: List[Dict]) -> None:
        self._populate(teams)

    def current_text_value(self) -> str:
        return self.lineEdit().text().strip()


# ---------------------------------------------------------------------------
# Growing message text area
# ---------------------------------------------------------------------------

class GrowingTextEdit(QTextEdit):
    focusChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setMinimumHeight(90)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focusChanged.emit(True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focusChanged.emit(False)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class QuickEntryWidget(QWidget):
    submitted = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        # ── Row 1: Sender / Receiver / Channel ──────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(3)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)

        grid.addWidget(_lbl("Sender"), 0, 0)
        self.from_field = _ContactCombo("Sending unit or call sign")
        grid.addWidget(self.from_field, 1, 0)

        grid.addWidget(_lbl("Receiver"), 0, 1)
        self.to_field = _ContactCombo("Receiving unit or call sign")
        grid.addWidget(self.to_field, 1, 1)

        grid.addWidget(_lbl("Channel"), 0, 2)
        self.channel_combo = QComboBox()
        self.channel_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.channel_combo.addItem("— Channel —", None)
        grid.addWidget(self.channel_combo, 1, 2)

        outer.addLayout(grid)

        # ── Row 2: Message label + Canned button ────────────────────────
        msg_row = QHBoxLayout()
        msg_row.addWidget(_lbl("Message"))
        msg_row.addStretch()
        self.canned_btn = QPushButton("⚡ Canned")
        self.canned_btn.setFixedHeight(22)
        self.canned_btn.setStyleSheet(
            "QPushButton { font-size:11px; background:#1a237e; color:#fff;"
            " border-radius:3px; padding:0 8px; }"
            "QPushButton:hover { background:#283593; }"
        )
        self.canned_btn.clicked.connect(self._pick_canned)
        msg_row.addWidget(self.canned_btn)
        outer.addLayout(msg_row)

        # ── Row 3: Message textarea ──────────────────────────────────────
        self.message_edit = GrowingTextEdit()
        self.message_edit.setPlaceholderText("Enter message…")
        outer.addWidget(self.message_edit, 1)

        outer.addWidget(_divider())

        # ── Row 4: Team Status + Priority ───────────────────────────────
        sp_row = QHBoxLayout()
        sp_row.addWidget(_lbl("Team Status"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("", None)
        for opt in TEAM_STATUSES:
            self.status_combo.addItem(opt, opt)
        self.status_combo.setMinimumWidth(160)
        sp_row.addWidget(self.status_combo)

        sp_row.addSpacing(16)
        sp_row.addWidget(_lbl("Priority"))
        self.priority_combo = QComboBox()
        for p in (PRIORITY_ROUTINE, PRIORITY_PRIORITY, PRIORITY_EMERGENCY):
            self.priority_combo.addItem(p, p)
        self.priority_combo.setCurrentIndex(0)
        self.priority_combo.setMinimumWidth(110)
        self.priority_combo.currentTextChanged.connect(self._on_priority_changed)
        sp_row.addWidget(self.priority_combo)

        sp_row.addStretch()
        outer.addLayout(sp_row)

        # ── Row 5: Timestamp + buttons ───────────────────────────────────
        outer.addWidget(_divider())
        bottom = QHBoxLayout()
        self.timestamp_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.timestamp_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.timestamp_edit.setCalendarPopup(True)
        self.timestamp_edit.setStyleSheet("font-size: 11px;")
        bottom.addWidget(self.timestamp_edit)

        now_btn = QPushButton("Now")
        now_btn.setFixedHeight(24)
        now_btn.setFixedWidth(42)
        now_btn.setToolTip("Set to current time")
        now_btn.setStyleSheet(
            "QPushButton { font-size:10px; background:#37474f; color:#cfd8dc;"
            " border-radius:3px; border:1px solid #546e7a; }"
            "QPushButton:hover { background:#455a64; }"
        )
        now_btn.clicked.connect(lambda: self.timestamp_edit.setDateTime(QDateTime.currentDateTime()))
        bottom.addWidget(now_btn)
        bottom.addStretch()

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setFixedHeight(30)
        self.reset_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#90a4ae; border:1px solid #546e7a;"
            " border-radius:3px; padding:0 14px; font-weight:600; }"
            "QPushButton:hover { background:#37474f; }"
        )
        self.reset_btn.clicked.connect(self.reset)
        bottom.addWidget(self.reset_btn)

        self.save_btn = QPushButton("Save Entry")
        self.save_btn.setDefault(True)
        self.save_btn.setFixedHeight(30)
        self.save_btn.setStyleSheet(
            "QPushButton { background:#1a237e; color:white; border-radius:3px;"
            " padding:0 18px; font-weight:700; }"
            "QPushButton:hover { background:#283593; }"
        )
        self.save_btn.clicked.connect(self._on_submit)
        bottom.addWidget(self.save_btn)
        outer.addLayout(bottom)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_channels(self, channels: Iterable[Dict]) -> None:
        self.channel_combo.clear()
        self.channel_combo.addItem("— Channel —", None)
        for ch in channels:
            label = ch.get("channel_name") or ch.get("channel") or ch.get("name") or ""
            self.channel_combo.addItem(label, ch.get("id"))

    def set_channel(self, channel_id) -> None:
        for i in range(self.channel_combo.count()):
            if self.channel_combo.itemData(i) == channel_id:
                self.channel_combo.setCurrentIndex(i)
                return

    def set_channel_by_label(self, label: str) -> None:
        idx = self.channel_combo.findText(label)
        if idx >= 0:
            self.channel_combo.setCurrentIndex(idx)

    def populate_teams(self, teams: List[Dict]) -> None:
        self.from_field.populate_teams(teams)
        self.to_field.populate_teams(teams)

    def set_contact_suggestions(self, suggestions: Iterable[Dict]) -> None:
        pass  # teams come via populate_teams()

    def set_default_resource(self, resource_id) -> None:
        self.set_channel(resource_id)

    def set_priority(self, priority: str) -> None:
        idx = self.priority_combo.findData(priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)

    def reset(self) -> None:
        self.message_edit.clear()
        self.from_field.setCurrentIndex(0)
        self.from_field.lineEdit().clear()
        self.to_field.setCurrentIndex(0)
        self.to_field.lineEdit().clear()
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.message_edit.setFocus()

    def focus_message(self) -> None:
        self.message_edit.setFocus()

    def insert_message_text(self, text: str, *, replace: bool = True) -> None:
        if replace:
            self.message_edit.setPlainText(text or "")
        else:
            existing = self.message_edit.toPlainText()
            self.message_edit.setPlainText(f"{existing}\n{text}".strip() if existing else text or "")
        self.message_edit.moveCursor(QTextCursor.End)

    def _on_priority_changed(self, text: str) -> None:
        colors = {
            PRIORITY_ROUTINE:   ("#2e7d32", "#e8f5e9"),
            PRIORITY_PRIORITY:  ("#e65100", "#fff3e0"),
            PRIORITY_EMERGENCY: ("#b71c1c", "#ffebee"),
        }
        fg, bg = colors.get(text, ("#fff", "transparent"))
        self.priority_combo.setStyleSheet(
            f"QComboBox {{ color:{fg}; background:{bg}; font-weight:700;"
            f" border:1px solid {fg}; border-radius:3px; padding:2px 6px; }}"
            "QComboBox QAbstractItemView { color:#fff; background:#1e1e2e; }"
        )

    # ------------------------------------------------------------------

    def _pick_canned(self) -> None:
        dialog = CannedCommPickerDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        entry = dialog.selected_entry() or {}
        text = str(entry.get("message") or "")
        if text:
            self.insert_message_text(text, replace=True)
        priority = entry.get("priority")
        if isinstance(priority, str) and priority:
            self.set_priority(priority)
        status = str(entry.get("status_update") or "").strip()
        if status:
            i = self.status_combo.findData(status)
            if i >= 0:
                self.status_combo.setCurrentIndex(i)

    def _on_submit(self) -> None:
        message = self.message_edit.toPlainText().strip()
        if not message:
            self.message_edit.setFocus()
            return

        ts = self.timestamp_edit.dateTime()
        priority = self.priority_combo.currentData() or PRIORITY_ROUTINE
        status_tag = self.status_combo.currentData()
        if status_tag:
            message = f"[Status: {status_tag}]\n{message}"

        payload: Dict = {
            "ts_local": ts.toString(Qt.ISODate),
            "ts_utc": ts.toUTC().toString(Qt.ISODate),
            "priority": priority,
            "resource_label": self.channel_combo.currentText() if self.channel_combo.currentData() else "",
            "resource_id": self.channel_combo.currentData(),
            "from_unit": self.from_field.current_text_value(),
            "to_unit": self.to_field.current_text_value(),
            "message": message,
            "follow_up_required": priority == PRIORITY_EMERGENCY,
        }
        self.submitted.emit(payload)
        self.reset()
        self.timestamp_edit.setDateTime(QDateTime.currentDateTime())


__all__ = ["QuickEntryWidget", "GrowingTextEdit"]
