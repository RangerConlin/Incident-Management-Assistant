"""SQLite-backed service for managing hospital catalog records."""

from __future__ import annotations

from dataclasses import asdict, fields
import sqlite3
from pathlib import Path
from typing import Sequence

from models.hospital import Hospital


_BOOL_COLUMNS = {
    "helipad",
    "burn_center",
    "pediatric_capability",
    "is_active",
}

_INT_COLUMNS = {
    "travel_time_min",
    "bed_available",
}

_FLOAT_COLUMNS = {
    "lat",
    "lon",
}

_SEARCHABLE = ["name", "city", "state", "code", "contact_name", "address"]


class HospitalService:
    """CRUD convenience wrapper around the ``hospitals`` table."""

    def __init__(self, db_path: str | Path = "data/master.db") -> None:
        self._db_path = str(db_path)
        self._field_names = {f.name for f in fields(Hospital)}
        self._available_columns = self._load_columns()
        if "name" not in self._available_columns:
            raise RuntimeError("hospitals table must include a 'name' column")

    # ----- Public API --------------------------------------------------
    @property
    def available_columns(self) -> list[str]:
        """Return the database-backed column names recognised by the service."""

        return list(self._available_columns)

    def list_hospitals(self, search: str | None = None) -> list[Hospital]:
        columns = ", ".join(self._available_columns)
        sql = f"SELECT {columns} FROM hospitals"
        params: list[str] = []
        where_clauses: list[str] = []

        if search:
            pattern = f"%{search.lower()}%"
            for col in _SEARCHABLE:
                if col in self._available_columns:
                    where_clauses.append(f"LOWER(IFNULL({col}, '')) LIKE ?")
                    params.append(pattern)
            if where_clauses:
                sql += " WHERE " + " OR ".join(where_clauses)

        sql += " ORDER BY name COLLATE NOCASE"

        with self._connect() as con:
            cur = con.execute(sql, params)
            rows = cur.fetchall()

        return [self._row_to_hospital(row) for row in rows]

    def get_hospital_by_id(self, hospital_id: int) -> Hospital | None:
        columns = ", ".join(self._available_columns)
        sql = f"SELECT {columns} FROM hospitals WHERE id=?"
        with self._connect() as con:
            cur = con.execute(sql, (hospital_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_hospital(row)

    def create_hospital(self, hospital: Hospital) -> int:
        payload = self._prepare_payload(hospital, include_id=False)
        if not hospital.name.strip():
            raise ValueError("Hospital name is required")
        self._assert_unique(hospital.name, hospital.code or None, None)

        columns = ", ".join(payload.keys())
        placeholders = ", ".join(["?"] * len(payload))
        sql = f"INSERT INTO hospitals ({columns}) VALUES ({placeholders})"
        values = list(payload.values())
        with self._connect() as con:
            cur = con.execute(sql, values)
            con.commit()
            return int(cur.lastrowid)

    def update_hospital(self, hospital: Hospital) -> None:
        if hospital.id is None:
            raise ValueError("Hospital id is required for updates")
        if not hospital.name.strip():
            raise ValueError("Hospital name is required")

        payload = self._prepare_payload(hospital, include_id=False)
        if not payload:
            return

        self._assert_unique(hospital.name, hospital.code or None, hospital.id)

        assignments = ", ".join(f"{col}=?" for col in payload.keys())
        sql = f"UPDATE hospitals SET {assignments} WHERE id=?"
        values = list(payload.values()) + [hospital.id]
        with self._connect() as con:
            con.execute(sql, values)
            con.commit()

    def delete_hospitals(self, hospital_ids: Sequence[int]) -> None:
        ids = [int(v) for v in hospital_ids if v is not None]
        if not ids:
            return
        placeholders = ", ".join(["?"] * len(ids))
        sql = f"DELETE FROM hospitals WHERE id IN ({placeholders})"
        with self._connect() as con:
            con.execute(sql, ids)
            con.commit()

    # ----- Internal utilities -----------------------------------------
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        return con

    def _load_columns(self) -> list[str]:
        with self._connect() as con:
            cur = con.execute("PRAGMA table_info(hospitals)")
            rows = cur.fetchall()

        columns = [str(row[1]) for row in rows]
        if not columns:
            raise RuntimeError("hospitals table not found in database")

        # Keep only fields supported by the dataclass to avoid surprises.
        return [col for col in columns if col in self._field_names]

    def _row_to_hospital(self, row: sqlite3.Row) -> Hospital:
        hospital = Hospital()
        for col in self._available_columns:
            if col not in row.keys():  # defensive: unexpected schema change
                continue
            value = row[col]
            if col in _BOOL_COLUMNS:
                setattr(hospital, col, self._to_bool(value))
            elif col in _INT_COLUMNS:
                setattr(hospital, col, self._to_int(value))
            elif col in _FLOAT_COLUMNS:
                setattr(hospital, col, self._to_float(value))
            else:
                setattr(hospital, col, value if value is not None else "")
        return hospital

    def _prepare_payload(self, hospital: Hospital, *, include_id: bool) -> dict[str, object]:
        data = asdict(hospital)
        payload: dict[str, object] = {}
        for col in self._available_columns:
            if col == "id" and not include_id:
                continue
            if col not in data:
                continue
            value = data[col]
            if col in _BOOL_COLUMNS:
                payload[col] = None if value is None else int(bool(value))
            elif col in _INT_COLUMNS:
                payload[col] = None if value in (None, "") else int(value)
            elif col in _FLOAT_COLUMNS:
                payload[col] = None if value in (None, "") else float(value)
            else:
                payload[col] = value
        return payload

    def _assert_unique(self, name: str, code: str | None, exclude_id: int | None) -> None:
        # Name uniqueness is advisory; enforce only if column exists.
        if "name" in self._available_columns:
            self._ensure_unique("name", name, exclude_id)
        if code and "code" in self._available_columns:
            self._ensure_unique("code", code, exclude_id)

    def _ensure_unique(self, column: str, value: str, exclude_id: int | None) -> None:
        sql = f"SELECT id FROM hospitals WHERE LOWER(IFNULL({column}, '')) = ?"
        params: list[object] = [value.lower()]
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)

        with self._connect() as con:
            cur = con.execute(sql, params)
            row = cur.fetchone()
        if row is not None:
            raise ValueError(f"A hospital with the same {column} already exists")

    @staticmethod
    def _to_bool(value: object) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            if isinstance(value, str):
                return value.strip().lower() in {"true", "t", "yes", "y"}
            return None

    @staticmethod
    def _to_int(value: object) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = ["HospitalService"]

