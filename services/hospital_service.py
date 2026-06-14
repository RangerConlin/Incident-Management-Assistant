"""MongoDB-backed service for managing hospital catalog records."""

from __future__ import annotations

from dataclasses import asdict, fields
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from models.hospital import Hospital
from modules.medical.data.mongo_access import get_master_db, strip_mongo_id


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
    """CRUD convenience wrapper around the master ``hospitals`` collection."""

    def __init__(self, db_path: str | Path = "data/master.db", db: Any = None) -> None:
        # ``db_path`` is retained for compatibility with existing callers.
        self._db = db or get_master_db()
        self._col = self._db["hospitals"]
        self._field_names = {f.name for f in fields(Hospital)}
        self._available_columns = list(self._field_names)
        self._ensure_indexes()

    @property
    def available_columns(self) -> list[str]:
        """Return the database-backed column names recognised by the service."""
        return list(self._available_columns)

    def list_hospitals(self, search: str | None = None) -> list[Hospital]:
        query: dict[str, Any] = {"deleted": {"$ne": True}}
        if search:
            import re

            pattern = {"$regex": re.escape(search), "$options": "i"}
            query["$or"] = [{field: pattern} for field in _SEARCHABLE]
        rows = self._col.find(query).sort("name", 1)
        return [self._document_to_hospital(row) for row in rows]

    def get_hospital_by_id(self, hospital_id: int) -> Hospital | None:
        row = self._col.find_one({"id": int(hospital_id), "deleted": {"$ne": True}})
        if row is None:
            return None
        return self._document_to_hospital(row)

    def create_hospital(self, hospital: Hospital) -> int:
        if not hospital.name.strip():
            raise ValueError("Hospital name is required")
        self._assert_unique(hospital.name, hospital.code or None, None)
        new_id = self._next_id()
        payload = self._prepare_payload(hospital)
        payload["id"] = new_id
        payload["hospital_id"] = str(new_id)
        payload["deleted"] = False
        self._col.insert_one(payload)
        return new_id

    def update_hospital(self, hospital: Hospital) -> None:
        if hospital.id is None:
            raise ValueError("Hospital id is required for updates")
        if not hospital.name.strip():
            raise ValueError("Hospital name is required")
        self._assert_unique(hospital.name, hospital.code or None, hospital.id)
        payload = self._prepare_payload(hospital)
        payload["hospital_id"] = str(hospital.id)
        self._col.update_one({"id": int(hospital.id)}, {"$set": payload})

    def delete_hospitals(self, hospital_ids: Sequence[int]) -> None:
        ids = [int(v) for v in hospital_ids if v is not None]
        if not ids:
            return
        self._col.update_many({"id": {"$in": ids}}, {"$set": {"deleted": True}})

    def _ensure_indexes(self) -> None:
        self._col.create_index([("id", 1)], unique=True)
        self._col.create_index([("hospital_id", 1)])
        self._col.create_index([("name", 1)])
        self._col.create_index([("state", 1)])
        self._col.create_index([("trauma_level", 1)])

    def _next_id(self) -> int:
        row = self._col.find_one(sort=[("id", -1)], projection={"id": 1})
        return int(row["id"]) + 1 if row and row.get("id") is not None else 1

    def _document_to_hospital(self, document: Mapping[str, Any]) -> Hospital:
        row = strip_mongo_id(dict(document)) or {}
        if "id" not in row and row.get("hospital_id"):
            row["id"] = self._coerce_int(row.get("hospital_id"))
        hospital = Hospital()
        for col in self._available_columns:
            if col not in row:
                continue
            value = row[col]
            if col in _BOOL_COLUMNS:
                setattr(hospital, col, self._to_bool(value))
            elif col in _INT_COLUMNS:
                setattr(hospital, col, self._to_int(value))
            elif col in _FLOAT_COLUMNS:
                setattr(hospital, col, self._to_float(value))
            elif col == "id":
                setattr(hospital, col, self._to_int(value))
            else:
                setattr(hospital, col, value if value is not None else "")
        return hospital

    def _prepare_payload(self, hospital: Hospital) -> dict[str, object]:
        data = asdict(hospital)
        payload: dict[str, object] = {}
        for col in self._available_columns:
            if col not in data or col == "id":
                continue
            value = data[col]
            if col in _BOOL_COLUMNS:
                payload[col] = None if value is None else bool(value)
            elif col in _INT_COLUMNS:
                payload[col] = None if value in (None, "") else int(value)
            elif col in _FLOAT_COLUMNS:
                payload[col] = None if value in (None, "") else float(value)
            else:
                payload[col] = value
        return payload

    def _assert_unique(self, name: str, code: str | None, exclude_id: int | None) -> None:
        self._ensure_unique("name", name, exclude_id)
        if code:
            self._ensure_unique("code", code, exclude_id)

    def _ensure_unique(self, column: str, value: str, exclude_id: int | None) -> None:
        query: dict[str, Any] = {
            column: {"$regex": f"^{re.escape(value)}$", "$options": "i"},
            "deleted": {"$ne": True},
        }
        if exclude_id is not None:
            query["id"] = {"$ne": int(exclude_id)}
        if self._col.find_one(query, projection={"id": 1}) is not None:
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
    def _coerce_int(value: object) -> int | None:
        return HospitalService._to_int(value)

    @staticmethod
    def _to_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = ["HospitalService"]
