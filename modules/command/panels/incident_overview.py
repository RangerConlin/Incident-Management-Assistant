from __future__ import annotations

"""
Incident Overview panel — manage the incident record itself.

Covers the high-level administrative data for the active incident:
name, number, type, status, ICP location, start/end dates, description,
and training flag.  Read-only by default; click Edit to modify.
"""

from typing import Any, Optional
import logging

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QDateTime

from utils.state import AppState

_LOGGER = logging.getLogger(__name__)

_INCIDENT_STATUSES = ["Active", "Standby", "Paused", "Terminated"]

_STATUS_COLORS = {
    "active":     "#2e7d32",
    "standby":    "#546e7a",
    "paused":     "#e65100",
    "terminated": "#c62828",
}


def _get_incident_types() -> list[str]:
    try:
        from utils.api_client import api_client
        return api_client.get("/api/lookup/incident-types") or []
    except Exception:
        return []


def _load_incident(incident_number: str) -> Optional[dict]:
    try:
        from utils.api_client import api_client
        return api_client.get(f"/api/incidents/{incident_number}/profile")
    except Exception:
        _LOGGER.exception("Failed to load incident profile via API")
        return None


def _save_incident(incident_id: Any, data: dict) -> bool:
    try:
        from utils.api_client import api_client
        api_client.patch(f"/api/incidents/{incident_id}/profile", json=data)
        return True
    except Exception:
        _LOGGER.exception("Failed to save incident profile via API")
        return False


def _parse_dt(value: Optional[str]) -> QDateTime:
    if not value:
        return QDateTime()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            from datetime import datetime
            dt = datetime.strptime(value, fmt)
            return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        except Exception:
            pass
    return QDateTime()


def _fmt_dt_display(value: Optional[str]) -> str:
    if not value:
        return "—"
    dt = _parse_dt(value)
    if dt.isValid():
        return dt.toString("yyyy-MM-dd  HH:mm")
    return value


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class IncidentOverviewPanel(QWidget):
    panel_title = "Incident Overview"

    incidentSaved = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("IncidentOverviewPanel")

        self._incident_id: Optional[int] = None
        self._editing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ---- Header row ------------------------------------------------
        header_row = QHBoxLayout()
        self._title_label = QLabel("Incident Overview")
        title_font = self._title_label.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        header_row.addWidget(self._title_label, 1)

        self._status_badge = QLabel()
        self._status_badge.setAlignment(Qt.AlignCenter)
        self._status_badge.setFixedHeight(26)
        self._status_badge.setStyleSheet(
            "border-radius: 12px; padding: 2px 12px; color: white; background: #424242;"
        )
        header_row.addWidget(self._status_badge, 0)
        root.addLayout(header_row)

        # ---- Divider ---------------------------------------------------
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        # ---- Form group ------------------------------------------------
        form_box = QGroupBox("Incident Record")
        form = QFormLayout(form_box)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setSpacing(8)

        self._fld_name        = QLineEdit()
        self._fld_number      = QLineEdit()
        self._fld_type        = QComboBox()
        self._fld_status      = QComboBox()
        self._fld_location    = QLineEdit()
        self._fld_start       = QDateTimeEdit()
        self._fld_end         = QDateTimeEdit()
        self._fld_description = QTextEdit()
        self._fld_training    = QCheckBox("This is a training exercise")

        self._fld_type.addItems(_get_incident_types())
        self._fld_status.addItems(_INCIDENT_STATUSES)

        self._fld_start.setDisplayFormat("yyyy-MM-dd  HH:mm")
        self._fld_start.setCalendarPopup(True)
        self._fld_end.setDisplayFormat("yyyy-MM-dd  HH:mm")
        self._fld_end.setCalendarPopup(True)

        self._fld_description.setFixedHeight(72)
        self._fld_description.setPlaceholderText("Brief description of the incident (optional)")

        form.addRow("Incident Name:", self._fld_name)
        form.addRow("Incident Number:", self._fld_number)
        form.addRow("Type:", self._fld_type)
        form.addRow("Status:", self._fld_status)
        form.addRow("ICP Location:", self._fld_location)
        form.addRow("Start Date/Time:", self._fld_start)
        form.addRow("End Date/Time:", self._fld_end)
        form.addRow("Description:", self._fld_description)
        form.addRow("", self._fld_training)

        root.addWidget(form_box)

        # ---- Training banner -------------------------------------------
        self._training_banner = QLabel("TRAINING EXERCISE")
        self._training_banner.setAlignment(Qt.AlignCenter)
        self._training_banner.setStyleSheet(
            "background: #e65100; color: white; font-weight: bold; "
            "font-size: 13px; padding: 4px; border-radius: 4px;"
        )
        self._training_banner.hide()
        root.addWidget(self._training_banner)

        root.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # ---- Action buttons --------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._btn_edit   = QPushButton("Edit")
        self._btn_save   = QPushButton("Save Changes")
        self._btn_cancel = QPushButton("Cancel")
        self._btn_save.hide()
        self._btn_cancel.hide()
        btn_row.addWidget(self._btn_edit)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_cancel)
        root.addLayout(btn_row)

        self._btn_edit.clicked.connect(self._enter_edit_mode)
        self._btn_save.clicked.connect(self._save)
        self._btn_cancel.clicked.connect(self._cancel_edit)

        self._set_fields_readonly(True)
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        number = AppState.get_active_incident() if hasattr(AppState, "get_active_incident") else None
        incident = _load_incident(number or "") if number else None
        if not incident:
            self._title_label.setText("No Active Incident")
            self._status_badge.setText("—")
            self._status_badge.setStyleSheet(
                "border-radius: 12px; padding: 2px 12px; color: white; background: #424242;"
            )
            self._clear_fields()
            return

        self._incident_id = incident["id"]
        self._populate_fields(incident)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _populate_fields(self, inc: dict) -> None:
        name   = inc.get("name") or ""
        number = inc.get("number") or ""
        itype  = inc.get("type") or ""
        status = inc.get("status") or ""
        loc    = inc.get("icp_location") or ""
        desc   = inc.get("description") or ""
        start  = inc.get("start_time") or ""
        end    = inc.get("end_time") or ""
        training = bool(inc.get("is_training"))

        self._title_label.setText(f"{name}  ({number})")

        self._fld_name.setText(name)
        self._fld_number.setText(number)

        idx = self._fld_type.findText(itype)
        if idx >= 0:
            self._fld_type.setCurrentIndex(idx)
        else:
            if itype:
                self._fld_type.insertItem(0, itype)
                self._fld_type.setCurrentIndex(0)

        idx = self._fld_status.findText(status, Qt.MatchFixedString | Qt.MatchCaseSensitive)
        if idx >= 0:
            self._fld_status.setCurrentIndex(idx)

        color = _STATUS_COLORS.get(status.lower(), "#424242")
        self._status_badge.setText(status or "—")
        self._status_badge.setStyleSheet(
            f"border-radius: 12px; padding: 2px 12px; color: white; background: {color};"
        )

        self._fld_location.setText(loc)
        self._fld_description.setPlainText(desc)
        self._fld_training.setChecked(training)

        start_dt = _parse_dt(start)
        if start_dt.isValid():
            self._fld_start.setDateTime(start_dt)
        else:
            self._fld_start.clear()

        end_dt = _parse_dt(end)
        if end_dt.isValid():
            self._fld_end.setDateTime(end_dt)
        else:
            self._fld_end.clear()

        self._training_banner.setVisible(training)

    def _clear_fields(self) -> None:
        for w in (self._fld_name, self._fld_number, self._fld_location):
            w.clear()
        self._fld_description.clear()
        self._fld_training.setChecked(False)
        self._training_banner.hide()

    def _set_fields_readonly(self, readonly: bool) -> None:
        self._fld_name.setReadOnly(readonly)
        self._fld_number.setReadOnly(readonly)
        self._fld_location.setReadOnly(readonly)
        self._fld_description.setReadOnly(readonly)
        self._fld_type.setEnabled(not readonly)
        self._fld_status.setEnabled(not readonly)
        self._fld_start.setReadOnly(readonly)
        self._fld_end.setReadOnly(readonly)
        self._fld_training.setEnabled(not readonly)

        # Visual hint
        style = "QLineEdit, QTextEdit { background: palette(window); }" if readonly else ""
        self._fld_name.setStyleSheet(style)
        self._fld_location.setStyleSheet(style)
        self._fld_description.setStyleSheet(style)

    @Slot()
    def _enter_edit_mode(self) -> None:
        self._editing = True
        self._set_fields_readonly(False)
        self._btn_edit.hide()
        self._btn_save.show()
        self._btn_cancel.show()

    @Slot()
    def _cancel_edit(self) -> None:
        self._editing = False
        self._set_fields_readonly(True)
        self._btn_edit.show()
        self._btn_save.hide()
        self._btn_cancel.hide()
        self.refresh()

    @Slot()
    def _save(self) -> None:
        if self._incident_id is None:
            QMessageBox.warning(self, "Incident Overview", "No incident loaded — cannot save.")
            return

        end_val = self._fld_end.dateTime()
        end_str = end_val.toString("yyyy-MM-dd HH:mm:ss") if end_val.isValid() and not self._fld_end.dateTime().isNull() else None

        data = {
            "name":        self._fld_name.text().strip(),
            "number":      self._fld_number.text().strip(),
            "type":        self._fld_type.currentText(),
            "status":      self._fld_status.currentText(),
            "description": self._fld_description.toPlainText().strip(),
            "start_time":  self._fld_start.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "end_time":    end_str,
            "icp_location": self._fld_location.text().strip(),
            "is_training": self._fld_training.isChecked(),
        }

        if not data["name"]:
            QMessageBox.warning(self, "Incident Overview", "Incident name cannot be empty.")
            return
        if not data["number"]:
            QMessageBox.warning(self, "Incident Overview", "Incident number cannot be empty.")
            return

        if _save_incident(self._incident_id, data):
            self._editing = False
            self._set_fields_readonly(True)
            self._btn_edit.show()
            self._btn_save.hide()
            self._btn_cancel.hide()
            self.refresh()
            self.incidentSaved.emit()
        else:
            QMessageBox.critical(self, "Incident Overview", "Failed to save changes. Check logs for details.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_command_incident_overview_panel(
    dock_manager: Any, app_context: Any
) -> "IncidentOverviewPanel":
    panel = IncidentOverviewPanel()
    return panel


__all__ = [
    "IncidentOverviewPanel",
    "create_command_incident_overview_panel",
]
