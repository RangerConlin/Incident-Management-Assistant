"""Quick entry widget for rapid logging."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import QDateTime, Qt, Signal, QStringListModel
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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


class GrowingTextEdit(QTextEdit):
    """QTextEdit that starts as a single line and grows with content."""

    focusChanged = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.document().documentLayout().documentSizeChanged.connect(self._update_height)  # type: ignore[arg-type]
        self.textChanged.connect(self._update_height)
        self._minimum_height = self._calculate_min_height()
        self._maximum_height = 220
        self._update_height()

    def _calculate_min_height(self) -> int:
        margins = self.contentsMargins()
        frame = int(self.frameWidth() * 2)
        return int(self.fontMetrics().lineSpacing() + margins.top() + margins.bottom() + frame + 4)

    def _update_height(self, *_) -> None:
        margins = self.contentsMargins()
        frame = int(self.frameWidth() * 2)
        doc_height = self.document().size().height()
        target = int(doc_height + margins.top() + margins.bottom() + frame)
        target = max(self._minimum_height, target)
        target = min(self._maximum_height, target)
        self.setFixedHeight(target)

    def focusInEvent(self, event) -> None:  # type: ignore[override]
        super().focusInEvent(event)
        self.focusChanged.emit(True)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        self.focusChanged.emit(False)


class QuickEntryWidget(QWidget):
    """Bottom dock widget used for rapid keyboard-first data entry."""

    submitted = Signal(dict)
    attachmentsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: List[str] = []
        self._alias_lookup: Dict[str, Dict[str, object]] = {}
        self._from_link: Optional[Dict[str, object]] = None
        self._to_link: Optional[Dict[str, object]] = None
        self._completer_model = QStringListModel(self)
        self._priority_shortcuts: List[QShortcut] = []
        self._template_had_status: bool = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        self.timestamp_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.timestamp_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.timestamp_edit.setCalendarPopup(True)
        top_row.addWidget(QLabel("Timestamp"))
        top_row.addWidget(self.timestamp_edit)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems([PRIORITY_ROUTINE, PRIORITY_PRIORITY, PRIORITY_EMERGENCY])
        top_row.addWidget(QLabel("Priority"))
        top_row.addWidget(self.priority_combo)

        self.resource_combo = QComboBox()
        self.resource_combo.setEditable(True)
        top_row.addWidget(QLabel("Resource"))
        top_row.addWidget(self.resource_combo, 1)

        self.from_field = QLineEdit()
        self.from_field.setPlaceholderText("From team or position")
        self.to_field = QLineEdit()
        self.to_field.setPlaceholderText("To team or position")

        names_layout = QHBoxLayout()
        names_layout.addWidget(QLabel("From"))
        names_layout.addWidget(self.from_field)
        names_layout.addWidget(QLabel("To"))
        names_layout.addWidget(self.to_field)
        layout.addLayout(names_layout)

        self._create_completer(self.from_field, "from")
        self._create_completer(self.to_field, "to")
        self.from_field.editingFinished.connect(lambda: self._resolve_field_match("from"))
        self.to_field.editingFinished.connect(lambda: self._resolve_field_match("to"))
        self.from_field.textChanged.connect(lambda text: self._handle_field_change("from", text))
        self.to_field.textChanged.connect(lambda text: self._handle_field_change("to", text))

        message_layout = QHBoxLayout()
        self.message_edit = GrowingTextEdit()
        self.message_edit.setReadOnly(False)
        self.message_edit.setPlaceholderText("Message body")
        message_layout.addWidget(QLabel("Message"))
        message_layout.addWidget(self.message_edit, 1)
        # Add canned message button on the same row
        self.canned_button = QPushButton("Canned…")
        self.canned_button.setToolTip("Insert a canned communication message")
        self.canned_button.clicked.connect(self._pick_canned_message)
        message_layout.addWidget(self.canned_button)
        layout.addLayout(message_layout)
        self.message_edit.focusChanged.connect(self._on_message_focus_changed)

        toggle_layout = QHBoxLayout()
        self.followup_checkbox = QCheckBox("Follow-up Required")
        toggle_layout.addWidget(self.followup_checkbox)
        # Optional status change dropdown (applies if template lacks one)
        self.status_change_combo = QComboBox()
        self.status_change_combo.setToolTip("Optional status change tag")
        self.status_change_combo.addItem("", None)
        for opt in TEAM_STATUSES:
            self.status_change_combo.addItem(opt, opt)
        toggle_layout.addWidget(QLabel("Status"))
        toggle_layout.addWidget(self.status_change_combo)
        toggle_layout.addStretch(1)

        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_submit)
        toggle_layout.addWidget(self.save_button)

        layout.addLayout(toggle_layout)

        # Numeric shortcuts for priority selection
        for key, priority in (
            ("1", PRIORITY_ROUTINE),
            ("2", PRIORITY_PRIORITY),
            ("3", PRIORITY_EMERGENCY),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda p=priority: self.set_priority(p))
            self._priority_shortcuts.append(shortcut)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_channels(self, channels: Iterable[Dict[str, str]]) -> None:
        self.resource_combo.clear()
        self.resource_combo.addItem("", None)
        for chan in channels:
            label = chan.get("display_name") or chan.get("name") or ""
            self.resource_combo.addItem(label, chan.get("id"))

    def set_contact_suggestions(self, suggestions: Iterable[Dict[str, object]]) -> None:
        entries: List[Dict[str, object]] = []
        alias_lookup: Dict[str, Dict[str, object]] = {}
        display_values: List[str] = []
        for item in suggestions:
            if not isinstance(item, dict):
                continue
            entity_id = item.get("id")
            if entity_id is None:
                continue
            primary = str(item.get("primary") or item.get("display") or item.get("name") or "").strip()
            if not primary:
                continue
            secondary = str(item.get("secondary") or "").strip()
            display = primary if not secondary else f"{primary} / {secondary}"
            alias_values = list(item.get("aliases") or [])
            alias_values.extend([primary, secondary, display])
            alias_keys = {self._normalize(alias) for alias in alias_values if alias}
            for alias in list(alias_keys):
                if "/" in alias:
                    for segment in alias.split("/"):
                        normalized_segment = self._normalize(segment)
                        if normalized_segment:
                            alias_keys.add(normalized_segment)
            entry = {
                "type": str(item.get("type") or "unit"),
                "id": int(entity_id),
                "display": display,
                "primary": primary,
                "aliases": alias_keys,
            }
            entries.append(entry)
            display_values.append(display)
            for key in alias_keys:
                alias_lookup[key] = entry
        self._alias_lookup = alias_lookup
        self._completer_model.setStringList(display_values)
        self._resolve_field_match("from", update_text=False)
        self._resolve_field_match("to", update_text=False)

    def set_default_resource(self, resource_id: Optional[int]) -> None:
        if resource_id is None:
            return
        for row in range(self.resource_combo.count()):
            if self.resource_combo.itemData(row) == resource_id:
                self.resource_combo.setCurrentIndex(row)
                break

    def reset(self) -> None:
        self.message_edit.clear()
        self.followup_checkbox.setChecked(False)
        self.from_field.clear()
        self.to_field.clear()
        self._from_link = None
        self._to_link = None
        self._attachments.clear()
        self.message_edit.setFocus()
        try:
            self.status_change_combo.setCurrentIndex(0)
        except Exception:
            pass
        self._template_had_status = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def set_priority(self, priority: str) -> None:
        index = self.priority_combo.findText(priority)
        if index >= 0:
            self.priority_combo.setCurrentIndex(index)

    def focus_message(self) -> None:
        self.message_edit.setFocus()

    # Convenience used by integrations (e.g., canned comms picker)
    def insert_message_text(self, text: str, *, replace: bool = True) -> None:
        if replace:
            self.message_edit.setPlainText(text or "")
        else:
            existing = self.message_edit.toPlainText()
            if existing:
                self.message_edit.setPlainText(f"{existing}\n{text}" if text else existing)
            else:
                self.message_edit.setPlainText(text or "")
        # Move cursor to end for convenience
        self.message_edit.moveCursor(QTextCursor.End)

    def _on_message_focus_changed(self, focused: bool) -> None:
        for shortcut in self._priority_shortcuts:
            shortcut.setEnabled(not focused)

    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def _create_completer(self, line_edit: QLineEdit, role: str) -> QCompleter:
        completer = QCompleter(self._completer_model, line_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated[str].connect(lambda value, r=role: self._on_completer_selected(r, value))
        line_edit.setCompleter(completer)
        return completer

    def _on_completer_selected(self, role: str, value: str) -> None:
        field = self.from_field if role == "from" else self.to_field
        field.setText(value)
        self._resolve_field_match(role)

    def _lookup_suggestion(self, text: str) -> Optional[Dict[str, object]]:
        key = self._normalize(text)
        if not key:
            return None
        suggestion = self._alias_lookup.get(key)
        if suggestion:
            return suggestion
        return None

    def _resolve_field_match(self, role: str, update_text: bool = True) -> None:
        field = self.from_field if role == "from" else self.to_field
        suggestion = self._lookup_suggestion(field.text())
        if suggestion:
            if update_text:
                field.setText(str(suggestion.get("display", "")))
            if role == "from":
                self._from_link = suggestion
            else:
                self._to_link = suggestion
        else:
            if role == "from":
                self._from_link = None
            else:
                self._to_link = None

    def _handle_field_change(self, role: str, text: str) -> None:
        suggestion = self._from_link if role == "from" else self._to_link
        if not suggestion:
            return
        if self._normalize(text) not in suggestion.get("aliases", set()):
            if role == "from":
                self._from_link = None
            else:
                self._to_link = None

    def _on_submit(self) -> None:
        message = self.message_edit.toPlainText().strip()
        if not message:
            return
        ts_local = self.timestamp_edit.dateTime()
        # Apply manual status tag only if template did not specify one
        try:
            if not getattr(self, "_template_had_status", False):
                manual = self.status_change_combo.currentData()
                if manual:
                    prefix = f"[Status: {manual}]"
                    message = f"{prefix}\n{message}" if message else prefix
        except Exception:
            pass
        payload: Dict[str, object] = {
            "ts_local": ts_local.toString(Qt.ISODate),
            "ts_utc": ts_local.toUTC().toString(Qt.ISODate),
            "priority": self.priority_combo.currentText(),
            "resource_label": self.resource_combo.currentText().strip(),
            "resource_id": self.resource_combo.currentData(),
            "from_unit": self.from_field.text().strip(),
            "to_unit": self.to_field.text().strip(),
            "message": message,
            "follow_up_required": self.followup_checkbox.isChecked(),
            "attachments": list(self._attachments),
        }
        for match in (self._from_link, self._to_link):
            if not match:
                continue
            entity_type = str(match.get("type"))
            entity_id = match.get("id")
            if entity_id is None:
                continue
            if entity_type == "team" and "team_id" not in payload:
                payload["team_id"] = int(entity_id)
            elif entity_type in {"personnel", "position"} and "personnel_id" not in payload:
                payload["personnel_id"] = int(entity_id)
        self.submitted.emit(payload)
        self.reset()

    # ------------------------------------------------------------------
    def add_attachments(self, paths: Iterable[str]) -> None:
        for path in paths:
            if path and path not in self._attachments:
                self._attachments.append(path)
        # Attach button removed; no UI update here

    def _pick_canned_message(self) -> None:
        dialog = CannedCommPickerDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        entry = dialog.selected_entry() or {}
        text = str(entry.get("message") or "")
        if not text:
            return
        self.insert_message_text(text, replace=True)
        # Apply priority if provided
        priority = entry.get("priority")
        if isinstance(priority, str) and priority:
            idx = self.priority_combo.findText(priority)
            if idx >= 0:
                self.priority_combo.setCurrentIndex(idx)
        # Track template-provided status and reflect in dropdown
        try:
            self._template_had_status = bool(entry.get("status_update"))
            if self._template_had_status:
                val = str(entry.get("status_update") or "").strip()
                if val:
                    i = self.status_change_combo.findData(val)
                    if i >= 0:
                        self.status_change_combo.setCurrentIndex(i)
        except Exception:
            self._template_had_status = False


__all__ = ["QuickEntryWidget"]

