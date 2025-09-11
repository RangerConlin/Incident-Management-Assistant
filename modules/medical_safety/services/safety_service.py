"""Low level SQLite helpers for safety data."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, List

from modules.medical_safety.models.safety_models import (
    ICS208,
    ICS215AItem,
    HazardLogItem,
    SafetyBriefing,
    SafetyIncident,
    PPEAdvisory,
)
from modules.medical_safety.services.printers.ics208_printer import print_ics208
from modules.medical_safety.services.printers.ics215a_printer import print_ics215a

MASTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS safety_hazard_category_template (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);
CREATE TABLE IF NOT EXISTS safety_ppe_catalog (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  description TEXT
);
CREATE TABLE IF NOT EXISTS safety_severity_matrix (
  id INTEGER PRIMARY KEY,
  likelihood TEXT NOT NULL,
  consequence TEXT NOT NULL,
  risk_level TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_ics208_template (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  last_updated_utc TEXT NOT NULL
);
"""

INCIDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS safety_ics208 (
  id INTEGER PRIMARY KEY,
  op_period_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  created_utc TEXT NOT NULL,
  updated_utc TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS safety_ics215a (
  id INTEGER PRIMARY KEY,
  op_period_id INTEGER NOT NULL,
  task_id INTEGER,
  hazard_category TEXT NOT NULL,
  hazard_description TEXT NOT NULL,
  mitigation TEXT,
  likelihood TEXT,
  consequence TEXT,
  residual_risk TEXT,
  owner_user_id INTEGER,
  status TEXT NOT NULL DEFAULT 'Open',
  location TEXT,
  attachments_json TEXT,
  created_utc TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_hazard_log (
  id INTEGER PRIMARY KEY,
  op_period_id INTEGER,
  title TEXT NOT NULL,
  category TEXT,
  severity TEXT,
  status TEXT NOT NULL DEFAULT 'Open',
  location TEXT,
  reported_by_user_id INTEGER,
  notes TEXT,
  created_utc TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_briefing (
  id INTEGER PRIMARY KEY,
  op_period_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  delivered_by_user_id INTEGER,
  delivered_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_briefing_attendance (
  id INTEGER PRIMARY KEY,
  briefing_id INTEGER NOT NULL,
  attendee_type TEXT NOT NULL,
  attendee_ref_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_incident (
  id INTEGER PRIMARY KEY,
  op_period_id INTEGER,
  type TEXT NOT NULL,
  description TEXT NOT NULL,
  location TEXT,
  severity TEXT,
  reported_by_user_id INTEGER,
  treated_on_site INTEGER DEFAULT 0,
  referred_to_medical INTEGER DEFAULT 0,
  created_utc TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_ppe_advisory (
  id INTEGER PRIMARY KEY,
  op_period_id INTEGER,
  code TEXT NOT NULL,
  label TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  created_utc TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);
"""


class SafetyService:
    """Service methods for safety tables."""

    def ensure_master_tables(self, db_path: str = "data/master.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.executescript(MASTER_SCHEMA)

    def seed_master(self, db_path: str, seed_dir: str) -> None:
        """Load seed JSON files into the master database."""
        self.ensure_master_tables(db_path)
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # Hazard categories
            path = Path(seed_dir) / "hazard_categories.json"
            if path.exists():
                categories = json.loads(path.read_text())
                for item in categories:
                    cur.execute(
                        "INSERT OR IGNORE INTO safety_hazard_category_template(name, description) VALUES (?,?)",
                        (item["name"], item.get("description")),
                    )
            # PPE catalog
            path = Path(seed_dir) / "ppe_catalog.json"
            if path.exists():
                ppes = json.loads(path.read_text())
                for item in ppes:
                    cur.execute(
                        "INSERT OR IGNORE INTO safety_ppe_catalog(code, label, description) VALUES (?,?,?)",
                        (item["code"], item["label"], item.get("description")),
                    )
            # Severity matrix
            path = Path(seed_dir) / "severity_matrix.json"
            if path.exists():
                matrix = json.loads(path.read_text())
                for item in matrix:
                    cur.execute(
                        "INSERT OR IGNORE INTO safety_severity_matrix(likelihood, consequence, risk_level) VALUES (?,?,?)",
                        (item["likelihood"], item["consequence"], item["risk_level"]),
                    )
            # ICS208 templates
            path = Path(seed_dir) / "ics208_templates.json"
            if path.exists():
                templates = json.loads(path.read_text())
                for item in templates:
                    cur.execute(
                        "INSERT OR IGNORE INTO safety_ics208_template(title, message, last_updated_utc) VALUES (?,?,?)",
                        (item["title"], item["message"], item["last_updated_utc"]),
                    )
            conn.commit()

    def ensure_incident_tables(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.executescript(INCIDENT_SCHEMA)

    # -- ICS 208 ---------------------------------------------------------
    def get_ics208(self, db_path: str, op_period_id: int) -> ICS208 | None:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, op_period_id, title, message, created_utc, updated_utc, version "
                "FROM safety_ics208 WHERE op_period_id=? ORDER BY version DESC LIMIT 1",
                (op_period_id,),
            )
            row = cur.fetchone()
            return ICS208.from_row(row) if row else None

    def save_ics208(self, db_path: str, record: ICS208) -> int:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(MAX(version),0) FROM safety_ics208 WHERE op_period_id=?",
                (record.op_period_id,),
            )
            version = cur.fetchone()[0] + 1
            cur.execute(
                "INSERT INTO safety_ics208(op_period_id,title,message,created_utc,updated_utc,version) "
                "VALUES (?,?,?,?,?,?)",
                (
                    record.op_period_id,
                    record.title,
                    record.message,
                    record.created_utc,
                    record.updated_utc,
                    version,
                ),
            )
            conn.commit()
            return cur.lastrowid

    # -- ICS 215A -------------------------------------------------------
    def list_215a_items(self, db_path: str, op_period_id: int) -> List[ICS215AItem]:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, op_period_id, task_id, hazard_category, hazard_description, mitigation, likelihood, consequence, residual_risk, owner_user_id, status, location, attachments_json, created_utc, updated_utc FROM safety_ics215a WHERE op_period_id=?",
                (op_period_id,),
            )
            return [ICS215AItem.from_row(row) for row in cur.fetchall()]

    def upsert_215a_item(self, db_path: str, item: ICS215AItem) -> int:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            if item.id:
                cur.execute(
                    "UPDATE safety_ics215a SET task_id=?, hazard_category=?, hazard_description=?, mitigation=?, likelihood=?, consequence=?, residual_risk=?, owner_user_id=?, status=?, location=?, attachments_json=?, created_utc=?, updated_utc=? WHERE id=?",
                    (
                        item.task_id,
                        item.hazard_category,
                        item.hazard_description,
                        item.mitigation,
                        item.likelihood,
                        item.consequence,
                        item.residual_risk,
                        item.owner_user_id,
                        item.status,
                        item.location,
                        item.attachments_json,
                        item.created_utc,
                        item.updated_utc,
                        item.id,
                    ),
                )
                conn.commit()
                return item.id
            cur.execute(
                "INSERT INTO safety_ics215a(op_period_id,task_id,hazard_category,hazard_description,mitigation,likelihood,consequence,residual_risk,owner_user_id,status,location,attachments_json,created_utc,updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item.op_period_id,
                    item.task_id,
                    item.hazard_category,
                    item.hazard_description,
                    item.mitigation,
                    item.likelihood,
                    item.consequence,
                    item.residual_risk,
                    item.owner_user_id,
                    item.status,
                    item.location,
                    item.attachments_json,
                    item.created_utc,
                    item.updated_utc,
                ),
            )
            conn.commit()
            return cur.lastrowid

    def close_215a_item(self, db_path: str, item_id: int) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE safety_ics215a SET status='Closed' WHERE id=?", (item_id,)
            )
            conn.commit()

    # -- Hazard Log -----------------------------------------------------
    def list_hazard_log(self, db_path: str) -> List[HazardLogItem]:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, op_period_id, title, category, severity, status, location, reported_by_user_id, notes, created_utc, updated_utc FROM safety_hazard_log"
            )
            return [HazardLogItem.from_row(r) for r in cur.fetchall()]

    def add_hazard(self, db_path: str, item: HazardLogItem) -> int:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO safety_hazard_log(op_period_id,title,category,severity,status,location,reported_by_user_id,notes,created_utc,updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
                item.to_row()[1:],
            )
            conn.commit()
            return cur.lastrowid

    def update_hazard_status(self, db_path: str, hazard_id: int, status: str) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE safety_hazard_log SET status=? WHERE id=?", (status, hazard_id)
            )
            conn.commit()

    # -- Briefings ------------------------------------------------------
    def record_briefing(self, db_path: str, briefing: SafetyBriefing) -> int:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO safety_briefing(op_period_id,title,content,delivered_by_user_id,delivered_utc) VALUES (?,?,?,?,?)",
                briefing.to_row()[1:],
            )
            conn.commit()
            return cur.lastrowid

    def record_attendance(
        self, db_path: str, briefing_id: int, attendee_type: str, attendee_ref_id: int
    ) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO safety_briefing_attendance(briefing_id,attendee_type,attendee_ref_id) VALUES (?,?,?)",
                (briefing_id, attendee_type, attendee_ref_id),
            )
            conn.commit()

    # -- Safety Incidents -----------------------------------------------
    def record_safety_incident(self, db_path: str, incident: SafetyIncident) -> int:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO safety_incident(op_period_id,type,description,location,severity,reported_by_user_id,treated_on_site,referred_to_medical,created_utc,updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
                incident.to_row()[1:],
            )
            conn.commit()
            return cur.lastrowid

    # -- PPE Advisories -------------------------------------------------
    def list_active_ppe_advisories(self, db_path: str) -> List[PPEAdvisory]:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, op_period_id, code, label, active, notes, created_utc, updated_utc FROM safety_ppe_advisory WHERE active=1"
            )
            return [PPEAdvisory.from_row(r) for r in cur.fetchall()]

    def set_ppe_advisory_active(self, db_path: str, advisory_id: int, active: int) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE safety_ppe_advisory SET active=? WHERE id=?",
                (active, advisory_id),
            )
            conn.commit()

    # -- Printing Helpers -----------------------------------------------
    def print_ics208(self, record: ICS208, out_path: str) -> None:
        print_ics208(record, out_path)

    def print_ics215a(self, items: Iterable[ICS215AItem], out_path: str) -> None:
        print_ics215a(list(items), out_path)
