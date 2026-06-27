"""Single-page ICS-206 Medical Plan panel backed by MedicalBridge."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
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
    QVBoxLayout,
    QWidget,
)

from bridge.medical_bridge import MedicalBridge
from modules.logistics.facilities.service import FacilitiesService
from modules.logistics.facilities.widgets.facility_picker import FacilityPicker
from utils.state import AppState


# ---------------------------------------------------------------------------
# Section specifications — drives tables and edit dialogs
# ---------------------------------------------------------------------------

SECTIONS = [
    {
        "key": "aid_stations",
        "label": "Aid Stations",
        "import_method": "import_aid_stations",
        "columns": ["Name", "Facility/Location", "Type", "Level", "24/7", "Manager", "Notes"],
        "fields": [
            ("facility_id", "Facility", "facility", "medical"),
            ("name", "Name", "text", None),
            ("type", "Type", "combo", ["Medical Aid", "BLS", "ALS", "Paramedic", "Other"]),
            ("level", "Level", "text", None),
            ("is_24_7", "24/7?", "bool", None),
            ("location_text", "Location", "text", None),
            ("manager_name", "Manager", "text", None),
            ("notes", "Notes", "text", None),
        ],
        "display": lambda r: [
            r.get("name") or "",
            r.get("location_text") or "",
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
        "import_method": "import_hospitals",
        "columns": ["Name", "Address", "Phone", "Helipad", "Burn Ctr", "Trauma Level", "Notes"],
        "fields": [
            ("name",        "Name",         "text",  None),
            ("address",     "Address",      "text",  None),
            ("phone",       "Phone",        "text",  None),
            ("helipad",     "Helipad?",     "bool",  None),
            ("burn_center", "Burn Center?", "bool",  None),
            ("level",       "Trauma Level", "combo", ["I", "II", "III", "IV", "None"]),
            ("notes",       "Notes",        "text",  None),
        ],
        "display": lambda r: [
            r.get("name") or "",
            r.get("address") or "",
            r.get("phone") or "",
            "Yes" if r.get("helipad") else "No",
            "Yes" if r.get("burn_center") else "No",
            r.get("level") or "",
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
# Resource section widget (table + toolbar)
# ---------------------------------------------------------------------------

class ResourceSection(QWidget):
    def __init__(self, spec: dict, bridge: MedicalBridge, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._bridge = bridge
        self._rows: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        layout.setSpacing(4)

        # Section header
        header = QLabel(self._spec["label"])
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        header.setFont(font)
        header.setStyleSheet("color: #1a237e;")
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add")
        edit_btn = QPushButton("Edit")
        remove_btn = QPushButton("Remove")
        import_btn = QPushButton("Import from Master")
        import_btn.setStyleSheet("color: #1565c0;")
        add_btn.clicked.connect(self._add)
        edit_btn.clicked.connect(self._edit)
        remove_btn.clicked.connect(self._remove)
        import_btn.clicked.connect(self._import)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addStretch()
        toolbar.addWidget(import_btn)
        layout.addLayout(toolbar)

        # Table
        cols = self._spec["columns"]
        self._table = QTableWidget(0, len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setFixedHeight(120)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(line)

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

class ICS206Panel(QWidget):
    """Single-page ICS-206 Medical Plan panel."""

    def __init__(self, incident_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._incident_id = incident_id
        try:
            self._bridge = MedicalBridge()
        except Exception:
            self._bridge = None
        self._sections: list[ResourceSection] = []
        self._build_ui()
        if self._bridge:
            self._load_text_sections()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setStyleSheet("background: #e8eaf6; padding: 6px;")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(12, 6, 12, 6)
        title = QLabel("Medical Plan (ICS-206)")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1a237e;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        op_lbl = QLabel("Op Period:")
        self._op_label = QLabel(str(AppState.get_active_op_period() or 1))
        self._op_label.setStyleSheet("font-weight: 700; min-width: 24px;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_all)
        dup_btn = QPushButton("Copy from Previous OP")
        dup_btn.setToolTip("Copy all resource entries from the previous operational period into this one")
        dup_btn.clicked.connect(self._duplicate_op)
        header_layout.addWidget(op_lbl)
        header_layout.addWidget(self._op_label)
        header_layout.addWidget(refresh_btn)
        header_layout.addWidget(dup_btn)
        outer.addWidget(header_bar)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(4)

        if self._bridge is None:
            body_layout.addWidget(QLabel("Medical bridge unavailable — no active incident."))
            body_layout.addStretch()
            scroll.setWidget(body)
            outer.addWidget(scroll, 1)
            return

        # Resource tables
        for spec in SECTIONS:
            section = ResourceSection(spec, self._bridge)
            self._sections.append(section)
            body_layout.addWidget(section)

        # Procedures
        proc_lbl = QLabel("Medical Emergency Procedures")
        proc_font = QFont()
        proc_font.setBold(True)
        proc_font.setPointSize(9)
        proc_lbl.setFont(proc_font)
        proc_lbl.setStyleSheet("color: #1a237e; padding-top: 6px;")
        body_layout.addWidget(proc_lbl)
        self._procedures = QTextEdit()
        self._procedures.setPlaceholderText(
            "Describe emergency procedures — reporting, on-scene care, transport decisions, communications plan, extraction notes…"
        )
        self._procedures.setMinimumHeight(120)
        body_layout.addWidget(self._procedures)
        save_proc_btn = QPushButton("Save Procedures")
        save_proc_btn.setFixedWidth(140)
        save_proc_btn.clicked.connect(self._save_procedures)
        body_layout.addWidget(save_proc_btn, alignment=Qt.AlignLeft)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #e0e0e0; margin-top: 8px;")
        body_layout.addWidget(div)

        # Signatures
        sig_lbl = QLabel("Prepared By / Approved By")
        sig_lbl.setFont(proc_font)
        sig_lbl.setStyleSheet("color: #1a237e; padding-top: 4px;")
        body_layout.addWidget(sig_lbl)
        sig_grid = QHBoxLayout()
        self._prepared_by = QLineEdit()
        self._prepared_by.setPlaceholderText("Prepared by")
        self._position = QLineEdit()
        self._position.setPlaceholderText("Position / Title")
        self._approved_by = QLineEdit()
        self._approved_by.setPlaceholderText("Approved by")
        self._sig_date = QLineEdit()
        self._sig_date.setPlaceholderText("Date / Time")
        for lbl_text, widget in [
            ("Prepared By", self._prepared_by),
            ("Position", self._position),
            ("Approved By", self._approved_by),
            ("Date", self._sig_date),
        ]:
            col = QVBoxLayout()
            col.addWidget(QLabel(lbl_text))
            col.addWidget(widget)
            sig_grid.addLayout(col)
        body_layout.addLayout(sig_grid)
        save_sig_btn = QPushButton("Save")
        save_sig_btn.setFixedWidth(80)
        save_sig_btn.clicked.connect(self._save_signatures)
        body_layout.addWidget(save_sig_btn, alignment=Qt.AlignLeft)
        body_layout.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _load_text_sections(self) -> None:
        try:
            text = self._bridge.get_procedures()
            self._procedures.setPlainText(text)
        except Exception:
            pass
        try:
            sigs = self._bridge.get_signatures()
            self._prepared_by.setText(sigs.get("prepared_by") or "")
            self._position.setText(sigs.get("position") or "")
            self._approved_by.setText(sigs.get("approved_by") or "")
            self._sig_date.setText(sigs.get("date") or "")
        except Exception:
            pass

    def _refresh_all(self) -> None:
        self._op_label.setText(str(AppState.get_active_op_period() or 1))
        for section in self._sections:
            section.refresh()
        self._load_text_sections()

    def _duplicate_op(self) -> None:
        if not self._bridge:
            return
        try:
            copied = self._bridge.duplicate_last_op()
            if copied:
                self._refresh_all()
                QMessageBox.information(self, "Copied", "Resource entries copied from the previous operational period.")
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

    def _save_signatures(self) -> None:
        if not self._bridge:
            return
        try:
            self._bridge.save_signatures({
                "prepared_by": self._prepared_by.text().strip(),
                "position": self._position.text().strip(),
                "approved_by": self._approved_by.text().strip(),
                "date": self._sig_date.text().strip(),
            })
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
