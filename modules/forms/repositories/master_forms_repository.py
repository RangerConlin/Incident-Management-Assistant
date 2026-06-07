from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from modules.forms.models import FormFamily, FormTemplate, FormTemplateVersion


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps(value: Any) -> str:
    def default(obj: Any) -> Any:
        if is_dataclass(obj):
            return asdict(obj)
        return obj
    return json.dumps(value, default=default, ensure_ascii=False, sort_keys=True)


def loads(value: str | None, default: Any) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)


class MasterFormsRepository:
    def __init__(self, db_path: Path | str = Path("data") / "master.db") -> None:
        self.db_path = Path(db_path)
        self.ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(MASTER_SCHEMA)

    def create_family(self, family: FormFamily) -> FormFamily:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO form_families (code,title,description,category,default_agency,is_active,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (family.code, family.title, family.description, family.category, family.default_agency, int(family.is_active), now, now),
            )
            family.id = int(cur.lastrowid)
            family.created_at = now
            family.updated_at = now
        return family

    def list_families(self, *, code: str | None = None, category: str | None = None, active: bool | None = None) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if code:
            where.append("code = ?")
            params.append(code)
        if category:
            where.append("category = ?")
            params.append(category)
        if active is not None:
            where.append("is_active = ?")
            params.append(int(active))
        sql = "SELECT * FROM form_families" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY code"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def get_family_by_code(self, code: str) -> dict[str, Any] | None:
        rows = self.list_families(code=code)
        return rows[0] if rows else None

    def create_template(self, template: FormTemplate) -> FormTemplate:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO form_templates (family_id,agency,system,code,title,description,status,compatibility_json,tags_json,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (template.family_id, template.agency, template.system, template.code, template.title, template.description, template.status,
                 dumps(template.compatibility), dumps(template.tags), template.created_by, now, now),
            )
            template.id = int(cur.lastrowid)
            template.created_at = now
            template.updated_at = now
        return template

    def create_template_version(self, version: FormTemplateVersion) -> FormTemplateVersion:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("UPDATE form_template_versions SET is_current = 0 WHERE template_id = ?", (version.template_id,))
            cur = conn.execute(
                """INSERT INTO form_template_versions
                (template_id,version_number,version_label,effective_date,retired_date,layout_json,fields_json,bindings_json,validation_json,export_profiles_json,source_asset_path,checksum,change_summary,created_by,created_at,is_current)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (version.template_id, version.version_number, version.version_label, version.effective_date, version.retired_date,
                 dumps(version.layout), dumps(version.fields), dumps(version.bindings), dumps(version.validation_rules), dumps(version.export_profiles),
                 version.source_asset_path, version.checksum, version.change_summary, version.created_by, now),
            )
            version.id = int(cur.lastrowid)
            version.created_at = now
            version.is_current = True
            conn.execute("UPDATE form_templates SET current_version_id = ?, updated_at = ? WHERE id = ?", (version.id, now, version.template_id))
            self.write_template_audit(conn, version.template_id, version.id, "version_created", version.created_by, {"version_number": version.version_number})
        return version

    def list_templates(self, **filters: Any) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        family_code = filters.get("family_code")
        if family_code:
            where.append("f.code = ?")
            params.append(family_code)
        for col in ("agency", "system", "status"):
            if filters.get(col):
                where.append(f"t.{col} = ?")
                params.append(filters[col])
        if filters.get("active_only"):
            where.append("t.status = 'active'")
            where.append("f.is_active = 1")
        sql = """SELECT t.*, f.code AS family_code, f.title AS family_title FROM form_templates t
                 JOIN form_families f ON f.id = t.family_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY f.code, t.agency, t.code"
        with self.connect() as conn:
            return [self._decode_template_row(r) for r in conn.execute(sql, params)]

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM form_templates WHERE id = ?", (template_id,)).fetchone()
            if not row:
                return None
            data = self._decode_template_row(row)
            if data.get("current_version_id"):
                data["current_version"] = self.get_template_version(template_id, int(data["current_version_id"]))
            return data

    def list_template_versions(self, template_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [self._decode_version_row(r) for r in conn.execute("SELECT * FROM form_template_versions WHERE template_id = ? ORDER BY version_number", (template_id,))]

    def get_template_version(self, template_id: int, version_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM form_template_versions WHERE template_id = ? AND id = ?", (template_id, version_id)).fetchone()
            return self._decode_version_row(row) if row else None

    def get_current_version(self, template_id: int) -> dict[str, Any] | None:
        template = self.get_template(template_id)
        if not template or not template.get("current_version_id"):
            return None
        return self.get_template_version(template_id, int(template["current_version_id"]))

    def retire_template(self, template_id: int, user_id: str | None = None) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("UPDATE form_templates SET status = 'retired', updated_at = ? WHERE id = ?", (now, template_id))
            self.write_template_audit(conn, template_id, None, "retired", user_id, {})

    def write_template_audit(self, conn: sqlite3.Connection, template_id: int | None, version_id: int | None, action: str, user_id: str | None, details: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO form_template_audit (template_id,template_version_id,action,user_id,timestamp,details_json) VALUES (?,?,?,?,?,?)",
            (template_id, version_id, action, user_id, utc_now(), dumps(details)),
        )

    def _decode_template_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["compatibility"] = loads(data.pop("compatibility_json", None), {})
        data["tags"] = loads(data.pop("tags_json", None), [])
        return data

    def _decode_version_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["layout"] = loads(data.pop("layout_json", None), {})
        data["fields"] = loads(data.pop("fields_json", None), [])
        data["bindings"] = loads(data.pop("bindings_json", None), [])
        data["validation"] = loads(data.pop("validation_json", None), [])
        data["export_profiles"] = loads(data.pop("export_profiles_json", None), {})
        return data


MASTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_families (
 id INTEGER PRIMARY KEY, code TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
 category TEXT, default_agency TEXT, is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(code)
);
CREATE TABLE IF NOT EXISTS form_templates (
 id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL, agency TEXT NOT NULL, system TEXT,
 code TEXT NOT NULL, title TEXT NOT NULL, description TEXT, status TEXT NOT NULL DEFAULT 'active',
 current_version_id INTEGER, compatibility_json TEXT, tags_json TEXT, created_by TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(family_id) REFERENCES form_families(id)
);
CREATE TABLE IF NOT EXISTS form_template_versions (
 id INTEGER PRIMARY KEY, template_id INTEGER NOT NULL, version_number INTEGER NOT NULL,
 version_label TEXT, effective_date TEXT, retired_date TEXT, layout_json TEXT NOT NULL,
 fields_json TEXT NOT NULL, bindings_json TEXT, validation_json TEXT, export_profiles_json TEXT,
 source_asset_path TEXT, checksum TEXT, change_summary TEXT, created_by TEXT, created_at TEXT NOT NULL,
 is_current INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(template_id) REFERENCES form_templates(id),
 UNIQUE(template_id, version_number)
);
CREATE TABLE IF NOT EXISTS form_template_fields (id INTEGER PRIMARY KEY, template_version_id INTEGER NOT NULL, field_key TEXT NOT NULL, field_json TEXT NOT NULL, FOREIGN KEY(template_version_id) REFERENCES form_template_versions(id));
CREATE TABLE IF NOT EXISTS form_template_bindings (id INTEGER PRIMARY KEY, template_version_id INTEGER NOT NULL, field_key TEXT NOT NULL, binding_key TEXT NOT NULL, binding_json TEXT, FOREIGN KEY(template_version_id) REFERENCES form_template_versions(id));
CREATE TABLE IF NOT EXISTS form_template_validation_rules (id INTEGER PRIMARY KEY, template_version_id INTEGER NOT NULL, field_key TEXT, rule_json TEXT NOT NULL, FOREIGN KEY(template_version_id) REFERENCES form_template_versions(id));
CREATE TABLE IF NOT EXISTS form_template_assets (id INTEGER PRIMARY KEY, template_id INTEGER, template_version_id INTEGER, asset_path TEXT NOT NULL, asset_type TEXT, metadata_json TEXT);
CREATE TABLE IF NOT EXISTS form_template_exports (id INTEGER PRIMARY KEY, template_id INTEGER, template_version_id INTEGER, export_type TEXT NOT NULL, profile_json TEXT);
CREATE TABLE IF NOT EXISTS form_template_audit (id INTEGER PRIMARY KEY, template_id INTEGER, template_version_id INTEGER, action TEXT NOT NULL, user_id TEXT, timestamp TEXT NOT NULL, details_json TEXT);
"""
