"""Quick personnel check-in window for rapid ID scanning workflows."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.logistics.checkin.services import CheckInService, get_service
from utils import incident_context


class QuickCheckInWindow(QWidget):
    """Stripped-down personnel check-in window for scan-and-go workflows."""

    def __init__(self, parent: Optional[QWidget] = None, checkin_service: Optional[CheckInService] = None) -> None:
        super().__init__(parent)
        self._checkin_service = checkin_service or get_service()
        self._selected_record: dict[str, Any] | None = None
        self._build_ui()
        self._reset_display()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self._center_on_screen()
        self._entry.setFocus()
        self._entry.selectAll()

    def _build_ui(self) -> None:
        self.setWindowTitle("Quick Check In")
        self.resize(720, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("Quick Check In", self)
        title.setProperty("sectionHeader", True)
        layout.addWidget(title)

        self._context_label = QLabel(self._incident_context_text(), self)
        self._context_label.setWordWrap(True)
        layout.addWidget(self._context_label)

        entry_row = QHBoxLayout()
        entry_row.setSpacing(8)
        self._entry = QLineEdit(self)
        self._entry.setPlaceholderText("Scan or enter personnel ID, CAPID, name, callsign, or phone")
        self._entry.returnPressed.connect(self.lookup_record)
        search_btn = QPushButton("Lookup", self)
        search_btn.clicked.connect(self.lookup_record)
        clear_btn = QPushButton("Clear", self)
        clear_btn.clicked.connect(self.clear_form)
        entry_row.addWidget(self._entry, 1)
        entry_row.addWidget(search_btn)
        entry_row.addWidget(clear_btn)
        layout.addLayout(entry_row)

        self._display = QTextEdit(self)
        self._display.setReadOnly(True)
        self._display.setMinimumHeight(220)
        layout.addWidget(self._display, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self._expected_btn = self._make_status_button("Expected")
        self._expected_btn.clicked.connect(lambda: self.apply_status("Expected"))
        self._enroute_btn = self._make_status_button("Enroute")
        self._enroute_btn.clicked.connect(lambda: self.apply_status("Enroute"))
        self._checkin_btn = self._make_status_button("Checked In")
        self._checkin_btn.clicked.connect(lambda: self.apply_status("Checked In"))
        self._checkout_btn = self._make_status_button("Check Out")
        self._checkout_btn.clicked.connect(lambda: self.apply_status("Demobilized"))
        button_row.addWidget(self._expected_btn)
        button_row.addWidget(self._enroute_btn)
        button_row.addWidget(self._checkin_btn)
        button_row.addWidget(self._checkout_btn)
        layout.addLayout(button_row)

    def _make_status_button(self, label: str) -> QPushButton:
        button = QPushButton(label, self)
        button.setMinimumHeight(56)
        return button

    def _center_on_screen(self) -> None:
        window = self.windowHandle()
        screen = window.screen() if window and window.screen() is not None else QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _incident_context_text(self) -> str:
        incident_id = incident_context.get_active_incident_id() or "No active incident"
        return f"Incident: {incident_id}"

    def _reset_display(self) -> None:
        self._context_label.setText(self._incident_context_text())
        self._display.setPlainText("Ready for scan.")
        self._selected_record = None

    def clear_form(self) -> None:
        self._entry.clear()
        self._reset_display()
        self._entry.setFocus()

    def lookup_record(self) -> None:
        query = self._entry.text().strip()
        if not query:
            self._display.setPlainText("Enter a personnel identifier to search.")
            self._selected_record = None
            return

        try:
            matches = self._checkin_service.search_master_records("personnel", query)
        except Exception as exc:  # noqa: BLE001 - surface service failure in UI
            self._display.setPlainText(f"Lookup failed:\n{exc}")
            self._selected_record = None
            return

        record = self._select_best_match(query, matches)
        if record is None:
            self._display.setPlainText(f"No personnel match for '{query}'.")
            self._selected_record = None
            return

        self._selected_record = record
        self._display.setPlainText(self._format_record(record))

    def _select_best_match(self, query: str, matches: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not matches:
            return None
        query_lower = query.strip().lower()
        for record in matches:
            if query_lower in self._personnel_tokens(record):
                return record
        return matches[0]

    def _personnel_tokens(self, record: dict[str, Any]) -> set[str]:
        return {
            str(record.get("id") or "").strip().lower(),
            str(record.get("person_id") or "").strip().lower(),
            str(record.get("name") or "").strip().lower(),
            str(record.get("callsign") or "").strip().lower(),
            str(record.get("phone") or "").strip().lower(),
            str(record.get("organization") or "").strip().lower(),
            str(record.get("primary_role") or record.get("role") or "").strip().lower(),
        }

    def _format_record(self, record: dict[str, Any], message: str | None = None) -> str:
        lines = [
            f"ID: {record.get('person_id') or record.get('id') or '—'}",
            f"Name: {record.get('name') or '—'}",
            f"Organization: {record.get('organization') or '—'}",
            f"Phone: {record.get('phone') or '—'}",
            f"Role: {record.get('primary_role') or record.get('role') or '—'}",
            f"Current Status: {record.get('status') or 'Pending'}",
            f"Checked In: {'Yes' if record.get('_checked_in') else 'No'}",
        ]
        if message:
            lines.extend(["", message])
        return "\n".join(lines)

    def apply_status(self, status: str) -> None:
        record = self._selected_record
        if record is None:
            self.lookup_record()
            record = self._selected_record
        if record is None:
            QMessageBox.information(self, "Quick Check In", "Scan or search for a person first.")
            return

        person_id = str(record.get("id") or record.get("person_id") or "")
        if not person_id:
            QMessageBox.warning(self, "Quick Check In", "The selected record is missing a personnel identifier.")
            return

        try:
            if status == "Checked In":
                updated = self._checkin_service.transition_to_checked_in(person_id)
            else:
                updated = self._checkin_service.set_planning_status(person_id, status)
                if updated is None:
                    updated = self._checkin_service.check_in(
                        "personnel",
                        person_id,
                        overrides={
                            "status": status,
                            "checked_in_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                        },
                    )
            if isinstance(updated, dict):
                record.update(updated)
            record["_checked_in"] = status == "Checked In"
            record["status"] = status
            self._display.setPlainText(self._format_record(record, message=f"{status} recorded."))
            self._entry.selectAll()
            self._entry.setFocus()
        except Exception as exc:  # noqa: BLE001 - surface service failure in UI
            QMessageBox.warning(self, "Quick Check In", str(exc))


CheckInWindow = QuickCheckInWindow

__all__ = ["CheckInWindow", "QuickCheckInWindow"]
