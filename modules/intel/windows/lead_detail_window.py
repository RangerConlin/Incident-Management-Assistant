"""LeadDetailWindow — modeless window for viewing and managing a single Lead."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QFrame, QDialog,
    QFormLayout, QLineEdit, QComboBox, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal

from modules.intel.models.leads import Lead, LeadStatus, LeadPriority, LeadSourceType
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.services.intel_service import IntelService


class _FieldRow(QWidget):
    def __init__(self, label: str, value: str | None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        lbl = QLabel(label + ":")
        lbl.setStyleSheet("font-weight: 600; min-width: 120px;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        val = QLabel(value or "—")
        val.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addWidget(val, 1)


class LeadDetailWindow(QMainWindow):
    """Modeless detail window for a single Lead.

    Provides read-only view of lead data with action buttons for common
    workflow operations (assign, convert, close, reject).
    """

    lead_updated = Signal(object)   # emits updated Lead

    def __init__(
        self,
        lead: Lead,
        service: IntelService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._lead = lead
        self._service = service

        self.setWindowTitle(f"{lead.display_number}: {lead.title}")
        self.resize(680, 520)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        root.addWidget(self._build_header())

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = self._build_body()
        scroll.setWidget(body)
        root.addWidget(scroll)

        # Action bar at the bottom
        root.addWidget(self._build_action_bar())

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(dark); padding: 12px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        num_lbl = QLabel(self._lead.display_number)
        num_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: palette(placeholderText);")
        title_lbl = QLabel(self._lead.title)
        title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: palette(bright-text);"
        )
        priority_chip = StatusChip(self._lead.priority)
        status_chip = StatusChip(self._lead.status)

        layout.addWidget(num_lbl)
        layout.addWidget(title_lbl)
        layout.addStretch()
        layout.addWidget(priority_chip)
        layout.addWidget(status_chip)
        return w

    def _build_body(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        lead = self._lead

        # Summary
        if lead.summary:
            summary_lbl = QLabel(lead.summary)
            summary_lbl.setWordWrap(True)
            summary_lbl.setStyleSheet("font-size: 13px; margin-bottom: 8px;")
            layout.addWidget(summary_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        layout.addWidget(QLabel("Source Information"))
        layout.addWidget(_FieldRow("Source Type", lead.source_type))
        layout.addWidget(_FieldRow("Reported By", lead.reported_by))
        layout.addWidget(_FieldRow("Contact Info", lead.contact_info))

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        layout.addWidget(QLabel("Location"))
        layout.addWidget(_FieldRow("Location", lead.location_text))

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        layout.addWidget(sep3)

        layout.addWidget(QLabel("Assignment"))
        layout.addWidget(_FieldRow("Assigned To", lead.assigned_to))
        layout.addWidget(_FieldRow("Status", lead.status))

        if lead.converted_to_type:
            sep4 = QFrame()
            sep4.setFrameShape(QFrame.HLine)
            layout.addWidget(sep4)
            layout.addWidget(QLabel("Conversion"))
            layout.addWidget(_FieldRow("Converted To", lead.converted_to_type.title()))
            layout.addWidget(_FieldRow("Target ID", lead.converted_to_id))

        if lead.notes:
            sep5 = QFrame()
            sep5.setFrameShape(QFrame.HLine)
            layout.addWidget(sep5)
            layout.addWidget(QLabel("Notes"))
            notes_lbl = QLabel(lead.notes)
            notes_lbl.setWordWrap(True)
            layout.addWidget(notes_lbl)

        sep6 = QFrame()
        sep6.setFrameShape(QFrame.HLine)
        layout.addWidget(sep6)
        layout.addWidget(_FieldRow("Created", lead.created_at[:16].replace("T", "  ")))
        layout.addWidget(_FieldRow("Updated", lead.updated_at[:16].replace("T", "  ")))

        layout.addStretch()
        return w

    def _build_action_bar(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(window); border-top: 1px solid palette(mid);")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        assign_btn = QPushButton("Assign")
        assign_btn.clicked.connect(self._assign)

        convert_btn = QPushButton("Convert →")
        convert_btn.clicked.connect(self._convert)

        close_btn = QPushButton("Close Lead")
        close_btn.clicked.connect(self._close_lead)

        reject_btn = QPushButton("Reject")
        reject_btn.clicked.connect(self._reject)

        layout.addStretch()
        layout.addWidget(assign_btn)
        layout.addWidget(convert_btn)
        layout.addWidget(close_btn)
        layout.addWidget(reject_btn)
        return w

    def _assign(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Assign Lead", "Assign to:", text=self._lead.assigned_to or ""
        )
        if ok:
            updated = self._service.leads.update(self._lead.id, {
                "assigned_to": name.strip() or None,
                "status": LeadStatus.ASSIGNED if name.strip() else self._lead.status,
            })
            if updated:
                self._lead = updated
                self.lead_updated.emit(updated)

    def _convert(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        choices = ["subject", "item", "assessment"]
        choice, ok = QInputDialog.getItem(
            self, "Convert Lead", "Convert this lead to:", choices, 0, False
        )
        if ok:
            updated = self._service.leads.convert(self._lead.id, choice)
            if updated:
                self._lead = updated
                self.lead_updated.emit(updated)

    def _close_lead(self) -> None:
        self._service.leads.close(self._lead.id)
        self.lead_updated.emit(self._lead)
        self.close()

    def _reject(self) -> None:
        updated = self._service.leads.update(self._lead.id, {"status": LeadStatus.REJECTED})
        if updated:
            self._lead = updated
            self.lead_updated.emit(updated)
            self.close()
