"""Data helpers for EMS agency catalogue management."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from itertools import combinations
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Sequence

from utils.audit import write_audit
from utils.context import master_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & validation helpers
# ---------------------------------------------------------------------------

EMS_AGENCY_TYPES: tuple[str, ...] = (
    "Ambulance",
    "Hospital",
    "Air Ambulance",
    "Medical Aid",
    "Other",
)

_TABLE_FIELDS = (
    "name",
    "type",
    "phone",
    "radio_channel",
    "address",
    "city",
    "state",
    "zip",
    "lat",
    "lon",
    "notes",
    "default_on_206",
    "is_active",
    "updated_at",
    "created_at",
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS ems_agencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    phone TEXT,
    radio_channel TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    lat REAL,
    lon REAL,
    notes TEXT,
    default_on_206 INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    updated_at TEXT,
    created_at TEXT
)
"""

_INDEXES = {
    "idx_ems_agencies_name": "CREATE INDEX IF NOT EXISTS idx_ems_agencies_name ON ems_agencies(name)",
    "idx_ems_agencies_type": "CREATE INDEX IF NOT EXISTS idx_ems_agencies_type ON ems_agencies(type)",
    "idx_ems_agencies_phone": "CREATE INDEX IF NOT EXISTS idx_ems_agencies_phone ON ems_agencies(phone)",
}

# ---------------------------------------------------------------------------
# Normalisation helpers used for duplicate detection / search
# ---------------------------------------------------------------------------

_NAME_SANITISE_RE = re.compile(r"[^A-Z0-9]+")
_PHONE_SANITISE_RE = re.compile(r"\D+")


def normalize_name(value: str | None) -> str:
    """Return an upper-case identifier with punctuation removed."""
    if not value:
        return ""
    value = value.upper().strip()
    return _NAME_SANITISE_RE.sub("", value)


def normalize_phone(value: str | None) -> str:
    """Return digits-only phone token used to match duplicates."""
    if not value:
        return ""
    digits = _PHONE_SANITISE_RE.sub("", value)
    return digits


def sanitize_phone(value: str) -> str:
    """Collapse whitespace and ensure separators are consistent."""
    cleaned = value.replace(";", "/").replace(",", "/")
    cleaned = re.sub(r"\s*[/]\s*", " / ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


@dataclass
class DuplicateGroup:
    """Grouping of potential duplicate agencies."""

    candidate_ids: List[int]
    reason: str


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


@contextmanager
def _connect(factory: Callable[[], sqlite3.Connection]) -> Iterator[sqlite3.Connection]:
    conn = factory()
    try:
        yield conn
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def ensure_schema(conn_factory: Callable[[], sqlite3.Connection] = master_db) -> None:
    """Create the EMS agencies table + indexes when missing."""
    with _connect(conn_factory) as conn:
        conn.execute(_CREATE_SQL)
        for stmt in _INDEXES.values():
            conn.execute(stmt)


class EMSAgencyRepository:
    """Persistence layer handling CRUD & reporting for EMS agencies."""

    def __init__(self, conn_factory: Callable[[], sqlite3.Connection] = master_db) -> None:
        self._conn_factory = conn_factory
        ensure_schema(conn_factory)

    # ----- Helpers -----------------------------------------------------
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _conn(self) -> sqlite3.Connection:
        conn = self._conn_factory()
        conn.row_factory = sqlite3.Row
        return conn

    def _write_audit(self, action: str, detail: Mapping[str, Any]) -> None:
        try:
            write_audit(action, detail=dict(detail), prefer_mission=False)
        except Exception:  # pragma: no cover - audit failures shouldn't block CRUD
            logger.exception("Failed to write audit entry for %s", action)

    # ----- Query helpers ----------------------------------------------
    def list_agencies(
        self,
        *,
        search: str | None = None,
        include_inactive: bool = True,
        sort_key: str = "name",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        """Return agencies filtered by text search."""
        allowed_sort = {
            "name": "name COLLATE NOCASE",
            "type": "type COLLATE NOCASE",
            "updated_at": "updated_at",
            "city": "city COLLATE NOCASE",
        }
        order_sql = allowed_sort.get(sort_key, "name COLLATE NOCASE")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        query = "SELECT * FROM ems_agencies"
        clauses: list[str] = []
        params: list[Any] = []
        if not include_inactive:
            clauses.append("is_active = 1")
        if search:
            like = f"%{search.lower()}%"
            clauses.append(
                "(LOWER(name) LIKE ? OR LOWER(type) LIKE ? OR LOWER(phone) LIKE ? "
                "OR LOWER(radio_channel) LIKE ? OR LOWER(city) LIKE ? OR LOWER(state) LIKE ?)"
            )
            params.extend([like] * 6)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += f" ORDER BY {order_sql} {direction}, name COLLATE NOCASE ASC"

        with self._conn() as conn:
            cur = conn.execute(query, params)
            rows = [dict(row) for row in cur.fetchall()]
        return rows

    def list_by_ids(self, ids: Iterable[int]) -> list[dict[str, Any]]:
        values = list({int(i) for i in ids})
        if not values:
            return []
        placeholders = ",".join(["?"] * len(values))
        with self._conn() as conn:
            cur = conn.execute(
                f"SELECT * FROM ems_agencies WHERE id IN ({placeholders}) ORDER BY name COLLATE NOCASE",
                values,
            )
            return [dict(row) for row in cur.fetchall()]

    def get(self, agency_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            cur = conn.execute("SELECT * FROM ems_agencies WHERE id = ?", (int(agency_id),))
            row = cur.fetchone()
            return dict(row) if row else None

    # ----- Mutations ---------------------------------------------------
    def create(self, payload: Mapping[str, Any]) -> int:
        data = self._prepare_payload(payload, creating=True)
        now = self._now()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        columns = [c for c in _TABLE_FIELDS if c in data]
        values = [data.get(col) for col in columns]
        placeholders = ",".join(["?"] * len(columns))
        sql = f"INSERT INTO ems_agencies ({','.join(columns)}) VALUES ({placeholders})"
        with self._conn() as conn:
            cur = conn.execute(sql, values)
            new_id = int(cur.lastrowid)
        detail = {
            "id": new_id,
            "action": "create",
            "data": data,
        }
        self._write_audit("ems_agency.create", detail)
        return new_id

    def update(self, agency_id: int, payload: Mapping[str, Any]) -> None:
        existing = self.get(int(agency_id))
        if not existing:
            raise ValueError(f"Agency {agency_id} not found")
        data = self._prepare_payload(payload, creating=False)
        changes: MutableMapping[str, Any] = {}
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in data.items():
            if key not in existing or existing[key] != value:
                assignments.append(f"{key} = ?")
                values.append(value)
                changes[key] = {"old": existing.get(key), "new": value}
        if not assignments:
            return
        assignments.append("updated_at = ?")
        now = self._now()
        values.append(now)
        values.append(int(agency_id))
        sql = f"UPDATE ems_agencies SET {', '.join(assignments)} WHERE id = ?"
        with self._conn() as conn:
            conn.execute(sql, values)
        detail = {
            "id": int(agency_id),
            "action": "update",
            "changes": changes,
        }
        self._write_audit("ems_agency.update", detail)

    def set_active(self, agency_id: int, active: bool) -> None:
        existing = self.get(int(agency_id))
        if not existing:
            raise ValueError(f"Agency {agency_id} not found")
        if bool(existing.get("is_active")) == bool(active):
            return
        with self._conn() as conn:
            conn.execute(
                "UPDATE ems_agencies SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if active else 0, self._now(), int(agency_id)),
            )
        self._write_audit(
            "ems_agency.restore" if active else "ems_agency.deactivate",
            {"id": int(agency_id), "previous": bool(existing.get("is_active")), "active": bool(active)},
        )

    def merge(self, survivor_id: int, duplicate_ids: Iterable[int]) -> None:
        survivor_id = int(survivor_id)
        dupes = {int(i) for i in duplicate_ids if int(i) != survivor_id}
        if not dupes:
            return
        now = self._now()
        with self._conn() as conn:
            for dup_id in dupes:
                conn.execute(
                    "UPDATE ems_agencies SET is_active = 0, updated_at = ? WHERE id = ?",
                    (now, dup_id),
                )
        # TODO: migrate foreign-key references once consuming modules available
        detail = {
            "survivor": survivor_id,
            "merged": sorted(dupes),
        }
        self._write_audit("ems_agency.merge", detail)

    # ----- Duplicate detection ----------------------------------------
    def duplicate_groups(self) -> list[tuple[DuplicateGroup, list[dict[str, Any]]]]:
        """Return groups of potential duplicates with their member rows."""
        rows = self.list_agencies(include_inactive=True)
        by_id = {int(row["id"]): row for row in rows if row.get("id") is not None}
        groups: list[set[int]] = []

        # Group by normalised phone number (>=7 digits to avoid noise)
        phone_groups: dict[str, set[int]] = {}
        for row in rows:
            phone_key = normalize_phone(row.get("phone"))
            if len(phone_key) >= 7:
                phone_groups.setdefault(phone_key, set()).add(int(row["id"]))
        for ids in phone_groups.values():
            if len(ids) > 1:
                _merge_group(groups, ids)

        # Similar name detection using SequenceMatcher from stdlib
        from difflib import SequenceMatcher

        for a, b in combinations(by_id.values(), 2):
            name_a = normalize_name(a.get("name"))
            name_b = normalize_name(b.get("name"))
            if not name_a or not name_b:
                continue
            if name_a == name_b:
                _merge_group(groups, {int(a["id"]), int(b["id"])})
                continue
            ratio = SequenceMatcher(None, name_a, name_b).ratio()
            if ratio >= 0.9:
                _merge_group(groups, {int(a["id"]), int(b["id"])})

        result: list[tuple[DuplicateGroup, list[dict[str, Any]]]] = []
        for ids in groups:
            members = [by_id[i] for i in sorted(ids)]
            reason = "Shared phone" if any(
                len(normalize_phone(m.get("phone"))) >= 7
                and normalize_phone(m.get("phone")) == normalize_phone(members[0].get("phone"))
                for m in members
            ) else "Similar name"
            result.append((DuplicateGroup(sorted(ids), reason), members))
        return result

    # ----- Audit -------------------------------------------------------
    def list_audit_entries(
        self,
        *,
        limit: int = 250,
        start: str | None = None,
        end: str | None = None,
        user_filter: str | None = None,
        action_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch audit log rows related to EMS agencies."""
        conn = master_db()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                incident_number TEXT
                )"""
            )
            clauses = ["action LIKE 'ems_agency.%'"]
            params: list[Any] = []
            if start:
                clauses.append("ts_utc >= ?")
                params.append(start)
            if end:
                clauses.append("ts_utc <= ?")
                params.append(end)
            if user_filter:
                clauses.append("CAST(user_id AS TEXT) LIKE ?")
                params.append(f"%{user_filter}%")
            if action_filter:
                clauses.append("action = ?")
                params.append(action_filter)
            where = " WHERE " + " AND ".join(clauses)
            sql = (
                "SELECT id, ts_utc, user_id, action, detail, incident_number "
                "FROM audit_logs" + where + " ORDER BY id DESC LIMIT ?"
            )
            params.append(int(limit))
            cur = conn.execute(sql, params)
            rows = []
            for row in cur.fetchall():
                detail_payload: Any = None
                try:
                    detail_payload = json.loads(row["detail"]) if row["detail"] else None
                except Exception:
                    detail_payload = row["detail"]
                rows.append(
                    {
                        "id": row["id"],
                        "ts_utc": row["ts_utc"],
                        "user_id": row["user_id"],
                        "action": row["action"],
                        "detail": detail_payload,
                        "incident_number": row["incident_number"],
                    }
                )
        finally:
            conn.close()
        return rows

    # ----- Validation --------------------------------------------------
    def _prepare_payload(self, payload: Mapping[str, Any], *, creating: bool) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValueError("Name is required")
        data["name"] = name

        type_value = (payload.get("type") or "").strip()
        if type_value not in EMS_AGENCY_TYPES:
            raise ValueError("Type is required")
        data["type"] = type_value

        phone = payload.get("phone") or ""
        data["phone"] = sanitize_phone(phone) if phone else None

        data["radio_channel"] = (payload.get("radio_channel") or "").strip() or None
        data["address"] = (payload.get("address") or "").strip() or None
        data["city"] = (payload.get("city") or "").strip() or None
        data["state"] = (payload.get("state") or "").strip() or None
        data["zip"] = (payload.get("zip") or "").strip() or None

        for field in ("lat", "lon"):
            raw = payload.get(field)
            if raw in (None, ""):
                data[field] = None
                continue
            try:
                data[field] = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field.upper()} must be a number") from exc

        data["notes"] = (payload.get("notes") or "").strip() or None
        data["default_on_206"] = 1 if payload.get("default_on_206") else 0
        is_active = payload.get("is_active")
        if creating:
            data["is_active"] = 1 if is_active in (None, "", True, 1) else 0
        elif is_active is not None:
            data["is_active"] = 1 if is_active else 0
        return data


def _merge_group(groups: list[set[int]], new_ids: set[int]) -> None:
    """Merge overlapping sets so duplicates propagate."""
    merged = set(new_ids)
    keep: list[set[int]] = []
    for existing in groups:
        if existing & merged:
            merged |= existing
        else:
            keep.append(existing)
    keep.append(merged)
    groups[:] = keep


def map_agencies_to_sections(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Mapping[str, Any]]]:
    """Partition agencies into ICS-206 sections."""
    sections: Dict[str, List[Mapping[str, Any]]] = {
        "Ambulance Services / Air Ambulance": [],
        "Hospitals": [],
        "Medical Aid Stations": [],
        "Other": [],
    }
    for row in rows:
        r_type = str(row.get("type") or "").strip()
        if r_type in {"Ambulance", "Air Ambulance"}:
            key = "Ambulance Services / Air Ambulance"
        elif r_type == "Hospital":
            key = "Hospitals"
        elif r_type == "Medical Aid":
            key = "Medical Aid Stations"
        else:
            key = "Other"
        sections[key].append(dict(row))
    return sections


def import_to_ics206(
    repository: EMSAgencyRepository,
    agency_ids: Iterable[int],
    *,
    mode: str = "append",
) -> Dict[str, int]:
    """Stub integration point for ICS-206 import flow.

    Parameters
    ----------
    repository:
        Repository instance used to resolve row details.
    agency_ids:
        Identifiers selected in the UI.
    mode:
        ``"append"`` or ``"create"`` depending on user action.

    Returns
    -------
    dict
        Summary of how many entries map to each ICS-206 section.
    """
    rows = repository.list_by_ids(agency_ids)
    sections = map_agencies_to_sections(rows)
    summary = {name: len(items) for name, items in sections.items() if items}
    logger.info("[ems] Requested ICS-206 import (mode=%s): %s", mode, summary)
    if not rows:
        return summary
    # TODO: integrate with incident-scoped ICS-206 storage layer when available
    return summary


__all__ = [
    "EMS_AGENCY_TYPES",
    "DuplicateGroup",
    "EMSAgencyRepository",
    "ensure_schema",
    "normalize_name",
    "normalize_phone",
    "sanitize_phone",
    "map_agencies_to_sections",
    "import_to_ics206",
]
