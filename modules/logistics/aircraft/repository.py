"""SQLite-backed repository for aircraft catalog records.

The legacy application used a lightweight QML table backed by the master
catalog service.  This module replaces that stack with a richer data model that
supports the Aircraft Inventory widget.  The repository ensures the SQLite
schema is up to date and provides convenience helpers for CRUD and bulk
operations used by the UI.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # Optional helper available inside the full desktop build
    from utils.db import get_master_conn  # type: ignore
except Exception:  # pragma: no cover - optional dependency in tests
    get_master_conn = None  # type: ignore

ISO_FMT = "%Y-%m-%dT%H:%M:%S"

# ---------------------------------------------------------------------------
# Data model helpers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AircraftRecord:
    """Serializable aircraft record used by the UI layer."""

    tail_number: str
    id: Optional[int] = None
    callsign: str = ""
    type: str = "Helicopter"
    make: str = ""
    model: str = ""
    base: str = ""
    current_location: str = ""
    status: str = "Available"
    assigned_team_id: Optional[str] = None
    assigned_team_name: Optional[str] = None
    organization: Optional[str] = None
    fuel_type: str = "Jet A"
    range_nm: int = 0
    endurance_hr: float = 0.0
    cruise_kt: int = 0
    crew_min: int = 0
    crew_max: int = 0
    adsb_hex: str = ""
    radio_vhf_air: bool = False
    radio_vhf_sar: bool = False
    radio_uhf: bool = False
    cap_hoist: bool = False
    cap_nvg: bool = False
    cap_flir: bool = False
    cap_ifr: bool = False
    payload_kg: float = 0.0
    med_config: str = "None"
    serial_number: str = ""
    year: Optional[int] = None
    owner_operator: str = ""
    registration_exp: Optional[str] = None
    inspection_due: Optional[str] = None
    last_100hr: Optional[str] = None
    next_100hr: Optional[str] = None
    notes: str = ""
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        """Return a dictionary ready for persistence in SQLite."""

        make_model = " ".join(part for part in (self.make, self.model) if part).strip()
        payload: Dict[str, Any] = {
            "id": self.id,
            "tail_number": self.tail_number.strip().upper(),
            "callsign": self.callsign.strip(),
            "type": self.type.strip() or "Other",
            "make": self.make.strip(),
            "model": self.model.strip(),
            "base": self.base.strip(),
            "current_location": self.current_location.strip(),
            "status": self.status.strip() or "Available",
            "assigned_team_id": (self.assigned_team_id or None),
            "assigned_team_name": (self.assigned_team_name or None),
            "organization": (self.organization or None),
            "fuel_type": self.fuel_type or "Jet A",
            "range_nm": int(max(self.range_nm, 0)),
            "endurance_hr": max(float(self.endurance_hr), 0.0),
            "cruise_kt": int(max(self.cruise_kt, 0)),
            "crew_min": int(max(self.crew_min, 0)),
            "crew_max": int(max(self.crew_max, self.crew_min)),
            "adsb_hex": self.adsb_hex.strip().upper(),
            "radio_vhf_air": 1 if self.radio_vhf_air else 0,
            "radio_vhf_sar": 1 if self.radio_vhf_sar else 0,
            "radio_uhf": 1 if self.radio_uhf else 0,
            "cap_hoist": 1 if self.cap_hoist else 0,
            "cap_nvg": 1 if self.cap_nvg else 0,
            "cap_flir": 1 if self.cap_flir else 0,
            "cap_ifr": 1 if self.cap_ifr else 0,
            "payload_kg": float(max(self.payload_kg, 0.0)),
            "med_config": self.med_config or "None",
            "serial_number": self.serial_number.strip(),
            "year": int(self.year) if self.year else None,
            "owner_operator": self.owner_operator.strip(),
            "registration_exp": self.registration_exp or None,
            "inspection_due": self.inspection_due or None,
            "last_100hr": self.last_100hr or None,
            "next_100hr": self.next_100hr or None,
            "notes": self.notes.strip(),
            "make_model": make_model,
            "make_model_display": make_model,
            "attachments_json": json.dumps(self.attachments, ensure_ascii=False),
            "history_json": json.dumps(self.history, ensure_ascii=False),
        }
        payload["base_location"] = payload["base"] or None
        payload["current_assignment"] = payload["assigned_team_name"]
        payload["team_id"] = _coerce_int(self.assigned_team_id)
        payload["capacity"] = payload["crew_max"]
        payload["capabilities"] = _capabilities_text(self)
        return payload


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _coerce_int(value: Optional[str | int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    return bool(int(value)) if value not in (None, "", False) else False


def _capabilities_text(record: AircraftRecord) -> Optional[str]:
    caps: List[str] = []
    if record.cap_hoist:
        caps.append("Hoist")
    if record.cap_nvg:
        caps.append("Night Ops")
    if record.cap_flir:
        caps.append("FLIR")
    if record.cap_ifr:
        caps.append("IFR")
    return ", ".join(caps) if caps else None


def _now_iso() -> str:
    return datetime.utcnow().strftime(ISO_FMT)


# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------


class AircraftRepository:
    """Persistence helper for aircraft master catalog entries."""

    REQUIRED_COLUMNS: Dict[str, str] = {
        "callsign": "TEXT",
        "type": "TEXT NOT NULL DEFAULT 'Helicopter'",
        "make": "TEXT",
        "model": "TEXT",
        "base": "TEXT",
        "current_location": "TEXT",
        "assigned_team_id": "TEXT",
        "assigned_team_name": "TEXT",
        "organization": "TEXT",
        "fuel_type": "TEXT",
        "range_nm": "INTEGER DEFAULT 0",
        "endurance_hr": "REAL DEFAULT 0",
        "cruise_kt": "INTEGER DEFAULT 0",
        "crew_min": "INTEGER DEFAULT 0",
        "crew_max": "INTEGER DEFAULT 0",
        "adsb_hex": "TEXT",
        "radio_vhf_air": "INTEGER DEFAULT 0",
        "radio_vhf_sar": "INTEGER DEFAULT 0",
        "radio_uhf": "INTEGER DEFAULT 0",
        "cap_hoist": "INTEGER DEFAULT 0",
        "cap_nvg": "INTEGER DEFAULT 0",
        "cap_flir": "INTEGER DEFAULT 0",
        "cap_ifr": "INTEGER DEFAULT 0",
        "payload_kg": "REAL DEFAULT 0",
        "med_config": "TEXT",
        "serial_number": "TEXT",
        "year": "INTEGER",
        "owner_operator": "TEXT",
        "registration_exp": "TEXT",
        "inspection_due": "TEXT",
        "last_100hr": "TEXT",
        "next_100hr": "TEXT",
        "make_model": "TEXT",
        "make_model_display": "TEXT",
        "attachments_json": "TEXT",
        "history_json": "TEXT",
        "team_id": "INTEGER",
        "base_location": "TEXT",
        "current_assignment": "TEXT",
        "capacity": "INTEGER",
        "status": "TEXT NOT NULL DEFAULT 'Available'",
        "notes": "TEXT",
        "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    }

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else None
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        if self._db_path is not None:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            return conn
        if get_master_conn is None:
            raise RuntimeError("utils.db.get_master_conn is unavailable")
        conn = get_master_conn()
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='aircraft'"
            )
            exists = cur.fetchone() is not None
            if not exists:
                conn.execute(
                    """
                    CREATE TABLE aircraft (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tail_number TEXT NOT NULL UNIQUE,
                        callsign TEXT,
                        type TEXT NOT NULL DEFAULT 'Helicopter',
                        make TEXT,
                        model TEXT,
                        base TEXT,
                        current_location TEXT,
                        status TEXT NOT NULL DEFAULT 'Available',
                        assigned_team_id TEXT,
                        assigned_team_name TEXT,
                        organization TEXT,
                        fuel_type TEXT,
                        range_nm INTEGER DEFAULT 0,
                        endurance_hr REAL DEFAULT 0,
                        cruise_kt INTEGER DEFAULT 0,
                        crew_min INTEGER DEFAULT 0,
                        crew_max INTEGER DEFAULT 0,
                        adsb_hex TEXT,
                        radio_vhf_air INTEGER DEFAULT 0,
                        radio_vhf_sar INTEGER DEFAULT 0,
                        radio_uhf INTEGER DEFAULT 0,
                        cap_hoist INTEGER DEFAULT 0,
                        cap_nvg INTEGER DEFAULT 0,
                        cap_flir INTEGER DEFAULT 0,
                        cap_ifr INTEGER DEFAULT 0,
                        payload_kg REAL DEFAULT 0,
                        med_config TEXT,
                        serial_number TEXT,
                        year INTEGER,
                        owner_operator TEXT,
                        registration_exp TEXT,
                        inspection_due TEXT,
                        last_100hr TEXT,
                        next_100hr TEXT,
                        notes TEXT,
                        make_model TEXT,
                        make_model_display TEXT,
                        attachments_json TEXT,
                        history_json TEXT,
                        team_id INTEGER,
                        base_location TEXT,
                        current_assignment TEXT,
                        capacity INTEGER,
                        payload TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
                return

            cur = conn.execute("PRAGMA table_info('aircraft')")
            existing = {row[1] for row in cur.fetchall()}
            for column, ddl in self.REQUIRED_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE aircraft ADD COLUMN {column} {ddl}")
            conn.commit()
            # migrate legacy columns into the richer schema
            self._migrate_legacy_columns(conn)
        finally:
            conn.close()

    def _migrate_legacy_columns(self, conn: sqlite3.Connection) -> None:
        """Populate new columns from the previous schema if needed."""

        cur = conn.execute("PRAGMA table_info('aircraft')")
        existing = {row[1] for row in cur.fetchall()}
        if "make" in existing and "make_model" in existing:
            rows = conn.execute("SELECT id, make_model, make, model FROM aircraft").fetchall()
            for row in rows:
                make = row["make"] or ""
                model = row["model"] or ""
                if not make and not model:
                    parts = (row["make_model"] or "").split(None, 1)
                    if parts:
                        make = parts[0]
                        model = parts[1] if len(parts) > 1 else ""
                make_model = " ".join(p for p in (make, model) if p).strip()
                conn.execute(
                    """
                    UPDATE aircraft
                       SET make = ?,
                           model = ?,
                           make_model = ?,
                           make_model_display = COALESCE(make_model_display, ?)
                     WHERE id = ?
                    """,
                    (make or None, model or None, make_model or None, make_model or None, row["id"]),
                )
        if "base_location" in existing and "base" in existing:
            conn.execute(
                "UPDATE aircraft SET base = COALESCE(base, base_location)"
            )
        if "current_assignment" in existing and "assigned_team_name" in existing:
            conn.execute(
                "UPDATE aircraft SET assigned_team_name = COALESCE(assigned_team_name, current_assignment)"
            )
        conn.commit()

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def list_aircraft(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT * FROM aircraft ORDER BY tail_number COLLATE NOCASE"
            )
            rows = [self._row_to_dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
        return rows

    def fetch_aircraft(self, aircraft_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM aircraft WHERE id = ?", (aircraft_id,))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def find_by_tail(self, tail_number: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT * FROM aircraft WHERE tail_number = ?",
                (tail_number.strip().upper(),),
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def create_aircraft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = AircraftRecord(**payload)
        prepared = record.to_payload()
        prepared["created_at"] = prepared["updated_at"] = _now_iso()
        conn = self._connect()
        try:
            self._insert_payload(conn, prepared)
            aircraft_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        created = self.fetch_aircraft(int(aircraft_id))
        if created is None:  # pragma: no cover - defensive
            raise RuntimeError("Failed to load newly created aircraft")
        return created

    def update_aircraft(self, aircraft_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        current = self.fetch_aircraft(int(aircraft_id))
        if current is None:
            raise LookupError(f"Aircraft {aircraft_id} does not exist")
        merged = {**current, **payload, "id": aircraft_id, "tail_number": current["tail_number"]}
        record = AircraftRecord(**merged)
        prepared = record.to_payload()
        prepared["updated_at"] = _now_iso()
        columns = [
            "callsign",
            "type",
            "make",
            "model",
            "base",
            "current_location",
            "status",
            "assigned_team_id",
            "assigned_team_name",
            "organization",
            "fuel_type",
            "range_nm",
            "endurance_hr",
            "cruise_kt",
            "crew_min",
            "crew_max",
            "adsb_hex",
            "radio_vhf_air",
            "radio_vhf_sar",
            "radio_uhf",
            "cap_hoist",
            "cap_nvg",
            "cap_flir",
            "cap_ifr",
            "payload_kg",
            "med_config",
            "serial_number",
            "year",
            "owner_operator",
            "registration_exp",
            "inspection_due",
            "last_100hr",
            "next_100hr",
            "notes",
            "make_model",
            "make_model_display",
            "attachments_json",
            "history_json",
            "team_id",
            "base_location",
            "current_assignment",
            "capacity",
            "updated_at",
        ]
        conn = self._connect()
        try:
            assignments = ", ".join(f"{col} = ?" for col in columns)
            values = [prepared.get(col) for col in columns]
            values.append(aircraft_id)
            conn.execute(
                f"UPDATE aircraft SET {assignments} WHERE id = ?",
                values,
            )
            conn.commit()
        finally:
            conn.close()
        updated = self.fetch_aircraft(int(aircraft_id))
        if updated is None:  # pragma: no cover - defensive
            raise RuntimeError("Updated aircraft could not be reloaded")
        return updated

    def delete_aircraft(self, aircraft_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM aircraft WHERE id = ?", (aircraft_id,))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------
    def set_status(self, aircraft_ids: Iterable[int], status: str, notes: str = "") -> None:
        normalized = status.strip() or "Available"
        now = _now_iso()
        conn = self._connect()
        try:
            for aircraft_id in aircraft_ids:
                conn.execute(
                    "UPDATE aircraft SET status = ?, updated_at = ?, history_json = ? WHERE id = ?",
                    (
                        normalized,
                        now,
                        self._history_with_entry(
                            conn,
                            int(aircraft_id),
                            "status",
                            f"Set to {normalized}",
                            notes,
                        ),
                        int(aircraft_id),
                    ),
                )
                if normalized.lower() == "out of service":
                    conn.execute(
                        """
                        UPDATE aircraft
                           SET assigned_team_id = NULL,
                               assigned_team_name = NULL,
                               team_id = NULL,
                               current_assignment = NULL
                         WHERE id = ?
                        """,
                        (int(aircraft_id),),
                    )
            conn.commit()
        finally:
            conn.close()

    def assign_team(
        self, aircraft_ids: Iterable[int], team_id: Optional[str], team_name: Optional[str], notify: bool = False
    ) -> None:
        del notify  # notification handled upstream; stored for audit purposes only
        now = _now_iso()
        conn = self._connect()
        try:
            for aircraft_id in aircraft_ids:
                history = self._history_with_entry(
                    conn,
                    int(aircraft_id),
                    "assignment",
                    f"Assigned to {team_name or 'unassigned'}",
                    "",
                )
                conn.execute(
                    """
                    UPDATE aircraft
                       SET assigned_team_id = ?,
                           assigned_team_name = ?,
                           team_id = ?,
                           current_assignment = ?,
                           updated_at = ?,
                           history_json = ?
                     WHERE id = ?
                    """,
                    (
                        team_id,
                        team_name,
                        _coerce_int(team_id),
                        team_name,
                        now,
                        history,
                        int(aircraft_id),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def clear_assignment(self, aircraft_ids: Iterable[int]) -> None:
        now = _now_iso()
        conn = self._connect()
        try:
            for aircraft_id in aircraft_ids:
                history = self._history_with_entry(
                    conn,
                    int(aircraft_id),
                    "assignment",
                    "Assignment cleared",
                    "",
                )
                conn.execute(
                    """
                    UPDATE aircraft
                       SET assigned_team_id = NULL,
                           assigned_team_name = NULL,
                           team_id = NULL,
                           current_assignment = NULL,
                           updated_at = ?,
                           history_json = ?
                     WHERE id = ?
                    """,
                    (now, history, int(aircraft_id)),
                )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _insert_payload(self, conn: sqlite3.Connection, payload: Dict[str, Any]) -> None:
        columns = [
            "tail_number",
            "callsign",
            "type",
            "make",
            "model",
            "base",
            "current_location",
            "status",
            "assigned_team_id",
            "assigned_team_name",
            "organization",
            "fuel_type",
            "range_nm",
            "endurance_hr",
            "cruise_kt",
            "crew_min",
            "crew_max",
            "adsb_hex",
            "radio_vhf_air",
            "radio_vhf_sar",
            "radio_uhf",
            "cap_hoist",
            "cap_nvg",
            "cap_flir",
            "cap_ifr",
            "payload_kg",
            "med_config",
            "serial_number",
            "year",
            "owner_operator",
            "registration_exp",
            "inspection_due",
            "last_100hr",
            "next_100hr",
            "notes",
            "make_model",
            "make_model_display",
            "attachments_json",
            "history_json",
            "team_id",
            "base_location",
            "current_assignment",
            "capacity",
            "created_at",
            "updated_at",
        ]
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO aircraft ({', '.join(columns)}) VALUES ({placeholders})",
            [payload.get(col) for col in columns],
        )

    def _row_to_dict(self, row: sqlite3.Row | None) -> Dict[str, Any]:
        if row is None:
            return {}
        data = dict(row)
        history = []
        attachments = []
        if data.get("history_json"):
            try:
                history = json.loads(data["history_json"])
            except json.JSONDecodeError:
                history = []
        if data.get("attachments_json"):
            try:
                attachments = json.loads(data["attachments_json"])
            except json.JSONDecodeError:
                attachments = []
        make = data.get("make") or ""
        model = data.get("model") or ""
        if not make and not model:
            make_model = data.get("make_model") or ""
            parts = make_model.split(None, 1)
            make = parts[0] if parts else ""
            model = parts[1] if len(parts) > 1 else ""
        base = data.get("base") or data.get("base_location") or ""
        assigned_name = data.get("assigned_team_name") or data.get("current_assignment") or None
        return {
            "id": data.get("id"),
            "tail_number": data.get("tail_number") or "",
            "callsign": data.get("callsign") or "",
            "type": data.get("type") or data.get("make_model") or "",
            "make": make,
            "model": model,
            "base": base,
            "current_location": data.get("current_location") or "",
            "status": data.get("status") or "Available",
            "assigned_team_id": data.get("assigned_team_id"),
            "assigned_team_name": assigned_name,
            "organization": data.get("organization"),
            "fuel_type": data.get("fuel_type") or "Jet A",
            "range_nm": data.get("range_nm") or 0,
            "endurance_hr": data.get("endurance_hr") or 0.0,
            "cruise_kt": data.get("cruise_kt") or 0,
            "crew_min": data.get("crew_min") or 0,
            "crew_max": data.get("crew_max") or 0,
            "adsb_hex": data.get("adsb_hex") or "",
            "radio_vhf_air": _bool(data.get("radio_vhf_air")),
            "radio_vhf_sar": _bool(data.get("radio_vhf_sar")),
            "radio_uhf": _bool(data.get("radio_uhf")),
            "cap_hoist": _bool(data.get("cap_hoist")),
            "cap_nvg": _bool(data.get("cap_nvg")),
            "cap_flir": _bool(data.get("cap_flir")),
            "cap_ifr": _bool(data.get("cap_ifr")),
            "payload_kg": data.get("payload_kg") or 0.0,
            "med_config": data.get("med_config") or "None",
            "serial_number": data.get("serial_number") or "",
            "year": data.get("year"),
            "owner_operator": data.get("owner_operator") or "",
            "registration_exp": data.get("registration_exp"),
            "inspection_due": data.get("inspection_due"),
            "last_100hr": data.get("last_100hr"),
            "next_100hr": data.get("next_100hr"),
            "notes": data.get("notes") or "",
            "attachments": attachments,
            "history": history,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "make_model": data.get("make_model") or " ".join(filter(None, (make, model))).strip(),
        }

    def _history_with_entry(
        self,
        conn: sqlite3.Connection,
        aircraft_id: int,
        action: str,
        summary: str,
        notes: str,
        actor: str = "system",
    ) -> str:
        cur = conn.execute("SELECT history_json FROM aircraft WHERE id = ?", (aircraft_id,))
        row = cur.fetchone()
        history: List[Dict[str, Any]] = []
        if row and row[0]:
            try:
                history = json.loads(row[0])
            except json.JSONDecodeError:
                history = []
        history.append(
            {
                "ts": _now_iso(),
                "actor": actor,
                "action": action,
                "details": summary,
                "notes": notes,
            }
        )
        return json.dumps(history, ensure_ascii=False)
