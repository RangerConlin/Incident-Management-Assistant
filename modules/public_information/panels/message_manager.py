"""Message manager, editor, workflow, and preview panels."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QTextCursor, QTextListFormat
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from modules.public_information.models.constants import (
    APPROVAL_STEPS,
    AUDIENCES,
    MERGE_FIELDS,
    MESSAGE_STATUSES,
    MESSAGE_TYPES,
    PRIORITIES,
)
from modules.public_information.services import PublicInformationRepository, build_release_html
from modules.public_information.widgets.common import combo, fill_table, selected_row_data


class ApprovalWorkflowPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.message: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Approval Workflow"))
        self.steps = QLabel("")
        self.comments = QTextBrowser()
        layout.addWidget(self.steps)
        layout.addWidget(QLabel("Reviewer Comments"))
        layout.addWidget(self.comments, 1)

    def set_message(self, message: dict[str, Any] | None) -> None:
        self.message = message
        status = (message or {}).get("status", "")
        step_order = list(APPROVAL_STEPS)
        reached = step_order.index(status) if status in step_order else -1
        lines = []
        for i, step in enumerate(step_order):
            marker = "✓" if i <= reached else "○"
            lines.append(f"{marker} {step}")
        self.steps.setText("\n".join(lines))
        if not message or not message.get("id"):
            self.comments.setText("")
            return
        approvals = self.repo.list_approvals(int(message["id"]))
        self.comments.setText("\n\n".join(f"{a['timestamp']} — {a['reviewer_name']} — {a['action']}\n{a['comment']}" for a in approvals))


class ReleasePreviewPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.message: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Preview"))
        header.addStretch(1)
        self.print_button = QPushButton("Print Preview")
        self.pdf_button = QPushButton("Generate PDF")
        self.print_button.clicked.connect(self._not_wired)
        self.pdf_button.clicked.connect(self._not_wired)
        header.addWidget(self.print_button)
        header.addWidget(self.pdf_button)
        layout.addLayout(header)
        self.browser = QTextBrowser()
        layout.addWidget(self.browser, 1)

    def set_message(self, message: dict[str, Any] | None) -> None:
        self.message = message
        template = None
        if message and message.get("template_id"):
            template = self.repo.get_template(int(message["template_id"]))
        self.browser.setHtml(build_release_html(message, template))

    def _not_wired(self) -> None:
        QMessageBox.information(self, "Export Preparation", "Document export is prepared for future forms/export integration.")


class MessageEditor(QWidget):
    saved = Signal(dict)

    def __init__(self, repo: PublicInformationRepository, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user or {}
        self.message: dict[str, Any] = {}
        self.template_lookup: dict[str, int | None] = {"None": None}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.subtitle_edit = QLineEdit()
        self.type_combo = combo(MESSAGE_TYPES)
        self.audience_combo = combo(AUDIENCES)
        self.priority_combo = combo(PRIORITIES, "Normal")
        self.status_combo = combo(MESSAGE_STATUSES, "Draft")
        self.template_combo = QComboBox()
        self.dateline_edit = QLineEdit()
        for label, widget in [
            ("Title", self.title_edit), ("Subtitle", self.subtitle_edit), ("Type", self.type_combo),
            ("Audience", self.audience_combo), ("Priority", self.priority_combo), ("Status", self.status_combo),
            ("Template", self.template_combo), ("Dateline", self.dateline_edit),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)
        toolbar = QToolBar()
        for text, callback in [
            ("Bold", lambda: self.body_edit.setFontWeight(700 if self.body_edit.fontWeight() < 700 else 400)),
            ("Italic", lambda: self.body_edit.setFontItalic(not self.body_edit.fontItalic())),
            ("Underline", lambda: self.body_edit.setFontUnderline(not self.body_edit.fontUnderline())),
            ("Bullets", self._insert_bullets),
            ("Numbered", self._insert_numbered),
            ("Insert Date/Time", self._insert_datetime),
        ]:
            toolbar.addAction(text, callback)
        self.merge_combo = QComboBox()
        self.merge_combo.addItems(["Insert Merge Field", *MERGE_FIELDS])
        self.merge_combo.activated.connect(self._insert_merge_field)
        toolbar.addWidget(self.merge_combo)
        layout.addWidget(toolbar)
        self.body_edit = QTextEdit()
        self.quote_edit = QTextEdit()
        self.safety_edit = QTextEdit()
        self.next_update_edit = QTextEdit()
        self.body_edit.setMinimumHeight(160)
        for editor in (self.quote_edit, self.safety_edit, self.next_update_edit):
            editor.setMaximumHeight(80)
        layout.addWidget(QLabel("Body"))
        layout.addWidget(self.body_edit, 1)
        layout.addWidget(QLabel("Quote Block"))
        layout.addWidget(self.quote_edit)
        layout.addWidget(QLabel("Safety Instructions"))
        layout.addWidget(self.safety_edit)
        layout.addWidget(QLabel("Next Update Statement"))
        layout.addWidget(self.next_update_edit)
        buttons = QHBoxLayout()
        actions = [
            ("Save Draft",           "Draft"),
            ("Submit for Approval",  "Pending Approval"),
            ("Return for Revision",  "Returned for Revision"),
            ("Approve",              "Approved"),
            ("Publish / Release",    "Published"),
            ("Flag Corrections",     "Needs Corrections"),
        ]
        for label, status in actions:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, s=status: self.save(s))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.refresh_templates()
        self.set_message({})

    def refresh_templates(self) -> None:
        current = self.template_combo.currentText() if self.template_combo.count() else "None"
        self.template_combo.clear()
        self.template_lookup = {"None": None}
        for template in self.repo.list_templates(active_only=True):
            name = template.get("template_name") or f"Template {template['id']}"
            self.template_lookup[name] = int(template["id"])
        self.template_combo.addItems(self.template_lookup.keys())
        if current in self.template_lookup:
            self.template_combo.setCurrentText(current)

    def set_message(self, message: dict[str, Any] | None) -> None:
        self.message = dict(message or {})
        self.refresh_templates()
        self.title_edit.setText(self.message.get("title", ""))
        self.subtitle_edit.setText(self.message.get("subtitle", ""))
        self.type_combo.setCurrentText(self.message.get("type", "Press Release"))
        self.audience_combo.setCurrentText(self.message.get("audience", "Public"))
        self.priority_combo.setCurrentText(self.message.get("priority", "Normal"))
        self.status_combo.setCurrentText(self.message.get("status", "Draft"))
        self.dateline_edit.setText(self.message.get("dateline", ""))
        self.body_edit.setPlainText(self.message.get("body", ""))
        self.quote_edit.setPlainText(self.message.get("quote_block", ""))
        self.safety_edit.setPlainText(self.message.get("safety_instructions", ""))
        self.next_update_edit.setPlainText(self.message.get("next_update_statement", ""))
        template_id = self.message.get("template_id")
        for name, candidate in self.template_lookup.items():
            if candidate == template_id:
                self.template_combo.setCurrentText(name)
                break

    def collect(self, status: str | None = None) -> dict[str, Any]:
        user_name = str(self.current_user.get("name") or self.current_user.get("id") or "")
        selected_template = self.template_lookup.get(self.template_combo.currentText())
        return {
            **self.message,
            "title": self.title_edit.text(),
            "subtitle": self.subtitle_edit.text(),
            "type": self.type_combo.currentText(),
            "audience": self.audience_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "status": status or self.status_combo.currentText(),
            "dateline": self.dateline_edit.text(),
            "body": self.body_edit.toPlainText(),
            "quote_block": self.quote_edit.toPlainText(),
            "safety_instructions": self.safety_edit.toPlainText(),
            "next_update_statement": self.next_update_edit.toPlainText(),
            "created_by": self.message.get("created_by") or user_name,
            "template_id": selected_template,
        }

    def save(self, status: str = "Draft") -> None:
        message = self.repo.save_message(self.collect(status), str(self.current_user.get("id", "")))
        if self.message.get("id") and status != self.message.get("status"):
            message = self.repo.set_message_status(int(message["id"]), status, str(self.current_user.get("id", "")))
        elif status != "Draft":
            message = self.repo.set_message_status(int(message["id"]), status, str(self.current_user.get("id", "")))
        self.set_message(message)
        self.saved.emit(message)

    def _insert_bullets(self) -> None:
        self.body_edit.textCursor().createList(QTextListFormat.ListDisc)

    def _insert_numbered(self) -> None:
        self.body_edit.textCursor().createList(QTextListFormat.ListDecimal)

    def _insert_datetime(self) -> None:
        self.body_edit.insertPlainText(QDateTime.currentDateTime().toString(Qt.ISODate))

    def _insert_merge_field(self, index: int) -> None:
        if index > 0:
            self.body_edit.insertPlainText(self.merge_combo.itemText(index))
            self.merge_combo.setCurrentIndex(0)


class MessageManagerPanel(QWidget):
    changed = Signal()

    def __init__(self, repo: PublicInformationRepository, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user or {}
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.new_button = QPushButton("New Message")
        self.refresh_button = QPushButton("Refresh")
        top.addWidget(self.new_button)
        top.addWidget(self.refresh_button)
        top.addStretch(1)
        layout.addLayout(top)
        splitter = QSplitter()
        self.table = QTableWidget()
        splitter.addWidget(self.table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.editor = MessageEditor(repo, current_user)
        side_splitter = QSplitter(Qt.Vertical)
        self.preview = ReleasePreviewPanel(repo)
        self.workflow = ApprovalWorkflowPanel(repo)
        side_splitter.addWidget(self.preview)
        side_splitter.addWidget(self.workflow)
        right_layout.addWidget(self.editor, 2)
        right_layout.addWidget(side_splitter, 1)
        splitter.addWidget(right)
        splitter.setSizes([350, 900])
        layout.addWidget(splitter, 1)
        self.new_button.clicked.connect(lambda: self.select_message(None))
        self.refresh_button.clicked.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._table_selection_changed)
        self.editor.saved.connect(self._saved)
        self.refresh()

    def refresh(self) -> None:
        rows = self.repo.list_messages()
        fill_table(
            self.table,
            rows,
            [("ID", "id"), ("Title", "title"), ("Type", "type"), ("Audience", "audience"), ("Priority", "priority"), ("Status", "status"), ("Updated", "updated_at")],
        )
        self.changed.emit()

    def select_message(self, message: dict[str, Any] | None) -> None:
        self.editor.set_message(message or {})
        self.preview.set_message(message or {})
        self.workflow.set_message(message or {})

    def _table_selection_changed(self) -> None:
        row = selected_row_data(self.table)
        self.select_message(row)

    def _saved(self, message: dict[str, Any]) -> None:
        self.refresh()
        self.preview.set_message(message)
        self.workflow.set_message(message)
