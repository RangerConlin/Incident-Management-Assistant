"""Release editor modal for Public Information releases."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.public_information.models.constants import AUDIENCES, MESSAGE_TYPES, PRIORITIES
from modules.public_information.services import PublicInformationRepository
from modules.public_information.services.release_workflow import LifecycleAction, lifecycle_actions_for_status
from modules.public_information.widgets.release_lifecycle_panel import ReleaseLifecyclePanel
from modules.public_information.widgets.release_preview import ReleasePreviewWidget


def _template_name(template: dict[str, Any]) -> str:
    return str(template.get("template_name") or f"Template {template.get('id')}")


class ReleaseEditorDialog(QDialog):
    saved = Signal(dict)

    def __init__(
        self,
        repo: PublicInformationRepository,
        current_user: dict[str, Any] | None = None,
        message: dict[str, Any] | None = None,
        parent=None,
        default_release_type: str = "Press Release",
        default_audience: str = "Public",
        default_priority: str = "Normal",
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user or {}
        self.message: dict[str, Any] = {}
        self.template_lookup: dict[str, int | None] = {"No Template": None}

        self.setWindowTitle("Release Editor")
        self.resize(1320, 900)
        self.setMinimumSize(1000, 700)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel("Release Editor"))
        header.addStretch(1)
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.show_preview)
        header.addWidget(self.preview_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_public_panel(default_release_type, default_audience, default_priority))
        splitter.addWidget(self._build_internal_panel())
        splitter.setSizes([780, 500])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)
        root.addLayout(footer)

        self.set_message(
            message
            or {
                "status": "Draft",
                "type": default_release_type,
                "audience": default_audience,
                "priority": default_priority,
            }
        )

    def _build_public_panel(self, default_release_type: str, default_audience: str, default_priority: str) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        form_box = QWidget()
        form = QFormLayout(form_box)
        self.type_combo = QComboBox()
        self.type_combo.addItems(MESSAGE_TYPES)
        if default_release_type in MESSAGE_TYPES:
            self.type_combo.setCurrentText(default_release_type)
        self.audience_combo = QComboBox()
        self.audience_combo.addItems(AUDIENCES)
        if default_audience in AUDIENCES:
            self.audience_combo.setCurrentText(default_audience)
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITIES)
        if default_priority in PRIORITIES:
            self.priority_combo.setCurrentText(default_priority)
        self.title_edit = QLineEdit()
        self.subtitle_edit = QLineEdit()
        self.dateline_edit = QLineEdit()
        self.body_edit = QTextEdit()
        self.body_edit.setMinimumHeight(260)
        self.next_update_edit = QTextEdit()
        self.next_update_edit.setMinimumHeight(80)
        self.boilerplate_edit = QTextEdit()
        self.boilerplate_edit.setMinimumHeight(80)
        self.template_combo = QComboBox()
        self.template_combo.currentIndexChanged.connect(lambda _index: self._update_preview())

        for label, widget in [
            ("Release Type", self.type_combo),
            ("Audience", self.audience_combo),
            ("Priority", self.priority_combo),
            ("Headline", self.title_edit),
            ("Subheadline", self.subtitle_edit),
            ("Dateline", self.dateline_edit),
            ("Release Body", self.body_edit),
            ("Next Update", self.next_update_edit),
            ("Boilerplate", self.boilerplate_edit),
        ]:
            form.addRow(label, widget)
        layout.addWidget(form_box, 1)

        template_box = QWidget()
        template_form = QFormLayout(template_box)
        template_form.addRow("Template / Letterhead", self.template_combo)
        layout.addWidget(template_box)

        self._wire_public_editors()
        self.refresh_templates()
        return panel

    def _wire_public_editors(self) -> None:
        for widget in [
            self.type_combo,
            self.audience_combo,
            self.priority_combo,
            self.title_edit,
            self.subtitle_edit,
            self.dateline_edit,
            self.body_edit,
            self.next_update_edit,
            self.boilerplate_edit,
        ]:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(lambda _index, w=widget: self._on_public_change())
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._on_public_change)
            elif isinstance(widget, QTextEdit):
                widget.textChanged.connect(self._on_public_change)

    def _build_internal_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        self.lifecycle = ReleaseLifecyclePanel(self.repo)
        self.lifecycle.action_requested.connect(self._handle_lifecycle_action)
        self.lifecycle.preview_requested.connect(self.show_preview)
        layout.addWidget(self.lifecycle, 1)
        return panel

    def refresh_templates(self) -> None:
        current = self.template_combo.currentText() if self.template_combo.count() else "No Template"
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_lookup = {"No Template": None}
        for template in self.repo.list_templates(active_only=True):
            name = _template_name(template)
            self.template_lookup[name] = int(template["id"])
        self.template_combo.addItems(list(self.template_lookup.keys()))
        if current in self.template_lookup:
            self.template_combo.setCurrentText(current)
        self.template_combo.blockSignals(False)

    def set_message(self, message: dict[str, Any] | None) -> None:
        self.message = dict(message or {})
        self.refresh_templates()
        self.title_edit.setText(str(self.message.get("title", "")))
        self.subtitle_edit.setText(str(self.message.get("subtitle", "")))
        self.type_combo.setCurrentText(str(self.message.get("type", self.type_combo.currentText() or "Press Release")))
        self.audience_combo.setCurrentText(str(self.message.get("audience", self.audience_combo.currentText() or "Public")))
        self.priority_combo.setCurrentText(str(self.message.get("priority", self.priority_combo.currentText() or "Normal")))
        self.dateline_edit.setText(str(self.message.get("dateline", "")))
        self.body_edit.setPlainText(str(self.message.get("body", "")))
        self.next_update_edit.setPlainText(str(self.message.get("next_update_statement", "")))
        self.boilerplate_edit.setPlainText(str(self.message.get("boilerplate", "")))
        template_id = self.message.get("template_id")
        template_name = "No Template"
        for name, candidate in self.template_lookup.items():
            if candidate == template_id:
                template_name = name
                break
        self.template_combo.setCurrentText(template_name)
        self.lifecycle.set_release(self.message)

    def current_template(self) -> dict[str, Any] | None:
        template_id = self.template_lookup.get(self.template_combo.currentText())
        if template_id is None:
            return None
        return self.repo.get_template(int(template_id))

    def collect_message(self, status: str | None = None) -> dict[str, Any]:
        user_name = str(self.current_user.get("name") or self.current_user.get("id") or "")
        payload = dict(self.message)
        payload.update(
            {
                "title": self.title_edit.text().strip(),
                "subtitle": self.subtitle_edit.text().strip(),
                "type": self.type_combo.currentText().strip(),
                "audience": self.audience_combo.currentText().strip(),
                "priority": self.priority_combo.currentText().strip(),
                "status": status or str(self.message.get("status") or "Draft"),
                "dateline": self.dateline_edit.text().strip(),
                "body": self.body_edit.toPlainText(),
                "next_update_statement": self.next_update_edit.toPlainText(),
                "boilerplate": self.boilerplate_edit.toPlainText(),
                "created_by": self.message.get("created_by") or user_name,
                "template_id": self.template_lookup.get(self.template_combo.currentText()),
            }
        )
        return payload

    def _handle_lifecycle_action(self, action_key: str) -> None:
        action = self._action_for_key(action_key)
        if action is None:
            return
        if action.opens_copy:
            self._create_update_copy()
            return
        if action.target_status is None:
            self._save_message()
            return
        self._save_and_transition(action.target_status)

    def _action_for_key(self, action_key: str) -> LifecycleAction | None:
        status = str(self.message.get("status") or "Draft")
        for action in lifecycle_actions_for_status(status):
            if action.key == action_key:
                return action
        return None

    def _save_message(self, status: str | None = None) -> dict[str, Any]:
        payload = self.collect_message(status=status)
        saved = self.repo.save_message(payload, str(self.current_user.get("id", "")))
        self.set_message(saved)
        self.saved.emit(saved)
        return saved

    def _save_and_transition(self, status: str) -> None:
        saved = self._save_message(status)
        transitioned = self.repo.set_message_status(
            int(saved["id"]),
            status,
            str(self.current_user.get("id", "")),
            self.lifecycle.comment(),
        )
        self.lifecycle.clear_comment()
        self.set_message(transitioned)
        self.saved.emit(transitioned)

    def _create_update_copy(self) -> None:
        current = self.collect_message("Draft")
        current.pop("id", None)
        current["status"] = "Draft"
        current["approved_by"] = ""
        current["approved_at"] = ""
        current["published_by"] = ""
        current["published_at"] = ""
        current["archived_by"] = ""
        current["archived_at"] = ""
        current["created_by"] = str(self.current_user.get("name") or self.current_user.get("id") or "")
        dialog = ReleaseEditorDialog(
            self.repo,
            self.current_user,
            current,
            self.parentWidget() or self,
        )
        dialog.saved.connect(lambda message: self.saved.emit(message))
        dialog.exec()

    def show_preview(self) -> None:
        preview = ReleasePreviewWidget(self.repo, self)
        preview.set_release(self.collect_message(), self.current_template())
        dialog = QDialog(self)
        dialog.setWindowTitle("Release Preview")
        dialog.resize(900, 900)
        layout = QVBoxLayout(dialog)
        layout.addWidget(preview, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.reject)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        dialog.exec()

    def _update_preview(self) -> None:
        # The modal only opens the preview on demand; this keeps the edit flow simple.
        return

    def _on_public_change(self) -> None:
        # Public fields are saved explicitly through lifecycle actions.
        return
