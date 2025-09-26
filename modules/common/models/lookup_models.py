from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from models.database import DB_PATH as DEFAULT_DB_PATH

ISO_TIMESTR = "%Y-%m-%dT%H:%M:%S"


def _local_timestamp() -> str:
    return datetime.now().strftime(ISO_TIMESTR)


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass(slots=True)
class ImportResult:
    inserted: int
    skipped_duplicates: List[str]
    errors: List[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.inserted or self.errors)


class BaseLookupRepository:
    table_name: str = ""
    create_table_sql: str = ""
    required_columns: dict[str, str] = {}
    default_values: dict[str, str | int] = {}
    unique_name_column: str = "name"

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.ensure_schema()

    # --- schema -----------------------------------------------------------------
    def ensure_schema(self) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(self.create_table_sql)
            existing_cols = {
                row["name"]: row for row in conn.execute(f"PRAGMA table_info({self.table_name})")
            }
            for column, ddl in self.required_columns.items():
                if column not in existing_cols:
                    # Prepare ADD COLUMN that is compatible with SQLite limitations.
                    # - PRIMARY KEY/UNIQUE are not allowed in ADD COLUMN; strip UNIQUE if present.
                    # - NOT NULL requires a DEFAULT when adding to a table with existing rows.
                    add_def = ddl
                    # Strip UNIQUE which SQLite does not accept in ADD COLUMN
                    add_def = add_def.replace(" UNIQUE", "").replace(" unique", "")
                    needs_default = (
                        "NOT NULL" in add_def.upper() and "DEFAULT" not in add_def.upper()
                    )
                    if needs_default:
                        # Choose a sensible default based on the column
                        if column in ("created_at", "updated_at"):
                            default_sql = f"'{_local_timestamp()}'"
                        elif column == "is_active":
                            default_sql = "1"
                        else:
                            # Fallback based on type hint in DDL
                            default_sql = "0" if "INTEGER" in add_def.upper() else "''"
                        add_def = f"{add_def} DEFAULT {default_sql}"

                    conn.execute(
                        f"ALTER TABLE {self.table_name} ADD COLUMN {column} {add_def}"
                    )

    # --- helpers ----------------------------------------------------------------
    def _normalize_name(self, name: str) -> str:
        return name.strip()

    def _prepare_payload(self, data: dict) -> dict:
        payload = {}
        for key in self.required_field_keys:
            if key in data:
                value = data[key]
                if isinstance(value, str):
                    value = value.strip()
                payload[key] = value
        for key, value in self.default_values.items():
            payload.setdefault(key, value)
        return payload

    # --- queries ----------------------------------------------------------------
    @property
    def required_field_keys(self) -> Iterable[str]:
        return (
            key
            for key in (
                "name",
                "description",
                "category",
                "default_priority",
                "is_active",
            )
            if key in self.required_columns
        )

    def list(self, filter_text: str = "", include_inactive: bool = False) -> list[dict]:
        filter_text = (filter_text or "").strip().lower()
        with _connect(self.db_path) as conn:
            clauses = []
            params: list = []
            if not include_inactive:
                clauses.append("is_active = 1")
            if filter_text:
                clauses.append(
                    "(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ?)"
                )
                like = f"%{filter_text}%"
                params.extend([like, like, like])
            sql = f"SELECT * FROM {self.table_name}"
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY name COLLATE NOCASE"
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get(self, record_id: int) -> Optional[dict]:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (record_id,),
            ).fetchone()
            return dict(row) if row else None

    def exists_with_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        norm = self._normalize_name(name)
        params: list = [norm.lower()]
        sql = f"SELECT id FROM {self.table_name} WHERE LOWER({self.unique_name_column}) = ?"
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)
        with _connect(self.db_path) as conn:
            row = conn.execute(sql, params).fetchone()
            return row is not None

    def create(self, data: dict) -> int:
        payload = self._prepare_payload(data)
        payload["name"] = self._normalize_name(payload.get("name", ""))
        now = _local_timestamp()
        payload.setdefault("created_at", now)
        payload.setdefault("updated_at", now)
        payload.setdefault("is_active", 1)
        columns = ",".join(payload.keys())
        placeholders = ",".join(["?"] * len(payload))
        values = list(payload.values())
        with _connect(self.db_path) as conn:
            cur = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                values,
            )
            return int(cur.lastrowid)

    def update(self, record_id: int, data: dict) -> None:
        payload = self._prepare_payload(data)
        payload["name"] = self._normalize_name(payload.get("name", ""))
        payload["updated_at"] = _local_timestamp()
        columns = [f"{col} = ?" for col in payload.keys()]
        values = list(payload.values())
        values.append(record_id)
        with _connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {', '.join(columns)} WHERE id = ?",
                values,
            )

    def soft_delete(self, record_id: int) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET is_active = 0, updated_at = ? WHERE id = ?",
                (_local_timestamp(), record_id),
            )

    def restore(self, record_id: int) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET is_active = 1, updated_at = ? WHERE id = ?",
                (_local_timestamp(), record_id),
            )

    # --- csv --------------------------------------------------------------------
    def export_csv(self, path: Path, rows: Optional[Iterable[dict]] = None) -> Path:
        output_path = Path(path)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".csv")
        headers = self.export_headers
        if rows is None:
            rows = self.list(include_inactive=True)
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})
        return output_path

    def import_csv(self, path: Path) -> ImportResult:
        inserted = 0
        skipped: list[str] = []
        errors: list[str] = []
        with Path(path).open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                return ImportResult(0, [], ["CSV file missing header row"])
            for idx, raw in enumerate(reader, start=2):
                try:
                    payload = self._map_csv_row(raw)
                    if not payload.get("name"):
                        skipped.append(f"Row {idx}: missing name")
                        continue
                    if self.exists_with_name(payload["name"]):
                        skipped.append(payload["name"])
                        continue
                    self.create(payload)
                    inserted += 1
                except Exception as exc:  # pragma: no cover - defensive
                    errors.append(f"Row {idx}: {exc}")
        return ImportResult(inserted, skipped, errors)

    # --- hooks ------------------------------------------------------------------
    @property
    def export_headers(self) -> List[str]:
        raise NotImplementedError

    def _map_csv_row(self, row: dict) -> dict:
        raise NotImplementedError


class TeamTypesRepository(BaseLookupRepository):
    table_name = "team_types"
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS team_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """
    required_columns = {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "name": "TEXT NOT NULL UNIQUE",
        "description": "TEXT DEFAULT ''",
        "category": "TEXT DEFAULT ''",
        "is_active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    }

    @property
    def export_headers(self) -> List[str]:
        return ["name", "category", "description", "is_active", "created_at", "updated_at"]

    def _map_csv_row(self, row: dict) -> dict:
        norm = {k.lower().strip(): v for k, v in row.items()}
        is_active_value = norm.get("is active") or norm.get("active") or "1"
        try:
            is_active = 1 if str(is_active_value).strip().lower() in {"1", "true", "yes", "active"} else 0
        except Exception:
            is_active = 1
        return {
            "name": norm.get("name", "").strip(),
            "category": norm.get("category", "").strip(),
            "description": norm.get("description", "").strip(),
            "is_active": is_active,
        }


class TaskTypesRepository(BaseLookupRepository):
    table_name = "task_types"
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS task_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            default_priority TEXT DEFAULT 'Normal',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """
    required_columns = {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "name": "TEXT NOT NULL UNIQUE",
        "description": "TEXT DEFAULT ''",
        "category": "TEXT DEFAULT ''",
        "default_priority": "TEXT DEFAULT 'Normal'",
        "is_active": "INTEGER NOT NULL DEFAULT 1",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    }
    default_values = {"default_priority": "Normal"}

    @property
    def export_headers(self) -> List[str]:
        return [
            "name",
            "category",
            "default_priority",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def _map_csv_row(self, row: dict) -> dict:
        norm = {k.lower().strip(): v for k, v in row.items()}
        is_active_value = norm.get("is active") or norm.get("active") or "1"
        try:
            is_active = 1 if str(is_active_value).strip().lower() in {"1", "true", "yes", "active"} else 0
        except Exception:
            is_active = 1
        default_priority = norm.get("default priority") or norm.get("priority") or "Normal"
        return {
            "name": norm.get("name", "").strip(),
            "category": norm.get("category", "").strip(),
            "default_priority": default_priority.strip().title(),
            "description": norm.get("description", "").strip(),
            "is_active": is_active,
        }
