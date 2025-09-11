"""Service helpers for CAP form templates and instances."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from modules.medical_safety.models.cap_form_models import (
    CapFormTemplate,
    CapFormInstance,
)
from modules.medical_safety.services.printers.cap_generic_form_printer import (
    print_cap_form,
)

MASTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS cap_form_template (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL,
  title TEXT NOT NULL,
  version TEXT,
  json_schema TEXT NOT NULL,
  layout_json TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(code, version)
);
"""

INCIDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS cap_form_instance (
  id INTEGER PRIMARY KEY,
  template_id INTEGER NOT NULL,
  op_period_id INTEGER,
  code TEXT NOT NULL,
  title TEXT,
  data_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Draft',
  version INTEGER NOT NULL DEFAULT 1,
  created_by_user_id INTEGER,
  created_utc TEXT NOT NULL,
  updated_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cap_form_attachment (
  id INTEGER PRIMARY KEY,
  form_instance_id INTEGER NOT NULL,
  filename TEXT NOT NULL,
  file_ref TEXT NOT NULL
);
"""


class CapFormsService:
    """CAP forms template and instance utilities."""

    def __init__(self, master_db_path: str = "data/master.db") -> None:
        self.master_db_path = master_db_path

    # -- Templates (master DB) -----------------------------------------
    def ensure_master_tables(self) -> None:
        Path(self.master_db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.master_db_path) as conn:
            conn.executescript(MASTER_SCHEMA)

    def seed_cap_templates_from_master(self, seed_dir: str) -> None:
        self.ensure_master_tables()
        catalog = json.loads((Path(seed_dir) / "cap_forms_catalog.json").read_text())
        with sqlite3.connect(self.master_db_path) as conn:
            cur = conn.cursor()
            for entry in catalog:
                layout_path = Path(seed_dir) / "cap_form_layouts" / entry["layout_file"]
                layout_json = layout_path.read_text()
                cur.execute(
                    "INSERT OR IGNORE INTO cap_form_template(code,title,version,json_schema,layout_json,is_active) VALUES (?,?,?,?,?,1)",
                    (
                        entry["code"],
                        entry["title"],
                        entry.get("version"),
                        json.dumps(entry["json_schema"]),
                        layout_json,
                    ),
                )
            conn.commit()

    def list_cap_templates(
        self, filter_code: str | None = None, active_only: bool = True
    ) -> List[CapFormTemplate]:
        self.ensure_master_tables()
        with sqlite3.connect(self.master_db_path) as conn:
            cur = conn.cursor()
            sql = "SELECT id,code,title,version,json_schema,layout_json,is_active FROM cap_form_template"
            clauses = []
            params: list = []
            if filter_code:
                clauses.append("code=?")
                params.append(filter_code)
            if active_only:
                clauses.append("is_active=1")
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            cur.execute(sql, params)
            return [CapFormTemplate.from_row(r) for r in cur.fetchall()]

    # -- Incident tables ------------------------------------------------
    def ensure_incident_tables(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.executescript(INCIDENT_SCHEMA)

    def create_cap_instance(
        self,
        incident_db: str,
        template_id: int,
        defaults: Optional[dict] = None,
        op_period_id: int | None = None,
        created_by_user_id: int | None = None,
        created_utc: str = "",
    ) -> int:
        template = self.get_template(template_id)
        data_json = json.dumps(defaults or {})
        with sqlite3.connect(incident_db) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO cap_form_instance(template_id,op_period_id,code,title,data_json,status,version,created_by_user_id,created_utc,updated_utc) VALUES (?,?,?,?,?,'Draft',1,?,?,?)",
                (
                    template_id,
                    op_period_id,
                    template.code,
                    template.title,
                    data_json,
                    created_by_user_id,
                    created_utc,
                    created_utc,
                ),
            )
            conn.commit()
            return cur.lastrowid

    def get_template(self, template_id: int) -> CapFormTemplate:
        with sqlite3.connect(self.master_db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,code,title,version,json_schema,layout_json,is_active FROM cap_form_template WHERE id=?",
                (template_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("template not found")
            return CapFormTemplate.from_row(row)

    def get_cap_instance(self, incident_db: str, form_id: int) -> CapFormInstance:
        with sqlite3.connect(incident_db) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,template_id,op_period_id,code,title,data_json,status,version,created_by_user_id,created_utc,updated_utc FROM cap_form_instance WHERE id=?",
                (form_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("form not found")
            return CapFormInstance.from_row(row)

    def update_cap_instance(
        self,
        incident_db: str,
        form_id: int,
        data_json: str,
        bump_version: bool = False,
        updated_utc: str = "",
    ) -> None:
        with sqlite3.connect(incident_db) as conn:
            cur = conn.cursor()
            if bump_version:
                cur.execute(
                    "UPDATE cap_form_instance SET data_json=?, version=version+1, updated_utc=? WHERE id=?",
                    (data_json, updated_utc, form_id),
                )
            else:
                cur.execute(
                    "UPDATE cap_form_instance SET data_json=?, updated_utc=? WHERE id=?",
                    (data_json, updated_utc, form_id),
                )
            conn.commit()

    def validate_cap_instance(self, incident_db: str, form_id: int) -> None:
        inst = self.get_cap_instance(incident_db, form_id)
        template = self.get_template(inst.template_id)
        schema = json.loads(template.json_schema)
        data = json.loads(inst.data_json)
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

    def render_cap_instance_pdf(self, incident_db: str, form_id: int, out_path: str) -> None:
        inst = self.get_cap_instance(incident_db, form_id)
        template = self.get_template(inst.template_id)
        data = json.loads(inst.data_json)
        print_cap_form(template, data, out_path)
