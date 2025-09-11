# type: ignore[override]
"""Bridge helpers for ICS 206 Medical Plan tables.

This module provides a thin wrapper around the incident specific SQLite
database used by the application.  All return values are plain Python
objects so that higher layers (Qt widgets, CLI tools, etc.) can consume the
information without depending on Qt types.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence
import sqlite3

from utils.state import AppState

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "modules"
    / "medical"
    / "data"
    / "ics206_schema.sql"
)

TABLES: Sequence[str] = (
    "ics206_aid_stations",
    "ics206_ambulance",
    "ics206_hospitals",
    "ics206_air_ambulance",
    "ics206_procedures",
    "ics206_comms",
    "ics206_signatures",
)


class Ics206Bridge:
    """Light weight database facade for ICS 206 tables."""

    # ------------------------------------------------------------------
    # path helpers
    def get_master_db_path(self) -> str:
        return str(Path("data") / "master.db")

    def get_incident_db_path(self) -> str:
        inc = AppState.get_active_incident()
        op = AppState.get_active_op_period()
        if inc is None or op is None:
            raise RuntimeError("No active incident/op period")
        path = Path("data") / "incidents" / str(inc)
        path.mkdir(parents=True, exist_ok=True)
        db_path = path / f"op_{int(op)}.db"
        return str(db_path)

    # internal connection helpers --------------------------------------
    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.get_incident_db_path())
        con.row_factory = sqlite3.Row
        return con

    def _connect_master(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.get_master_db_path())
        con.row_factory = sqlite3.Row
        return con

    # migration ---------------------------------------------------------
    def ensure_ics206_tables(self) -> None:
        with self._connect() as con, open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
            con.executescript(fh.read())

    # generic helpers ---------------------------------------------------
    def _list(self, table: str) -> List[dict]:
        with self._connect() as con:
            cur = con.execute(f"SELECT * FROM {table} ORDER BY id")
            return [dict(r) for r in cur.fetchall()]

    def _insert(self, table: str, row: dict) -> int:
        cols = ", ".join(row.keys())
        q = ", ".join(["?" for _ in row])
        with self._connect() as con:
            cur = con.execute(
                f"INSERT INTO {table} ({cols}) VALUES ({q})", list(row.values())
            )
            con.commit()
            return int(cur.lastrowid)

    def _update(self, table: str, row_id: int, row: dict) -> None:
        assigns = ", ".join([f"{k}=?" for k in row.keys()])
        params = list(row.values()) + [row_id]
        with self._connect() as con:
            con.execute(f"UPDATE {table} SET {assigns} WHERE id=?", params)
            con.commit()

    def _delete(self, table: str, row_id: int) -> None:
        with self._connect() as con:
            con.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
            con.commit()

    # aid stations ------------------------------------------------------
    def list_aid_stations(self) -> List[dict]:
        return self._list("ics206_aid_stations")

    def add_aid_station(self, row: dict) -> int:
        return self._insert("ics206_aid_stations", row)

    def update_aid_station(self, row_id: int, row: dict) -> None:
        self._update("ics206_aid_stations", row_id, row)

    def delete_aid_station(self, row_id: int) -> None:
        self._delete("ics206_aid_stations", row_id)

    def import_aid_from_205(self) -> int:  # placeholder
        return 0

    # ambulance ---------------------------------------------------------
    def list_ambulance(self) -> List[dict]:
        return self._list("ics206_ambulance")

    def add_ambulance(self, row: dict) -> int:
        return self._insert("ics206_ambulance", row)

    def update_ambulance(self, row_id: int, row: dict) -> None:
        self._update("ics206_ambulance", row_id, row)

    def delete_ambulance(self, row_id: int) -> None:
        self._delete("ics206_ambulance", row_id)

    def import_ambulance_from_master(self, ids: Sequence[int]) -> int:
        count = 0
        if not ids:
            return count
        with self._connect_master() as mcon, self._connect() as icon:
            for rid in ids:
                row = mcon.execute(
                    "SELECT agency, level, et_minutes, notes FROM ambulance_master WHERE id=?",
                    (rid,),
                ).fetchone()
                if row:
                    icon.execute(
                        "INSERT INTO ics206_ambulance (agency, level, et_minutes, notes) VALUES (?,?,?,?)",
                        (row[0], row[1], row[2], row[3]),
                    )
                    count += 1
            icon.commit()
        return count

    # hospitals ---------------------------------------------------------
    def list_hospitals(self) -> List[dict]:
        return self._list("ics206_hospitals")

    def add_hospital(self, row: dict) -> int:
        return self._insert("ics206_hospitals", row)

    def update_hospital(self, row_id: int, row: dict) -> None:
        self._update("ics206_hospitals", row_id, row)

    def delete_hospital(self, row_id: int) -> None:
        self._delete("ics206_hospitals", row_id)

    def update_hospital_details(self, row_id: int, details: dict) -> None:
        self._update("ics206_hospitals", row_id, details)

    def import_hospitals_from_master(self, ids: Sequence[int]) -> int:
        count = 0
        if not ids:
            return count
        with self._connect_master() as mcon, self._connect() as icon:
            for rid in ids:
                row = mcon.execute(
                    """
                    SELECT hospital, trauma_center, bed_cap, phone_er, address,
                           city, state, zip, helipad_lat, helipad_lon
                    FROM hospitals_master WHERE id=?
                    """,
                    (rid,),
                ).fetchone()
                if row:
                    icon.execute(
                        """
                        INSERT INTO ics206_hospitals(
                            hospital, trauma_center, bed_cap, phone_er, address,
                            city, state, zip, helipad_lat, helipad_lon
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        tuple(row),
                    )
                    count += 1
            icon.commit()
        return count

    # air ambulance -----------------------------------------------------
    def list_air_ambulance(self) -> List[dict]:
        return self._list("ics206_air_ambulance")

    def add_air_ambulance(self, row: dict) -> int:
        return self._insert("ics206_air_ambulance", row)

    def update_air_ambulance(self, row_id: int, row: dict) -> None:
        self._update("ics206_air_ambulance", row_id, row)

    def delete_air_ambulance(self, row_id: int) -> None:
        self._delete("ics206_air_ambulance", row_id)

    # procedures --------------------------------------------------------
    def get_procedures(self) -> dict:
        with self._connect() as con:
            row = con.execute(
                "SELECT id, notes FROM ics206_procedures WHERE id=1"
            ).fetchone()
            if row:
                return dict(row)
            return {"id": 1, "notes": ""}

    def save_procedures(self, notes: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO ics206_procedures(id, notes) VALUES(1, ?) "
                "ON CONFLICT(id) DO UPDATE SET notes=excluded.notes",
                (notes,),
            )
            con.commit()

    # comms -------------------------------------------------------------
    def list_comms(self) -> List[dict]:
        return self._list("ics206_comms")

    def add_comm(self, row: dict) -> int:
        return self._insert("ics206_comms", row)

    def update_comm(self, row_id: int, row: dict) -> None:
        self._update("ics206_comms", row_id, row)

    def delete_comm(self, row_id: int) -> None:
        self._delete("ics206_comms", row_id)

    def import_comms_from_master(self, ids: Sequence[int]) -> int:
        count = 0
        if not ids:
            return count
        with self._connect_master() as mcon, self._connect() as icon:
            for rid in ids:
                row = mcon.execute(
                    "SELECT function, channel, notes FROM comms_resources WHERE id=?",
                    (rid,),
                ).fetchone()
                if row:
                    icon.execute(
                        "INSERT INTO ics206_comms(function, channel, notes) VALUES (?,?,?)",
                        (row[0], row[1], row[2]),
                    )
                    count += 1
            icon.commit()
        return count

    # signatures --------------------------------------------------------
    def get_signatures(self) -> dict:
        with self._connect() as con:
            row = con.execute(
                "SELECT id, prepared_by, prepared_position, approved_by, signed_at "
                "FROM ics206_signatures WHERE id=1"
            ).fetchone()
            if row:
                return dict(row)
            return {
                "id": 1,
                "prepared_by": "",
                "prepared_position": "",
                "approved_by": "",
                "signed_at": "",
            }

    def save_signatures(self, row: dict) -> None:
        with self._connect() as con:
            fields = (
                "prepared_by",
                "prepared_position",
                "approved_by",
                "signed_at",
            )
            values = [row.get(f, "") for f in fields]
            con.execute(
                """
                INSERT INTO ics206_signatures(id, prepared_by, prepared_position, approved_by, signed_at)
                VALUES (1,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    prepared_by=excluded.prepared_by,
                    prepared_position=excluded.prepared_position,
                    approved_by=excluded.approved_by,
                    signed_at=excluded.signed_at
                """,
                values,
            )
            con.commit()

    # duplication -------------------------------------------------------
    def duplicate_last_op(self) -> None:
        inc = AppState.get_active_incident()
        op = AppState.get_active_op_period()
        if inc is None or op is None or int(op) <= 1:
            return
        src = Path("data") / "incidents" / str(inc) / f"op_{int(op)-1}.db"
        dest = Path(self.get_incident_db_path())
        if not src.exists():
            return
        with sqlite3.connect(dest) as con:
            con.row_factory = sqlite3.Row
            con.execute(f"ATTACH DATABASE '{src}' AS prev")
            for table in TABLES:
                con.execute(f"DELETE FROM {table}")
                con.execute(
                    f"INSERT INTO {table} SELECT * FROM prev.{table}"
                )
            con.commit()

    # pdf ---------------------------------------------------------------
    def export_pdf(self, output_path: str) -> str:
        # Placeholder implementation – real PDF generation handled elsewhere
        return output_path
