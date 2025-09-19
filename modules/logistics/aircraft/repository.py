"""Persistence helpers for the Aircraft Inventory window.

This module owns the SQLite backing store for aircraft metadata.  It mirrors the
vehicle repository approach so the UI can remain fully widget based and avoid
any QML dependencies.  The repository is intentionally self-contained: it
creates the table on demand, normalises payloads, and exposes higher level
methods used by the UI (listing with filters, CRUD operations, bulk actions,
and import/export helpers).

The schema follows the product specification included with this task.  Only the
columns required by the UI contract are created.  Storage uses primitive types
compatible with SQLite – complex values such as attachments and history are
serialised as JSON strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence

try:  # Optional import used outside of tests
    from utils.db import get_master_conn  # type: ignore
except Exception:  # pragma: no cover - optional dependency when utils.db absent
    get_master_conn = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AircraftRecord:
    """In-memory representation of a single aircraft record."""

    id: int | None
    tail_number: str
    callsign: str | None = None
    type: str = "Other"
    make: str | None = None
    model: str | None = None
    make_model_display: str | None = None
    base: str | None = None
    current_location: str | None = None
    status: str = "Available"
    assigned_team_id: str | None = None
    assigned_team_name: str | None = None
    fuel_type: str | None = None
    range_nm: int | None = None
    endurance_hr: float | None = None
    cruise_kt: int | None = None
    crew_min: int | None = None
    crew_max: int | None = None
    adsb_hex: str | None = None
    radio_vhf_air: bool = False
    radio_vhf_sar: bool = False
    radio_uhf: bool = False
    cap_hoist: bool = False
    cap_nvg: bool = False
    cap_flir: bool = False
    cap_ifr: bool = False
    payload_kg: int | None = None
    med_config: str | None = None
    serial_number: str | None = None
    year: int | None = None
    owner_operator: str | None = None
    registration_exp: str | None = None
    inspection_due: str | None = None
    last_100hr: str | None = None
    next_100hr: str | None = None
    notes: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None

    def to_table_row(self) -> dict[str, Any]:
        """Return a dict that matches the SQLite table schema."""

        return {
            "tail_number": self.tail_number,
            "callsign": self.callsign,
            "type": self.type,
            "make": self.make,
            "model": self.model,
            "make_model_display": self.make_model_display or self._compose_display(),
            "base": self.base,
            "current_location": self.current_location,
            "status": self.status,
            "assigned_team_id": self.assigned_team_id,
            "assigned_team_name": self.assigned_team_name,
            "fuel_type": self.fuel_type,
            "range_nm": self.range_nm,
            "endurance_hr": self.endurance_hr,
            "cruise_kt": self.cruise_kt,
            "crew_min": self.crew_min,
            "crew_max": self.crew_max,
            "adsb_hex": self._normalise_hex(self.adsb_hex),
            "radio_vhf_air": int(bool(self.radio_vhf_air)),
            "radio_vhf_sar": int(bool(self.radio_vhf_sar)),
            "radio_uhf": int(bool(self.radio_uhf)),
            "cap_hoist": int(bool(self.cap_hoist)),
            "cap_nvg": int(bool(self.cap_nvg)),
            "cap_flir": int(bool(self.cap_flir)),
            "cap_ifr": int(bool(self.cap_ifr)),
            "payload_kg": self.payload_kg,
            "med_config": self.med_config,
            "serial_number": self.serial_number,
            "year": self.year,
            "owner_operator": self.owner_operator,
            "registration_exp": self.registration_exp,
            "inspection_due": self.inspection_due,
            "last_100hr": self.last_100hr,
            "next_100hr": self.next_100hr,
            "notes": self.notes,
            "attachments": json.dumps(self.attachments, ensure_ascii=False),
            "history": json.dumps(self.history, ensure_ascii=False),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def _compose_display(self) -> str:
        parts = [p.strip() for p in (self.make or "", self.model or "") if p]
        return " ".join(parts)

    @staticmethod
    def _normalise_hex(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip().upper()
        return cleaned or None


# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------


class AircraftRepository:
    """SQLite-backed repository for aircraft records."""

    TABLE_NAME = "aircraft_inventory"

    SORT_COLUMNS: dict[str, str] = {
        "name": "make_model_display",
        "tail_number": "tail_number",
        "type": "type",
        "status": "status",
        "base": "base",
        "fuel": "fuel_type",
        "endurance": "endurance_hr",
        "updated": "updated_at",
    }

    DEFAULT_TYPES = ["Helicopter", "Fixed-Wing", "UAS", "Gyroplane", "Other"]
    DEFAULT_STATUSES = [
        "Available",
        "Assigned",
        "Out of Service",
        "Standby",
        "In Transit",
    ]
    DEFAULT_FUELS = ["Jet A", "Avgas", "Electric", "Other"]
    DEFAULT_MED_CONFIGS = ["None", "Basic", "Advanced"]

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else None
        self._ensure_schema()

    # -- schema ---------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        if self._db_path is not None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            return conn
        if get_master_conn is None:
            raise RuntimeError("No database path provided and utils.db.get_master_conn() unavailable")
        conn = get_master_conn()
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tail_number TEXT NOT NULL UNIQUE,
                    callsign TEXT,
                    type TEXT NOT NULL,
                    make TEXT,
                    model TEXT,
                    make_model_display TEXT,
                    base TEXT,
                    current_location TEXT,
                    status TEXT NOT NULL,
                    assigned_team_id TEXT,
                    assigned_team_name TEXT,
                    fuel_type TEXT,
                    range_nm INTEGER,
                    endurance_hr REAL,
                    cruise_kt INTEGER,
                    crew_min INTEGER,
                    crew_max INTEGER,
                    adsb_hex TEXT,
                    radio_vhf_air INTEGER NOT NULL DEFAULT 0,
                    radio_vhf_sar INTEGER NOT NULL DEFAULT 0,
                    radio_uhf INTEGER NOT NULL DEFAULT 0,
                    cap_hoist INTEGER NOT NULL DEFAULT 0,
                    cap_nvg INTEGER NOT NULL DEFAULT 0,
                    cap_flir INTEGER NOT NULL DEFAULT 0,
                    cap_ifr INTEGER NOT NULL DEFAULT 0,
                    payload_kg INTEGER,
                    med_config TEXT,
                    serial_number TEXT,
                    year INTEGER,
                    owner_operator TEXT,
                    registration_exp TEXT,
                    inspection_due TEXT,
                    last_100hr TEXT,
                    next_100hr TEXT,
                    notes TEXT,
                    attachments TEXT,
                    history TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    # -- helpers --------------------------------------------------------
    @staticmethod
    def _utc_now() -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat(timespec="seconds") + "Z"

    @staticmethod
    def _decode_json(value: str | None) -> list[dict[str, Any]]:
        if not value:
            return []
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        return []

    def _row_to_record(self, row: sqlite3.Row) -> AircraftRecord:
        record = AircraftRecord(
            id=row["id"],
            tail_number=row["tail_number"],
            callsign=row["callsign"],
            type=row["type"],
            make=row["make"],
            model=row["model"],
            make_model_display=row["make_model_display"],
            base=row["base"],
            current_location=row["current_location"],
            status=row["status"],
            assigned_team_id=row["assigned_team_id"],
            assigned_team_name=row["assigned_team_name"],
            fuel_type=row["fuel_type"],
            range_nm=row["range_nm"],
            endurance_hr=row["endurance_hr"],
            cruise_kt=row["cruise_kt"],
            crew_min=row["crew_min"],
            crew_max=row["crew_max"],
            adsb_hex=row["adsb_hex"],
            radio_vhf_air=bool(row["radio_vhf_air"]),
            radio_vhf_sar=bool(row["radio_vhf_sar"]),
            radio_uhf=bool(row["radio_uhf"]),
            cap_hoist=bool(row["cap_hoist"]),
            cap_nvg=bool(row["cap_nvg"]),
            cap_flir=bool(row["cap_flir"]),
            cap_ifr=bool(row["cap_ifr"]),
            payload_kg=row["payload_kg"],
            med_config=row["med_config"],
            serial_number=row["serial_number"],
            year=row["year"],
            owner_operator=row["owner_operator"],
            registration_exp=row["registration_exp"],
            inspection_due=row["inspection_due"],
            last_100hr=row["last_100hr"],
            next_100hr=row["next_100hr"],
            notes=row["notes"],
            attachments=self._decode_json(row["attachments"]),
            history=self._decode_json(row["history"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        if not record.make_model_display:
            record.make_model_display = record._compose_display()
        return record

    # -- query helpers --------------------------------------------------
    def _build_where(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        search = (filters.get("search") or "").strip().lower()
        if search:
            like = f"%{search}%"
            clauses.append(
                "(" + " OR ".join(
                    [
                        "LOWER(tail_number) LIKE ?",
                        "LOWER(callsign) LIKE ?",
                        "LOWER(make) LIKE ?",
                        "LOWER(model) LIKE ?",
                        "LOWER(adsb_hex) LIKE ?",
                        "LOWER(base) LIKE ?",
                    ]
                ) + ")"
            )
            params.extend([like] * 6)

        if value := filters.get("type"):
            if value not in ("All", None):
                clauses.append("LOWER(type) = ?")
                params.append(value.lower())

        if value := filters.get("status"):
            if value not in ("All", None):
                clauses.append("LOWER(status) = ?")
                params.append(value.lower())

        if value := filters.get("base"):
            if value not in ("All", None):
                clauses.append("LOWER(base) = ?")
                params.append(value.lower())

        fuels: Iterable[str] = filters.get("fuels") or []
        fuels = [f for f in fuels if f]
        if fuels:
            placeholders = ",".join(["?"] * len(fuels))
            clauses.append(f"fuel_type IN ({placeholders})")
            params.extend(fuels)

        capabilities: Iterable[str] = filters.get("capabilities") or []
        capability_map = {
            "Hoist": "cap_hoist",
            "NVG": "cap_nvg",
            "FLIR": "cap_flir",
            "IFR": "cap_ifr",
        }
        for cap in capabilities:
            col = capability_map.get(cap)
            if col:
                clauses.append(f"{col} = 1")

        if filters.get("night_ops"):
            clauses.append("cap_nvg = 1")
        if filters.get("ifr"):
            clauses.append("cap_ifr = 1")
        if filters.get("hoist"):
            clauses.append("cap_hoist = 1")
        if filters.get("flir"):
            clauses.append("cap_flir = 1")

        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return where, params

    def _build_order(self, sort_key: str, sort_order: str) -> str:
        column = self.SORT_COLUMNS.get(sort_key, "tail_number")
        direction = "DESC" if sort_order.lower() in {"desc", "descending"} else "ASC"
        return f" ORDER BY {column} {direction}"

    # -- public API -----------------------------------------------------
    def list_aircraft(
        self,
        filters: dict[str, Any] | None = None,
        *,
        sort_key: str = "tail_number",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AircraftRecord], int]:
        filters = filters or {}
        where, params = self._build_where(filters)
        order = self._build_order(sort_key, sort_order)

        conn = self._connect()
        try:
            query = (
                f"SELECT * FROM {self.TABLE_NAME}{where}{order} LIMIT ? OFFSET ?"
            )
            rows = conn.execute(query, (*params, limit, offset)).fetchall()
            total = conn.execute(
                f"SELECT COUNT(*) FROM {self.TABLE_NAME}{where}", params
            ).fetchone()[0]
        finally:
            conn.close()

        return [self._row_to_record(row) for row in rows], int(total)

    def fetch_aircraft(self, aircraft_id: int) -> AircraftRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?",
                (aircraft_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_record(row) if row else None

    def create_aircraft(self, payload: dict[str, Any]) -> AircraftRecord:
        record = self._payload_to_record(payload, new_record=True)
        timestamp = self._utc_now()
        record.created_at = timestamp
        record.updated_at = timestamp
        record.history.append({
            "ts": timestamp,
            "actor": payload.get("actor", "system"),
            "action": "Created",
            "details": payload.get("history_details") or "Record created",
        })

        data = record.to_table_row()
        conn = self._connect()
        try:
            cur = conn.execute(
                f"""
                INSERT INTO {self.TABLE_NAME} (
                    tail_number, callsign, type, make, model, make_model_display,
                    base, current_location, status, assigned_team_id, assigned_team_name,
                    fuel_type, range_nm, endurance_hr, cruise_kt, crew_min, crew_max,
                    adsb_hex, radio_vhf_air, radio_vhf_sar, radio_uhf,
                    cap_hoist, cap_nvg, cap_flir, cap_ifr, payload_kg, med_config,
                    serial_number, year, owner_operator, registration_exp,
                    inspection_due, last_100hr, next_100hr, notes, attachments,
                    history, created_at, updated_at
                ) VALUES (
                    :tail_number, :callsign, :type, :make, :model, :make_model_display,
                    :base, :current_location, :status, :assigned_team_id, :assigned_team_name,
                    :fuel_type, :range_nm, :endurance_hr, :cruise_kt, :crew_min, :crew_max,
                    :adsb_hex, :radio_vhf_air, :radio_vhf_sar, :radio_uhf,
                    :cap_hoist, :cap_nvg, :cap_flir, :cap_ifr, :payload_kg, :med_config,
                    :serial_number, :year, :owner_operator, :registration_exp,
                    :inspection_due, :last_100hr, :next_100hr, :notes, :attachments,
                    :history, :created_at, :updated_at
                )
                """,
                data,
            )
            conn.commit()
            new_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("Tail number must be unique") from exc
        finally:
            conn.close()

        created = self.fetch_aircraft(new_id)
        if created is None:  # pragma: no cover - defensive fallback
            raise RuntimeError("Aircraft creation failed")
        return created

    def update_aircraft(self, aircraft_id: int, patch: dict[str, Any]) -> AircraftRecord:
        existing = self.fetch_aircraft(aircraft_id)
        if existing is None:
            raise LookupError(f"Aircraft {aircraft_id} not found")

        record = self._payload_to_record(patch, new_record=False, base=existing)
        timestamp = self._utc_now()
        record.id = aircraft_id
        record.created_at = existing.created_at
        record.updated_at = timestamp

        if record.status == "Out of Service":
            record.assigned_team_id = None
            record.assigned_team_name = None

        history_entry = patch.get("history_entry")
        if isinstance(history_entry, dict):
            history = existing.history + [history_entry]
        else:
            history = existing.history + [
                {
                    "ts": timestamp,
                    "actor": patch.get("actor", "system"),
                    "action": "Updated",
                    "details": patch.get("history_details") or "Fields updated",
                }
            ]
        record.history = history

        data = record.to_table_row()
        placeholders = ", ".join(f"{key} = :{key}" for key in data.keys())
        data["id"] = aircraft_id

        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE {self.TABLE_NAME} SET {placeholders} WHERE id = :id",
                data,
            )
            conn.commit()
        finally:
            conn.close()

        updated = self.fetch_aircraft(aircraft_id)
        if updated is None:  # pragma: no cover - defensive fallback
            raise RuntimeError("Failed to reload aircraft after update")
        return updated

    def delete_aircraft(self, aircraft_ids: Sequence[int]) -> int:
        if not aircraft_ids:
            return 0
        conn = self._connect()
        try:
            placeholders = ",".join(["?"] * len(aircraft_ids))
            cur = conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE id IN ({placeholders})",
                tuple(aircraft_ids),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    # -- bulk operations ------------------------------------------------
    def set_status(self, aircraft_ids: Sequence[int], status: str, notes: str | None = None) -> list[AircraftRecord]:
        updated_records: list[AircraftRecord] = []
        for aircraft_id in aircraft_ids:
            payload = {
                "status": status,
                "notes": notes or None,
                "history_details": f"Status set to {status}" + (f" ({notes})" if notes else ""),
            }
            updated_records.append(self.update_aircraft(aircraft_id, payload))
        return updated_records

    def assign_team(
        self,
        aircraft_ids: Sequence[int],
        team_id: str | None,
        team_name: str | None,
    ) -> list[AircraftRecord]:
        updated: list[AircraftRecord] = []
        for aircraft_id in aircraft_ids:
            payload = {
                "assigned_team_id": team_id,
                "assigned_team_name": team_name,
                "history_details": (
                    f"Assigned to {team_name or '(none)'}"
                    if team_name
                    else "Assignment cleared"
                ),
            }
            updated.append(self.update_aircraft(aircraft_id, payload))
        return updated

    def clear_assignment(self, aircraft_ids: Sequence[int]) -> list[AircraftRecord]:
        return self.assign_team(aircraft_ids, None, None)

    # -- import/export --------------------------------------------------
    def export_rows(
        self,
        filters: dict[str, Any] | None = None,
        *,
        sort_key: str = "tail_number",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        rows, _ = self.list_aircraft(filters, sort_key=sort_key, sort_order=sort_order, limit=10_000, offset=0)
        return [row.to_table_row() | {"id": row.id} for row in rows]

    def import_rows(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        update_existing: bool = True,
        conflict_mode: str = "skip",
    ) -> dict[str, int]:
        inserted = 0
        updated = 0
        for payload in rows:
            tail = (payload.get("tail_number") or "").strip()
            if not tail:
                continue
            existing = self.find_by_tail_number(tail)
            if existing is None:
                self.create_aircraft(payload)
                inserted += 1
                continue
            if not update_existing:
                continue
            if conflict_mode == "skip":
                continue
            if conflict_mode == "overwrite":
                self.update_aircraft(existing.id or 0, payload)
                updated += 1
            elif conflict_mode == "merge":
                merged_payload = {**existing.to_table_row(), **payload}
                self.update_aircraft(existing.id or 0, merged_payload)
                updated += 1
        return {"inserted": inserted, "updated": updated}

    def find_by_tail_number(self, tail_number: str) -> AircraftRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {self.TABLE_NAME} WHERE LOWER(tail_number) = ?",
                (tail_number.strip().lower(),),
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_record(row) if row else None

    def ensure_seed_data(self, seed_path: str | os.PathLike[str] | None = None) -> int:
        """Populate the repository with demo data if it is currently empty."""

        conn = self._connect()
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME}").fetchone()
            if row and row[0]:
                return 0
        finally:
            conn.close()

        path = Path(seed_path) if seed_path is not None else Path("data/examples/aircraft_inventory_seed.json")
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as fh:
            try:
                payload = json.load(fh)
            except json.JSONDecodeError:
                return 0
        if not isinstance(payload, list):
            return 0
        result = self.import_rows(payload, update_existing=False, conflict_mode="skip")
        return int(result.get("inserted", 0))

    # -- payload conversion --------------------------------------------
    def _payload_to_record(
        self,
        payload: dict[str, Any],
        *,
        new_record: bool,
        base: AircraftRecord | None = None,
    ) -> AircraftRecord:
        base_record = base or AircraftRecord(id=None, tail_number="", type="Other")

        def _get(key: str, default: Any = None) -> Any:
            if key in payload:
                return payload.get(key)
            return getattr(base_record, key, default)

        def _parse_int(value: Any) -> int | None:
            if value in (None, ""):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _parse_float(value: Any) -> float | None:
            if value in (None, ""):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        record = AircraftRecord(
            id=base_record.id,
            tail_number=str(_get("tail_number", base_record.tail_number)).strip(),
            callsign=_clean_str(_get("callsign")),
            type=_clean_enum(_get("type"), self.DEFAULT_TYPES, base_record.type),
            make=_clean_str(_get("make")),
            model=_clean_str(_get("model")),
            make_model_display=_clean_str(_get("make_model_display")),
            base=_clean_str(_get("base")),
            current_location=_clean_str(_get("current_location")),
            status=_clean_enum(_get("status"), self.DEFAULT_STATUSES, base_record.status),
            assigned_team_id=_clean_str(_get("assigned_team_id")),
            assigned_team_name=_clean_str(_get("assigned_team_name")),
            fuel_type=_clean_enum(_get("fuel_type"), self.DEFAULT_FUELS, base_record.fuel_type),
            range_nm=_parse_int(_get("range_nm")),
            endurance_hr=_parse_float(_get("endurance_hr")),
            cruise_kt=_parse_int(_get("cruise_kt")),
            crew_min=_parse_int(_get("crew_min")),
            crew_max=_parse_int(_get("crew_max")),
            adsb_hex=_clean_hex(_get("adsb_hex")),
            radio_vhf_air=bool(_get("radio_vhf_air", base_record.radio_vhf_air)),
            radio_vhf_sar=bool(_get("radio_vhf_sar", base_record.radio_vhf_sar)),
            radio_uhf=bool(_get("radio_uhf", base_record.radio_uhf)),
            cap_hoist=bool(_get("cap_hoist", base_record.cap_hoist)),
            cap_nvg=bool(_get("cap_nvg", base_record.cap_nvg)),
            cap_flir=bool(_get("cap_flir", base_record.cap_flir)),
            cap_ifr=bool(_get("cap_ifr", base_record.cap_ifr)),
            payload_kg=_parse_int(_get("payload_kg")),
            med_config=_clean_enum(_get("med_config"), self.DEFAULT_MED_CONFIGS, base_record.med_config),
            serial_number=_clean_str(_get("serial_number")),
            year=_parse_int(_get("year")),
            owner_operator=_clean_str(_get("owner_operator")),
            registration_exp=_clean_date(_get("registration_exp")),
            inspection_due=_clean_date(_get("inspection_due")),
            last_100hr=_clean_date(_get("last_100hr")),
            next_100hr=_clean_date(_get("next_100hr")),
            notes=_get("notes", base_record.notes),
            attachments=_normalise_list_of_dicts(_get("attachments", base_record.attachments)),
            history=_normalise_list_of_dicts(_get("history", base_record.history)),
            created_at=base_record.created_at,
            updated_at=base_record.updated_at,
        )

        if not record.tail_number:
            raise ValueError("Tail number is required")
        if new_record and not record.make_model_display:
            record.make_model_display = record._compose_display()
        if record.crew_min is not None and record.crew_max is not None:
            if record.crew_max < record.crew_min:
                record.crew_max = record.crew_min
        return record


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _clean_enum(value: Any, allowed: Sequence[str], fallback: str | None) -> str:
    if value is None and fallback is not None:
        return fallback
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed and fallback is not None:
            return fallback
        # Perform case-insensitive match against allowed list
        for option in allowed:
            if option.lower() == trimmed.lower():
                return option
        return trimmed
    return fallback or allowed[0]


def _clean_hex(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    filtered = "".join(ch for ch in text.upper() if ch in "0123456789ABCDEF")
    if len(filtered) == 0:
        return None
    return filtered


def _clean_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    # Accept ISO date or date-time strings.  No strict validation required for UI use.
    return text


def _normalise_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [dict(item) for item in parsed if isinstance(item, dict)]
    return []

