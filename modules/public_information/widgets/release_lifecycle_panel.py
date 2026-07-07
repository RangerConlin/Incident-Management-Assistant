"""Lifecycle and approval controls for Public Information releases."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.public_information.services import PublicInformationRepository
from modules.public_information.services.release_workflow import (
    approval_history_rows,
    lifecycle_actions_for_status,
)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


class ReleaseLifecyclePanel(QWidget):
    action_requested = Signal(str)
    preview_requested = Signal()

    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.message: dict[str, Any] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel("Lifecycle"))
        header.addStretch(1)
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.preview_requested.emit)
        header.addWidget(self.preview_button)
        layout.addLayout(header)

        status_box = QGroupBox("Current Status")
        status_layout = QVBoxLayout(status_box)
        self.status_label = QLabel("Draft")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        self.actions_layout = QHBoxLayout()
        status_layout.addLayout(self.actions_layout)
        layout.addWidget(status_box)

        comment_box = QGroupBox("Reviewer / Lifecycle Comment")
        comment_layout = QVBoxLayout(comment_box)
        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("Add internal reviewer or lifecycle notes here.")
        self.comment_edit.setMaximumHeight(110)
        comment_layout.addWidget(self.comment_edit)
        layout.addWidget(comment_box)

        checks_box = QGroupBox("Basic Release Checks")
        checks_layout = QVBoxLayout(checks_box)
        self.checks_browser = QTextBrowser()
        self.checks_browser.setMinimumHeight(120)
        checks_layout.addWidget(self.checks_browser)
        layout.addWidget(checks_box)

        approval_box = QGroupBox("Approval History")
        approval_layout = QVBoxLayout(approval_box)
        self.approval_browser = QTextBrowser()
        self.approval_browser.setMinimumHeight(120)
        approval_layout.addWidget(self.approval_browser)
        layout.addWidget(approval_box)

        history_box = QGroupBox("Lifecycle History")
        history_layout = QVBoxLayout(history_box)
        self.history_browser = QTextBrowser()
        self.history_browser.setMinimumHeight(120)
        history_layout.addWidget(self.history_browser)
        layout.addWidget(history_box)

        metadata_box = QGroupBox("Release Metadata")
        metadata_layout = QFormLayout(metadata_box)
        self.prepared_by_label = QLabel("—")
        self.approved_by_label = QLabel("—")
        self.approved_at_label = QLabel("—")
        self.published_by_label = QLabel("—")
        self.published_at_label = QLabel("—")
        self.archived_by_label = QLabel("—")
        self.archived_at_label = QLabel("—")
        metadata_layout.addRow("Prepared By", self.prepared_by_label)
        metadata_layout.addRow("Approved By", self.approved_by_label)
        metadata_layout.addRow("Approved At", self.approved_at_label)
        metadata_layout.addRow("Published By", self.published_by_label)
        metadata_layout.addRow("Published At", self.published_at_label)
        metadata_layout.addRow("Archived By", self.archived_by_label)
        metadata_layout.addRow("Archived At", self.archived_at_label)
        layout.addWidget(metadata_box)
        layout.addStretch(1)

        self.set_release({})

    def set_release(self, message: dict[str, Any] | None) -> None:
        self.message = dict(message or {})
        status = str(self.message.get("status") or "Draft")
        self.status_label.setText(f"Status: {status}")
        self._rebuild_actions(status)
        self._refresh_checks()
        self._refresh_history()
        self._refresh_metadata()

    def comment(self) -> str:
        return self.comment_edit.toPlainText().strip()

    def clear_comment(self) -> None:
        self.comment_edit.clear()

    def _rebuild_actions(self, status: str) -> None:
        _clear_layout(self.actions_layout)
        actions = lifecycle_actions_for_status(status)
        if not actions:
            self.actions_layout.addWidget(QLabel("No lifecycle actions available for this status."))
            return
        for action in actions:
            button = QPushButton(action.label)
            button.clicked.connect(lambda _checked=False, key=action.key: self.action_requested.emit(key))
            self.actions_layout.addWidget(button)
        self.actions_layout.addStretch(1)

    def _refresh_checks(self) -> None:
        message = self.message
        checks = [
            ("Headline", bool(message.get("title"))),
            ("Release Body", bool(message.get("body"))),
            ("Dateline", bool(message.get("dateline"))),
            ("Next Update", bool(message.get("next_update_statement"))),
            ("Boilerplate", bool(message.get("boilerplate"))),
        ]
        rows = []
        for label, passed in checks:
            state = "Ready" if passed else "Missing"
            rows.append(f"<li>{label}: {state}</li>")
        self.checks_browser.setHtml("<ul>" + "".join(rows) + "</ul>")

    def _refresh_history(self) -> None:
        approvals = self.repo.list_approvals(int(self.message["id"])) if self.message.get("id") else []
        lifecycle_rows = approvals
        approval_rows = approval_history_rows(approvals)
        self.approval_browser.setHtml(self._history_html(approval_rows))
        self.history_browser.setHtml(self._history_html(lifecycle_rows))

    def _refresh_metadata(self) -> None:
        self.prepared_by_label.setText(str(self.message.get("created_by") or "—"))
        self.approved_by_label.setText(str(self.message.get("approved_by") or "—"))
        self.approved_at_label.setText(str(self.message.get("approved_at") or "—"))
        self.published_by_label.setText(str(self.message.get("published_by") or "—"))
        self.published_at_label.setText(str(self.message.get("published_at") or "—"))
        self.archived_by_label.setText(str(self.message.get("archived_by") or "—"))
        self.archived_at_label.setText(str(self.message.get("archived_at") or "—"))

    @staticmethod
    def _history_html(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p>No history recorded yet.</p>"
        items = []
        for row in rows:
            who = row.get("reviewer_name") or row.get("reviewer_id") or ""
            action = row.get("action") or ""
            timestamp = row.get("timestamp") or ""
            comment = row.get("comment") or ""
            parts = [f"<strong>{action}</strong>"]
            if timestamp:
                parts.append(str(timestamp))
            if who:
                parts.append(str(who))
            line = " - ".join(parts)
            if comment:
                line = f"{line}<br>{comment}"
            items.append(f"<li>{line}</li>")
        return "<ul>" + "".join(items) + "</ul>"

