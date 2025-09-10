"""Bridge layer exposing ICS 206 data to QML.

The bridge is responsible for CRUD operations against the incident specific
SQLite database as well as importing reference data from the read only
``data/master.db`` catalogue.  All returned values are plain Python objects so
that they can be serialised to JSON and consumed directly by QML.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from PySide6.QtCore import QObject, Signal

from utils.state import AppState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TABLE_FIELDS: Dict[str, Sequence[str]] = {
    "aid_stations": ["id", "op_period", "name", "type", "level", "is_24_7", "notes"],
    "ambulance_services": [
        "id",
        "op_period",
        "name",
        "type",
        "phone",
        "location",
        "notes",
    ],
    "hospitals": [
        "id",
        "op_period",
        "name",
        "address",
        "phone",
        "helipad",
        "burn_center",
        "level",
        "notes",
    ],
    "air_ambulance": [
        "id",
        "op_period",
        "name",
        "phone",
        "base",
        "contact",
        "notes",
    ],
    "medical_comms": [
        "id",
        "op_period",
        "channel",
        "function",
        "frequency",
        "mode",
        "notes",
    ],
    "procedures": ["id", "op_period", "content"],
    "ics206_signatures": [
        "id",
        "op_period",
        "prepared_by",
        "position",
        "approved_by",
        "date",
    ],
}

MASTER_DB = Path("data/master.db")

# ---------------------------------------------------------------------------


class MedicalBridge(QObject):
    """SQLite helper used by :class:`modules.medical.panels.ics206_panel.ICS206Panel`."""

    data_changed = Signal(str)
    toast = Signal(str)

    # ------------------------------------------------------------------
    def _incident_path(self) -> Path:
        inc = AppState.get_active_incident()
        if not inc:
            raise RuntimeError("No active incident selected")
        p = Path("data") / "incidents" / f"{inc}.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _op_period(self) -> int:
        op = AppState.get_active_op_period()
        if op is None:
            raise RuntimeError("No active operational period selected")
        return int(op)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self._incident_path()))
        con.row_factory = sqlite3.Row
        return con

    def _connect_master(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(MASTER_DB))
        con.row_factory = sqlite3.Row
        return con

    # ------------------------------------------------------------------
    def ensure_ics206_tables(self) -> None:
        """Create required tables if missing in the incident DB."""
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS aid_stations (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL,
                    name TEXT,
                    type TEXT,
                    level TEXT,
                    is_24_7 INTEGER DEFAULT 0,
                    notes TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ambulance_services (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL,
                    name TEXT,
                    type TEXT,
                    phone TEXT,
                    location TEXT,
                    notes TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS hospitals (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL,
                    name TEXT,
                    address TEXT,
                    phone TEXT,
                    helipad INTEGER DEFAULT 0,
                    burn_center INTEGER DEFAULT 0,
                    level TEXT,
                    notes TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS air_ambulance (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL,
                    name TEXT,
                    phone TEXT,
                    base TEXT,
                    contact TEXT,
                    notes TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS procedures (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL UNIQUE,
                    content TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS medical_comms (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL,
                    channel TEXT,
                    function TEXT,
                    frequency TEXT,
                    mode TEXT,
                    notes TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ics206_signatures (
                    id INTEGER PRIMARY KEY,
                    op_period INTEGER NOT NULL UNIQUE,
                    prepared_by TEXT,
                    position TEXT,
                    approved_by TEXT,
                    date TEXT
                )
                """
            )
            con.commit()

    # ------------------------------------------------------------------
    # Generic CRUD helpers
    # ------------------------------------------------------------------
    def _rows_to_dicts(self, rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
        return [dict(r) for r in rows]

    def list_table(self, table: str) -> List[Dict[str, Any]]:
        fields = ",".join(TABLE_FIELDS[table])
        op = self._op_period()
        with self._connect() as con:
            cur = con.execute(
                f"SELECT {fields} FROM {table} WHERE op_period=? ORDER BY id", (op,)
            )
            return self._rows_to_dicts(cur.fetchall())

    def add_record(self, table: str, data: Dict[str, Any]) -> int:
        cols = [c for c in TABLE_FIELDS[table] if c not in ("id", "op_period")]
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO {table} (op_period, {', '.join(cols)}) VALUES (?, {placeholders})"
        params = [self._op_period()] + [data.get(c) for c in cols]
        with self._connect() as con:
            cur = con.execute(sql, params)
            con.commit()
            self.data_changed.emit(table)
            return int(cur.lastrowid)

    def update_record(self, table: str, id_value: int, data: Dict[str, Any]) -> bool:
        cols = [c for c in data.keys() if c in TABLE_FIELDS[table] and c not in ("id", "op_period")]
        if not cols:
            return False
        set_clause = ", ".join([f"{c}=?" for c in cols])
        sql = f"UPDATE {table} SET {set_clause} WHERE id=?"
        params = [data.get(c) for c in cols] + [id_value]
        with self._connect() as con:
            con.execute(sql, params)
            con.commit()
            self.data_changed.emit(table)
            return True

    def delete_record(self, table: str, id_value: int) -> bool:
        with self._connect() as con:
            con.execute(f"DELETE FROM {table} WHERE id=?", (id_value,))
            con.commit()
            self.data_changed.emit(table)
            return True

    # ------------------------------------------------------------------
    # Table specific helpers
    # ------------------------------------------------------------------
    def get_procedures(self) -> str:
        op = self._op_period()
        with self._connect() as con:
            cur = con.execute(
                "SELECT content FROM procedures WHERE op_period=?", (op,)
            )
            row = cur.fetchone()
            return row["content"] if row else ""

    def save_procedures(self, text: str) -> None:
        op = self._op_period()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO procedures (op_period, content)
                VALUES (?, ?)
                ON CONFLICT(op_period) DO UPDATE SET content=excluded.content
                """,
                (op, text),
            )
            con.commit()
            self.data_changed.emit("procedures")

    def get_signatures(self) -> Dict[str, Any]:
        op = self._op_period()
        with self._connect() as con:
            cur = con.execute(
                "SELECT prepared_by, position, approved_by, date FROM ics206_signatures WHERE op_period=?",
                (op,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}

    def save_signatures(self, data: Dict[str, Any]) -> None:
        op = self._op_period()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO ics206_signatures (op_period, prepared_by, position, approved_by, date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(op_period) DO UPDATE SET
                    prepared_by=excluded.prepared_by,
                    position=excluded.position,
                    approved_by=excluded.approved_by,
                    date=excluded.date
                """,
                (
                    op,
                    data.get("prepared_by"),
                    data.get("position"),
                    data.get("approved_by"),
                    data.get("date"),
                ),
            )
            con.commit()
            self.data_changed.emit("ics206_signatures")

    # ------------------------------------------------------------------
    def import_aid_stations(self) -> int:
        op = self._op_period()
        with self._connect_master() as mcon, self._connect() as con:
            cur = mcon.execute(
                "SELECT name, type, phone, notes FROM ems"
            )
            rows = cur.fetchall()
            for r in rows:
                con.execute(
                    "INSERT INTO aid_stations (op_period, name, type, level, is_24_7, notes) VALUES (?,?,?,?,?,?)",
                    (op, r["name"], r["type"], "", 0, r["notes"]),
                )
            con.commit()
            self.data_changed.emit("aid_stations")
            return len(rows)

    def import_ambulance_services(self) -> int:
        op = self._op_period()
        with self._connect_master() as mcon, self._connect() as con:
            cur = mcon.execute(
                "SELECT name, type, phone, address, notes FROM ems"
            )
            rows = cur.fetchall()
            for r in rows:
                con.execute(
                    "INSERT INTO ambulance_services (op_period, name, type, phone, location, notes) VALUES (?,?,?,?,?,?)",
                    (op, r["name"], r["type"], r["phone"], r["address"], r["notes"]),
                )
            con.commit()
            self.data_changed.emit("ambulance_services")
            return len(rows)

    def import_hospitals(self) -> int:
        op = self._op_period()
        with self._connect_master() as mcon, self._connect() as con:
            cur = mcon.execute(
                "SELECT name, address, phone, notes FROM hospitals"
            )
            rows = cur.fetchall()
            for r in rows:
                con.execute(
                    "INSERT INTO hospitals (op_period, name, address, phone, helipad, burn_center, level, notes) VALUES (?,?,?,?,?,?,?,?)",
                    (op, r["name"], r["address"], r["phone"], 0, 0, "", r["notes"]),
                )
            con.commit()
            self.data_changed.emit("hospitals")
            return len(rows)

    def import_air_ambulance(self) -> int:
        op = self._op_period()
        with self._connect_master() as mcon, self._connect() as con:
            cur = mcon.execute(
                "SELECT name, phone, address, contact, notes FROM ems"
            )
            rows = cur.fetchall()
            for r in rows:
                con.execute(
                    "INSERT INTO air_ambulance (op_period, name, phone, base, contact, notes) VALUES (?,?,?,?,?,?)",
                    (op, r["name"], r["phone"], r["address"], r["contact"], r["notes"]),
                )
            con.commit()
            self.data_changed.emit("air_ambulance")
            return len(rows)

    def import_medical_comms(self) -> int:
        op = self._op_period()
        with self._connect_master() as mcon, self._connect() as con:
            cur = mcon.execute(
                "SELECT alpha_tag, function, freq_rx, mode, notes FROM comms_resources"
            )
            rows = cur.fetchall()
            for r in rows:
                con.execute(
                    "INSERT INTO medical_comms (op_period, channel, function, frequency, mode, notes) VALUES (?,?,?,?,?,?)",
                    (op, r["alpha_tag"], r["function"], r["freq_rx"], r["mode"], r["notes"]),
                )
            con.commit()
            self.data_changed.emit("medical_comms")
            return len(rows)

    # ------------------------------------------------------------------
    def duplicate_last_op(self) -> bool:
        """Copy data from the most recent previous operational period."""
        cur_op = self._op_period()
        with self._connect() as con:
            cur = con.execute(
                "SELECT MAX(op_period) FROM aid_stations WHERE op_period < ?", (cur_op,)
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                return False
            prev = int(row[0])
            for table, fields in TABLE_FIELDS.items():
                cols = [c for c in fields if c not in ("id", "op_period")]
                col_str = ", ".join(cols)
                con.execute(
                    f"INSERT INTO {table} (op_period, {col_str}) SELECT ?, {col_str} FROM {table} WHERE op_period=?",
                    (cur_op, prev),
                )
            con.commit()
            self.data_changed.emit("all")
            return True
