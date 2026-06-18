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
from typing import Any, Dict, Iterable, List, Optional

from PySide6 import QtCore, QtWidgets

from modules.admin.resource_types.data import ApiResourceAssignmentRepository, ApiResourceTypeRepository
from modules.admin.resource_types.widgets import ResourceTypeSearchBox

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
        self.resource_assignments = ApiResourceAssignmentRepository()
        self._id_is_integer = False
        self._has_unit_column = False
        self._has_contact_column = False
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
            metadata = self._prepare_personnel_table(cur)
            self._create_support_tables(cur)
            con.commit()
        self._id_is_integer = metadata["id_is_integer"]
        self._has_unit_column = metadata["has_unit"]
        self._has_contact_column = metadata["has_contact"]

    # --- schema helpers -------------------------------------------------
    def _get_table_info(self, cur: sqlite3.Cursor, table: str) -> Dict[str, tuple]:
        try:
            cur.execute(f"PRAGMA table_info({table})")
        except sqlite3.DatabaseError:
            return {}
        rows = cur.fetchall()
        return {row[1]: row for row in rows}

    def _prepare_personnel_table(self, cur: sqlite3.Cursor) -> Dict[str, bool]:
        info = self._get_table_info(cur, "personnel")
        if not info:
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
        else:
            if "organization" not in info:
                cur.execute("ALTER TABLE personnel ADD COLUMN organization TEXT")
                if "unit" in info:
                    cur.execute(
                        "UPDATE personnel SET organization = COALESCE(unit, '') WHERE organization IS NULL OR TRIM(organization) = ''"
                    )
            if "notes" not in info:
                cur.execute("ALTER TABLE personnel ADD COLUMN notes TEXT")
                if "contact" in info:
                    cur.execute(
                        "UPDATE personnel SET notes = COALESCE(contact, '') WHERE notes IS NULL OR TRIM(notes) = ''"
                    )
            if "photo_url" not in info:
                cur.execute("ALTER TABLE personnel ADD COLUMN photo_url TEXT")
            # refresh info after possible ALTER TABLE commands
        info = self._get_table_info(cur, "personnel")
        id_info = info.get("id")
        id_is_integer = bool(id_info and isinstance(id_info[2], str) and "INT" in id_info[2].upper())
        has_unit = "unit" in info
        has_contact = "contact" in info
        return {"id_is_integer": id_is_integer, "has_unit": has_unit, "has_contact": has_contact}

    def _create_support_tables(self, cur: sqlite3.Cursor) -> None:
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

    # --- helpers --------------------------------------------------------
    def _prepare_personnel_id(self, personnel_id: str) -> str | int:
        if self._id_is_integer:
            try:
                return int(str(personnel_id).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError("Personnel IDs must be numeric for this database.") from exc
        return str(personnel_id)

    def normalize_personnel_id(self, personnel_id: str) -> str:
        return str(self._prepare_personnel_id(personnel_id))

    # --------- Personnel CRUD ---------
    def list_personnel(
        self,
        role_filter: str = "",
        org_filter: str = "",
        search: str = "",
    ) -> List[Personnel]:
        id_expr = "CAST(id AS TEXT)" if self._id_is_integer else "id"
        query = [
            f"SELECT {id_expr} AS id, name, callsign, role, rank, organization, email, phone, notes, photo_url FROM personnel WHERE 1=1"
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
                f"AND ({id_expr} LIKE ? OR name LIKE ? OR callsign LIKE ? OR phone LIKE ? OR email LIKE ?)"
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

    def upsert_personnel(self, person: Personnel) -> str:
        db_id = self._prepare_personnel_id(person.id)
        columns = [
            ("id", db_id),
            ("name", person.name),
            ("callsign", person.callsign),
            ("role", person.role),
            ("rank", person.rank),
            ("organization", person.organization),
            ("email", person.email),
            ("phone", person.phone),
            ("notes", person.notes),
            ("photo_url", person.photo_url),
        ]
        if self._has_unit_column:
            columns.append(("unit", person.organization))
        if self._has_contact_column:
            columns.append(("contact", person.notes))

        col_names = ", ".join(name for name, _ in columns)
        placeholders = ", ".join(["?"] * len(columns))
        assignments = ", ".join(f"{name}=excluded.{name}" for name, _ in columns if name != "id")
        values = [value for _, value in columns]

        sql = (
            f"INSERT INTO personnel ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}"
        )
        with self._conn() as con:
            con.execute(sql, values)
        return str(db_id)

    def delete_personnel(self, ids: Iterable[str]) -> None:
        ids = list(ids)
        if not ids:
            return
        db_ids = [self._prepare_personnel_id(pid) for pid in ids]
        try:
            with self._conn() as con:
                # Proactively clear legacy references that do not declare ON DELETE CASCADE
                # 1) Legacy join table
                try:
                    con.executemany(
                        "DELETE FROM personnel_certifications WHERE person_id=?",
                        [(pid,) for pid in db_ids],
                    )
                except sqlite3.DatabaseError:
                    # Table may not exist in some profiles; ignore if missing
                    pass

                # 2) Users association — keep user but drop link to personnel
                try:
                    con.executemany(
                        "UPDATE users SET associated_personnel_id = NULL WHERE associated_personnel_id = ?",
                        [(pid,) for pid in db_ids],
                    )
                except sqlite3.DatabaseError:
                    pass

                # Now delete from personnel (support tables use ON DELETE CASCADE)
                con.executemany("DELETE FROM personnel WHERE id=?", [(pid,) for pid in db_ids])
        except sqlite3.IntegrityError as exc:
            # Surface a friendly message to the UI so the user understands why
            raise ValueError(
                "Delete blocked: one or more selected records are still referenced by other tables. "
                "Unlink related records (assignments, users, certifications) and try again."
            ) from exc

    def get_personnel(self, pid: str) -> Optional[Personnel]:
        id_expr = "CAST(id AS TEXT)" if self._id_is_integer else "id"
        with self._conn() as con:
            cur = con.execute(
                f"SELECT {id_expr} AS id, name, callsign, role, rank, organization, email, phone, notes, photo_url FROM personnel WHERE id=?",
                (self._prepare_personnel_id(pid),),
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
        self.txt_id.setPlaceholderText("Auto-assigned if blank")
        self.txt_name = QtWidgets.QLineEdit()
        self.txt_callsign = QtWidgets.QLineEdit()
        self.txt_role = QtWidgets.QLineEdit()
        self.txt_role.setPlaceholderText("e.g. Search Team Leader")
        self.txt_rank = QtWidgets.QLineEdit()
        self.txt_org = QtWidgets.QLineEdit()
        self.txt_email = QtWidgets.QLineEdit()
        self.txt_phone = QtWidgets.QLineEdit()
        self.txt_notes = QtWidgets.QLineEdit()
        self.btn_photo = QtWidgets.QPushButton("Photo…")
        self.btn_photo.setFixedWidth(80)
        self.btn_photo.clicked.connect(self._choose_photo)

        # Row 0: ID, Name, Callsign
        grid.addWidget(QtWidgets.QLabel("ID:"), 0, 0)
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

        # Row 2: Email, Phone, Photo
        grid.addWidget(QtWidgets.QLabel("Email:"), 2, 0)
        grid.addWidget(self.txt_email, 2, 1)
        grid.addWidget(QtWidgets.QLabel("Phone:"), 2, 2)
        grid.addWidget(self.txt_phone, 2, 3)
        grid.addWidget(QtWidgets.QLabel("Notes:"), 2, 4)
        notes_row = QtWidgets.QHBoxLayout()
        notes_row.addWidget(self.txt_notes)
        notes_row.addWidget(self.btn_photo)
        grid.addLayout(notes_row, 2, 5)

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
        self.txt_name.setText(doc.get("name") or "")
        self.txt_callsign.setText(doc.get("callsign") or "")
        self.txt_role.setText(doc.get("primary_role") or doc.get("role") or "")
        self.txt_rank.setText(doc.get("rank") or "")
        self.txt_org.setText(doc.get("home_unit") or doc.get("organization") or "")
        self.txt_email.setText(doc.get("email") or "")
        self.txt_phone.setText(doc.get("phone") or "")
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

    def _collect_personnel(self) -> Personnel:
        pid = self.txt_id.text().strip() or self.personnel_id
        return Personnel(
            id=pid,
            name=self.txt_name.text().strip(),
            callsign=self.txt_callsign.text().strip(),
            role=self.txt_role.text().strip(),
            rank=self.txt_rank.text().strip(),
            organization=self.txt_org.text().strip(),
            email=self.txt_email.text().strip(),
            phone=self.txt_phone.text().strip(),
            notes=self.txt_notes.text().strip(),
            photo_url=self._photo_path,
        )

    def _collect_emergency(self) -> EmergencyInfo:
        pid = self.txt_id.text().strip() or self.personnel_id
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
        pid = self.txt_id.text().strip() or self.personnel_id
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
            "home_unit": self.txt_org.text().strip(),
            "email": self.txt_email.text().strip(),
            "phone": self.txt_phone.text().strip(),
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
                result = api_client.put(f"/api/master/personnel/{self.personnel_id}", json=doc)
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
class PersonnelInventoryWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Personnel Inventory")
        self.resize(1000, 600)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by name, callsign, ID, email, phone…")

        self._model = _PersonnelTableModel(self)
        self._proxy = QtCore.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, QtCore.Qt.AscendingOrder)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        from utils.itemview_delegates import RowOutlineSelectionDelegate
        self.table.setItemDelegate(RowOutlineSelectionDelegate(self.table))
        self.table.doubleClicked.connect(self._on_edit)

        btn_add = QtWidgets.QPushButton("Add")
        btn_edit = QtWidgets.QPushButton("Edit")
        btn_delete = QtWidgets.QPushButton("Delete")
        btn_import = QtWidgets.QPushButton("Import CSV")
        btn_export = QtWidgets.QPushButton("Export CSV")
        btn_refresh = QtWidgets.QPushButton("Refresh")

        btn_add.clicked.connect(self._on_add)
        btn_edit.clicked.connect(self._on_edit)
        btn_delete.clicked.connect(self._on_delete)
        btn_import.clicked.connect(self._on_import)
        btn_export.clicked.connect(self._on_export)
        btn_refresh.clicked.connect(self.refresh)
        self.search.textChanged.connect(self._proxy.setFilterFixedString)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel("Search:"))
        filter_row.addWidget(self.search, stretch=2)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_import)
        btn_row.addWidget(btn_export)
        btn_row.addWidget(btn_refresh)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(filter_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(btn_row)

        self.refresh()

    # ----------------------------- Helpers ---------------------------------
    def refresh(self) -> None:
        from utils.api_client import api_client
        try:
            records = api_client.get("/api/master/personnel") or []
        except Exception:
            records = []
        self._model.set_records(records)

    def _selected_record(self) -> Optional[dict[str, Any]]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self._model.record_at(self._proxy.mapToSource(idx).row())

    # ----------------------------- Slots ----------------------------------
    def _on_add(self) -> None:
        dialog = PersonnelDetailDialog(parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.refresh()

    def _on_edit(self) -> None:
        record = self._selected_record()
        if not record:
            idx = self.table.currentIndex()
            if not idx.isValid():
                return
            record = self._model.record_at(self._proxy.mapToSource(idx).row())
        if not record:
            return
        pid = str(record.get("id") or "")
        dialog = PersonnelDetailDialog(parent=self, personnel_id=pid)
        dialog.exec()
        self.refresh()

    def _on_delete(self) -> None:
        from utils.api_client import api_client, APIError
        record = self._selected_record()
        if not record:
            QtWidgets.QMessageBox.information(self, "No Selection", "Select a record to delete.")
            return
        name = record.get("name") or record.get("id", "")
        if QtWidgets.QMessageBox.question(self, "Confirm Delete", f"Delete '{name}'?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            api_client.delete(f"/api/master/personnel/{record['id']}")
        except APIError as exc:
            QtWidgets.QMessageBox.warning(self, "Delete Failed", str(exc))
            return
        self.refresh()

    def _on_import(self) -> None:
        from utils.api_client import api_client
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Personnel", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            records = CsvUtil.import_personnel(path)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Import Failed", str(exc))
            return
        imported = 0
        skipped: list[str] = []
        for person in records:
            if not person.name:
                skipped.append(person.id or "<no name>")
                continue
            try:
                api_client.post("/api/master/personnel", json={
                    "name": person.name,
                    "callsign": person.callsign,
                    "primary_role": person.role,
                    "rank": person.rank,
                    "home_unit": person.organization,
                    "email": person.email,
                    "phone": person.phone,
                    "notes": person.notes,
                })
                imported += 1
            except Exception as exc:
                skipped.append(f"{person.name}: {exc}")
        message = f"Imported {imported} personnel record(s)."
        if skipped:
            QtWidgets.QMessageBox.warning(self, "Import Completed With Warnings",
                message + "\n\n" + "\n".join(skipped[:5]))
        else:
            QtWidgets.QMessageBox.information(self, "Import Complete", message)
        self.refresh()

    def _on_export(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Personnel", "personnel.csv", "CSV Files (*.csv)")
        if not path:
            return
        records = [
            Personnel(
                id=str(r.get("id") or ""),
                name=r.get("name") or "",
                callsign=r.get("callsign") or "",
                role=r.get("primary_role") or "",
                rank=r.get("rank") or "",
                organization=r.get("home_unit") or "",
                email=r.get("email") or "",
                phone=r.get("phone") or "",
                notes=r.get("notes") or "",
            )
            for r in self._model._records
        ]
        try:
            CsvUtil.export_personnel(path, records)
        except (OSError, csv.Error) as exc:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Export Complete", f"Exported {len(records)} personnel record(s).")
