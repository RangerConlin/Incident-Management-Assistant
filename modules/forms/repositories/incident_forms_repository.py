from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .master_forms_repository import dumps, loads, utc_now


class IncidentFormsRepository:
    def __init__(self, incident_id: str, db_path: Path | str | None = None, base_dir: Path | str = Path("data") / "incidents") -> None:
        if not incident_id or not str(incident_id).strip():
            raise ValueError("incident_id is required")
        self.incident_id = str(incident_id).strip()
        self.db_path = Path(db_path) if db_path else Path(base_dir) / f"{self.incident_id}.db"
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
            conn.executescript(INCIDENT_SCHEMA)

    def create_instance(self, data: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO form_instances
                (family_id,template_id,template_version_id,incident_id,operational_period_id,linked_module,linked_record_id,title,agency,status,revision_number,created_by,created_at,updated_by,updated_at,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data["family_id"], data["template_id"], data["template_version_id"], data["incident_id"], data.get("operational_period_id"),
                 data.get("linked_module"), data.get("linked_record_id"), data.get("title"), data.get("agency"), data.get("status", "draft"),
                 data.get("revision_number", 1), data.get("created_by"), now, data.get("created_by"), now, dumps(data.get("metadata", {}))),
            )
            instance_id = int(cur.lastrowid)
            if data.get("linked_module") and data.get("linked_record_id"):
                conn.execute(
                    "INSERT INTO form_instance_links (instance_id,linked_module,linked_record_id,relationship_type,created_by,created_at) VALUES (?,?,?,?,?,?)",
                    (instance_id, data["linked_module"], data["linked_record_id"], "source", data.get("created_by"), now),
                )
            self.write_audit(conn, instance_id, None, "created", None, data, data.get("created_by"), {})
            self.create_revision(conn, instance_id, 1, "created", data.get("created_by"))
        return self.get_instance(instance_id) or {}

    def list_instances(self, **filters: Any) -> list[dict[str, Any]]:
        where = ["incident_id = ?"]
        params: list[Any] = [self.incident_id]
        for col in ("agency", "status", "operational_period_id", "linked_module", "linked_record_id"):
            if filters.get(col):
                where.append(f"{col} = ?")
                params.append(filters[col])
        sql = "SELECT * FROM form_instances WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC"
        with self.connect() as conn:
            return [self._decode_instance(r) for r in conn.execute(sql, params)]

    def get_instance(self, instance_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM form_instances WHERE id = ?", (instance_id,)).fetchone()
            if not row:
                return None
            data = self._decode_instance(row)
            data["values"] = {v["field_key"]: v for v in self.list_values(instance_id)}
            return data

    def list_values(self, instance_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [self._decode_value(r) for r in conn.execute("SELECT * FROM form_instance_values WHERE instance_id = ? ORDER BY field_key", (instance_id,))]

    def upsert_values(self, instance_id: int, updates: dict[str, dict[str, Any]], user_id: str | None = None, *, require_override_reason: bool = True) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            instance = conn.execute("SELECT * FROM form_instances WHERE id = ?", (instance_id,)).fetchone()
            if not instance:
                raise ValueError("instance not found")
            if instance["status"] == "finalized":
                raise ValueError("finalized form cannot be edited unless reopened")
            for key, payload in updates.items():
                old_row = conn.execute("SELECT * FROM form_instance_values WHERE instance_id = ? AND field_key = ?", (instance_id, key)).fetchone()
                if old_row and old_row["is_locked"]:
                    raise ValueError(f"field is locked: {key}")
                old_value = self._decode_value(old_row) if old_row else None
                is_override = bool(payload.get("is_overridden", False))
                if require_override_reason and is_override and not payload.get("override_reason"):
                    raise ValueError(f"override reason is required for {key}")
                conn.execute(
                    """INSERT INTO form_instance_values
                    (instance_id,field_key,value_json,display_value,source_type,source_binding,source_module,source_record_id,is_locked,is_overridden,override_reason,updated_by,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(instance_id, field_key) DO UPDATE SET
                    value_json=excluded.value_json, display_value=excluded.display_value, source_type=excluded.source_type,
                    source_binding=excluded.source_binding, source_module=excluded.source_module, source_record_id=excluded.source_record_id,
                    is_locked=excluded.is_locked, is_overridden=excluded.is_overridden, override_reason=excluded.override_reason,
                    updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                    (instance_id, key, dumps(payload.get("value")), payload.get("display_value"), payload.get("source_type", "manual"),
                     payload.get("source_binding"), payload.get("source_module"), payload.get("source_record_id"), int(payload.get("is_locked", False)),
                     int(is_override), payload.get("override_reason"), user_id, now),
                )
                self.write_audit(conn, instance_id, key, "value_updated", old_value, payload, user_id, {"source_type": payload.get("source_type", "manual")})
            revision = int(instance["revision_number"]) + 1
            conn.execute("UPDATE form_instances SET revision_number = ?, updated_by = ?, updated_at = ? WHERE id = ?", (revision, user_id, now, instance_id))
            self.create_revision(conn, instance_id, revision, "values saved", user_id)
        return self.get_instance(instance_id) or {}

    def finalize_instance(self, instance_id: int, user_id: str | None = None) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM form_instances WHERE id = ?", (instance_id,)).fetchone()
            if not row:
                raise ValueError("instance not found")
            if row["status"] == "finalized":
                return self.get_instance(instance_id) or {}
            revision = int(row["revision_number"]) + 1
            conn.execute("UPDATE form_instances SET status='finalized', revision_number=?, finalized_by=?, finalized_at=?, updated_by=?, updated_at=? WHERE id=?", (revision, user_id, now, user_id, now, instance_id))
            conn.execute("UPDATE form_instance_values SET is_locked = 1 WHERE instance_id = ?", (instance_id,))
            self.write_audit(conn, instance_id, None, "finalized", None, {"status": "finalized"}, user_id, {})
            self.create_revision(conn, instance_id, revision, "finalized", user_id)
        return self.get_instance(instance_id) or {}

    def reopen_instance(self, instance_id: int, user_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM form_instances WHERE id = ?", (instance_id,)).fetchone()
            if not row:
                raise ValueError("instance not found")
            revision = int(row["revision_number"]) + 1
            conn.execute("UPDATE form_instances SET status='draft', revision_number=?, finalized_by=NULL, finalized_at=NULL, updated_by=?, updated_at=? WHERE id=?", (revision, user_id, now, instance_id))
            self.write_audit(conn, instance_id, None, "reopened", None, {"status": "draft"}, user_id, {"reason": reason})
            self.create_revision(conn, instance_id, revision, "reopened", user_id)
        return self.get_instance(instance_id) or {}

    def set_exported_pdf(self, instance_id: int, path: str, user_id: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE form_instances SET exported_pdf_path = ?, updated_by = ?, updated_at = ? WHERE id = ?", (path, user_id, utc_now(), instance_id))

    def create_export_record(self, record: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO form_instance_exports (instance_id,export_type,export_path,template_version_id,revision_number,created_by,created_at,checksum) VALUES (?,?,?,?,?,?,?,?)",
                (record["instance_id"], record["export_type"], record["export_path"], record["template_version_id"], record["revision_number"], record.get("created_by"), utc_now(), record.get("checksum")),
            )
            record["id"] = int(cur.lastrowid)
        return record

    def list_revisions(self, instance_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) | {"snapshot": loads(r["snapshot_json"], {})} for r in conn.execute("SELECT * FROM form_instance_revisions WHERE instance_id = ? ORDER BY revision_number", (instance_id,))]

    def list_audit(self, instance_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(r) | {"old_value": loads(r["old_value_json"], None), "new_value": loads(r["new_value_json"], None), "details": loads(r["details_json"], {})} for r in conn.execute("SELECT * FROM form_instance_audit WHERE instance_id = ? ORDER BY timestamp, id", (instance_id,))]

    def write_audit(self, conn: sqlite3.Connection, instance_id: int, field_key: str | None, action: str, old_value: Any, new_value: Any, user_id: str | None, details: dict[str, Any]) -> None:
        conn.execute("INSERT INTO form_instance_audit (instance_id,field_key,action,old_value_json,new_value_json,user_id,timestamp,details_json) VALUES (?,?,?,?,?,?,?,?)", (instance_id, field_key, action, dumps(old_value), dumps(new_value), user_id, utc_now(), dumps(details)))

    def create_revision(self, conn: sqlite3.Connection, instance_id: int, revision_number: int, summary: str, user_id: str | None) -> None:
        values = [self._decode_value(r) for r in conn.execute("SELECT * FROM form_instance_values WHERE instance_id = ?", (instance_id,))]
        instance = dict(conn.execute("SELECT * FROM form_instances WHERE id = ?", (instance_id,)).fetchone())
        snapshot = {"instance": instance, "values": values}
        conn.execute("INSERT OR IGNORE INTO form_instance_revisions (instance_id,revision_number,snapshot_json,change_summary,created_by,created_at) VALUES (?,?,?,?,?,?)", (instance_id, revision_number, dumps(snapshot), summary, user_id, utc_now()))

    def _decode_instance(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = loads(data.pop("metadata_json", None), {})
        return data

    def _decode_value(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        data = dict(row)
        data["value"] = loads(data.pop("value_json", None), None)
        data["is_locked"] = bool(data["is_locked"])
        data["is_overridden"] = bool(data["is_overridden"])
        return data


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


INCIDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_instances (
 id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL, template_id INTEGER NOT NULL, template_version_id INTEGER NOT NULL,
 incident_id TEXT NOT NULL, operational_period_id TEXT, linked_module TEXT, linked_record_id TEXT, title TEXT, agency TEXT,
 status TEXT NOT NULL DEFAULT 'draft', revision_number INTEGER NOT NULL DEFAULT 1, created_by TEXT, created_at TEXT NOT NULL,
 updated_by TEXT, updated_at TEXT NOT NULL, finalized_by TEXT, finalized_at TEXT, exported_pdf_path TEXT, metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS form_instance_values (
 id INTEGER PRIMARY KEY, instance_id INTEGER NOT NULL, field_key TEXT NOT NULL, value_json TEXT, display_value TEXT,
 source_type TEXT NOT NULL DEFAULT 'manual', source_binding TEXT, source_module TEXT, source_record_id TEXT,
 is_locked INTEGER NOT NULL DEFAULT 0, is_overridden INTEGER NOT NULL DEFAULT 0, override_reason TEXT, updated_by TEXT,
 updated_at TEXT NOT NULL, FOREIGN KEY(instance_id) REFERENCES form_instances(id), UNIQUE(instance_id, field_key)
);
CREATE TABLE IF NOT EXISTS form_instance_revisions (id INTEGER PRIMARY KEY, instance_id INTEGER NOT NULL, revision_number INTEGER NOT NULL, snapshot_json TEXT NOT NULL, change_summary TEXT, created_by TEXT, created_at TEXT NOT NULL, FOREIGN KEY(instance_id) REFERENCES form_instances(id), UNIQUE(instance_id, revision_number));
CREATE TABLE IF NOT EXISTS form_instance_audit (id INTEGER PRIMARY KEY, instance_id INTEGER NOT NULL, field_key TEXT, action TEXT NOT NULL, old_value_json TEXT, new_value_json TEXT, user_id TEXT, timestamp TEXT NOT NULL, details_json TEXT, FOREIGN KEY(instance_id) REFERENCES form_instances(id));
CREATE TABLE IF NOT EXISTS form_instance_exports (id INTEGER PRIMARY KEY, instance_id INTEGER NOT NULL, export_type TEXT NOT NULL, export_path TEXT NOT NULL, template_version_id INTEGER NOT NULL, revision_number INTEGER NOT NULL, created_by TEXT, created_at TEXT NOT NULL, checksum TEXT, FOREIGN KEY(instance_id) REFERENCES form_instances(id));
CREATE TABLE IF NOT EXISTS form_instance_links (id INTEGER PRIMARY KEY, instance_id INTEGER NOT NULL, linked_module TEXT NOT NULL, linked_record_id TEXT NOT NULL, relationship_type TEXT, created_by TEXT, created_at TEXT NOT NULL, FOREIGN KEY(instance_id) REFERENCES form_instances(id));
"""
