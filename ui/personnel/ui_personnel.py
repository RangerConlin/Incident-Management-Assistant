"""
Personnel Inventory & Detail Edit Window (QtWidgets, PySide6)
REPLACES the prior QML implementation. No QML imports anywhere.

Placement: keep within your app's UI layer (NOT under backend/). For example:
  src/ui/personnel/ui_personnel.py

DB: Expects SQLite at data/master.db (adjust MASTER_DB_PATH if needed).

This file provides:
  - PersonnelInventoryWindow (main roster window with search/filters/import/export)
  - PersonnelDetailDialog (tabbed modal: Demographics, Emergency, Contact, Certifications)
  - Csv helpers for roster and certifications
  - Very small SQLite DAL with safe parameterized queries

Notes:
  - This is a scaffold: fields and validation hooks are provided with TODO tags.
  - Connect this window from your Edit menu: e.g., actionEditPersonnel.triggered -> open_inventory()
  - Columns are restricted to persistent master-personnel data (no incident-specific fields).
"""
from __future__ import annotations

import csv
import os
import sqlite3
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional

from PySide6 import QtCore, QtWidgets

# ----------------------------- Configuration ---------------------------------
MASTER_DB_PATH = os.path.join("data", "master.db")


# ----------------------------- Data Models -----------------------------------
@dataclass
class Personnel:
    id: str
    name: str
    callsign: str = ""
    role: str = ""
    rank: str = ""
    organization: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    photo_url: str = ""


@dataclass
class EmergencyInfo:
    personnel_id: str
    primary_name: str = ""
    primary_relationship: str = ""
    primary_phone: str = ""
    secondary_name: str = ""
    secondary_relationship: str = ""
    secondary_phone: str = ""
    medical: str = ""
    blood_type: str = ""
    insurance: str = ""


@dataclass
class ContactInfo:
    personnel_id: str
    address1: str = ""
    address2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    work_phone: str = ""
    secondary_phone: str = ""
    pager_id: str = ""
    notes: str = ""


@dataclass
class Certification:
    id: Optional[int]
    personnel_id: str
    code: str
    name: str
    level: int = 0  # 0=None, 1=Trainee, 2=Qualified, 3=Evaluator
    expiration: str = ""  # ISO yyyy-mm-dd
    docs: str = ""


# ----------------------------- SQLite DAL ------------------------------------
class MasterDAL:
    def __init__(self, path: str = MASTER_DB_PATH):
        self.path = path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        try:
            con.execute("PRAGMA foreign_keys = ON")
        except sqlite3.DatabaseError:
            pass
        return con

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with self._conn() as con:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS personnel (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    callsign TEXT,
                    role TEXT,
                    rank TEXT,
                    organization TEXT,
                    email TEXT,
                    phone TEXT,
                    notes TEXT,
                    photo_url TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS emergency_info (
                    personnel_id TEXT UNIQUE,
                    primary_name TEXT,
                    primary_relationship TEXT,
                    primary_phone TEXT,
                    secondary_name TEXT,
                    secondary_relationship TEXT,
                    secondary_phone TEXT,
                    medical TEXT,
                    blood_type TEXT,
                    insurance TEXT,
                    FOREIGN KEY(personnel_id) REFERENCES personnel(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS contact_info (
                    personnel_id TEXT UNIQUE,
                    address1 TEXT,
                    address2 TEXT,
                    city TEXT,
                    state TEXT,
                    zip TEXT,
                    work_phone TEXT,
                    secondary_phone TEXT,
                    pager_id TEXT,
                    notes TEXT,
                    FOREIGN KEY(personnel_id) REFERENCES personnel(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS certifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    personnel_id TEXT,
                    code TEXT,
                    name TEXT,
                    level INTEGER,
                    expiration TEXT,
                    docs TEXT,
                    FOREIGN KEY(personnel_id) REFERENCES personnel(id) ON DELETE CASCADE
                )
                """
            )
            con.commit()

    # --------- Personnel CRUD ---------
    def list_personnel(
        self,
        role_filter: str = "",
        org_filter: str = "",
        search: str = "",
    ) -> List[Personnel]:
        query = [
            "SELECT id, name, callsign, role, rank, organization, email, phone, notes, photo_url FROM personnel WHERE 1=1"
        ]
        params: list[str] = []
        if role_filter and role_filter != "All Roles":
            query.append("AND role = ?")
            params.append(role_filter)
        if org_filter and org_filter != "All Organizations":
            query.append("AND organization = ?")
            params.append(org_filter)
        if search:
            like = f"%{search}%"
            query.append(
                "AND (id LIKE ? OR name LIKE ? OR callsign LIKE ? OR phone LIKE ? OR email LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        query.append("ORDER BY name COLLATE NOCASE")
        with self._conn() as con:
            cur = con.execute(" ".join(query), params)
            rows = cur.fetchall()
        return [Personnel(*row) for row in rows]

    def list_roles(self) -> List[str]:
        with self._conn() as con:
            cur = con.execute(
                "SELECT DISTINCT role FROM personnel WHERE role IS NOT NULL AND TRIM(role) <> '' ORDER BY role COLLATE NOCASE"
            )
            return [row[0] for row in cur.fetchall() if row[0]]

    def list_organizations(self) -> List[str]:
        with self._conn() as con:
            cur = con.execute(
                "SELECT DISTINCT organization FROM personnel WHERE organization IS NOT NULL AND TRIM(organization) <> '' ORDER BY organization COLLATE NOCASE"
            )
            return [row[0] for row in cur.fetchall() if row[0]]

    def upsert_personnel(self, person: Personnel) -> None:
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO personnel (id, name, callsign, role, rank, organization, email, phone, notes, photo_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    callsign=excluded.callsign,
                    role=excluded.role,
                    rank=excluded.rank,
                    organization=excluded.organization,
                    email=excluded.email,
                    phone=excluded.phone,
                    notes=excluded.notes,
                    photo_url=excluded.photo_url
                """,
                (
                    person.id,
                    person.name,
                    person.callsign,
                    person.role,
                    person.rank,
                    person.organization,
                    person.email,
                    person.phone,
                    person.notes,
                    person.photo_url,
                ),
            )

    def delete_personnel(self, ids: Iterable[str]) -> None:
        ids = list(ids)
        if not ids:
            return
        with self._conn() as con:
            con.executemany("DELETE FROM personnel WHERE id=?", [(pid,) for pid in ids])

    def get_personnel(self, pid: str) -> Optional[Personnel]:
        with self._conn() as con:
            cur = con.execute(
                "SELECT id, name, callsign, role, rank, organization, email, phone, notes, photo_url FROM personnel WHERE id=?",
                (pid,),
            )
            row = cur.fetchone()
        return Personnel(*row) if row else None

    # --------- Emergency / Contact ---------
    def upsert_emergency(self, info: EmergencyInfo) -> None:
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO emergency_info (
                    personnel_id, primary_name, primary_relationship, primary_phone, secondary_name,
                    secondary_relationship, secondary_phone, medical, blood_type, insurance
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(personnel_id) DO UPDATE SET
                    primary_name=excluded.primary_name,
                    primary_relationship=excluded.primary_relationship,
                    primary_phone=excluded.primary_phone,
                    secondary_name=excluded.secondary_name,
                    secondary_relationship=excluded.secondary_relationship,
                    secondary_phone=excluded.secondary_phone,
                    medical=excluded.medical,
                    blood_type=excluded.blood_type,
                    insurance=excluded.insurance
                """,
                (
                    info.personnel_id,
                    info.primary_name,
                    info.primary_relationship,
                    info.primary_phone,
                    info.secondary_name,
                    info.secondary_relationship,
                    info.secondary_phone,
                    info.medical,
                    info.blood_type,
                    info.insurance,
                ),
            )

    def get_emergency(self, pid: str) -> EmergencyInfo:
        with self._conn() as con:
            cur = con.execute("SELECT * FROM emergency_info WHERE personnel_id=?", (pid,))
            row = cur.fetchone()
        if row:
            return EmergencyInfo(*row)
        return EmergencyInfo(personnel_id=pid)

    def upsert_contact(self, info: ContactInfo) -> None:
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO contact_info (
                    personnel_id, address1, address2, city, state, zip,
                    work_phone, secondary_phone, pager_id, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(personnel_id) DO UPDATE SET
                    address1=excluded.address1,
                    address2=excluded.address2,
                    city=excluded.city,
                    state=excluded.state,
                    zip=excluded.zip,
                    work_phone=excluded.work_phone,
                    secondary_phone=excluded.secondary_phone,
                    pager_id=excluded.pager_id,
                    notes=excluded.notes
                """,
                (
                    info.personnel_id,
                    info.address1,
                    info.address2,
                    info.city,
                    info.state,
                    info.zip,
                    info.work_phone,
                    info.secondary_phone,
                    info.pager_id,
                    info.notes,
                ),
            )

    def get_contact(self, pid: str) -> ContactInfo:
        with self._conn() as con:
            cur = con.execute("SELECT * FROM contact_info WHERE personnel_id=?", (pid,))
            row = cur.fetchone()
        if row:
            return ContactInfo(*row)
        return ContactInfo(personnel_id=pid)

    # --------- Certifications ---------
    def list_certs(self, pid: str) -> List[Certification]:
        with self._conn() as con:
            cur = con.execute(
                "SELECT id, personnel_id, code, name, level, expiration, docs FROM certifications WHERE personnel_id=? ORDER BY code",
                (pid,),
            )
            rows = cur.fetchall()
        return [Certification(*row) for row in rows]

    def add_cert(self, cert: Certification) -> int:
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO certifications (personnel_id, code, name, level, expiration, docs) VALUES (?,?,?,?,?,?)",
                (cert.personnel_id, cert.code, cert.name, cert.level, cert.expiration, cert.docs),
            )
            return int(cur.lastrowid)

    def update_cert(self, cert: Certification) -> None:
        if cert.id is None:
            return
        with self._conn() as con:
            con.execute(
                "UPDATE certifications SET code=?, name=?, level=?, expiration=?, docs=? WHERE id=?",
                (cert.code, cert.name, cert.level, cert.expiration, cert.docs, cert.id),
            )

    def delete_cert(self, cert_ids: Iterable[int]) -> None:
        cert_ids = [int(c) for c in cert_ids]
        if not cert_ids:
            return
        with self._conn() as con:
            con.executemany("DELETE FROM certifications WHERE id=?", [(cid,) for cid in cert_ids])


# ----------------------------- CSV Helpers -----------------------------------
class CsvUtil:
    @staticmethod
    def export_personnel(path: str, records: Iterable[Personnel]) -> None:
        fieldnames = list(asdict(Personnel(id="", name="")).keys())
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

    @staticmethod
    def import_personnel(path: str) -> List[Personnel]:
        people: list[Personnel] = []
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                people.append(Personnel(**row))
        return people

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


# ----------------------------- UI: Detail Dialog ------------------------------
class PersonnelDetailDialog(QtWidgets.QDialog):
    def __init__(self, dal: MasterDAL, parent: Optional[QtWidgets.QWidget] = None, personnel_id: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Personnel Record" if personnel_id else "Add New Personnel")
        self.setModal(True)
        self.dal = dal
        self.personnel_id = personnel_id or ""
        self._photo_path = ""

        self.tabs = QtWidgets.QTabWidget()
        self._build_tab_demographics()
        self._build_tab_emergency()
        self._build_tab_contact()
        self._build_tab_certifications()

        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addLayout(btn_row)

        if self.personnel_id:
            self._load_all()

    # ----------------- Tabs -----------------
    def _build_tab_demographics(self) -> None:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(widget)

        self.txt_id = QtWidgets.QLineEdit()
        self.txt_id.setReadOnly(bool(self.personnel_id))
        self.txt_name = QtWidgets.QLineEdit()
        self.txt_callsign = QtWidgets.QLineEdit()
        self.cbo_role = QtWidgets.QComboBox()
        self.cbo_role.setEditable(True)
        self.cbo_rank = QtWidgets.QComboBox()
        self.cbo_rank.setEditable(True)
        self.txt_org = QtWidgets.QLineEdit()
        self.txt_email = QtWidgets.QLineEdit()
        self.txt_phone = QtWidgets.QLineEdit()
        self.txt_notes = QtWidgets.QTextEdit()
        self.btn_photo = QtWidgets.QPushButton("Upload Photo…")
        self.btn_photo.clicked.connect(self._choose_photo)

        form.addRow("ID:", self.txt_id)
        form.addRow("Name:", self.txt_name)
        form.addRow("Callsign:", self.txt_callsign)
        form.addRow("Role/Title:", self.cbo_role)
        form.addRow("Rank:", self.cbo_rank)
        form.addRow("Organization:", self.txt_org)
        form.addRow("Email:", self.txt_email)
        form.addRow("Phone:", self.txt_phone)
        form.addRow("Notes:", self.txt_notes)
        form.addRow("Photo:", self.btn_photo)

        self.tabs.addTab(widget, "Demographics & Contact")

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
        person = self.dal.get_personnel(self.personnel_id)
        if person:
            self.txt_id.setText(person.id)
            self.txt_name.setText(person.name)
            self.txt_callsign.setText(person.callsign)
            self.cbo_role.setCurrentText(person.role)
            self.cbo_rank.setCurrentText(person.rank)
            self.txt_org.setText(person.organization)
            self.txt_email.setText(person.email)
            self.txt_phone.setText(person.phone)
            self.txt_notes.setPlainText(person.notes)
            self._photo_path = person.photo_url
        else:
            self._photo_path = ""

        emergency = self.dal.get_emergency(self.personnel_id)
        self.em_primary_name.setText(emergency.primary_name)
        self.em_primary_rel.setText(emergency.primary_relationship)
        self.em_primary_phone.setText(emergency.primary_phone)
        self.em_secondary_name.setText(emergency.secondary_name)
        self.em_secondary_rel.setText(emergency.secondary_relationship)
        self.em_secondary_phone.setText(emergency.secondary_phone)
        self.em_medical.setPlainText(emergency.medical)
        self.em_blood.setCurrentText(emergency.blood_type)
        self.em_ins.setPlainText(emergency.insurance)

        contact = self.dal.get_contact(self.personnel_id)
        self.addr1.setText(contact.address1)
        self.addr2.setText(contact.address2)
        self.city.setText(contact.city)
        self.state.setCurrentText(contact.state)
        self.zip.setText(contact.zip)
        self.work_phone.setText(contact.work_phone)
        self.secondary_phone.setText(contact.secondary_phone)
        self.pager.setText(contact.pager_id)
        self.c_notes.setPlainText(contact.notes)

        self._refresh_certs()

    def _collect_personnel(self) -> Personnel:
        pid = self.txt_id.text().strip() or self.personnel_id
        return Personnel(
            id=pid,
            name=self.txt_name.text().strip(),
            callsign=self.txt_callsign.text().strip(),
            role=self.cbo_role.currentText().strip(),
            rank=self.cbo_rank.currentText().strip(),
            organization=self.txt_org.text().strip(),
            email=self.txt_email.text().strip(),
            phone=self.txt_phone.text().strip(),
            notes=self.txt_notes.toPlainText().strip(),
            photo_url=self._photo_path,
        )

    def _collect_emergency(self) -> EmergencyInfo:
        pid = self.txt_id.text().strip()
        return EmergencyInfo(
            personnel_id=pid,
            primary_name=self.em_primary_name.text().strip(),
            primary_relationship=self.em_primary_rel.text().strip(),
            primary_phone=self.em_primary_phone.text().strip(),
            secondary_name=self.em_secondary_name.text().strip(),
            secondary_relationship=self.em_secondary_rel.text().strip(),
            secondary_phone=self.em_secondary_phone.text().strip(),
            medical=self.em_medical.toPlainText().strip(),
            blood_type=self.em_blood.currentText().strip(),
            insurance=self.em_ins.toPlainText().strip(),
        )

    def _collect_contact(self) -> ContactInfo:
        pid = self.txt_id.text().strip()
        return ContactInfo(
            personnel_id=pid,
            address1=self.addr1.text().strip(),
            address2=self.addr2.text().strip(),
            city=self.city.text().strip(),
            state=self.state.currentText().strip(),
            zip=self.zip.text().strip(),
            work_phone=self.work_phone.text().strip(),
            secondary_phone=self.secondary_phone.text().strip(),
            pager_id=self.pager.text().strip(),
            notes=self.c_notes.toPlainText().strip(),
        )

    def _refresh_certs(self) -> None:
        self.tbl_certs.setRowCount(0)
        pid = self.txt_id.text().strip() or self.personnel_id
        if not pid:
            return
        certs = self.dal.list_certs(pid)
        for cert in certs:
            row = self.tbl_certs.rowCount()
            self.tbl_certs.insertRow(row)
            self.tbl_certs.setItem(row, 0, QtWidgets.QTableWidgetItem(cert.code))
            self.tbl_certs.setItem(row, 1, QtWidgets.QTableWidgetItem(cert.name))
            self.tbl_certs.setItem(row, 2, QtWidgets.QTableWidgetItem(str(cert.level)))
            self.tbl_certs.setItem(row, 3, QtWidgets.QTableWidgetItem(cert.expiration))
            self.tbl_certs.setItem(row, 4, QtWidgets.QTableWidgetItem(cert.docs))
            header_item = QtWidgets.QTableWidgetItem(str(cert.id)) if cert.id is not None else QtWidgets.QTableWidgetItem("")
            self.tbl_certs.setVerticalHeaderItem(row, header_item)

    # ----------------- Actions -----------------
    def _on_save(self) -> None:
        # TODO: add field validation (e.g., required Name/ID, email format, etc.)
        person = self._collect_personnel()
        if not person.id or not person.name:
            QtWidgets.QMessageBox.warning(self, "Missing Required", "ID and Name are required.")
            return
        self.dal.upsert_personnel(person)
        self.dal.upsert_emergency(self._collect_emergency())
        self.dal.upsert_contact(self._collect_contact())
        self.personnel_id = person.id
        self.accept()

    def _choose_photo(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose Photo", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self._photo_path = path
            self.btn_photo.setText(os.path.basename(path))

    def _on_add_cert(self) -> None:
        pid = self.txt_id.text().strip() or self.personnel_id
        if not pid:
            QtWidgets.QMessageBox.information(
                self,
                "Set ID First",
                "Please set/save Personnel ID before adding certifications.",
            )
            return
        dialog = CertEditDialog(parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            cert = Certification(
                id=None,
                personnel_id=pid,
                code=dialog.code(),
                name=dialog.cname(),
                level=dialog.level(),
                expiration=dialog.expiration(),
                docs=dialog.docs(),
            )
            self.dal.add_cert(cert)
            self._refresh_certs()

    def _on_edit_cert(self) -> None:
        row = self.tbl_certs.currentRow()
        if row < 0:
            return
        cert_id_item = self.tbl_certs.verticalHeaderItem(row)
        cert_id = int(cert_id_item.text()) if cert_id_item and cert_id_item.text().isdigit() else None
        code_item = self.tbl_certs.item(row, 0)
        name_item = self.tbl_certs.item(row, 1)
        level_item = self.tbl_certs.item(row, 2)
        exp_item = self.tbl_certs.item(row, 3)
        docs_item = self.tbl_certs.item(row, 4)
        dialog = CertEditDialog(
            parent=self,
            code=code_item.text() if code_item else "",
            name=name_item.text() if name_item else "",
            level=int(level_item.text()) if level_item and level_item.text().isdigit() else 0,
            expiration=exp_item.text() if exp_item else "",
            docs=docs_item.text() if docs_item else "",
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted and cert_id is not None:
            self.dal.update_cert(
                Certification(
                    id=cert_id,
                    personnel_id=self.txt_id.text().strip() or self.personnel_id,
                    code=dialog.code(),
                    name=dialog.cname(),
                    level=dialog.level(),
                    expiration=dialog.expiration(),
                    docs=dialog.docs(),
                )
            )
            self._refresh_certs()

    def _on_del_cert(self) -> None:
        row = self.tbl_certs.currentRow()
        if row < 0:
            return
        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm",
                "Remove selected certification?",
            )
            != QtWidgets.QMessageBox.Yes
        ):
            return
        cert_id_item = self.tbl_certs.verticalHeaderItem(row)
        if cert_id_item and cert_id_item.text().isdigit():
            self.dal.delete_cert([int(cert_id_item.text())])
            self._refresh_certs()

    def _on_import_certs(self) -> None:
        pid = self.txt_id.text().strip() or self.personnel_id
        if not pid:
            QtWidgets.QMessageBox.information(
                self,
                "Set ID First",
                "Please set/save Personnel ID before importing certifications.",
            )
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Certifications",
            "",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            certs = CsvUtil.import_certifications(path)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Import Failed", str(exc))
            return
        imported = 0
        for cert in certs:
            cert.personnel_id = pid or cert.personnel_id
            cert.id = None
            if cert.code or cert.name:
                self.dal.add_cert(cert)
                imported += 1
        QtWidgets.QMessageBox.information(
            self,
            "Import Complete",
            f"Imported {imported} certification(s).",
        )
        self._refresh_certs()

    def _on_export_certs(self) -> None:
        pid = self.txt_id.text().strip() or self.personnel_id
        if not pid:
            QtWidgets.QMessageBox.information(
                self,
                "Save Record First",
                "Please save this personnel record before exporting certifications.",
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Certifications",
            "certifications.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        certs = self.dal.list_certs(pid)
        try:
            CsvUtil.export_certifications(path, certs)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {len(certs)} certification(s).",
        )


# ----------------------------- UI: Cert Edit Dialog ---------------------------
class CertEditDialog(QtWidgets.QDialog):
    LEVEL_MAP = [
        (0, "None"),
        (1, "Trainee"),
        (2, "Qualified"),
        (3, "Evaluator"),
    ]

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        code: str = "",
        name: str = "",
        level: int = 0,
        expiration: str = "",
        docs: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Certification")
        form = QtWidgets.QFormLayout(self)

        self._code = QtWidgets.QLineEdit(code)
        self._name = QtWidgets.QLineEdit(name)
        self._level = QtWidgets.QComboBox()
        for value, label in self.LEVEL_MAP:
            self._level.addItem(label, value)
        index = next((i for i, (value, _) in enumerate(self.LEVEL_MAP) if value == level), 0)
        self._level.setCurrentIndex(index)
        self._expiration = QtWidgets.QLineEdit(expiration)
        self._docs = QtWidgets.QLineEdit(docs)

        form.addRow("Code:", self._code)
        form.addRow("Name:", self._name)
        form.addRow("Level:", self._level)
        form.addRow("Expiration (YYYY-MM-DD):", self._expiration)
        form.addRow("Documents/Notes:", self._docs)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        form.addRow(btn_box)

    def code(self) -> str:
        return self._code.text().strip()

    def cname(self) -> str:
        return self._name.text().strip()

    def level(self) -> int:
        return int(self._level.currentData())

    def expiration(self) -> str:
        return self._expiration.text().strip()

    def docs(self) -> str:
        return self._docs.text().strip()


# ----------------------------- UI: Inventory Window --------------------------
class PersonnelInventoryWindow(QtWidgets.QDialog):
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        dal: Optional[MasterDAL] = None,
    ) -> None:
        super().__init__(parent)
        self.dal = dal or MasterDAL()
        self.setWindowTitle("Personnel Inventory")
        self.resize(1100, 650)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by name, ID, callsign, phone, or email…")
        self.cbo_role = QtWidgets.QComboBox()
        self.cbo_org = QtWidgets.QComboBox()
        self.cbo_role.addItem("All Roles")
        self.cbo_org.addItem("All Organizations")

        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(QtWidgets.QLabel("Search:"))
        filter_layout.addWidget(self.search, stretch=2)
        filter_layout.addWidget(QtWidgets.QLabel("Role:"))
        filter_layout.addWidget(self.cbo_role)
        filter_layout.addWidget(QtWidgets.QLabel("Organization:"))
        filter_layout.addWidget(self.cbo_org)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Name",
                "Callsign",
                "Role",
                "Rank",
                "Organization",
                "Email",
                "Phone",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_edit)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_import = QtWidgets.QPushButton("Import CSV")
        self.btn_export = QtWidgets.QPushButton("Export CSV")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_refresh)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(filter_layout)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

        self.search.textChanged.connect(self._refresh_table)
        self.cbo_role.currentIndexChanged.connect(self._refresh_table)
        self.cbo_org.currentIndexChanged.connect(self._refresh_table)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_import.clicked.connect(self._on_import)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_refresh.clicked.connect(self.refresh)

        self.refresh()

    # ----------------------------- Helpers ---------------------------------
    def refresh(self) -> None:
        self._load_filters()
        self._refresh_table()

    def _load_filters(self) -> None:
        current_role = self.cbo_role.currentText() if self.cbo_role.count() else "All Roles"
        current_org = self.cbo_org.currentText() if self.cbo_org.count() else "All Organizations"

        roles = ["All Roles"] + self.dal.list_roles()
        orgs = ["All Organizations"] + self.dal.list_organizations()

        self.cbo_role.blockSignals(True)
        self.cbo_org.blockSignals(True)
        try:
            self.cbo_role.clear()
            self.cbo_role.addItems(roles)
            self.cbo_org.clear()
            self.cbo_org.addItems(orgs)
        finally:
            self.cbo_role.blockSignals(False)
            self.cbo_org.blockSignals(False)

        if current_role in roles:
            self.cbo_role.setCurrentText(current_role)
        else:
            self.cbo_role.setCurrentIndex(0)
        if current_org in orgs:
            self.cbo_org.setCurrentText(current_org)
        else:
            self.cbo_org.setCurrentIndex(0)

    def _current_role_filter(self) -> str:
        return self.cbo_role.currentText()

    def _current_org_filter(self) -> str:
        return self.cbo_org.currentText()

    def _refresh_table(self) -> None:
        role = self._current_role_filter()
        org = self._current_org_filter()
        search_text = self.search.text().strip()
        records = self.dal.list_personnel(role, org, search_text)

        self.table.setRowCount(0)
        for person in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            columns = [
                person.id,
                person.name,
                person.callsign,
                person.role,
                person.rank,
                person.organization,
                person.email,
                person.phone,
            ]
            for col, value in enumerate(columns):
                item = QtWidgets.QTableWidgetItem(value or "")
                if col == 0:
                    item.setData(QtCore.Qt.UserRole, person)
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()

    def _selected_rows(self) -> List[int]:
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def _selected_ids(self) -> List[str]:
        ids: list[str] = []
        for row in self._selected_rows():
            item = self.table.item(row, 0)
            if item:
                ids.append(item.text())
        return ids

    # ----------------------------- Slots ----------------------------------
    def _on_add(self) -> None:
        dialog = PersonnelDetailDialog(self.dal, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.refresh()

    def _on_edit(self) -> None:
        selected = self._selected_rows()
        if not selected:
            # Allow double-click editing via event argument but keep behaviour consistent
            index = self.table.currentRow()
            if index >= 0:
                selected = [index]
            else:
                return
        row = selected[0]
        item = self.table.item(row, 0)
        if not item:
            return
        pid = item.text()
        dialog = PersonnelDetailDialog(self.dal, parent=self, personnel_id=pid)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.refresh()
        else:
            # Always refresh after edit to reflect potential external changes
            self.refresh()

    def _on_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "No Selection", "Select at least one record to delete.")
            return
        if (
            QtWidgets.QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete {len(ids)} personnel record(s)?",
            )
            != QtWidgets.QMessageBox.Yes
        ):
            return
        self.dal.delete_personnel(ids)
        self.refresh()

    def _on_import(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Personnel",
            "",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            records = CsvUtil.import_personnel(path)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Import Failed", str(exc))
            return
        for person in records:
            if person.id and person.name:
                self.dal.upsert_personnel(person)
        QtWidgets.QMessageBox.information(
            self,
            "Import Complete",
            f"Imported {len(records)} personnel record(s).",
        )
        self.refresh()

    def _on_export(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Personnel",
            "personnel.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        role = self._current_role_filter()
        org = self._current_org_filter()
        search_text = self.search.text().strip()
        records = self.dal.list_personnel(role, org, search_text)
        try:
            CsvUtil.export_personnel(path, records)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self,
            "Export Complete",
            f"Exported {len(records)} personnel record(s).",
        )
