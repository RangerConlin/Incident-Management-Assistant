"""Personnel Inventory & Detail Edit Window (QtWidgets, PySide6).

Placement: keep within the app UI layer. Do not place this module under backend/.

Data: fully MongoDB-backed via the SARApp API (utils.api_client); no direct
SQLite access remains in this module.

This file provides:
  - PersonnelInventoryWindow: main roster window with search, import, export
  - PersonnelDetailDialog: tabbed modal with demographics, emergency, contact,
    and certifications

Certification storage rule:
  - Personnel records store only cert_type_id and level.
  - Display fields and medic-checkoff status come from the certification catalog.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from notifications.models import Notification
from notifications.services import get_notifier
from utils.edit_window_kit import (
    ExportDialog,
    FieldSpec,
    ImportWizard,
    run_async,
    write_export_file,
)
from utils.org_combo import make_org_combo


_LEVEL_LABELS = ["None", "Trainee", "Qualified", "Evaluator"]
_LEVEL_BY_LABEL = {label: i for i, label in enumerate(_LEVEL_LABELS)}
STATE_CODES = [
    "", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]


def _clamp_level(value: Any) -> int:
    try:
        return max(0, min(3, int(value)))
    except (TypeError, ValueError):
        return 0


# ----------------------------- UI: Personnel Table Model ----------------------
class _PersonnelTableModel(QtCore.QAbstractTableModel):
    HEADERS = ["ID", "Name", "Callsign", "Rank", "Organization", "Email", "Phone"]
    KEYS = ["person_id", "name", "callsign", "rank", "home_unit", "email", "phone"]

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


# ----------------------------- Certification Dialogs --------------------------
class _CertPickerDialog(QtWidgets.QDialog):
    """Search the cert catalog, pick one certification, and set its level."""

    def __init__(self, catalog: list[dict[str, Any]], parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Certification")
        self.resize(760, 520)
        self.setModal(True)
        self._all_certs = catalog
        self._result: Optional[dict[str, Any]] = None

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search by code, name, category, organization, or tag...")

        self.catalog_table = QtWidgets.QTableWidget(0, 4)
        self.catalog_table.setHorizontalHeaderLabels(["Code", "Name", "Category", "Medical"])
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.catalog_table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.catalog_table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.catalog_table.doubleClicked.connect(self._on_accept)

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(_LEVEL_LABELS)
        self.level_combo.setCurrentIndex(2)

        detail_form = QtWidgets.QFormLayout()
        detail_form.addRow("Level:", self.level_combo)

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
        self._populate(self._all_certs)

    def _filter(self, text: str) -> None:
        t = text.lower().strip()
        self._populate([
            c for c in self._all_certs
            if not t
            or t in str(c.get("code") or "").lower()
            or t in str(c.get("name") or "").lower()
            or t in str(c.get("category") or "").lower()
            or t in str(c.get("issuing_org") or "").lower()
            or t in " ".join(str(tag) for tag in c.get("tags") or []).lower()
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
            self.catalog_table.setItem(row, 3, QtWidgets.QTableWidgetItem("Yes" if cert.get("is_medical") else ""))

    def _on_accept(self) -> None:
        row = self.catalog_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(self, "Select Certification", "Pick a certification from the list.")
            return
        item = self.catalog_table.item(row, 0)
        cert = item.data(QtCore.Qt.UserRole) if item else None
        cert_type_id = cert.get("cert_type_id") or cert.get("int_id") or cert.get("id") if cert else None
        if cert_type_id is None:
            QtWidgets.QMessageBox.warning(self, "Invalid Certification", "Selected certification is missing a catalog ID.")
            return
        self._result = {
            "cert_type_id": int(cert_type_id),
            "level": _LEVEL_BY_LABEL.get(self.level_combo.currentText(), 0),
        }
        self.accept()

    def result_cert(self) -> Optional[dict[str, Any]]:
        return self._result


class _CertLevelDialog(QtWidgets.QDialog):
    """Edit only the level for an existing personnel certification."""

    def __init__(self, cert: dict[str, Any], catalog: dict[int, dict[str, Any]], parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Certification Level")
        self.setModal(True)
        self._cert = dict(cert)
        cert_type_id = int(cert.get("cert_type_id") or 0)
        catalog_row = catalog.get(cert_type_id, {})

        name = catalog_row.get("name") or cert.get("name") or "Certification"
        code = catalog_row.get("code") or cert.get("code") or str(cert_type_id)
        name_label = QtWidgets.QLabel(f"<b>{code} - {name}</b>")

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(_LEVEL_LABELS)
        self.level_combo.setCurrentIndex(_clamp_level(cert.get("level")))

        form = QtWidgets.QFormLayout()
        form.addRow(name_label)
        form.addRow("Level:", self.level_combo)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def updated_cert(self) -> dict[str, int]:
        return {
            "cert_type_id": int(self._cert.get("cert_type_id")),
            "level": self.level_combo.currentIndex(),
        }


# ----------------------------- UI: Detail Dialog ------------------------------
class PersonnelDetailDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, person_record: Optional[int] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Personnel Record" if person_record else "Add New Personnel")
        self.resize(760, 640)
        self.setModal(True)
        self.person_record: Optional[int] = person_record
        self._photo_path = ""
        self._local_certs: list[dict[str, int]] = []
        self._catalog: list[dict[str, Any]] = []
        self._catalog_by_id: dict[int, dict[str, Any]] = {}
        self._catalog_by_code: dict[str, dict[str, Any]] = {}

        self._load_catalog()
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

        if self.person_record:
            self._load_all()

    # ----------------- Catalog helpers -----------------
    def _load_catalog(self) -> None:
        from modules.personnel.api.cert_api import list_catalog
        self._catalog = list_catalog()
        self._catalog_by_id.clear()
        self._catalog_by_code.clear()
        for cert in self._catalog:
            cert_type_id = cert.get("cert_type_id") or cert.get("int_id") or cert.get("id")
            try:
                cert_type_id = int(cert_type_id)
            except (TypeError, ValueError):
                continue
            self._catalog_by_id[cert_type_id] = cert
            code = str(cert.get("code") or "").strip().upper()
            if code:
                self._catalog_by_code[code] = cert

    def _normalize_cert_rows(self, certs: list[dict[str, Any]]) -> list[dict[str, int]]:
        rows: dict[int, dict[str, int]] = {}
        for cert in certs or []:
            if not isinstance(cert, dict):
                continue
            cert_type_id = cert.get("cert_type_id") or cert.get("int_id") or cert.get("id")
            if cert_type_id is None and cert.get("code"):
                catalog_row = self._catalog_by_code.get(str(cert.get("code")).strip().upper())
                cert_type_id = catalog_row.get("id") or catalog_row.get("int_id") if catalog_row else None
            try:
                cert_type_id = int(cert_type_id)
            except (TypeError, ValueError):
                continue
            level = _clamp_level(cert.get("level"))
            rows[cert_type_id] = {
                "cert_type_id": cert_type_id,
                "level": max(rows.get(cert_type_id, {}).get("level", 0), level),
            }
        return sorted(rows.values(), key=lambda c: c["cert_type_id"])

    def _cert_display(self, cert: dict[str, Any]) -> dict[str, Any]:
        cert_type_id = int(cert.get("cert_type_id") or 0)
        catalog_row = self._catalog_by_id.get(cert_type_id, {})
        return {
            "code": catalog_row.get("code", str(cert_type_id)),
            "name": catalog_row.get("name", ""),
            "category": catalog_row.get("category", ""),
            "is_medical": bool(catalog_row.get("is_medical")),
            "level": _clamp_level(cert.get("level")),
        }

    def _minimal_certs_for_save(self) -> list[dict[str, int]]:
        return [
            {"cert_type_id": int(cert["cert_type_id"]), "level": _clamp_level(cert.get("level"))}
            for cert in self._normalize_cert_rows(self._local_certs)
        ]

    # ----------------- Layout -----------------
    def _build_basic_panel(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Basic Information")
        grid = QtWidgets.QGridLayout(box)

        self.txt_person_id = QtWidgets.QLineEdit()
        self.txt_person_id.setPlaceholderText("Personnel ID / Badge #")
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
        self.btn_photo = QtWidgets.QPushButton("Photo...")
        self.btn_photo.setFixedWidth(80)
        self.btn_photo.clicked.connect(self._choose_photo)

        grid.addWidget(QtWidgets.QLabel("ID:"), 0, 0)
        grid.addWidget(self.txt_person_id, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Name:"), 0, 2)
        grid.addWidget(self.txt_name, 0, 3)
        grid.addWidget(QtWidgets.QLabel("Callsign:"), 0, 4)
        grid.addWidget(self.txt_callsign, 0, 5)

        grid.addWidget(QtWidgets.QLabel("Role/Title:"), 1, 0)
        grid.addWidget(self.txt_role, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Rank:"), 1, 2)
        grid.addWidget(self.txt_rank, 1, 3)
        grid.addWidget(QtWidgets.QLabel("Organization:"), 1, 4)
        grid.addWidget(self.txt_org, 1, 5)

        grid.addWidget(QtWidgets.QLabel("Email:"), 2, 0)
        grid.addWidget(self.txt_email, 2, 1)
        grid.addWidget(QtWidgets.QLabel("Phone:"), 2, 2)
        grid.addWidget(self.txt_phone, 2, 3)
        grid.addWidget(self.chk_medic, 2, 4)

        grid.addWidget(QtWidgets.QLabel("Notes:"), 3, 0)
        notes_row = QtWidgets.QHBoxLayout()
        notes_row.addWidget(self.txt_notes)
        notes_row.addWidget(self.btn_photo)
        grid.addLayout(notes_row, 3, 1, 1, 5)

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
        self.state.addItems(STATE_CODES)
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

        self.tbl_certs = QtWidgets.QTableWidget(0, 4)
        self.tbl_certs.setHorizontalHeaderLabels(["Code", "Name", "Level", "Medical"])
        self.tbl_certs.horizontalHeader().setStretchLastSection(True)
        self.tbl_certs.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.tbl_certs.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.tbl_certs.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)

        btns = QtWidgets.QHBoxLayout()
        self.btn_add_cert = QtWidgets.QPushButton("Add Certification")
        self.btn_edit_cert = QtWidgets.QPushButton("Edit Level")
        self.btn_del_cert = QtWidgets.QPushButton("Remove")

        btns.addWidget(self.btn_add_cert)
        btns.addWidget(self.btn_edit_cert)
        btns.addWidget(self.btn_del_cert)
        btns.addStretch(1)

        layout.addWidget(self.tbl_certs)
        layout.addLayout(btns)

        self.btn_add_cert.clicked.connect(self._on_add_cert)
        self.btn_edit_cert.clicked.connect(self._on_edit_cert)
        self.btn_del_cert.clicked.connect(self._on_del_cert)

        self.tabs.addTab(widget, "Certifications")

    # ----------------- Load/Save -----------------
    def _load_all(self) -> None:
        from utils.api_client import api_client
        try:
            doc = api_client.get(f"/api/master/personnel/{self.person_record}")
        except Exception:
            doc = None
        if not doc:
            self._photo_path = ""
            return

        self.txt_person_id.setText(doc.get("person_id") or "")
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

        self._local_certs = self._normalize_cert_rows(list(doc.get("certifications") or []))
        self._refresh_certs()

    def _refresh_certs(self) -> None:
        self.tbl_certs.setRowCount(0)
        self._local_certs = self._normalize_cert_rows(self._local_certs)
        for i, cert in enumerate(self._local_certs):
            display = self._cert_display(cert)
            row = self.tbl_certs.rowCount()
            self.tbl_certs.insertRow(row)
            self.tbl_certs.setItem(row, 0, QtWidgets.QTableWidgetItem(str(display["code"])))
            self.tbl_certs.setItem(row, 1, QtWidgets.QTableWidgetItem(str(display["name"])))
            self.tbl_certs.setItem(row, 2, QtWidgets.QTableWidgetItem(_LEVEL_LABELS[display["level"]]))
            self.tbl_certs.setItem(row, 3, QtWidgets.QTableWidgetItem("Yes" if display["is_medical"] else ""))
            self.tbl_certs.setVerticalHeaderItem(row, QtWidgets.QTableWidgetItem(str(i)))

    # ----------------- Actions -----------------
    def _on_save(self) -> None:
        from utils.api_client import APIError, api_client
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
            "person_id": self.txt_person_id.text().strip(),
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
            "certifications": self._minimal_certs_for_save(),
        }
        try:
            if self.person_record:
                from utils import incident_context
                active_incident_id = incident_context.get_active_incident_id()
                params = {"active_incident_id": active_incident_id} if active_incident_id else None
                result = api_client.put(f"/api/master/personnel/{self.person_record}", json=doc, params=params)
                self.person_record = int(result.get("person_record") or self.person_record)
            else:
                result = api_client.post("/api/master/personnel", json=doc)
                self.person_record = int(result.get("person_record") or 0) or None
        except APIError as exc:
            QtWidgets.QMessageBox.warning(self, "Save Failed", str(exc))
            return
        self.accept()

    def _choose_photo(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose Photo", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self._photo_path = path
            self.btn_photo.setText(os.path.basename(path))

    def _on_add_cert(self) -> None:
        dialog = _CertPickerDialog(self._catalog, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            cert = dialog.result_cert()
            if cert:
                self._local_certs = [c for c in self._local_certs if c["cert_type_id"] != cert["cert_type_id"]]
                self._local_certs.append(cert)
                self._refresh_certs()

    def _on_edit_cert(self) -> None:
        row = self.tbl_certs.currentRow()
        if row < 0 or row >= len(self._local_certs):
            return
        dialog = _CertLevelDialog(self._local_certs[row], self._catalog_by_id, parent=self)
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
    """Personnel inventory window with card shell, filters, import, and export."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.Window)
        self.setWindowTitle("Personnel Inventory")
        self.resize(1040, 660)
        self._notifier = get_notifier()
        self._all_records: list[dict[str, Any]] = []
        self._filtered_records: list[dict[str, Any]] = []
        self._search_text = ""

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
        self.search_edit.setPlaceholderText("Search by name, callsign, ID, email, phone...")
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

    # ----- Data loading ----------------------------------------------------
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
        self._render_page()

    def _render_page(self) -> None:
        self._model.set_records(self._filtered_records)
        total = len(self._filtered_records)

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

    # ----- Selection ------------------------------------------------------
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
        prec = record.get("person_record")
        if not prec:
            return
        dialog = PersonnelDetailDialog(parent=self, person_record=int(prec))
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()
            self._show_toast("Personnel saved", f"'{record.get('name', '')}' updated.")

    def _on_delete(self) -> None:
        from utils.api_client import APIError, api_client
        record = self._selected_record()
        if not record:
            return
        prec = record.get("person_record")
        name = record.get("name") or record.get("person_id", "")
        if not prec:
            return
        if QtWidgets.QMessageBox.question(
            self, "Confirm Delete", f"Delete '{name}'? This cannot be undone."
        ) != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            api_client.delete(f"/api/master/personnel/{prec}")
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

    # ----- Toast helper ----------------------------------------------------
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
