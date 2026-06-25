"""
Personnel Inventory & Detail Edit Window (QtWidgets, PySide6)
REPLACES the prior QML implementation. No QML imports anywhere.

Placement: keep within your app's UI layer (NOT under backend/). For example:
  src/ui/personnel/ui_personnel.py

Data: fully MongoDB-backed via the SARApp API (utils.api_client); no direct
SQLite access remains in this module.

This file provides:
  - PersonnelInventoryWindow (main roster window with search/filters/import/export)
  - PersonnelDetailDialog (tabbed modal: Demographics, Emergency, Contact, Certifications)
  - Csv helpers for the per-person certifications tab

Notes:
  - Connect this window from your Edit menu: e.g., actionEditPersonnel.triggered -> open_inventory()
  - Columns are restricted to persistent master-personnel data (no incident-specific fields).
"""
from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from notifications.models import Notification
from notifications.services import get_notifier
from utils.edit_window_kit import (
    ExportDialog,
    FieldSpec,
    ImportWizard,
    PaginationControls,
    run_async,
    write_export_file,
)
from utils.org_combo import make_org_combo


# ----------------------------- Data Models -----------------------------------
@dataclass
class Certification:
    id: Optional[int]
    personnel_id: str
    code: str
    name: str
    level: int = 0  # 0=None, 1=Trainee, 2=Qualified, 3=Evaluator
    expiration: str = ""  # ISO yyyy-mm-dd
    docs: str = ""



# ----------------------------- CSV Helpers -----------------------------------
class CsvUtil:
    @staticmethod
    def export_certifications(path: str, records: Iterable[Certification]) -> None:
        fieldnames = ["id", "personnel_id", "code", "name", "level", "expiration", "docs"]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for cert in records:
                payload = asdict(cert)
                writer.writerow(payload)

    @staticmethod
    def import_certifications(path: str) -> List[Certification]:
        certs: list[Certification] = []
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                cert_id = int(row["id"]) if row.get("id") else None
                try:
                    level = int(row.get("level", "") or 0)
                except ValueError:
                    level = 0
                certs.append(
                    Certification(
                        id=cert_id,
                        personnel_id=row.get("personnel_id", ""),
                        code=row.get("code", ""),
                        name=row.get("name", ""),
                        level=level,
                        expiration=row.get("expiration", ""),
                        docs=row.get("docs", ""),
                    )
                )
        return certs


# ----------------------------- UI: Personnel Table Model ----------------------
class _PersonnelTableModel(QtCore.QAbstractTableModel):
    HEADERS = ["ID", "Name", "Callsign", "Role", "Organization", "Email", "Phone"]
    KEYS = ["id", "name", "callsign", "primary_role", "home_unit", "email", "phone"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[dict[str, Any]] = []

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        rec = self._records[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return str(rec.get(self.KEYS[index.column()]) or "")
        if role == QtCore.Qt.UserRole:
            return rec
        return None

    def set_records(self, records: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def record_at(self, row: int) -> Optional[dict[str, Any]]:
        return self._records[row] if 0 <= row < len(self._records) else None


# ----------------------------- UI: Cert Picker Dialog -------------------------
class _CertPickerDialog(QtWidgets.QDialog):
    """Search the cert catalog and pick one to add, setting level/expiration/docs."""

    _LEVEL_LABELS = ["None", "Trainee", "Qualified", "Evaluator"]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Certification")
        self.resize(720, 520)
        self.setModal(True)
        self._all_certs: list[dict[str, Any]] = []
        self._result: Optional[dict[str, Any]] = None

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search by code, name, or category…")

        self.catalog_table = QtWidgets.QTableWidget(0, 3)
        self.catalog_table.setHorizontalHeaderLabels(["Code", "Name", "Category"])
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.catalog_table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.catalog_table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.catalog_table.doubleClicked.connect(self._on_accept)

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(self._LEVEL_LABELS)
        self.level_combo.setCurrentIndex(2)
        self.exp_edit = QtWidgets.QLineEdit()
        self.exp_edit.setPlaceholderText("YYYY-MM-DD")
        self.docs_edit = QtWidgets.QLineEdit()
        self.docs_edit.setPlaceholderText("Certificate number, file path, or notes")

        detail_form = QtWidgets.QFormLayout()
        detail_form.addRow("Level:", self.level_combo)
        detail_form.addRow("Expiration:", self.exp_edit)
        detail_form.addRow("Documents:", self.docs_edit)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(QtWidgets.QLabel("Search:"))
        search_row.addWidget(self.search_edit, 1)
        layout.addLayout(search_row)
        layout.addWidget(self.catalog_table, 1)
        layout.addLayout(detail_form)
        layout.addWidget(buttons)

        self.search_edit.textChanged.connect(self._filter)
        self._load_catalog()

    def _load_catalog(self) -> None:
        from utils.api_client import api_client
        try:
            self._all_certs = api_client.get("/api/master/certifications/types") or []
        except Exception:
            self._all_certs = []
        self._populate(self._all_certs)

    def _filter(self, text: str) -> None:
        t = text.lower()
        self._populate([
            c for c in self._all_certs
            if not t
            or t in (c.get("code") or "").lower()
            or t in (c.get("name") or "").lower()
            or t in (c.get("category") or "").lower()
        ])

    def _populate(self, certs: list[dict[str, Any]]) -> None:
        self.catalog_table.setRowCount(0)
        for cert in certs:
            row = self.catalog_table.rowCount()
            self.catalog_table.insertRow(row)
            code_item = QtWidgets.QTableWidgetItem(cert.get("code") or "")
            code_item.setData(QtCore.Qt.UserRole, cert)
            self.catalog_table.setItem(row, 0, code_item)
            self.catalog_table.setItem(row, 1, QtWidgets.QTableWidgetItem(cert.get("name") or ""))
            self.catalog_table.setItem(row, 2, QtWidgets.QTableWidgetItem(cert.get("category") or ""))

    def _on_accept(self) -> None:
        row = self.catalog_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(self, "Select Certification", "Pick a certification from the list.")
            return
        item = self.catalog_table.item(row, 0)
        cert = item.data(QtCore.Qt.UserRole) if item else None
        if not cert:
            return
        level_map = {label: i for i, label in enumerate(self._LEVEL_LABELS)}
        self._result = {
            "code": cert.get("code", ""),
            "name": cert.get("name", ""),
            "category": cert.get("category", ""),
            "cert_type_id": cert.get("int_id"),
            "level": level_map.get(self.level_combo.currentText(), 0),
            "expiration": self.exp_edit.text().strip(),
            "docs": self.docs_edit.text().strip(),
        }
        self.accept()

    def result_cert(self) -> Optional[dict[str, Any]]:
        return self._result


class _CertEditDetailsDialog(QtWidgets.QDialog):
    """Edit level/expiration/docs for an existing cert entry (catalog already known)."""

    _LEVEL_LABELS = ["None", "Trainee", "Qualified", "Evaluator"]

    def __init__(self, cert: dict[str, Any], parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit — {cert.get('name') or cert.get('code', '')}")
        self.setModal(True)
        self._cert = dict(cert)

        name_label = QtWidgets.QLabel(f"<b>{cert.get('code', '')} — {cert.get('name', '')}</b>")
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(self._LEVEL_LABELS)
        self.level_combo.setCurrentIndex(int(cert.get("level") or 0))
        self.exp_edit = QtWidgets.QLineEdit(cert.get("expiration") or "")
        self.exp_edit.setPlaceholderText("YYYY-MM-DD")
        self.docs_edit = QtWidgets.QLineEdit(cert.get("docs") or "")

        form = QtWidgets.QFormLayout()
        form.addRow(name_label)
        form.addRow("Level:", self.level_combo)
        form.addRow("Expiration:", self.exp_edit)
        form.addRow("Documents:", self.docs_edit)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def updated_cert(self) -> dict[str, Any]:
        result = dict(self._cert)
        result["level"] = self.level_combo.currentIndex()
        result["expiration"] = self.exp_edit.text().strip()
        result["docs"] = self.docs_edit.text().strip()
        return result


# ----------------------------- UI: Detail Dialog ------------------------------
class PersonnelDetailDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, personnel_id: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Personnel Record" if personnel_id else "Add New Personnel")
        self.resize(760, 640)
        self.setModal(True)
        self.personnel_id = personnel_id or ""
        self._photo_path = ""
        self._local_certs: list[dict[str, Any]] = []

        basic_panel = self._build_basic_panel()

        self.tabs = QtWidgets.QTabWidget()
        self._build_tab_certifications()
        self._build_tab_emergency()
        self._build_tab_contact()

        btn_save = QtWidgets.QPushButton("Save")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(basic_panel)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(btn_row)

        if self.personnel_id:
            self._load_all()

    # ----------------- Layout -----------------
    def _build_basic_panel(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Basic Information")
        grid = QtWidgets.QGridLayout(box)

        self.txt_id = QtWidgets.QLineEdit()
        self.txt_id.setPlaceholderText("Auto-assigned")
        self.txt_id.setReadOnly(True)
        self.txt_badge = QtWidgets.QLineEdit()
        self.txt_badge.setPlaceholderText("Badge / Employee #")
        self.txt_name = QtWidgets.QLineEdit()
        self.txt_callsign = QtWidgets.QLineEdit()
        self.txt_role = QtWidgets.QLineEdit()
        self.txt_role.setPlaceholderText("e.g. Search Team Leader")
        self.txt_rank = QtWidgets.QLineEdit()
        self.txt_org = make_org_combo()
        self.txt_email = QtWidgets.QLineEdit()
        self.txt_phone = QtWidgets.QLineEdit()
        self.txt_notes = QtWidgets.QLineEdit()
        self.chk_medic = QtWidgets.QCheckBox("Medic")
        self.btn_photo = QtWidgets.QPushButton("Photo…")
        self.btn_photo.setFixedWidth(80)
        self.btn_photo.clicked.connect(self._choose_photo)

        # Row 0: Internal ID, Name, Callsign
        grid.addWidget(QtWidgets.QLabel("Internal ID:"), 0, 0)
        grid.addWidget(self.txt_id, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Name:"), 0, 2)
        grid.addWidget(self.txt_name, 0, 3)
        grid.addWidget(QtWidgets.QLabel("Callsign:"), 0, 4)
        grid.addWidget(self.txt_callsign, 0, 5)

        # Row 1: Role, Rank, Organization
        grid.addWidget(QtWidgets.QLabel("Role/Title:"), 1, 0)
        grid.addWidget(self.txt_role, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Rank:"), 1, 2)
        grid.addWidget(self.txt_rank, 1, 3)
        grid.addWidget(QtWidgets.QLabel("Organization:"), 1, 4)
        grid.addWidget(self.txt_org, 1, 5)

        # Row 2: Email, Phone, Medic
        grid.addWidget(QtWidgets.QLabel("Email:"), 2, 0)
        grid.addWidget(self.txt_email, 2, 1)
        grid.addWidget(QtWidgets.QLabel("Phone:"), 2, 2)
        grid.addWidget(self.txt_phone, 2, 3)
        grid.addWidget(self.chk_medic, 2, 4)

        # Row 3: Badge #, Notes, Photo
        grid.addWidget(QtWidgets.QLabel("Badge #:"), 3, 0)
        grid.addWidget(self.txt_badge, 3, 1)
        grid.addWidget(QtWidgets.QLabel("Notes:"), 3, 4)
        notes_row = QtWidgets.QHBoxLayout()
        notes_row.addWidget(self.txt_notes)
        notes_row.addWidget(self.btn_photo)
        grid.addLayout(notes_row, 3, 5)

        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(5, 3)
        return box

    def _build_tab_emergency(self) -> None:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.em_primary_name = QtWidgets.QLineEdit()
        self.em_primary_rel = QtWidgets.QLineEdit()
        self.em_primary_phone = QtWidgets.QLineEdit()
        self.em_secondary_name = QtWidgets.QLineEdit()
        self.em_secondary_rel = QtWidgets.QLineEdit()
        self.em_secondary_phone = QtWidgets.QLineEdit()
        self.em_medical = QtWidgets.QTextEdit()
        self.em_blood = QtWidgets.QComboBox()
        self.em_blood.addItems(["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
        self.em_ins = QtWidgets.QTextEdit()

        form.addRow("Primary Name:", self.em_primary_name)
        form.addRow("Primary Relationship:", self.em_primary_rel)
        form.addRow("Primary Phone:", self.em_primary_phone)
        form.addRow("Secondary Name:", self.em_secondary_name)
        form.addRow("Secondary Relationship:", self.em_secondary_rel)
        form.addRow("Secondary Phone:", self.em_secondary_phone)
        form.addRow("Medical/Allergies:", self.em_medical)
        form.addRow("Blood Type:", self.em_blood)
        form.addRow("Insurance Info:", self.em_ins)

        self.tabs.addTab(widget, "Emergency Info")

    def _build_tab_contact(self) -> None:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.addr1 = QtWidgets.QLineEdit()
        self.addr2 = QtWidgets.QLineEdit()
        self.city = QtWidgets.QLineEdit()
        self.state = QtWidgets.QComboBox()
        self.state.addItems([
            "",
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
        ])
        self.zip = QtWidgets.QLineEdit()
        self.work_phone = QtWidgets.QLineEdit()
        self.secondary_phone = QtWidgets.QLineEdit()
        self.pager = QtWidgets.QLineEdit()
        self.c_notes = QtWidgets.QTextEdit()

        form.addRow("Address 1:", self.addr1)
        form.addRow("Address 2:", self.addr2)
        form.addRow("City:", self.city)
        form.addRow("State:", self.state)
        form.addRow("Zip:", self.zip)
        form.addRow("Work Phone:", self.work_phone)
        form.addRow("Secondary Phone:", self.secondary_phone)
        form.addRow("Pager/Radio ID:", self.pager)
        form.addRow("Notes:", self.c_notes)

        self.tabs.addTab(widget, "Contact Info")

    def _build_tab_certifications(self) -> None:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.tbl_certs = QtWidgets.QTableWidget(0, 5)
        self.tbl_certs.setHorizontalHeaderLabels(["Code", "Name", "Level", "Expiration", "Docs"])
        self.tbl_certs.horizontalHeader().setStretchLastSection(True)
        self.tbl_certs.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.tbl_certs.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)

        btns = QtWidgets.QHBoxLayout()
        self.btn_add_cert = QtWidgets.QPushButton("Add Certification")
        self.btn_edit_cert = QtWidgets.QPushButton("Edit")
        self.btn_del_cert = QtWidgets.QPushButton("Remove")
        self.btn_imp_cert = QtWidgets.QPushButton("Import CSV")
        self.btn_exp_cert = QtWidgets.QPushButton("Export CSV")

        btns.addWidget(self.btn_add_cert)
        btns.addWidget(self.btn_edit_cert)
        btns.addWidget(self.btn_del_cert)
        btns.addStretch(1)
        btns.addWidget(self.btn_imp_cert)
        btns.addWidget(self.btn_exp_cert)

        layout.addWidget(self.tbl_certs)
        layout.addLayout(btns)

        self.btn_add_cert.clicked.connect(self._on_add_cert)
        self.btn_edit_cert.clicked.connect(self._on_edit_cert)
        self.btn_del_cert.clicked.connect(self._on_del_cert)
        self.btn_imp_cert.clicked.connect(self._on_import_certs)
        self.btn_exp_cert.clicked.connect(self._on_export_certs)

        self.tabs.addTab(widget, "Certifications")

    # ----------------- Load/Save -----------------
    def _load_all(self) -> None:
        from utils.api_client import api_client
        try:
            doc = api_client.get(f"/api/master/personnel/{self.personnel_id}")
        except Exception:
            doc = None
        if not doc:
            self._photo_path = ""
            return

        self.txt_id.setText(str(doc.get("id") or ""))
        self.txt_badge.setText(doc.get("badge_number") or "")
        self.txt_name.setText(doc.get("name") or "")
        self.txt_callsign.setText(doc.get("callsign") or "")
        self.txt_role.setText(doc.get("primary_role") or doc.get("role") or "")
        self.txt_rank.setText(doc.get("rank") or "")
        self.txt_org.setCurrentText(doc.get("home_unit") or doc.get("organization") or "")
        self.txt_email.setText(doc.get("email") or "")
        self.txt_phone.setText(doc.get("phone") or "")
        self.chk_medic.setChecked(bool(doc.get("is_medic")))
        self.txt_notes.setText(doc.get("notes") or "")
        self._photo_path = doc.get("photo_url") or ""

        em = doc.get("emergency_info") or {}
        self.em_primary_name.setText(em.get("primary_name") or "")
        self.em_primary_rel.setText(em.get("primary_relationship") or "")
        self.em_primary_phone.setText(em.get("primary_phone") or "")
        self.em_secondary_name.setText(em.get("secondary_name") or "")
        self.em_secondary_rel.setText(em.get("secondary_relationship") or "")
        self.em_secondary_phone.setText(em.get("secondary_phone") or "")
        self.em_medical.setPlainText(em.get("medical") or "")
        self.em_blood.setCurrentText(em.get("blood_type") or "")
        self.em_ins.setPlainText(em.get("insurance") or "")

        ct = doc.get("contact_info") or {}
        self.addr1.setText(ct.get("address1") or "")
        self.addr2.setText(ct.get("address2") or "")
        self.city.setText(ct.get("city") or "")
        self.state.setCurrentText(ct.get("state") or "")
        self.zip.setText(ct.get("zip") or "")
        self.work_phone.setText(ct.get("work_phone") or "")
        self.secondary_phone.setText(ct.get("secondary_phone") or "")
        self.pager.setText(ct.get("pager_id") or "")
        self.c_notes.setPlainText(ct.get("notes") or "")

        self._local_certs = list(doc.get("certifications") or [])
        self._refresh_certs()

    def _refresh_certs(self) -> None:
        self.tbl_certs.setRowCount(0)
        for i, cert in enumerate(self._local_certs):
            row = self.tbl_certs.rowCount()
            self.tbl_certs.insertRow(row)
            self.tbl_certs.setItem(row, 0, QtWidgets.QTableWidgetItem(str(cert.get("code") or "")))
            self.tbl_certs.setItem(row, 1, QtWidgets.QTableWidgetItem(str(cert.get("name") or "")))
            level_labels = {0: "None", 1: "Trainee", 2: "Qualified", 3: "Evaluator"}
            self.tbl_certs.setItem(row, 2, QtWidgets.QTableWidgetItem(level_labels.get(int(cert.get("level") or 0), str(cert.get("level") or ""))))
            self.tbl_certs.setItem(row, 3, QtWidgets.QTableWidgetItem(str(cert.get("expiration") or "")))
            self.tbl_certs.setItem(row, 4, QtWidgets.QTableWidgetItem(str(cert.get("docs") or "")))
            self.tbl_certs.setVerticalHeaderItem(row, QtWidgets.QTableWidgetItem(str(i)))

    # ----------------- Actions -----------------
    def _on_save(self) -> None:
        from utils.api_client import api_client, APIError
        name = self.txt_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Missing Required", "Name is required.")
            return
        doc = {
            "name": name,
            "callsign": self.txt_callsign.text().strip(),
            "primary_role": self.txt_role.text().strip(),
            "rank": self.txt_rank.text().strip(),
            "home_unit": self.txt_org.currentText().strip(),
            "email": self.txt_email.text().strip(),
            "phone": self.txt_phone.text().strip(),
            "badge_number": self.txt_badge.text().strip(),
            "is_medic": self.chk_medic.isChecked(),
            "notes": self.txt_notes.text().strip(),
            "photo_url": self._photo_path,
            "emergency_info": {
                "primary_name": self.em_primary_name.text().strip(),
                "primary_relationship": self.em_primary_rel.text().strip(),
                "primary_phone": self.em_primary_phone.text().strip(),
                "secondary_name": self.em_secondary_name.text().strip(),
                "secondary_relationship": self.em_secondary_rel.text().strip(),
                "secondary_phone": self.em_secondary_phone.text().strip(),
                "medical": self.em_medical.toPlainText().strip(),
                "blood_type": self.em_blood.currentText().strip(),
                "insurance": self.em_ins.toPlainText().strip(),
            },
            "contact_info": {
                "address1": self.addr1.text().strip(),
                "address2": self.addr2.text().strip(),
                "city": self.city.text().strip(),
                "state": self.state.currentText().strip(),
                "zip": self.zip.text().strip(),
                "work_phone": self.work_phone.text().strip(),
                "secondary_phone": self.secondary_phone.text().strip(),
                "pager_id": self.pager.text().strip(),
                "notes": self.c_notes.toPlainText().strip(),
            },
            "certifications": self._local_certs,
        }
        try:
            if self.personnel_id:
                from utils import incident_context
                active_incident_id = incident_context.get_active_incident_id()
                params = {"active_incident_id": active_incident_id} if active_incident_id else None
                result = api_client.put(f"/api/master/personnel/{self.personnel_id}", json=doc, params=params)
                normalized_id = str(result.get("id") or self.personnel_id)
            else:
                result = api_client.post("/api/master/personnel", json=doc)
                normalized_id = str(result.get("id") or "")
        except APIError as exc:
            QtWidgets.QMessageBox.warning(self, "Save Failed", str(exc))
            return
        self.personnel_id = normalized_id
        self.txt_id.setText(normalized_id)
        self.accept()

    def _choose_photo(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose Photo", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self._photo_path = path
            self.btn_photo.setText(os.path.basename(path))

    def _on_add_cert(self) -> None:
        dialog = _CertPickerDialog(parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            cert = dialog.result_cert()
            if cert:
                self._local_certs.append(cert)
                self._refresh_certs()

    def _on_edit_cert(self) -> None:
        row = self.tbl_certs.currentRow()
        if row < 0 or row >= len(self._local_certs):
            return
        dialog = _CertEditDetailsDialog(self._local_certs[row], parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self._local_certs[row] = dialog.updated_cert()
            self._refresh_certs()

    def _on_del_cert(self) -> None:
        row = self.tbl_certs.currentRow()
        if row < 0 or row >= len(self._local_certs):
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Remove selected certification?") != QtWidgets.QMessageBox.Yes:
            return
        self._local_certs.pop(row)
        self._refresh_certs()

    def _on_import_certs(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Certifications", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            certs = CsvUtil.import_certifications(path)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Import Failed", str(exc))
            return
        imported = 0
        for cert in certs:
            if cert.code or cert.name:
                self._local_certs.append({
                    "code": cert.code,
                    "name": cert.name,
                    "level": cert.level,
                    "expiration": cert.expiration,
                    "docs": cert.docs,
                })
                imported += 1
        QtWidgets.QMessageBox.information(self, "Import Complete", f"Imported {imported} certification(s).")
        self._refresh_certs()

    def _on_export_certs(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Certifications", "certifications.csv", "CSV Files (*.csv)")
        if not path:
            return
        certs = [
            Certification(
                id=None,
                personnel_id=self.personnel_id,
                code=c.get("code", ""),
                name=c.get("name", ""),
                level=int(c.get("level") or 0),
                expiration=c.get("expiration", ""),
                docs=c.get("docs", ""),
            )
            for c in self._local_certs
        ]
        try:
            CsvUtil.export_certifications(path, certs)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Export Complete", f"Exported {len(certs)} certification(s).")


# ----------------------------- UI: Inventory Window --------------------------
PERSONNEL_FIELDS: list[FieldSpec] = [
    FieldSpec("name", "Name", required=True),
    FieldSpec("callsign", "Callsign"),
    FieldSpec("primary_role", "Role"),
    FieldSpec("rank", "Rank"),
    FieldSpec("home_unit", "Organization"),
    FieldSpec("email", "Email"),
    FieldSpec("phone", "Phone"),
    FieldSpec("notes", "Notes"),
]
_PERSONNEL_FIELD_LABELS = {spec.key: spec.label for spec in PERSONNEL_FIELDS}


class PersonnelInventoryWindow(QtWidgets.QWidget):
    """Implements ``Design Documents/edit_window_style_guide.md``: card shell,
    header (Add/Delete/Import/Export), filter bar with empty states, pagination
    footer, generic import wizard, and export dialog with async export."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.setWindowTitle("Personnel Inventory")
        self.resize(1040, 660)
        self._notifier = get_notifier()
        self._all_records: list[dict[str, Any]] = []
        self._filtered_records: list[dict[str, Any]] = []
        self._search_text = ""
        self._page = 1
        self._page_size = 20

        self._build_ui()
        self.refresh()

    # ----- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        card = QtWidgets.QFrame(self)
        card.setObjectName("personnelCard")
        card.setStyleSheet(
            """
            #personnelCard {
                border-radius: 16px;
                background: palette(Base);
                border: 1px solid palette(Midlight);
            }
            QTableView { border: none; }
            """
        )
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Personnel Inventory")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)

        self.add_button = QtWidgets.QPushButton("Add")
        self.add_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.add_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.add_button.setToolTip("Add personnel")
        header.addWidget(self.add_button)

        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.delete_button.setEnabled(False)
        header.addWidget(self.delete_button)

        self.import_button = QtWidgets.QPushButton("Import")
        self.import_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowDown))
        self.import_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.import_button)

        self.export_button = QtWidgets.QPushButton("Export")
        self.export_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton))
        self.export_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.export_button)

        card_layout.addLayout(header)

        filter_bar = QtWidgets.QHBoxLayout()
        filter_bar.setSpacing(12)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search by name, callsign, ID, email, phone…")
        self.search_edit.setClearButtonEnabled(True)
        filter_bar.addWidget(self.search_edit, stretch=2)

        self.reset_button = QtWidgets.QToolButton()
        self.reset_button.setText("Reset filters")
        self.reset_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.reset_button.setStyleSheet("QToolButton { text-decoration: underline; border: none; padding: 4px; }")
        self.reset_button.hide()
        filter_bar.addWidget(self.reset_button)
        filter_bar.addStretch(1)
        card_layout.addLayout(filter_bar)

        self.error_banner = QtWidgets.QFrame()
        self.error_banner.setStyleSheet("background: #fdecea; border-radius: 8px; border: 1px solid #f5c6cb;")
        self.error_banner.hide()
        error_layout = QtWidgets.QHBoxLayout(self.error_banner)
        error_layout.setContentsMargins(12, 8, 12, 8)
        self.error_label = QtWidgets.QLabel("Failed to load data.")
        self.error_label.setStyleSheet("color: #b71c1c;")
        error_layout.addWidget(self.error_label, stretch=1)
        self.retry_button = QtWidgets.QPushButton("Retry")
        error_layout.addWidget(self.retry_button)
        card_layout.addWidget(self.error_banner)

        self._model = _PersonnelTableModel(self)
        self.table = QtWidgets.QTableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        from utils.itemview_delegates import RowOutlineSelectionDelegate
        self.table.setItemDelegate(RowOutlineSelectionDelegate(self.table, QtGui.QColor("#FFFFFF")))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.doubleClicked.connect(self._on_edit_selected)

        self.table_stack = QtWidgets.QStackedLayout()
        table_container = QtWidgets.QWidget()
        table_layout = QtWidgets.QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)
        self.table_stack.addWidget(table_container)

        self.no_results_widget = QtWidgets.QWidget()
        nr_layout = QtWidgets.QVBoxLayout(self.no_results_widget)
        nr_layout.addStretch(1)
        nr_label = QtWidgets.QLabel("No personnel match your filters.")
        nr_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        nr_label.setStyleSheet("font-size: 16px; color: palette(Mid);")
        nr_layout.addWidget(nr_label)
        clear_btn = QtWidgets.QPushButton("Clear filters")
        clear_btn.setFixedWidth(160)
        clear_btn.clicked.connect(self._on_reset_filters)
        nr_layout.addWidget(clear_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        nr_layout.addStretch(1)
        self.table_stack.addWidget(self.no_results_widget)

        self.first_run_widget = QtWidgets.QWidget()
        fr_layout = QtWidgets.QVBoxLayout(self.first_run_widget)
        fr_layout.addStretch(1)
        fr_label = QtWidgets.QLabel("Add your first personnel record.")
        fr_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        fr_label.setStyleSheet("font-size: 16px; color: palette(Mid);")
        fr_layout.addWidget(fr_label)
        fr_btn = QtWidgets.QPushButton("Add personnel")
        fr_btn.setFixedWidth(160)
        fr_btn.clicked.connect(self._on_add)
        fr_layout.addWidget(fr_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        fr_layout.addStretch(1)
        self.table_stack.addWidget(self.first_run_widget)

        card_layout.addLayout(self.table_stack, stretch=1)

        self.pagination = PaginationControls(self)
        card_layout.addWidget(self.pagination)

        outer.addWidget(card)

        self._debounce = QtCore.QTimer(self)
        self._debounce.setInterval(250)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._apply_filters)
        self.search_edit.textChanged.connect(self._on_search_text)
        self.reset_button.clicked.connect(self._on_reset_filters)

        self.add_button.clicked.connect(self._on_add)
        self.delete_button.clicked.connect(self._on_delete)
        self.import_button.clicked.connect(self._on_import)
        self.export_button.clicked.connect(self._on_export)
        self.retry_button.clicked.connect(self.refresh)

        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._update_buttons)

        self.pagination.pageRequested.connect(self._on_page_requested)
        self.pagination.pageSizeChanged.connect(self._on_page_size_changed)

    # ----- Data loading ------------------------------------------------------
    def refresh(self) -> None:
        from utils.api_client import api_client
        try:
            records = api_client.get("/api/master/personnel") or []
        except Exception as exc:
            self._show_error(f"Unable to load personnel: {exc}")
            return
        self._hide_error()
        self._all_records = records
        self._apply_filters()

    def _apply_filters(self) -> None:
        self._debounce.stop()
        needle = self._search_text.strip().lower()
        if needle:
            keys = _PersonnelTableModel.KEYS
            self._filtered_records = [
                r for r in self._all_records
                if needle in " ".join(str(r.get(k) or "") for k in keys).lower()
            ]
        else:
            self._filtered_records = list(self._all_records)
        self.reset_button.setVisible(bool(needle))
        self._page = 1
        self._render_page()

    def _render_page(self) -> None:
        total = len(self._filtered_records)
        max_page = max(1, -(-total // self._page_size)) if self._page_size else 1
        self._page = min(max(1, self._page), max_page)
        start = (self._page - 1) * self._page_size
        self._model.set_records(self._filtered_records[start:start + self._page_size])
        self.pagination.update_state(total=total, page=self._page, page_size=self._page_size)

        if total == 0:
            if self._search_text.strip():
                self.table_stack.setCurrentWidget(self.no_results_widget)
            else:
                self.table_stack.setCurrentWidget(self.first_run_widget)
        else:
            self.table_stack.setCurrentIndex(0)
        self._update_buttons()

    def _on_search_text(self, text: str) -> None:
        self._search_text = text
        self._debounce.start()

    def _on_reset_filters(self) -> None:
        self.search_edit.clear()
        self._search_text = ""
        self._apply_filters()

    def _on_page_requested(self, page: int) -> None:
        self._page = page
        self._render_page()

    def _on_page_size_changed(self, page_size: int) -> None:
        self._page_size = page_size
        self._page = 1
        self._render_page()

    # ----- Selection ----------------------------------------------------
    def _selected_record(self) -> Optional[dict[str, Any]]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self._model.record_at(idx.row())

    def _update_buttons(self) -> None:
        self.delete_button.setEnabled(self._selected_record() is not None)

    # ----- Error banner ---------------------------------------------------
    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_banner.show()

    def _hide_error(self) -> None:
        self.error_banner.hide()

    # ----------------------------- Slots ----------------------------------
    def _on_add(self) -> None:
        dialog = PersonnelDetailDialog(parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()
            self._show_toast("Personnel saved", "Personnel record added successfully.")

    def _on_edit_selected(self) -> None:
        record = self._selected_record()
        if not record:
            return
        pid = str(record.get("id") or "")
        dialog = PersonnelDetailDialog(parent=self, personnel_id=pid)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()
            self._show_toast("Personnel saved", f"'{record.get('name', '')}' updated.")

    def _on_delete(self) -> None:
        from utils.api_client import api_client, APIError
        record = self._selected_record()
        if not record:
            return
        name = record.get("name") or record.get("id", "")
        if QtWidgets.QMessageBox.question(
            self, "Confirm Delete", f"Delete '{name}'? This cannot be undone."
        ) != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            api_client.delete(f"/api/master/personnel/{record['id']}")
        except APIError as exc:
            QtWidgets.QMessageBox.warning(self, "Delete Failed", str(exc))
            return
        self.refresh()
        self._show_toast("Personnel deleted", f"'{name}' was deleted.")

    def _on_import(self) -> None:
        from utils.api_client import api_client

        def _import_row(payload: dict[str, Any]) -> Any:
            return api_client.post("/api/master/personnel", json=payload)

        wizard = ImportWizard(fields=PERSONNEL_FIELDS, import_row=_import_row, title="Import Personnel", parent=self)
        result = wizard.exec()
        created = wizard.created_records()
        errors = wizard.error_count()
        if result == QtWidgets.QDialog.DialogCode.Accepted and (created or errors):
            self.refresh()
            if created and errors:
                self._show_toast("Import complete", f"{len(created)} personnel imported with {errors} errors.", severity="warning")
            elif created:
                self._show_toast("Import complete", f"Imported {len(created)} personnel.")
            elif errors:
                self._show_toast("Import issues", "No rows were imported. Check the error report.", severity="warning")

    def _on_export(self) -> None:
        selection_model = self.table.selectionModel()
        allow_selected = bool(selection_model and selection_model.hasSelection())
        dialog = ExportDialog(fields=PERSONNEL_FIELDS, allow_selected=allow_selected, title="Export Personnel", parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        scope = dialog.selected_scope()
        file_format = dialog.selected_format()
        fields = dialog.selected_fields()

        if scope == "selected":
            rec = self._selected_record()
            if rec is None:
                QtWidgets.QMessageBox.information(self, "No selection", "Select a row to export or choose a different scope.")
                return
            rows = [rec]
        elif scope == "filters":
            rows = list(self._filtered_records)
        else:
            rows = list(self._all_records)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path(tempfile.gettempdir()) / f"personnel-{scope}-{timestamp}.{file_format}"

        def _task() -> dict[str, Any]:
            write_export_file(path, rows, fields, _PERSONNEL_FIELD_LABELS, file_format)
            return {"path": str(path), "count": len(rows)}

        self.export_button.setEnabled(False)
        run_async(self, _task, self._on_export_done, self._on_export_failed)

    def _on_export_done(self, result: dict[str, Any]) -> None:
        self.export_button.setEnabled(True)
        message = f"{result.get('count', 0)} personnel exported. Saved to {result.get('path')}."
        self._show_toast("Export ready", message)
        QtWidgets.QMessageBox.information(self, "Export ready", message)

    def _on_export_failed(self, message: str) -> None:
        self.export_button.setEnabled(True)
        self._show_toast("Export failed", message, severity="error")
        QtWidgets.QMessageBox.critical(self, "Export failed", message)

    # ----- Toast helper ------------------------------------------------------
    def _show_toast(self, title: str, message: str, *, severity: str = "success") -> None:
        try:
            self._notifier.notify(
                Notification(
                    title=title,
                    message=message,
                    severity=severity if severity in {"info", "success", "warning", "error"} else "info",
                    source="Personnel",
                )
            )
        except Exception:
            pass
