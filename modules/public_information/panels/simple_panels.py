"""Table-based Public Information panels for logs, templates, and trackers."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.public_information.models.constants import (
    DISTRIBUTION_CHANNELS,
    MEDIA_STATUSES,
    MISINFORMATION_SEVERITIES,
    MISINFORMATION_STATUSES,
    OPERATIONAL_IMPACTS,
    RESPONSE_DECISIONS,
    TALKING_POINT_CATEGORIES,
    TALKING_POINT_STATUSES,
    TEMPLATE_TYPES,
    VERIFICATION_STATUSES,
)
from modules.public_information.services import PublicInformationRepository
from modules.public_information.widgets.common import SimpleRecordDialog, combo, fill_table, selected_row_data


class MisinformationDialog(QDialog):
    def __init__(self, repo: PublicInformationRepository, data: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.data = dict(data or {})
        self.setWindowTitle("Misinformation Item")
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._overview_tab(), "Overview")
        tabs.addTab(self._verification_tab(), "Verification")
        tabs.addTab(self._response_tab(), "Response")
        tabs.addTab(self._timeline_tab(), "Timeline")
        layout.addWidget(tabs)
        buttons = QHBoxLayout()
        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _line(self, key: str) -> QLineEdit:
        widget = QLineEdit(str(self.data.get(key, "")))
        setattr(self, key, widget)
        return widget

    def _text(self, key: str) -> QTextEdit:
        widget = QTextEdit(str(self.data.get(key, "")))
        setattr(self, key, widget)
        return widget

    def _combo(self, key: str, values: list[str]) -> Any:
        widget = combo(values, str(self.data.get(key, values[0] if values else "")))
        setattr(self, key, widget)
        return widget

    def _overview_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.addRow("Claim / Rumor", self._text("claim_rumor"))
        form.addRow("Source", self._line("source"))
        form.addRow("Platform", self._line("platform"))
        form.addRow("First Observed", self._line("first_seen"))
        form.addRow("Last Observed", self._line("last_seen"))
        form.addRow("Reported By", self._line("reported_by"))
        form.addRow("Severity", self._combo("severity", MISINFORMATION_SEVERITIES))
        form.addRow("Operational Impact", self._combo("operational_impact", OPERATIONAL_IMPACTS))
        form.addRow("Current Status", self._combo("status", MISINFORMATION_STATUSES))
        form.addRow("Attachments Placeholder", self._line("attachments_note"))
        return page

    def _verification_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.addRow("Verification Status", self._combo("verification_status", VERIFICATION_STATUSES))
        form.addRow("Source Reliability", self._line("source_reliability"))
        form.addRow("Notes", self._text("verification_notes"))
        form.addRow("Related Confirmed Facts", self._text("related_confirmed_facts"))
        return page

    def _response_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.addRow("Response Decision", self._combo("response_decision", RESPONSE_DECISIONS))
        form.addRow("Linked PIO Message / Correction", self._line("linked_response"))
        form.addRow("Approval Status", self._line("approval_status"))
        form.addRow("Distribution Channels", self._line("distribution_channels"))
        return page

    def _timeline_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.timeline = QListWidget()
        if self.data.get("id"):
            for event in self.repo.list_misinformation_timeline(int(self.data["id"])):
                self.timeline.addItem(f"{event['event_time']} — {event['event_text']}")
        self.timeline_entry = QLineEdit()
        add = QPushButton("Add Timeline Event")
        add.clicked.connect(self._add_timeline_event)
        layout.addWidget(self.timeline)
        layout.addWidget(self.timeline_entry)
        layout.addWidget(add)
        return page

    def _add_timeline_event(self) -> None:
        text = self.timeline_entry.text().strip()
        if not text:
            return
        if self.data.get("id"):
            self.repo.add_misinformation_timeline(int(self.data["id"]), text)
            self.timeline.addItem(text)
            self.timeline_entry.clear()
        else:
            QMessageBox.information(self, "Save Required", "Save the item before adding timeline events.")

    def values(self) -> dict[str, Any]:
        result = dict(self.data)
        for key in [
            "claim_rumor", "source", "platform", "first_seen", "last_seen", "reported_by", "attachments_note",
            "source_reliability", "verification_notes", "related_confirmed_facts", "linked_response", "approval_status",
            "distribution_channels", "assigned_to",
        ]:
            widget = getattr(self, key, None)
            if isinstance(widget, QLineEdit):
                result[key] = widget.text()
            elif isinstance(widget, QTextEdit):
                result[key] = widget.toPlainText()
        for key in ["severity", "operational_impact", "status", "verification_status", "response_decision"]:
            widget = getattr(self, key, None)
            if widget is not None:
                result[key] = widget.currentText()
        return result


class MisinformationPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        add = QPushButton("Add Item")
        edit = QPushButton("Edit Selected")
        refresh = QPushButton("Refresh")
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.table = QTableWidget()
        layout.addWidget(self.table, 1)
        add.clicked.connect(lambda: self.edit_item(None))
        edit.clicked.connect(lambda: self.edit_item(selected_row_data(self.table)))
        refresh.clicked.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        rows = self.repo.list_records("pio_misinformation_items", "last_update DESC, id DESC")
        fill_table(self.table, rows, [("Severity", "severity"), ("Claim / Rumor", "claim_rumor"), ("Source / Platform", "platform"), ("First Seen", "first_seen"), ("Last Seen", "last_seen"), ("Operational Impact", "operational_impact"), ("Status", "status"), ("Assigned To", "assigned_to"), ("Linked Response", "linked_response"), ("Last Update", "last_update")])

    def edit_item(self, data: dict[str, Any] | None) -> None:
        dialog = MisinformationDialog(self.repo, data, self)
        if dialog.exec() == QDialog.Accepted:
            self.repo.save_record("pio_misinformation_items", dialog.values(), "last_update")
            self.refresh()


class MediaLogPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user or {}
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        add = QPushButton("Add Inquiry")
        edit = QPushButton("Edit Selected")
        draft = QPushButton("Create Response Draft")
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addWidget(draft)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.table = QTableWidget()
        layout.addWidget(self.table, 1)
        add.clicked.connect(lambda: self.edit_item(None))
        edit.clicked.connect(lambda: self.edit_item(selected_row_data(self.table)))
        draft.clicked.connect(self.create_draft)
        self.refresh()

    def refresh(self) -> None:
        rows = self.repo.list_records("pio_media_log", "time DESC, id DESC")
        fill_table(self.table, rows, [("Time", "time"), ("Outlet / Agency", "outlet_agency"), ("Contact Name", "contact_name"), ("Contact Info", "contact_info"), ("Topic", "topic"), ("Deadline", "deadline"), ("Assigned To", "assigned_to"), ("Status", "status"), ("Related Message", "related_message_id"), ("Follow-Up Needed", "follow_up_needed")])

    def edit_item(self, data: dict[str, Any] | None) -> None:
        fields = [("Time", "time", "line", None), ("Outlet / Agency", "outlet_agency", "line", None), ("Contact Name", "contact_name", "line", None), ("Contact Info", "contact_info", "line", None), ("Topic", "topic", "line", None), ("Deadline", "deadline", "line", None), ("Assigned To", "assigned_to", "line", None), ("Status", "status", "combo", MEDIA_STATUSES), ("Related Message", "related_message_id", "line", None), ("Follow-Up Needed", "follow_up_needed", "check", None)]
        dialog = SimpleRecordDialog("Media Inquiry", fields, data, self)
        if dialog.exec() == QDialog.Accepted:
            self.repo.save_record("pio_media_log", dialog.values())
            self.refresh()

    def create_draft(self) -> None:
        row = selected_row_data(self.table)
        if not row:
            return
        message = self.repo.create_response_draft_from_media(int(row["id"]), str(self.current_user.get("id", "")))
        QMessageBox.information(self, "Response Draft", f"Created response draft #{message.get('id')}.")
        self.refresh()


class TalkingPointsPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        add = QPushButton("Add Talking Point")
        edit = QPushButton("Edit Selected")
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.table = QTableWidget()
        layout.addWidget(self.table, 1)
        add.clicked.connect(lambda: self.edit_item(None))
        edit.clicked.connect(lambda: self.edit_item(selected_row_data(self.table)))
        self.refresh()

    def refresh(self) -> None:
        fill_table(self.table, self.repo.list_records("pio_talking_points", "updated_at DESC, id DESC"), [("Title", "title"), ("Category", "category"), ("Body", "body"), ("Status", "status"), ("Created By", "created_by"), ("Approved By", "approved_by"), ("Updated At", "updated_at")])

    def edit_item(self, data: dict[str, Any] | None) -> None:
        fields = [("Title", "title", "line", None), ("Category", "category", "combo", TALKING_POINT_CATEGORIES), ("Body", "body", "text", None), ("Status", "status", "combo", TALKING_POINT_STATUSES), ("Created By", "created_by", "line", None), ("Approved By", "approved_by", "line", None)]
        dialog = SimpleRecordDialog("Talking Point", fields, data, self)
        if dialog.exec() == QDialog.Accepted:
            self.repo.save_record("pio_talking_points", dialog.values(), "updated_at")
            self.refresh()


class TemplateManagerPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        add = QPushButton("Add Template")
        edit = QPushButton("Edit Selected")
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Supported merge fields are listed in the editor insert menu."))
        self.table = QTableWidget()
        layout.addWidget(self.table, 1)
        add.clicked.connect(lambda: self.edit_item(None))
        edit.clicked.connect(lambda: self.edit_item(selected_row_data(self.table)))
        self.refresh()

    def refresh(self) -> None:
        fill_table(self.table, self.repo.list_templates(), [("Name", "template_name"), ("Type", "template_type"), ("Agency", "agency_name"), ("Release Label", "release_label"), ("Active", "is_active"), ("Version", "version"), ("Updated", "updated_at")])

    def edit_item(self, data: dict[str, Any] | None) -> None:
        fields = [("Template Name", "template_name", "line", None), ("Template Type", "template_type", "combo", TEMPLATE_TYPES), ("Agency Name", "agency_name", "line", None), ("Header Text", "header_text", "text", None), ("Footer Text", "footer_text", "text", None), ("Contact Block", "contact_block", "text", None), ("Logo Path / Asset Path", "logo_path", "line", None), ("Release Label", "release_label", "line", None), ("Default Classification Label", "default_classification_label", "line", None), ("Default Font Name", "default_font_name", "line", None), ("Default Footer Disclaimer", "default_footer_disclaimer", "text", None), ("Is Active", "is_active", "check", None), ("Version", "version", "line", None)]
        dialog = SimpleRecordDialog("Template", fields, data or {"is_active": 1, "version": 1}, self)
        if dialog.exec() == QDialog.Accepted:
            values = dialog.values()
            values["version"] = int(values.get("version") or 1)
            self.repo.save_template(values)
            self.refresh()


class DistributionLogPanel(QWidget):
    def __init__(self, repo: PublicInformationRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        add = QPushButton("Add Distribution Record")
        edit = QPushButton("Edit Selected")
        buttons.addWidget(add)
        buttons.addWidget(edit)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.table = QTableWidget()
        layout.addWidget(self.table, 1)
        add.clicked.connect(lambda: self.edit_item(None))
        edit.clicked.connect(lambda: self.edit_item(selected_row_data(self.table)))
        self.refresh()

    def refresh(self) -> None:
        fill_table(self.table, self.repo.list_records("pio_distribution_log", "distributed_at DESC, id DESC"), [("Message ID", "message_id"), ("Channel", "channel"), ("Date/Time", "distributed_at"), ("Distributed By", "distributed_by"), ("Audience", "audience"), ("Recipient / Outlet", "recipient_outlet"), ("Confirmation Notes", "confirmation_notes"), ("Attachment / Export Path", "attachment_export_path")])

    def edit_item(self, data: dict[str, Any] | None) -> None:
        fields = [("Message ID", "message_id", "line", None), ("Channel", "channel", "combo", DISTRIBUTION_CHANNELS), ("Date/Time", "distributed_at", "line", None), ("Distributed By", "distributed_by", "line", None), ("Audience", "audience", "line", None), ("Recipient / Outlet", "recipient_outlet", "line", None), ("Confirmation Notes", "confirmation_notes", "text", None), ("Attachment / Export Path", "attachment_export_path", "line", None)]
        dialog = SimpleRecordDialog("Distribution Record", fields, data, self)
        if dialog.exec() == QDialog.Accepted:
            self.repo.save_record("pio_distribution_log", dialog.values())
            self.refresh()
