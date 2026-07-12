"""ICS-211 Check-In Workbench (Qt Widgets)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QDateTimeEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from utils.org_combo import make_org_combo
from utils import incident_context
from utils.api_client import api_client
from notifications.models.notification import Notification
from notifications.services.notifier import get_notifier

from modules.operations.teams.data.repository import get_team
from modules.logistics.checkin.services import CheckInService, get_service

logger = logging.getLogger(__name__)

CHECKED_IN_STATUSES = {
    "Available",
    "Assigned",
    "Out of Service",
    "Preparing for Demobilization",
    "Checked In",
}


@dataclass(slots=True)
class LookupResult:
    record: dict[str, Any]
    resource_type: str


class ICS211CheckInWindow(QWidget):
    """Tabbed workbench for fast incident intake and team check-in."""

    def __init__(self, parent: Optional[QWidget] = None, checkin_service: Optional[CheckInService] = None) -> None:
        super().__init__(parent)
        self._id_inputs: dict[str, QLineEdit] = {}
        self._previews: dict[str, QLabel] = {}
        self._org_combos: dict[str, QComboBox] = {}
        self._pickers: dict[str, QComboBox] = {}
        self._reporting_inputs: dict[str, QLineEdit] = {}
        self._ldw_datetimes: dict[str, QDateTimeEdit] = {}
        self._ldw_enabled: dict[str, QCheckBox] = {}
        self._ldw_notes: dict[str, QLineEdit] = {}
        self._checkin_notes: dict[str, QLineEdit] = {}
        self._active_selection: dict[str, dict[str, Any]] = {}
        self._team_rows: list[dict[str, Any]] = []
        self._checkin_service = checkin_service or get_service()
        self._build_ui()
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._center_on_screen()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        header = QLabel("ICS-211 Check-In")
        header.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(header)

        context = QLabel(self._incident_context_text())
        context.setWordWrap(True)
        context.setObjectName("incidentContext")
        layout.addWidget(context)
        self._context_label = context

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_resource_tab("personnel"), "Personnel")
        self.tabs.addTab(self._build_team_tab(), "Groups / Teams")
        self.tabs.addTab(self._build_resource_tab("vehicle"), "Vehicles")
        self.tabs.addTab(self._build_resource_tab("aircraft"), "Aircraft")
        self.tabs.addTab(self._build_resource_tab("equipment"), "Equipment")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

    def _incident_context_text(self) -> str:
        incident_id = incident_context.get_active_incident_id() or "No active incident"
        op_period = None
        try:
            op_period = incident_context.get_active_operational_period()
        except Exception:
            op_period = None
        if op_period:
            return f"Incident: {incident_id} | Operational Period: {op_period}"
        return f"Incident: {incident_id}"

    def _center_on_screen(self) -> None:
        window = self.windowHandle()
        screen = window.screen() if window and window.screen() is not None else QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _build_resource_tab(self, resource_type: str) -> QWidget:
        tab = QWidget(self)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        top_actions = QHBoxLayout()
        top_actions.setSpacing(8)
        check_btn = QPushButton("Check In Selected")
        check_btn.clicked.connect(lambda _, rt=resource_type: self._check_in_current(rt))
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda _, rt=resource_type: self._clear_tab(rt))
        top_actions.addWidget(check_btn)
        top_actions.addWidget(clear_btn)
        top_actions.addStretch(1)
        outer.addLayout(top_actions)

        section1 = self._section_frame("Fast Check-In")
        form1 = QHBoxLayout()
        form1.setSpacing(8)
        self._id_inputs[resource_type] = QLineEdit()
        self._id_inputs[resource_type].setPlaceholderText(self._lookup_placeholder(resource_type))
        self._id_inputs[resource_type].returnPressed.connect(lambda rt=resource_type: self._lookup_resource(rt))
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(lambda _, rt=resource_type: self._lookup_resource(rt))
        form1.addWidget(self._id_inputs[resource_type], 2)
        form1.addWidget(search_btn)
        section1.layout().addLayout(form1)
        section1.layout().addWidget(self._preview_label(resource_type))
        outer.addWidget(section1)
        outer.addSpacing(8)

        section2 = self._section_frame("Select Existing Record")
        org_row = QHBoxLayout()
        org_row.setSpacing(8)
        org_combo = make_org_combo()
        org_combo.setCurrentIndex(-1)
        org_combo.currentTextChanged.connect(lambda _: self._refresh_resource_picker(resource_type))
        picker = QComboBox()
        picker.setEditable(True)
        picker.setInsertPolicy(QComboBox.NoInsert)
        picker.setPlaceholderText("No record selected")
        picker.clear()
        picker.currentIndexChanged.connect(lambda _: self._populate_preview_from_picker(resource_type))
        load_btn = QPushButton("Load Records")
        load_btn.clicked.connect(lambda _, rt=resource_type: self._refresh_resource_picker(rt))
        section2.layout().addWidget(self._section_row("Organization:", org_combo, load_btn))
        section2.layout().addWidget(self._section_row("Record:", picker))
        outer.addWidget(section2)

        outer.addSpacing(12)

        section3 = self._section_frame("Reporting / LDW")
        ldw_dt = QDateTimeEdit(self)
        ldw_dt.setCalendarPopup(True)
        ldw_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        ldw_dt.setDateTime(datetime.now().astimezone())
        ldw_dt.setEnabled(False)
        ldw_enable = QCheckBox("Set LDW")
        ldw_enable.setChecked(False)
        ldw_enable.toggled.connect(ldw_dt.setEnabled)
        reporting = QLineEdit()
        reporting.setPlaceholderText("Reporting location")
        ldw_notes = QLineEdit()
        ldw_notes.setPlaceholderText("LDW notes")
        notes = QLineEdit()
        notes.setPlaceholderText("Check-in notes")
        section3.layout().addWidget(QLabel("Reporting Location:"))
        section3.layout().addWidget(reporting)
        ldw_row = QHBoxLayout()
        ldw_row.setSpacing(8)
        ldw_row.addWidget(ldw_enable)
        ldw_row.addWidget(ldw_dt)
        ldw_row.addWidget(ldw_notes, 1)
        section3.layout().addLayout(ldw_row)
        section3.layout().addWidget(notes)
        outer.addWidget(section3)

        outer.addSpacing(12)

        section4 = self._section_frame("Status Actions")
        status_preview = QLabel("Select or search a record to see its current status.")
        status_preview.setFrameShape(QFrame.StyledPanel)
        status_preview.setWordWrap(True)
        status_preview.setMinimumHeight(48)
        actions = QHBoxLayout()
        enroute_btn = QPushButton("Mark Enroute")
        enroute_btn.clicked.connect(lambda _, rt=resource_type: self._set_status(rt, "Enroute"))
        prep_btn = QPushButton("Prep Demob")
        prep_btn.clicked.connect(lambda _, rt=resource_type: self._set_status(rt, "Preparing for Demobilization"))
        cancel_btn = QPushButton("Mark Cancelled")
        cancel_btn.clicked.connect(lambda _, rt=resource_type: self._set_status(rt, "Cancelled"))
        actions.addWidget(enroute_btn)
        actions.addWidget(prep_btn)
        actions.addWidget(cancel_btn)
        actions.addStretch(1)
        preview = QLabel("Ready")
        preview.setFrameShape(QFrame.StyledPanel)
        preview.setWordWrap(True)
        section4.layout().addLayout(actions)
        section4.layout().addWidget(QLabel("Loaded Record Preview"))
        section4.layout().addWidget(preview)
        section4.layout().addWidget(status_preview)
        outer.addWidget(section4)

        outer.addSpacing(12)

        section5 = self._section_frame("Add New Record")
        add_btn = QPushButton(self._create_button_text(resource_type))
        add_btn.clicked.connect(lambda _, rt=resource_type: self._open_create_dialog(rt))
        section5.layout().addWidget(add_btn)
        outer.addWidget(section5)

        self._org_combos[resource_type] = org_combo
        self._pickers[resource_type] = picker
        self._reporting_inputs[resource_type] = reporting
        self._ldw_datetimes[resource_type] = ldw_dt
        self._ldw_enabled[resource_type] = ldw_enable
        self._ldw_notes[resource_type] = ldw_notes
        self._checkin_notes[resource_type] = notes
        self._previews[resource_type] = preview
        self._refresh_resource_picker(resource_type, populate=False)
        return tab

    def _section_row(
        self,
        label_text: str,
        field: QWidget,
        button: QWidget | None = None,
    ) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel(label_text))
        layout.addWidget(field, 1)
        if button is not None:
            layout.addWidget(button)
        return row

    def _build_team_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        team_row = QHBoxLayout()
        self.team_combo = QComboBox(self)
        self.team_combo.currentIndexChanged.connect(self._update_team_preview)
        refresh_btn = QPushButton("Refresh Teams")
        refresh_btn.clicked.connect(self._refresh_teams)
        team_row.addWidget(QLabel("Team:"))
        team_row.addWidget(self.team_combo, 1)
        team_row.addWidget(refresh_btn)
        layout.addLayout(team_row)

        self.team_preview = QLabel("Select a team.")
        self.team_preview.setFrameShape(QFrame.StyledPanel)
        self.team_preview.setWordWrap(True)
        layout.addWidget(self.team_preview)

        self.team_checkin_btn = QPushButton("Open Team Check-In Confirmation")
        self.team_checkin_btn.clicked.connect(self._open_team_confirmation)
        self.team_expected_btn = QPushButton("Mark Team Expected")
        self.team_expected_btn.clicked.connect(lambda: self._set_team_planning("Expected"))
        self.team_enroute_btn = QPushButton("Mark Team Enroute")
        self.team_enroute_btn.clicked.connect(lambda: self._set_team_planning("Enroute"))
        layout.addWidget(self.team_checkin_btn)
        layout.addWidget(self.team_expected_btn)
        layout.addWidget(self.team_enroute_btn)
        self._refresh_teams()
        return tab

    def _section_frame(self, title: str) -> QFrame:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        frame_layout.addWidget(QLabel(title))
        return frame

    def _lookup_placeholder(self, resource_type: str) -> str:
        return {
            "personnel": "Scan/enter ID, CAPID, name, or callsign",
            "vehicle": "Scan/enter vehicle ID, plate, or organization",
            "aircraft": "Scan/enter tail number or callsign",
            "equipment": "Scan/enter asset tag, serial number, or name",
        }.get(resource_type, "Scan/enter identifier")

    def _create_button_text(self, resource_type: str) -> str:
        return {
            "personnel": "+ Add New Personnel Record",
            "vehicle": "+ Add New Vehicle Record",
            "aircraft": "+ Add New Aircraft Record",
            "equipment": "+ Add New Equipment Record",
        }.get(resource_type, "+ Add New Record")

    def _current_record(self, resource_type: str) -> Optional[LookupResult]:
        picker = self._pickers.get(resource_type)
        if not picker:
            return None
        payload = picker.currentData()
        if isinstance(payload, dict):
            return LookupResult(payload, resource_type)
        return None

    def _preview_label(self, resource_type: str) -> QLabel:
        label = QLabel("Ready")
        label.setFrameShape(QFrame.StyledPanel)
        label.setWordWrap(True)
        self._previews[resource_type] = label
        return label

    def _lookup_resource(self, resource_type: str) -> None:
        typed = self._id_inputs[resource_type].text().strip()
        if not typed:
            self._previews[resource_type].setText("Enter an identifier to search.")
            return
        try:
            current = self._find_incident_record(resource_type, typed)
            if current:
                self._show_lookup(resource_type, LookupResult(current, resource_type))
                return
            matches = self._search_master_records(resource_type, typed)
            if len(matches) == 1:
                self._show_lookup(resource_type, LookupResult(matches[0], resource_type))
            elif len(matches) > 1:
                chosen = self._resolve_match(resource_type, matches)
                if chosen is not None:
                    self._show_lookup(resource_type, LookupResult(chosen, resource_type))
                else:
                    self._previews[resource_type].setText(
                        "Multiple matches found. Use the resolver to choose the correct record."
                    )
            else:
                self._previews[resource_type].setText(f"No match for '{typed}'. Use Add New Record.")
        except Exception as exc:
            self._previews[resource_type].setText(f"Search failed: {exc}")

    def _show_lookup(self, resource_type: str, result: LookupResult) -> None:
        self._active_selection[resource_type] = result.record
        self._previews[resource_type].setText(self._describe_record(resource_type, result.record))
        self._sync_picker_to_record(resource_type, result.record)

    def _describe_record(self, resource_type: str, record: dict[str, Any]) -> str:
        status = self._status_summary(record)
        if resource_type == "personnel":
            return " | ".join(filter(None, [
                f"ID: {record.get('person_id') or record.get('id')}",
                record.get("name"),
                record.get("organization"),
                record.get("phone"),
                record.get("primary_role") or record.get("role"),
                status,
            ]))
        if resource_type == "vehicle":
            return " | ".join(filter(None, [
                f"Vehicle: {record.get('id') or record.get('vehicle_id')}",
                record.get("license_plate"),
                record.get("type_id") or record.get("type"),
                record.get("organization"),
                status,
            ]))
        if resource_type == "aircraft":
            return " | ".join(filter(None, [
                f"Tail: {record.get('tail_number')}",
                record.get("callsign"),
                record.get("type"),
                record.get("organization"),
                status,
            ]))
        return " | ".join(filter(None, [
            f"Asset: {record.get('id') or record.get('int_id')}",
            record.get("name"),
            record.get("serial_number"),
            record.get("organization"),
            status,
        ]))

    def _status_summary(self, record: dict[str, Any]) -> str:
        status = record.get("status") or "Pending"
        checked_in = record["_checked_in"] if "_checked_in" in record else status in CHECKED_IN_STATUSES
        return f"Status: {status} | Checked In: {'Yes' if checked_in else 'No'}"

    def _find_incident_record(self, resource_type: str, typed: str) -> Optional[dict[str, Any]]:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return None
        typed_lower = typed.strip().lower()

        # First search the master catalog for the actual record identity.
        master_matches = self._search_master_records(resource_type, typed)
        for row in master_matches:
            if typed_lower in self._record_search_tokens(resource_type, row):
                return row

        # Fall back to incident check-in rows only as a status overlay.
        try:
            if resource_type == "personnel":
                records = api_client.get(f"/api/incidents/{incident_id}/checkin/roster", params={"q": typed}) or []
            else:
                records = api_client.get(f"/api/incidents/{incident_id}/resources", params={"resource_type": resource_type}) or []
        except Exception:
            records = []
        for row in records:
            if typed_lower in self._record_search_tokens(resource_type, row):
                return row
        try:
            checkins = api_client.get(f"/api/incidents/{incident_id}/checkin/roster", params={"q": typed}) or []
        except Exception:
            checkins = []
        for row in checkins:
            if typed.lower() in {
                str(row.get("person_id") or "").lower(),
                str(row.get("name") or "").lower(),
                str(row.get("callsign") or "").lower(),
            }:
                return row
        return None

    def _record_search_tokens(self, resource_type: str, row: dict[str, Any]) -> set[str]:
        tokens = {
            str(row.get("id") or "").strip().lower(),
            str(row.get("name") or "").strip().lower(),
            str(row.get("organization") or "").strip().lower(),
            str(row.get("callsign") or "").strip().lower(),
            str(row.get("tail_number") or "").strip().lower(),
            str(row.get("license_plate") or "").strip().lower(),
            str(row.get("serial_number") or "").strip().lower(),
        }
        if resource_type == "personnel":
            tokens.update({
                str(row.get("person_id") or "").strip().lower(),
                str(row.get("phone") or "").strip().lower(),
                str(row.get("primary_role") or row.get("role") or "").strip().lower(),
            })
        if resource_type == "vehicle":
            tokens.update({
                str(row.get("vehicle_id") or "").strip().lower(),
                str(row.get("type_id") or row.get("type") or "").strip().lower(),
            })
        if resource_type == "aircraft":
            tokens.update({
                str(row.get("type") or "").strip().lower(),
                str(row.get("base") or row.get("base_location") or "").strip().lower(),
            })
        if resource_type == "equipment":
            tokens.update({
                str(row.get("asset_tag") or "").strip().lower(),
                str(row.get("type") or "").strip().lower(),
            })
        return {token for token in tokens if token}

    def _search_master_records(self, resource_type: str, typed: str) -> list[dict[str, Any]]:
        entity = resource_type
        try:
            return self._checkin_service.search_master_records(entity, typed, limit=20)
        except Exception:
            return []

    def _sync_picker_to_record(self, resource_type: str, record: dict[str, Any]) -> None:
        picker = self._pickers.get(resource_type)
        if not picker:
            return
        for idx in range(picker.count()):
            if picker.itemData(idx) == record:
                picker.setCurrentIndex(idx)
                return

    def _resolve_match(self, resource_type: str, matches: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        dlg = QDialog(self)
        dlg.setWindowTitle("Choose Record")
        dlg.setModal(True)
        dlg.setMinimumSize(720, 320)
        layout = QVBoxLayout(dlg)
        table = QTableWidget(0, 4, dlg)
        table.setHorizontalHeaderLabels(["ID", "Name", "Organization", "Status"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setRowCount(len(matches))
        for row_idx, row in enumerate(matches):
            table.setItem(row_idx, 0, QTableWidgetItem(str(row.get("person_id") or row.get("id") or row.get("vehicle_id") or row.get("tail_number") or "")))
            table.setItem(row_idx, 1, QTableWidgetItem(str(row.get("name") or row.get("callsign") or row.get("resource_name") or "")))
            table.setItem(row_idx, 2, QTableWidgetItem(str(row.get("organization") or "")))
            table.setItem(row_idx, 3, QTableWidgetItem(self._status_summary(row)))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return None
        current = table.currentRow()
        if current < 0:
            current = 0
        return matches[current] if 0 <= current < len(matches) else None

    def _refresh_resource_picker(self, resource_type: str, populate: bool = True) -> None:
        picker = self._pickers[resource_type]
        org = self._org_combos[resource_type].currentText().strip()
        picker.blockSignals(True)
        picker.clear()
        records = self._list_records(resource_type, org)
        for row in records:
            picker.addItem(self._display_text(resource_type, row), row)
        picker.setCurrentIndex(-1)
        picker.setCurrentText("")
        picker.blockSignals(False)
        if not populate or not records:
            self._previews[resource_type].setText("No record selected.")
        else:
            self._previews[resource_type].setText("No record selected.")

    def _display_text(self, resource_type: str, row: dict[str, Any]) -> str:
        if resource_type == "personnel":
            return f"{row.get('name') or ''} ({row.get('person_id') or ''})"
        if resource_type == "vehicle":
            return f"{row.get('vehicle_id') or row.get('license_plate') or ''} {row.get('type_id') or row.get('type') or ''}".strip()
        if resource_type == "aircraft":
            return f"{row.get('aircraft_id') or row.get('tail_number') or ''} {row.get('callsign') or ''}".strip()
        return f"{row.get('name') or row.get('serial_number') or row.get('id') or ''}"

    def _list_records(self, resource_type: str, org: str) -> list[dict[str, Any]]:
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return []
        records: list[dict[str, Any]] = []
        try:
            rows = self._checkin_service.list_master_records(resource_type)
        except Exception:
            rows = []
        for row in rows:
            if org:
                text = str(row.get("organization") or "")
                if org.lower() not in text.lower():
                    continue
            records.append(row)
        return records

    def _populate_preview_from_picker(self, resource_type: str) -> None:
        picker = self._pickers[resource_type]
        row = picker.currentData()
        if isinstance(row, dict):
            self._active_selection[resource_type] = row
            self._previews[resource_type].setText(self._describe_record(resource_type, row))

    def _selected_ldw_payload(self, resource_type: str) -> dict[str, Any]:
        notes = self._ldw_notes[resource_type].text().strip() or None
        payload: dict[str, Any] = {}
        if self._ldw_enabled[resource_type].isChecked():
            payload["ldw_date"] = self._ldw_datetimes[resource_type].dateTime().toString(Qt.ISODate)
        if notes:
            payload["ldw_notes"] = notes
        return payload

    def _check_in_current(self, resource_type: str) -> None:
        row = self._active_selection.get(resource_type)
        if not row:
            row = self._current_record(resource_type).record if self._current_record(resource_type) else None
        if not row:
            QMessageBox.information(self, "Check-In", "Select or search for a record first.")
            return
        try:
            identifier = self._record_identifier(resource_type, row)
            logger.info(
                "check-in window submit resource_type=%s identifier=%s has_person_record=%s row_keys=%s",
                resource_type,
                identifier,
                bool(row.get("person_record")),
                sorted(row.keys()),
            )
            if resource_type == "personnel":
                result = self._checkin_service.transition_to_checked_in(str(identifier))
                logger.info(
                    "check-in window personnel result resource_type=%s identifier=%s "
                    "result_status=%s result_checked_in=%s",
                    resource_type,
                    identifier,
                    result.get("status") if isinstance(result, dict) else None,
                    result.get("checked_in") if isinstance(result, dict) else None,
                )
                ldw_payload = self._selected_ldw_payload(resource_type)
                self._checkin_service.update_ldw(
                    str(identifier),
                    ldw_date=ldw_payload.get("ldw_date"),
                    ldw_notes=ldw_payload.get("ldw_notes"),
                )
            else:
                arrival_status = self._checkin_service.default_arrival_status(
                    resource_type,
                    row,
                    record_id=identifier,
                )
                self._checkin_service.check_in(resource_type, identifier, overrides={
                    "checked_in_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "status": arrival_status,
                    "notes": self._checkin_notes[resource_type].text().strip() or None,
                    "reporting_location": self._reporting_inputs[resource_type].text().strip() or None,
                    **self._selected_ldw_payload(resource_type),
                })
                logger.info(
                    "check-in window asset check-in submitted resource_type=%s identifier=%s arrival_status=%s",
                    resource_type,
                    identifier,
                    arrival_status,
                )
            self._previews[resource_type].setText(self._describe_record(resource_type, row) + "\nChecked in.")
            self._clear_tab(resource_type, keep_preview=True)
            self.refresh()
        except Exception as exc:
            logger.exception(
                "check-in window submit failed resource_type=%s identifier=%s",
                resource_type,
                locals().get("identifier"),
            )
            QMessageBox.warning(self, "Check-In", str(exc))

    def _record_identifier(self, resource_type: str, row: dict[str, Any]) -> Any:
        if resource_type == "personnel":
            return row.get("person_record") or row.get("id") or row.get("person_id")
        if resource_type == "vehicle":
            return row.get("vehicle_record") or row.get("id") or row.get("vehicle_id")
        if resource_type == "aircraft":
            return row.get("aircraft_record") or row.get("id") or row.get("int_id") or row.get("tail_number")
        return row.get("equipment_record") or row.get("id") or row.get("int_id")

    def _clear_tab(self, resource_type: str, keep_preview: bool = False) -> None:
        self._id_inputs[resource_type].clear()
        self._reporting_inputs[resource_type].clear()
        self._checkin_notes[resource_type].clear()
        self._ldw_notes[resource_type].clear()
        self._ldw_enabled[resource_type].setChecked(False)
        self._ldw_datetimes[resource_type].setDateTime(datetime.now().astimezone())
        if not keep_preview:
            self._previews[resource_type].setText("Ready")
        self._id_inputs[resource_type].setFocus()

    def _set_status(self, resource_type: str, status: str) -> None:
        row = self._active_selection.get(resource_type)
        if not row:
            QMessageBox.information(self, "Status", "Search or select a record first.")
            return
        try:
            identifier = self._record_identifier(resource_type, row)
            if resource_type == "personnel":
                self._checkin_service.set_planning_status(str(identifier), status)
            else:
                incident_id = incident_context.get_active_incident_id()
                if incident_id:
                    existing = api_client.get(f"/api/incidents/{incident_id}/resources", params={"resource_type": resource_type}) or []
                    match = next((r for r in existing if str(self._record_identifier(resource_type, r)) == str(identifier)), None)
                    if match:
                        api_client.patch(
                            f"/api/incidents/{incident_id}/resource-status/{match['id']}/status",
                            json={"status": status, "changed_by": "ICS-211 Check-In"},
                        )
            self._previews[resource_type].setText(self._describe_record(resource_type, row) + f"\nStatus set to {status}.")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Status", str(exc))

    def _open_create_dialog(self, resource_type: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(self._create_button_text(resource_type).replace("+ ", ""))
        layout = QFormLayout(dlg)
        fields: dict[str, QLineEdit] = {}
        for label, name in self._create_fields(resource_type):
            edit = QLineEdit()
            layout.addRow(label, edit)
            fields[name] = edit
        org = make_org_combo()
        layout.addRow("Organization", org)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        payload = {k: v.text().strip() for k, v in fields.items() if v.text().strip()}
        payload["organization"] = org.currentText().strip()
        if resource_type == "personnel":
            payload.setdefault("name", "")
            payload.setdefault("person_id", payload.get("id") or payload.get("person_id") or "")
            payload.pop("id", None)
        try:
            created = self._checkin_service.create_master_record(resource_type, payload)
            self._previews[resource_type].setText(self._describe_record(resource_type, created) + "\nCreated.")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Create Record", str(exc))

    def _create_fields(self, resource_type: str) -> list[tuple[str, str]]:
        if resource_type == "personnel":
            return [("Name *", "name"), ("ID / Local ID", "person_id"), ("Phone", "phone"), ("Role", "role")]
        if resource_type == "vehicle":
            return [("Vehicle ID", "id"), ("Type", "type_id"), ("Plate", "license_plate")]
        if resource_type == "aircraft":
            return [("Tail Number", "tail_number"), ("Callsign", "callsign"), ("Aircraft Type", "type"), ("PIC", "pic")]
        return [("Name *", "name"), ("Asset Tag", "id"), ("Serial Number", "serial_number"), ("Type", "type")]

    def _open_team_confirmation(self) -> None:
        team_id = self.team_combo.currentData()
        if team_id is None:
            QMessageBox.information(self, "Team Check-In", "Select a team first.")
            return
        team = get_team(int(team_id))
        if not team:
            QMessageBox.warning(self, "Team Check-In", "Team could not be loaded.")
            return
        dlg = TeamCheckInDialog(team, self._checkin_service, self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_teams()
            self.refresh()

    def _set_team_planning(self, planning_status: str) -> None:
        team_id = self.team_combo.currentData()
        if team_id is None:
            QMessageBox.information(self, "Team Planning", "Select a team first.")
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            QMessageBox.information(self, "Team Planning", "Open an incident before changing team status.")
            return
        try:
            api_client.patch(f"/api/incidents/{incident_id}/operations/teams/{team_id}", json={"status": planning_status})
            self._refresh_teams()
            idx = self.team_combo.findData(team_id)
            if idx >= 0:
                self.team_combo.setCurrentIndex(idx)
                self._update_team_preview()
        except Exception as exc:
            QMessageBox.warning(self, "Team Planning", str(exc))

    def _refresh_teams(self) -> None:
        self.team_combo.clear()
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        try:
            teams = api_client.get(f"/api/incidents/{incident_id}/checkin/teams/checked-state", params={"checked_in": True, "include_disbanded": False}) or []
        except Exception:
            teams = []
        self._team_rows = list(teams)
        for row in self._team_rows:
            self.team_combo.addItem(f"{row.get('name') or row.get('int_id')}", row.get("int_id"))
        self._update_team_preview()

    def _update_team_preview(self) -> None:
        row = self.team_combo.currentData()
        if row is None or not self._team_rows:
            self.team_preview.setText("Select a team.")
            return
        match = next((t for t in self._team_rows if str(t.get("int_id")) == str(row)), None)
        if match:
            self.team_preview.setText(
                f"Team: {match.get('name')}\nChecked In: {match.get('checked_in')}\nDisbanded: {match.get('disbanded')}\nStatus: {match.get('status')}"
            )

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._refresh_teams()

    def refresh(self) -> None:
        self._context_label.setText(self._incident_context_text())
        for rt in ("personnel", "vehicle", "aircraft", "equipment"):
            self._refresh_resource_picker(rt)
        self._refresh_teams()

    def _sync_status_hooks(self) -> None:
        """Compatibility hook for future board refresh integration."""
        try:
            from utils.app_signals import app_signals
            app_signals.teamStatusChanged.emit()
        except Exception:
            pass


class TeamCheckInDialog(QDialog):
    """Confirmation modal for team package check-in."""

    def __init__(self, team: Any, checkin_service: CheckInService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._team = team
        self._checkin_service = checkin_service
        self.setWindowTitle(f"Team Check-In: {team.name}")
        self.setModal(True)
        self.setMinimumSize(760, 460)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(
            f"Team: {self._team.name}\n"
            f"Members: {len(self._team.members)} | Vehicles: {len(self._team.vehicles)} | Equipment: {len(self._team.equipment)} | Aircraft: {len(self._team.aircraft)}"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Check", "Name / Asset", "Type", "Status", "LDW Notes"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table, 1)
        self._populate()
        row = QHBoxLayout()
        keep = QPushButton("Keep Team Together")
        keep.clicked.connect(lambda: self._submit(True))
        disband = QPushButton("Disband Team After Check-In")
        disband.clicked.connect(lambda: self._submit(False))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(keep)
        row.addWidget(disband)
        row.addStretch(1)
        row.addWidget(cancel)
        layout.addLayout(row)

    def _populate(self) -> None:
        members = [("Personnel", str(mid)) for mid in getattr(self._team, "members", [])]
        vehicles = [("Vehicle", str(vid)) for vid in getattr(self._team, "vehicles", [])]
        equipment = [("Equipment", str(eid)) for eid in getattr(self._team, "equipment", [])]
        aircraft = [("Aircraft", str(aid)) for aid in getattr(self._team, "aircraft", [])]
        rows = members + vehicles + equipment + aircraft
        self.table.setRowCount(len(rows))
        for idx, (typ, ident) in enumerate(rows):
            cb = QCheckBox()
            cb.setChecked(True)
            self.table.setCellWidget(idx, 0, cb)
            self.table.setItem(idx, 1, QTableWidgetItem(ident))
            self.table.setItem(idx, 2, QTableWidgetItem(typ))
            self.table.setItem(idx, 3, QTableWidgetItem("Pending"))
            self.table.setItem(idx, 4, QTableWidgetItem(""))

    def _submit(self, keep_together: bool) -> None:
        if not keep_together and getattr(self._team, "current_task_id", None) is not None:
            if QMessageBox.question(self, "Disband Team", "This team has a task assignment. Disbanding will remove the team assignment. Continue?") != QMessageBox.Yes:
                return
        try:
            team_id = int(self._team.team_id)
            team_result = self._checkin_service.team_check_in(str(team_id), keep_together=keep_together)
            if not keep_together:
                self._checkin_service.team_disband(str(team_id))
            if team_result:
                self._notify_operational_unit(keep_together=keep_together)
                self.accept()
            else:
                QMessageBox.warning(self, "Team Check-In", "The team could not be checked in.")
        except Exception as exc:
            QMessageBox.warning(self, "Team Check-In", str(exc))

    def _notify_operational_unit(self, *, keep_together: bool) -> None:
        unit_id = getattr(self._team, "operational_unit_id", None)
        if unit_id in (None, ""):
            return
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return
        unit_title = self._resolve_unit_title(incident_id, int(unit_id))
        team_name = getattr(self._team, "name", f"Team {self._team.team_id}")
        action = "checked in" if keep_together else "checked in and disbanded"
        title = f"Team {team_name} checked in"
        message = f"{team_name} has {action}"
        if unit_title:
            message += f" under {unit_title}"
        message += "."
        try:
            get_notifier().notify(
                Notification(
                    title=title,
                    message=message,
                    category="logistics",
                    severity="routine",
                    source="ICS-211 Check-In",
                    entity_type="team",
                    entity_id=str(self._team.team_id or ""),
                )
            )
        except Exception:
            pass

    @staticmethod
    def _resolve_unit_title(incident_id: str, unit_id: int) -> str:
        try:
            doc = api_client.get(f"/api/incidents/{incident_id}/org/positions/{unit_id}")
        except Exception:
            return ""
        if not doc:
            return ""
        title = str(doc.get("title") or "").strip()
        classification = str(doc.get("classification") or "").strip().title()
        if classification and title:
            return f"{classification} {title}"
        return title or classification


__all__ = ["ICS211CheckInWindow", "TeamCheckInDialog"]
