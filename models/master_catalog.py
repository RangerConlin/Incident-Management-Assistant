from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@dataclass
class BaseService:
    db_path: str
    table: str
    columns: List[str]
    pk: str = "id"
    search_fields: Optional[List[str]] = None

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = dict_factory
        return conn

    def list(self, search_text: str = "", limit: int = 0) -> List[Dict[str, Any]]:
        sql = f"SELECT {', '.join(self.columns)} FROM {self.table}"
        try:
            with self._conn() as con:
                cur = con.execute(sql)
                rows = cur.fetchall()
        except sqlite3.Error as e:
            # return empty list on error; UI can show empty state
            print(f"[BaseService.list] {self.table}: {e}")
            return []

        if search_text:
            txt = search_text.lower().strip()
            fields = self.search_fields or self.columns
            def match(r: Dict[str, Any]) -> bool:
                for f in fields:
                    v = r.get(f)
                    if v is None:
                        continue
                    if txt in str(v).lower():
                        return True
                return False
            rows = [r for r in rows if match(r)]

        if limit and limit > 0:
            rows = rows[:limit]
        return rows

    def create(self, payload: Dict[str, Any]) -> int:
        cols = [c for c in self.columns if c != self.pk]
        vals = [payload.get(c) for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders})"
        try:
            with self._conn() as con:
                cur = con.execute(sql, vals)
                con.commit()
                return int(cur.lastrowid)
        except sqlite3.Error as e:
            print(f"[BaseService.create] {self.table}: {e}")
            return 0

    def update(self, id_value: int, payload: Dict[str, Any]) -> bool:
        cols = [c for c in self.columns if c != self.pk and c in payload]
        if not cols:
            return False
        set_clause = ", ".join([f"{c}=?" for c in cols])
        sql = f"UPDATE {self.table} SET {set_clause} WHERE {self.pk}=?"
        try:
            with self._conn() as con:
                vals = [payload.get(c) for c in cols] + [id_value]
                con.execute(sql, vals)
                con.commit()
                return True
        except sqlite3.Error as e:
            print(f"[BaseService.update] {self.table}: {e}")
            return False

    def delete(self, id_value: int) -> bool:
        # TODO: add soft-delete option (e.g., is_active flag)
        sql = f"DELETE FROM {self.table} WHERE {self.pk}=?"
        try:
            with self._conn() as con:
                con.execute(sql, (id_value,))
                con.commit()
                return True
        except sqlite3.Error as e:
            print(f"[BaseService.delete] {self.table}: {e}")
            return False


# Entity configurations
ENTITY_CONFIGS: Dict[str, Dict[str, Any]] = {
    "personnel": {
        "table": "personnel",
        "pk": "id",
        "searchFields": ["name", "id"],
        "columns": ["id", "name", "callsign", "role", "phone", "email", "organization"],
        "defaultSort": {"key": "name", "order": "asc"},
    },
    "vehicles": {
        "table": "vehicles",
        "pk": "id",
        "searchFields": ["identifier", "id", "make", "model", "license_plate"],
        "columns": [
            "id", "vin", "license_plate", "year", "make", "model",
            "capacity", "type_id", "status_id", "tags", "organization"
        ],
        "defaultSort": {"key": "make", "order": "asc"},
    },
    "aircraft": {
        "table": "aircraft",
        "pk": "id",
        "searchFields": ["callsign", "tail_number"],
        "columns": [
            "id",
            "tail_number",
            "callsign",
            "type",
            "make_model",
            "capacity",
            "status",
            "base_location",
            "current_assignment",
            "capabilities",
            "notes",
            "created_at",
            "updated_at",
        ],
        "defaultSort": {"key": "tail_number", "order": "asc"},
    },
    "equipment": {
        "table": "equipment",
        "pk": "id",
        "searchFields": ["name", "id", "serial_number"],
        "columns": ["id", "name", "type", "serial_number", "condition", "notes"],
        "defaultSort": {"key": "name", "order": "asc"},
    },
    "comms_resources": {
        "table": "comms_resources",
        "pk": "id",
        "searchFields": ["alpha_tag", "id"],
        "columns": [
            "id", "alpha_tag", "function", "freq_rx", "rx_tone",
            "freq_tx", "tx_tone", "system", "mode", "notes", "line_a", "line_c"
        ],
        "defaultSort": {"key": "alpha_tag", "order": "asc"},
    },
    "incident_objectives": {
        "table": "incident_objectives",
        "pk": "id",
        "searchFields": ["description", "id"],
        "columns": [
            "id", "description", "priority", "status", "section",
            "due_time", "customer", "created_by", "created_at", "closed_at"
        ],
        "defaultSort": {"key": "priority", "order": "desc"},
    },
    "certification_types": {
        "table": "certification_types",
        "pk": "id",
        "searchFields": ["code", "name", "id"],
        "columns": [
            "id", "code", "name", "description", "category",
            "issuing_organization", "parent_certification_id"
        ],
        "defaultSort": {"key": "code", "order": "asc"},
    },
    # Placeholders
    "ems": {
        "table": "ems",
        "pk": "id",
        "searchFields": ["name", "id"],
        "columns": [
            "id", "name", "type", "phone", "fax", "email", "contact",
            "address", "city", "state", "zip", "notes", "is_active"
        ],
        "defaultSort": {"key": "name", "order": "asc"},
    },
    "canned_comm_entries": {
        "table": "canned_comm_entries",
        "pk": "id",
        "searchFields": ["title", "category", "message", "id"],
        "columns": ["id", "title", "category", "message", "notification_level", "status_update", "is_active"],
        "defaultSort": {"key": "title", "order": "asc"},
    },
    "task_types": {
        "table": "task_types",
        "pk": "id",
        "searchFields": ["name", "id"],
        "columns": ["id", "name", "category", "description", "is_active"],
        "defaultSort": {"key": "name", "order": "asc"},
    },
    "team_types": {
        "table": "team_types",
        "pk": "id",
        "searchFields": ["name", "id"],
        "columns": ["id", "name", "description", "is_active"],
        "defaultSort": {"key": "name", "order": "asc"},
    },
    "safety_templates": {
        "table": "safety_templates",
        "pk": "id",
        "searchFields": ["name", "hazard", "id"],
        "columns": [
            "id", "name", "operational_context", "hazard", "controls",
            "residual_risk", "ppe", "notes", "created_at", "updated_at"
        ],
        "defaultSort": {"key": "name", "order": "asc"},
    },
}


def make_service(db_path: str, key: str) -> BaseService:
    cfg = ENTITY_CONFIGS[key]
    return BaseService(
        db_path=db_path,
        table=cfg["table"],
        columns=cfg["columns"],
        pk=cfg.get("pk", "id"),
        search_fields=cfg.get("searchFields"),
    )

