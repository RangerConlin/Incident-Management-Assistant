"""Quick entry widget for rapid logging."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import QDateTime, Qt, Signal, QStringListModel
from PySide6.QtWidgets import (
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


class GrowingTextEdit(QTextEdit):
    """QTextEdit that starts as a single line and grows with content."""

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
        self.message_edit.setPlaceholderText("Message body")
        message_layout.addWidget(QLabel("Message"))
        message_layout.addWidget(self.message_edit, 1)
        layout.addLayout(message_layout)

        action_layout = QHBoxLayout()
        self.action_edit = QLineEdit()
        self.action_edit.setPlaceholderText("Action taken")
        action_layout.addWidget(QLabel("Action"))
        action_layout.addWidget(self.action_edit, 1)
        layout.addLayout(action_layout)

        toggle_layout = QHBoxLayout()
        self.status_checkbox = QCheckBox("Status Update")
        self.followup_checkbox = QCheckBox("Follow-up Required")
        toggle_layout.addWidget(self.status_checkbox)
        toggle_layout.addWidget(self.followup_checkbox)
        toggle_layout.addStretch(1)

        self.attach_button = QPushButton("Attach…")
        self.attach_button.clicked.connect(self.attachmentsRequested.emit)
        toggle_layout.addWidget(self.attach_button)

        self.save_button = QPushButton("Save")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_submit)
        toggle_layout.addWidget(self.save_button)

        layout.addLayout(toggle_layout)

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
            display = primary if not secondary else f"{primary} — {secondary}"
            alias_values = list(item.get("aliases") or [])
            alias_values.extend([primary, secondary, display])
            alias_keys = {self._normalize(alias) for alias in alias_values if alias}
            # Include split tokens such as callsigns separated by '/'
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
        self.action_edit.clear()
        self.followup_checkbox.setChecked(False)
        self.status_checkbox.setChecked(False)
        self.from_field.clear()
        self.to_field.clear()
        self._from_link = None
        self._to_link = None
        self._attachments.clear()
        self.attach_button.setText("Attach…")
        self.message_edit.setFocus()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
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
        payload: Dict[str, object] = {
            "ts_local": ts_local.toString(Qt.ISODate),
            "ts_utc": ts_local.toUTC().toString(Qt.ISODate),
            "priority": self.priority_combo.currentText(),
            "resource_label": self.resource_combo.currentText().strip(),
            "resource_id": self.resource_combo.currentData(),
            "from_unit": self.from_field.text().strip(),
            "to_unit": self.to_field.text().strip(),
            "message": message,
            "action_taken": self.action_edit.text().strip(),
            "follow_up_required": self.followup_checkbox.isChecked(),
            "is_status_update": self.status_checkbox.isChecked(),
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
        if self._attachments:
            self.attach_button.setText(f"Attach… ({len(self._attachments)})")


__all__ = ["QuickEntryWidget"]
