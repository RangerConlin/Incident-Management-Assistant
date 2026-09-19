"""Single-page ICS-206 Medical Plan panel (collapsible drawers, versioned) backed by MedicalBridge."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bridge.medical_bridge import (
    APPROVAL_APPROVED,
    APPROVAL_LABELS,
    APPROVAL_NOT_STARTED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    MedicalBridge,
)
from modules.approvals.panels.approval_timeline import ApprovalTimeline
from modules.approvals.service import ApprovalService
from modules.logistics.facilities.service import FacilitiesService
from modules.logistics.facilities.widgets.facility_picker import FacilityPicker
from utils.app_signals import app_signals
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.state import AppState
from utils.styles import medical_plan_status_colors, subscribe_theme
from utils.timefmt import to_datetime


# ---------------------------------------------------------------------------
# Section specifications — drives tables and edit dialogs
# ---------------------------------------------------------------------------

SECTIONS = [
    {
        "key": "aid_stations",
        "label": "Aid Stations",
        "import_method": "import_aid_stations",
        "columns": ["Name", "Facility/Location", "Contact/Frequency", "Type", "Level", "24/7", "Manager", "Notes"],
        "fields": [
            ("facility_id", "Facility", "facility", "medical"),
            ("name", "Name", "text", None),
            ("type", "Type", "combo", ["Medical Aid", "BLS", "ALS", "Paramedic", "Other"]),
            ("level", "Level", "text", None),
            ("contact_frequency", "Contact/Frequency", "text", None),
            ("is_24_7", "24/7?", "bool", None),
            ("location_text", "Location", "text", None),
            ("manager_name", "Manager", "text", None),
            ("notes", "Notes", "text", None),
        ],
        "display": lambda r: [
            r.get("name") or "",
            r.get("location_text") or "",
            r.get("contact_frequency") or "",
            r.get("type") or "",
            r.get("level") or "",
            "Yes" if r.get("is_24_7") else "No",
            r.get("manager_name") or "",
            r.get("notes") or "",
        ],
    },
    {
        "key": "ambulance_services",
        "label": "Ambulance Services",
        "nearby": True,
        "import_method": "import_ambulance_services",
        "columns": ["Name", "Type", "Phone", "Location", "Notes"],
        "fields": [
            ("name",     "Name",     "text",  None),
            ("type",     "Type",     "combo", ["Ground BLS", "Ground ALS", "Air", "Other"]),
            ("phone",    "Phone",    "text",  None),
            ("location", "Location", "text",  None),
            ("notes",    "Notes",    "text",  None),
        ],
        "display": lambda r: [
            r.get("name") or "",
            r.get("type") or "",
            r.get("phone") or "",
            r.get("location") or "",
            r.get("notes") or "",
        ],
    },
    {
        "key": "hospitals",
        "label": "Hospitals",
        "nearby": True,
        "import_method": "import_hospitals",
        "columns": ["Name", "Address", "Phone", "Helipad", "Burn Ctr", "Trauma Level", "Ground", "Air", "Notes"],
        "fields": [
            ("name",        "Name",         "text",  None),
            ("address",     "Address",      "text",  None),
            ("phone",       "Phone",        "text",  None),
            ("helipad",     "Helipad?",     "bool",  None),
            ("burn_center", "Burn Center?", "bool",  None),
            ("level",       "Trauma Level", "combo", ["I", "II", "III", "IV", "None"]),
            ("lat",         "Latitude",     "text",  None),
            ("lon",         "Longitude",    "text",  None),
            ("travel_time_ground_min", "Ground Travel (min)", "text", None),
            ("travel_time_air_min",    "Air Travel (min)",    "text", None),
            ("notes",       "Notes",        "text",  None),
        ],
        "display": lambda r: [
            r.get("name") or "",
            r.get("address") or "",
            r.get("phone") or "",
            "Yes" if r.get("helipad") else "No",
            "Yes" if r.get("burn_center") else "No",
            r.get("level") or "",
            "" if r.get("travel_time_ground_min") in (None, "") else str(r.get("travel_time_ground_min")),
            "" if r.get("travel_time_air_min") in (None, "") else str(r.get("travel_time_air_min")),
            r.get("notes") or "",
        ],
    },
    {
        "key": "air_ambulance",
        "label": "Air Ambulance / MedEvac",
        "import_method": "import_air_ambulance",
        "columns": ["Name", "Phone", "Base", "Contact", "Notes"],
        "fields": [
            ("name",    "Name",    "text", None),
            ("phone",   "Phone",   "text", None),
            ("base",    "Base",    "text", None),
            ("contact", "Contact", "text", None),
            ("notes",   "Notes",   "text", None),
        ],
        "display": lambda r: [
            r.get("name") or "",
            r.get("phone") or "",
            r.get("base") or "",
            r.get("contact") or "",
            r.get("notes") or "",
        ],
    },
    {
        "key": "medical_comms",
        "label": "Medical Communications",
        "import_method": "import_medical_comms",
        "columns": ["Channel", "Function", "Frequency", "Mode", "Notes"],
        "fields": [
            ("channel",   "Channel",   "text",  None),
            ("function",  "Function",  "text",  None),
            ("frequency", "Frequency", "text",  None),
            ("mode",      "Mode",      "combo", ["Analog", "Digital", "Mixed"]),
            ("notes",     "Notes",     "text",  None),
        ],
        "display": lambda r: [
            r.get("channel") or "",
            r.get("function") or "",
            r.get("frequency") or "",
            r.get("mode") or "",
            r.get("notes") or "",
        ],
    },
]


# ---------------------------------------------------------------------------
# Generic row edit dialog
# ---------------------------------------------------------------------------

class RowEditDialog(QDialog):
    def __init__(self, fields: list, parent=None, data: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit" if data else "Add")
        self.setMinimumWidth(460)
        self._fields = fields
        self._widgets: dict[str, Any] = {}
        self._facility_service = FacilitiesService()
        self._selected_facility_snapshot: dict[str, Any] = {}
        layout = QFormLayout(self)
        d = data or {}
        for key, label, kind, options in fields:
            if kind == "text":
                w = QLineEdit(str(d.get(key) or ""))
                layout.addRow(label, w)
            elif kind == "combo":
                w = QComboBox()
                w.addItem("")
                w.addItems(options or [])
                val = str(d.get(key) or "")
                idx = w.findText(val)
                w.setCurrentIndex(idx if idx >= 0 else 0)
                layout.addRow(label, w)
            elif kind == "bool":
                w = QCheckBox()
                val = d.get(key)
                w.setChecked(bool(val) and val not in (0, "0", False, "No", "false"))
                layout.addRow(label, w)
            elif kind == "facility":
                w = FacilityPicker(service=self._facility_service, facility_type=str(options or ""))
                facility_name = str(d.get("name") or d.get("location_text") or "")
                w.set_value(str(d.get(key) or ""), facility_name)
                w.facilitySelected.connect(self._on_facility_selected)
                layout.addRow(label, w)
            self._widgets[key] = (kind, w)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_facility_selected(self, facility_id: object, facility_name: str) -> None:
        facility_id_text = str(facility_id or "")
        self._selected_facility_snapshot = {}
        if not facility_id_text:
            return
        facility = self._facility_service.get_facility(facility_id_text)
        if facility is None:
            return
        self._selected_facility_snapshot = {
            "facility_id": facility.id,
            "name": facility.name,
            "location_text": facility.address or facility.geocoded_address or "",
            "latitude": facility.latitude,
            "longitude": facility.longitude,
        }
        self._set_text_if_blank("name", facility.name)
        self._set_text_if_blank("location_text", facility.address or facility.geocoded_address or facility_name)

    def _set_text_if_blank(self, key: str, value: str) -> None:
        entry = self._widgets.get(key)
        if not entry:
            return
        kind, widget = entry
        if kind != "text":
            return
        if not widget.text().strip():
            widget.setText(value or "")

    def result_data(self) -> dict:
        out = {}
        for key, (kind, w) in self._widgets.items():
            if kind == "text":
                out[key] = w.text().strip()
            elif kind == "combo":
                out[key] = w.currentText()
            elif kind == "bool":
                out[key] = 1 if w.isChecked() else 0
            elif kind == "facility":
                out[key] = w.facility_id
                if w.facility_id:
                    facility = self._facility_service.get_facility(w.facility_id)
                    if facility is not None:
                        out["name"] = out.get("name") or facility.name
                        out["location_text"] = out.get("location_text") or facility.address or facility.geocoded_address or ""
                        out["latitude"] = facility.latitude
                        out["longitude"] = facility.longitude
                    else:
                        out["latitude"] = self._selected_facility_snapshot.get("latitude")
                        out["longitude"] = self._selected_facility_snapshot.get("longitude")
                else:
                    out.setdefault("latitude", None)
                    out.setdefault("longitude", None)
        return out


# ---------------------------------------------------------------------------
# Nearby facility picker
# ---------------------------------------------------------------------------

class HiddenFacilitiesDialog(QDialog):
    """Facilities hidden from nearby searches, with a way to restore them."""

    COLUMNS = ["Name", "Address", "Reason", "Hidden By"]

    def __init__(self, bridge: MedicalBridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._rows: list[dict] = []
        self.setWindowTitle("Hidden Facilities")
        self.resize(720, 340)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("These facilities never appear in nearby searches, for any incident."))
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        row = QHBoxLayout()
        restore_btn = QPushButton("Restore Selected")
        restore_btn.clicked.connect(self._restore)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        row.addWidget(restore_btn)
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)
        self._load()

    def _load(self) -> None:
        try:
            self._rows = self._bridge.list_hidden_nearby()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            self._rows = []
        self._table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, key in enumerate(["name", "address", "reason", "excluded_by"]):
                self._table.setItem(r, c, QTableWidgetItem(str(row.get(key) or "")))
        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)

    def _restore(self) -> None:
        idx = self._table.currentRow()
        if not 0 <= idx < len(self._rows):
            return
        try:
            self._bridge.restore_nearby(self._rows[idx]["id"])
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._load()


class NearbyPickerDialog(QDialog):
    """Search for facilities near the incident and tick the ones to add to the plan."""

    COLUMNS = ["Add", "Name", "Address", "Phone", "Distance (mi)", "Data as of"]

    def __init__(self, label: str, table_key: str, bridge: MedicalBridge, parent=None):
        super().__init__(parent)
        self._table_key = table_key
        self._bridge = bridge
        self._rows: list[dict] = []
        self.setWindowTitle(f"Find Nearby — {label}")
        self.resize(820, 460)

        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Within"))
        self._radius = QDoubleSpinBox()
        self._radius.setRange(1, 100)
        self._radius.setDecimals(0)
        self._radius.setValue(25)
        self._radius.setSuffix(" mi of the incident")
        search_row.addWidget(self._radius)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search)
        search_row.addWidget(search_btn)
        self._refresh_check = QCheckBox("Re-read source data")
        self._refresh_check.setToolTip("Fetch the latest hospital list instead of using the saved copy")
        self._refresh_check.setVisible(table_key == "hospitals")
        search_row.addWidget(self._refresh_check)
        search_row.addStretch()
        layout.addLayout(search_row)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        self._note = QLabel()
        self._note.setWordWrap(True)
        layout.addWidget(self._note)

        curate_row = QHBoxLayout()
        hide_btn = QPushButton("Hide Highlighted Entry…")
        hide_btn.setToolTip("Remove a wrong entry (closed, prison hospital, doesn't exist) from all future searches")
        hide_btn.clicked.connect(self._hide_selected)
        hidden_btn = QPushButton("Hidden Facilities…")
        hidden_btn.clicked.connect(lambda: HiddenFacilitiesDialog(self._bridge, self).exec())
        curate_row.addWidget(hide_btn)
        curate_row.addWidget(hidden_btn)
        curate_row.addStretch()
        layout.addLayout(curate_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._add_btn = buttons.button(QDialogButtonBox.Ok)
        self._add_btn.setText("Add Selected")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._search()

    def _search(self) -> None:
        self._table.setRowCount(0)
        self._rows = []
        self._status.setText("Searching… (the first search in a new state can take a few seconds)")
        self._status.repaint()
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            found = self._bridge.find_nearby(self._table_key, self._radius.value(), self._refresh_check.isChecked())
        except Exception as exc:
            self._status.setText(f"Search failed: {exc}")
            return
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._refresh_check.setChecked(False)
        self._rows = found.get("results", [])
        summary = f"{len(self._rows)} found." if self._rows else "Nothing found in that radius."
        self._status.setText(" ".join([summary, *found.get("warnings", [])]))
        self._note.setText(found.get("note", ""))
        self._table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            check = QTableWidgetItem()
            if row["already_added"]:
                check.setFlags(Qt.ItemIsEnabled)
                check.setCheckState(Qt.Checked)
                check.setToolTip("Already in this plan")
            else:
                check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                check.setCheckState(Qt.Unchecked)
            self._table.setItem(r, 0, check)
            approximate = bool(row.get("location_approximate"))
            values = [
                row["name"],
                row["address"],
                row.get("phone", ""),
                f"{'~' if approximate else ''}{row['distance_mi']:.1f}",
                row["source_date"],
            ]
            for c, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if approximate and c == 4:
                    item.setToolTip("Approximate: placed at the centre of the ZIP code area")
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)

    HIDE_REASONS = [
        "Closed or no longer exists",
        "Prison or correctional facility",
        "Not available to the public",
        "Duplicate or wrong location",
    ]

    def _hide_selected(self) -> None:
        idx = self._table.currentRow()
        if not 0 <= idx < len(self._rows):
            QMessageBox.information(self, "Hide", "Click a row first, then hide it.")
            return
        row = self._rows[idx]
        reason, ok = QInputDialog.getItem(
            self,
            "Hide Facility",
            f"Hide '{row['name']}' from all future searches (every incident).\nWhy?",
            self.HIDE_REASONS,
            0,
            True,
        )
        if not ok:
            return
        try:
            self._bridge.hide_nearby(self._table_key, row, reason.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Hide Failed", str(exc))
            return
        self._rows.pop(idx)
        self._table.removeRow(idx)
        self._status.setText(f"{len(self._rows)} found. '{row['name']}' hidden.")

    def selected_rows(self) -> list[dict]:
        return [
            row
            for r, row in enumerate(self._rows)
            if not row["already_added"] and self._table.item(r, 0).checkState() == Qt.Checked
        ]


# ---------------------------------------------------------------------------
# Drawer (collapsible section)
# ---------------------------------------------------------------------------

class DrawerSection(QFrame):
    """A titled section whose body is collapsed until the header is clicked."""

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self._title = title
        self._content = content
        self.setFrameShape(QFrame.StyledPanel)

        self._toggle = QToolButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setAutoRaise(True)
        self._toggle.setArrowType(Qt.RightArrow)
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        font = self._toggle.font()
        font.setBold(True)
        self._toggle.setFont(font)
        self._toggle.setText(title)
        self._toggle.toggled.connect(self._on_toggled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addWidget(self._toggle)
        layout.addWidget(content)
        content.setVisible(False)

    def set_summary(self, summary: str) -> None:
        self._toggle.setText(f"{self._title}  ({summary})" if summary else self._title)

    def _on_toggled(self, expanded: bool) -> None:
        self._toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._content.setVisible(expanded)


# ---------------------------------------------------------------------------
# Resource section widget (table + toolbar)
# ---------------------------------------------------------------------------

class ResourceSection(QWidget):
    countChanged = Signal(int)

    def __init__(self, spec: dict, bridge: MedicalBridge, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._bridge = bridge
        self._rows: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._edit_btn = QPushButton("Edit")
        self._remove_btn = QPushButton("Remove")
        self._import_btn = QPushButton("Import from Master")
        self._nearby_btn = QPushButton("Find Nearby…")
        self._nearby_btn.setToolTip("Search for facilities near the incident and pick which to add")
        self._nearby_btn.setVisible(bool(self._spec.get("nearby")))
        self._nearby_btn.clicked.connect(self._find_nearby)
        self._add_btn.clicked.connect(self._add)
        self._edit_btn.clicked.connect(self._edit)
        self._remove_btn.clicked.connect(self._remove)
        self._import_btn.clicked.connect(self._import)
        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._edit_btn)
        toolbar.addWidget(self._remove_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._nearby_btn)
        toolbar.addWidget(self._import_btn)
        layout.addLayout(toolbar)

        cols = self._spec["columns"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setFixedHeight(120)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table)

    def set_read_only(self, read_only: bool) -> None:
        for btn in (self._add_btn, self._edit_btn, self._remove_btn, self._import_btn, self._nearby_btn):
            btn.setEnabled(not read_only)

    def refresh(self) -> None:
        try:
            self._rows = self._bridge.list_table(self._spec["key"])
        except Exception:
            self._rows = []
        t = self._table
        t.setRowCount(len(self._rows))
        display_fn = self._spec["display"]
        for r, row in enumerate(self._rows):
            for c, val in enumerate(display_fn(row)):
                t.setItem(r, c, QTableWidgetItem(val))
        t.resizeColumnsToContents()
        t.horizontalHeader().setStretchLastSection(True)
        self.countChanged.emit(len(self._rows))

    def _selected_row(self) -> Optional[dict]:
        idx = self._table.currentRow()
        if 0 <= idx < len(self._rows):
            return self._rows[idx]
        return None

    def _add(self) -> None:
        dlg = RowEditDialog(self._spec["fields"], self)
        if dlg.exec() == QDialog.Accepted:
            try:
                self._bridge.add_record(self._spec["key"], dlg.result_data())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _edit(self) -> None:
        if not self._edit_btn.isEnabled():
            return
        row = self._selected_row()
        if not row:
            return
        dlg = RowEditDialog(self._spec["fields"], self, data=row)
        if dlg.exec() == QDialog.Accepted:
            try:
                self._bridge.update_record(self._spec["key"], row["id"], dlg.result_data())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _remove(self) -> None:
        row = self._selected_row()
        if not row:
            return
        name = row.get("name") or row.get("channel") or str(row.get("id"))
        if QMessageBox.question(self, "Remove", f"Remove '{name}'?") == QMessageBox.Yes:
            try:
                self._bridge.delete_record(self._spec["key"], row["id"])
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _find_nearby(self) -> None:
        dlg = NearbyPickerDialog(self._spec["label"], self._spec["key"], self._bridge, self)
        if dlg.exec() != QDialog.Accepted:
            return
        picked = dlg.selected_rows()
        if not picked:
            return
        try:
            added = self._bridge.add_nearby(self._spec["key"], picked)
            self.refresh()
            QMessageBox.information(
                self, "Added", f"Added {added} from the nearby search. Review each entry and fill in the missing details."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _import(self) -> None:
        try:
            method = getattr(self._bridge, self._spec["import_method"])
            count = method()
            self.refresh()
            QMessageBox.information(self, "Import", f"Imported {count} record(s) from master database.")
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))


# ---------------------------------------------------------------------------
# Main ICS-206 panel
# ---------------------------------------------------------------------------

def _display_stamp(value: str) -> str:
    """Human-readable local timestamp, whole seconds."""
    dt = to_datetime(value) if value else None
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S") if dt else ""


class ICS206Panel(QWidget):
    """Single-page ICS-206 Medical Plan panel with collapsible drawers and versioning."""

    VERSION_COLUMNS = ["Version", "Status", "Prepared By", "Prepared", "Approved By", "Approved", "Change Note"]

    def __init__(self, incident_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        try:
            self._bridge = MedicalBridge()
        except Exception:
            self._bridge = None
        self._sections: list[ResourceSection] = []
        self._locked = False
        self._approval_status = APPROVAL_NOT_STARTED
        self._build_ui()
        if self._bridge:
            self._bridge.data_changed.connect(self._on_data_changed)
            self._refresh_all()
        app_signals.opPeriodChanged.connect(self._on_op_period_changed)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header_bar = QWidget()
        header_layout = QVBoxLayout(header_bar)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("Medical Plan (ICS-206)")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        title.setFont(title_font)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(QLabel("Op Period:"))
        self._op_label = QLabel(str(AppState.get_active_op_period() or 1))
        op_font = self._op_label.font()
        op_font.setBold(True)
        self._op_label.setFont(op_font)
        title_row.addWidget(self._op_label)
        header_layout.addLayout(title_row)

        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("Version:"))
        self._version_combo = QComboBox()
        self._version_combo.setMinimumWidth(150)
        self._version_combo.currentIndexChanged.connect(self._on_version_selected)
        version_row.addWidget(self._version_combo)
        self._status_chip = QLabel()
        self._status_chip.setAlignment(Qt.AlignCenter)
        version_row.addWidget(self._status_chip)
        self._new_version_btn = QPushButton("New Version…")
        self._new_version_btn.setToolTip("Copy the selected version into a new draft version")
        self._new_version_btn.clicked.connect(self._create_version)
        self._submit_btn = QPushButton("Submit for Approval…")
        self._submit_btn.setToolTip(
            "Send the selected version through the ICS-206 approval chain (Medical Unit Leader, then Safety Officer)"
        )
        self._submit_btn.clicked.connect(self._submit_for_approval)
        self._reject_btn = QPushButton("Reject…")
        self._reject_btn.setToolTip("Reject the selected version at your approval step")
        self._reject_btn.clicked.connect(self._reject)
        self._reject_btn.setVisible(False)
        version_row.addWidget(self._new_version_btn)
        version_row.addWidget(self._submit_btn)
        version_row.addWidget(self._reject_btn)
        version_row.addStretch()
        self._copy_prev_btn = QPushButton("Copy from Previous OP")
        self._copy_prev_btn.setToolTip(
            "Replace this draft's contents with the plan from the previous operational period"
        )
        self._copy_prev_btn.clicked.connect(self._duplicate_op)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_all)
        version_row.addWidget(self._copy_prev_btn)
        version_row.addWidget(refresh_btn)
        header_layout.addLayout(version_row)

        self._lock_note = QLabel()
        self._lock_note.setWordWrap(True)
        self._lock_note.setVisible(False)
        header_layout.addWidget(self._lock_note)
        self._timeline = ApprovalTimeline()
        self._timeline.sign_requested.connect(self._on_sign_requested)
        self._timeline.setVisible(False)
        header_layout.addWidget(self._timeline)
        outer.addWidget(header_bar)
        subscribe_theme(self, self._apply_theme)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(6)

        if self._bridge is None:
            body_layout.addWidget(QLabel("Medical bridge unavailable — no active incident."))
            body_layout.addStretch()
            scroll.setWidget(body)
            outer.addWidget(scroll, 1)
            for widget in (self._version_combo, self._new_version_btn, self._submit_btn, self._copy_prev_btn):
                widget.setEnabled(False)
            return

        self._drawers: list[DrawerSection] = []
        for spec in SECTIONS:
            section = ResourceSection(spec, self._bridge)
            drawer = DrawerSection(spec["label"], section)
            section.countChanged.connect(lambda n, d=drawer: d.set_summary(str(n)))
            section.countChanged.emit(len(section._rows))
            self._sections.append(section)
            body_layout.addWidget(drawer)

        body_layout.addWidget(DrawerSection("Medical Emergency Procedures", self._build_procedures()))
        body_layout.addWidget(DrawerSection("Prepared By / Approved By", self._build_signoff()))
        self._history_drawer = DrawerSection("Version History", self._build_history())
        body_layout.addWidget(self._history_drawer)
        body_layout.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _build_procedures(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        self._procedures = QTextEdit()
        self._procedures.setPlaceholderText(
            "Describe emergency procedures — reporting, on-scene care, transport decisions, communications plan, extraction notes…"
        )
        self._procedures.setMinimumHeight(120)
        layout.addWidget(self._procedures)
        self._save_proc_btn = QPushButton("Save Procedures")
        self._save_proc_btn.setFixedWidth(140)
        self._save_proc_btn.clicked.connect(self._save_procedures)
        layout.addWidget(self._save_proc_btn, alignment=Qt.AlignLeft)
        return box

    def _build_signoff(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        self._prepared_by = QLabel()
        self._prepared_position = QLabel()
        self._prepared_at = QLabel()
        self._approved_by = QLabel()
        self._approved_position = QLabel()
        self._approved_at = QLabel()
        form.addRow("Prepared by", self._prepared_by)
        form.addRow("Position", self._prepared_position)
        form.addRow("Prepared at", self._prepared_at)
        form.addRow("Approved by", self._approved_by)
        form.addRow("Position", self._approved_position)
        form.addRow("Approved at", self._approved_at)
        return box

    def _build_history(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Double-click a version to open it.")
        layout.addWidget(hint)
        self._history_table = QTableWidget(0, len(self.VERSION_COLUMNS))
        self._history_table.setHorizontalHeaderLabels(self.VERSION_COLUMNS)
        apply_statusboard_table_behavior(self._history_table, stretch_last_section=True)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.setFixedHeight(140)
        self._history_table.doubleClicked.connect(self._open_history_version)
        layout.addWidget(self._history_table)
        return box

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _apply_theme(self, _name: str = "") -> None:
        status = getattr(self, "_status_key", "draft")
        colors = medical_plan_status_colors().get(status)
        if not colors:
            return
        self._status_chip.setStyleSheet(
            "QLabel { border-radius: 8px; padding: 2px 10px; font-weight: 600;"
            f" background: {colors['bg'].color().name()}; color: {colors['fg'].color().name()}; }}"
        )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _on_data_changed(self, table: str) -> None:
        if table == "all":
            self._refresh_all()

    def _refresh_all(self) -> None:
        if not self._bridge:
            return
        self._op_label.setText(str(AppState.get_active_op_period() or 1))
        try:
            versions = self._bridge.list_versions()
            current = self._bridge.current_version()
            status = self._bridge.approval_status()
        except Exception as exc:
            self._lock_note.setText(str(exc))
            self._lock_note.setVisible(True)
            return
        self._approval_status = status
        self._locked = status != APPROVAL_NOT_STARTED
        self._load_versions(versions, current)
        for section in self._sections:
            section.set_read_only(self._locked)
            section.refresh()
        self._load_text_sections()
        self._apply_lock_state(current)

    def _load_versions(self, versions: list[dict], current: int) -> None:
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        known = {row["version"] for row in versions}
        if current not in known:
            # The selected version has no saved plan yet (first open of an OP).
            versions = versions + [{"version": current, "approval_status": APPROVAL_NOT_STARTED}]
        for row in versions:
            label = f"v{row['version']} — {APPROVAL_LABELS.get(row['approval_status'], row['approval_status'])}"
            self._version_combo.addItem(label, row["version"])
        idx = self._version_combo.findData(current)
        self._version_combo.setCurrentIndex(max(idx, 0))
        self._version_combo.blockSignals(False)

        table = self._history_table
        table.setRowCount(len(versions))
        for r, row in enumerate(versions):
            cells = [
                f"v{row['version']}",
                APPROVAL_LABELS.get(row["approval_status"], row["approval_status"]),
                row.get("prepared_by") or "",
                _display_stamp(row.get("prepared_at") or ""),
                row.get("approved_by") or "",
                _display_stamp(row.get("approved_at") or ""),
                row.get("change_note") or "",
            ]
            for c, val in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(val))
            if row["version"] == current:
                table.selectRow(r)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        self._history_drawer.set_summary(f"{len(versions)}")

    def _load_text_sections(self) -> None:
        try:
            self._procedures.setPlainText(self._bridge.get_procedures())
        except Exception:
            pass
        try:
            sigs = self._bridge.get_signatures()
        except Exception:
            sigs = {}
        self._prepared_by.setText(sigs.get("prepared_by") or "—")
        self._prepared_position.setText(sigs.get("position") or "—")
        self._prepared_at.setText(_display_stamp(sigs.get("prepared_at") or "") or "—")
        self._approved_by.setText(sigs.get("approved_by") or "Not approved")
        self._approved_position.setText(sigs.get("approved_by_position") or "—")
        self._approved_at.setText(_display_stamp(sigs.get("approved_at") or "") or "—")

    def _apply_lock_state(self, version: int) -> None:
        status = self._approval_status
        locked = self._locked
        self._status_key = status
        self._status_chip.setText(
            APPROVAL_LABELS[status] + (" — locked" if status == APPROVAL_APPROVED else "")
        )
        self._apply_theme()
        self._procedures.setReadOnly(locked)
        self._save_proc_btn.setEnabled(not locked)
        self._submit_btn.setEnabled(not locked)
        self._copy_prev_btn.setEnabled(not locked)
        self._lock_note.setVisible(locked)
        if locked:
            self._lock_note.setText(
                f"Version {version} is {APPROVAL_LABELS[status].lower()} and locked. Use New Version to make changes."
            )
        self._load_approval_state()

    def _person_record(self) -> int:
        uid = AppState.get_active_user_id()
        return int(uid) if uid and str(uid).isdigit() else 0

    def _load_approval_state(self) -> None:
        """Show the approval chain for the selected version and who can act on it."""
        self._reject_btn.setVisible(False)
        if self._approval_status == APPROVAL_NOT_STARTED:
            self._timeline.set_state(None)
            self._timeline.setVisible(False)
            return
        try:
            incident_id, plan_id = self._bridge.approval_target()
            service = ApprovalService(incident_id)
            instance = service.get("ics_206", plan_id)
            person_record = self._person_record()
            assignment_type = service.assignment_type_for(person_record) if person_record else None
        except Exception as exc:
            self._timeline.setVisible(False)
            self._lock_note.setText(f"{self._lock_note.text()}  (Approval details unavailable: {exc})")
            return
        self._timeline.set_state(instance, person_record, assignment_type)
        self._timeline.setVisible(instance is not None)
        if instance is not None and self._approval_status == APPROVAL_PENDING and person_record:
            self._reject_btn.setVisible(
                any(
                    service.can_sign(instance, step.step_id, person_record, assignment_type or "primary")
                    for step in instance.steps
                )
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_op_period_changed(self, op_data: object) -> None:
        """Reload the plan for the newly active operational period."""
        if not self._bridge:
            return
        self._bridge.select_version(None)

    def _on_version_selected(self, index: int) -> None:
        version = self._version_combo.itemData(index)
        if self._bridge and version is not None:
            self._bridge.select_version(int(version))

    def _open_history_version(self, index) -> None:
        item = self._history_table.item(index.row(), 0)
        if self._bridge and item is not None:
            self._bridge.select_version(int(item.text().lstrip("v")))

    def _create_version(self) -> None:
        if not self._bridge:
            return
        source = self._bridge.current_version()
        note, ok = QInputDialog.getText(
            self,
            "New Version",
            f"Create a new draft version from v{source}.\nWhat changed? (optional)",
        )
        if not ok:
            return
        try:
            self._bridge.create_new_version(note)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _submit_for_approval(self) -> None:
        if not self._bridge:
            return
        version = self._bridge.current_version()
        if QMessageBox.question(
            self,
            "Submit for Approval",
            f"Submit v{version} for approval?\n\nThe version will be locked while it is in review. "
            "If it is rejected, create a new version to make changes.",
        ) != QMessageBox.Yes:
            return
        try:
            incident_id, plan_id = self._bridge.approval_target()
            ApprovalService(incident_id).start("ics_206", plan_id)
            self._bridge.mark_pending()
        except Exception as exc:
            QMessageBox.critical(self, "Submission Failed", str(exc))

    def _on_sign_requested(self, step_id: str) -> None:
        self._act_on_step(step_id, "approved")

    def _reject(self) -> None:
        if not self._bridge:
            return
        try:
            incident_id, plan_id = self._bridge.approval_target()
            service = ApprovalService(incident_id)
            instance = service.get("ics_206", plan_id)
            person_record = self._person_record()
            assignment_type = service.assignment_type_for(person_record)
            step = next(
                (
                    s for s in (instance.steps if instance else [])
                    if service.can_sign(instance, s.step_id, person_record, assignment_type)
                ),
                None,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Reject Failed", str(exc))
            return
        if step is None:
            QMessageBox.information(self, "Reject", "No approval step is waiting on you.")
            return
        reason, ok = QInputDialog.getText(self, "Reject Version", f"Why is this being rejected at '{step.label}'?")
        if ok:
            self._act_on_step(step.step_id, "rejected", reason.strip() or None)

    def _act_on_step(self, step_id: str, action: str, notes: Optional[str] = None) -> None:
        if not self._bridge:
            return
        try:
            incident_id, plan_id = self._bridge.approval_target()
            service = ApprovalService(incident_id)
            instance = service.get("ics_206", plan_id)
            if instance is None:
                raise RuntimeError("This version has not been submitted for approval.")
            person_record = self._person_record()
            assignment_type = service.assignment_type_for(person_record) if person_record else "primary"
            if not service.can_sign(instance, step_id, person_record, assignment_type):
                raise RuntimeError("You are not able to act on this approval step.")
            step = next(s for s in instance.steps if s.step_id == step_id)
            updated = service.sign(
                instance,
                step_id=step_id,
                actor_id=str(person_record),
                role_at_time=step.resolved_role or step.role,
                assignment_type=assignment_type,
                action=action,
                notes=notes,
            )
            if updated.status in (APPROVAL_APPROVED, APPROVAL_REJECTED):
                self._bridge.apply_approval_outcome(updated.status)
            else:
                self._refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Approval Failed", str(exc))

    def _duplicate_op(self) -> None:
        if not self._bridge:
            return
        if QMessageBox.question(
            self,
            "Copy from Previous OP",
            f"Replace the contents of v{self._bridge.current_version()} with the previous operational period's plan?",
        ) != QMessageBox.Yes:
            return
        try:
            if self._bridge.duplicate_last_op():
                QMessageBox.information(self, "Copied", "Plan copied from the previous operational period.")
            else:
                QMessageBox.information(self, "Nothing to Copy", "No entries found in a prior operational period.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _save_procedures(self) -> None:
        if not self._bridge:
            return
        try:
            self._bridge.save_procedures(self._procedures.toPlainText().strip())
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
