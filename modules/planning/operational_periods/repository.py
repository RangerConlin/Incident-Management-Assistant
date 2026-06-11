from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils import incident_storage
from utils.state import AppState


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _format_storage_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.replace(microsecond=0).isoformat(sep="T")


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


@dataclass(slots=True)
class OperationalPeriodRecord:
    id: int | None = None
    incident_id: str = ""
    number: int = 1
    name: str = ""
    status: str = "Planned"
    start_time: str = ""
    end_time: str = ""
    briefing_time: str = ""
    debrief_time: str = ""
    objectives: str = ""
    weather_summary: str = ""
    safety_message: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def code(self) -> str:
        return f"OP{self.number}"

    @property
    def display_name(self) -> str:
        return self.name.strip() or f"Operational Period {self.number}"


class OperationalPeriodRepository:
    STATUSES = ("Planned", "Active", "Complete", "Canceled")

    def __init__(self, incident_id: str | None = None, db_path: str | Path | None = None) -> None:
        incident = incident_id or AppState.get_active_incident()
        if not incident and db_path is None:
            raise RuntimeError("No active incident configured")
        self.incident_id = str(incident or "test-incident")
        self._db_path = Path(db_path) if db_path else self._incident_db_path(self.incident_id)
        with self._connect() as conn:
            self._ensure_schema(conn)

    @staticmethod
    def _incident_db_path(incident_id: str) -> Path:
        paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
        if paths is None:
            meta = incident_storage.infer_incident_metadata(incident_id)
            paths = incident_storage.get_incident_paths(
                incident_number=meta.get("incident_number") or incident_id,
                incident_name=meta.get("name") or incident_id,
                incident_id=meta.get("incident_id") or incident_id,
            )
            incident_storage.ensure_incident_structure(paths, meta)
        return paths.incident_db

    @contextmanager
    def _connect(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 4000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        if column not in self._table_columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operationalperiods (
                id INTEGER PRIMARY KEY,
                mission_id TEXT,
                op_number TEXT,
                start_time TEXT,
                end_time TEXT
            )
            """
        )
        self._ensure_column(conn, "operationalperiods", "incident_id", "incident_id TEXT")
        self._ensure_column(conn, "operationalperiods", "number", "number INTEGER")
        self._ensure_column(conn, "operationalperiods", "name", "name TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "operationalperiods", "status", "status TEXT NOT NULL DEFAULT 'Planned'")
        self._ensure_column(conn, "operationalperiods", "briefing_time", "briefing_time TEXT")
        self._ensure_column(conn, "operationalperiods", "debrief_time", "debrief_time TEXT")
        self._ensure_column(conn, "operationalperiods", "objectives", "objectives TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "operationalperiods", "weather_summary", "weather_summary TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "operationalperiods", "safety_message", "safety_message TEXT NOT NULL DEFAULT ''")
        self._ensure_column(conn, "operationalperiods", "created_at", "created_at TEXT")
        self._ensure_column(conn, "operationalperiods", "updated_at", "updated_at TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_operationalperiods_incident_number "
            "ON operationalperiods(incident_id, number)"
        )
        self._backfill_schema(conn)
        conn.commit()

    def _backfill_schema(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT * FROM operationalperiods").fetchall()
        for row in rows:
            op_id = int(row["id"])
            number = row["number"] if "number" in row.keys() else None
            number = int(number) if number not in (None, "") else _coerce_int(row["op_number"])
            if number is None or number <= 0:
                number = op_id
            incident_id = (row["incident_id"] if "incident_id" in row.keys() else None) or row["mission_id"] or self.incident_id
            op_number = (row["op_number"] or "").strip() or f"OP{number}"
            created_at = row["created_at"] if "created_at" in row.keys() else None
            updated_at = row["updated_at"] if "updated_at" in row.keys() else None
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE operationalperiods
                SET incident_id=?,
                    mission_id=?,
                    number=?,
                    op_number=?,
                    created_at=COALESCE(created_at, ?),
                    updated_at=COALESCE(updated_at, ?)
                WHERE id=?
                """,
                (incident_id, incident_id, number, op_number, created_at or now, updated_at or now, op_id),
            )

    def list_periods(self) -> list[OperationalPeriodRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM operationalperiods
                WHERE COALESCE(incident_id, mission_id, '') IN (?, '')
                   OR incident_id IS NULL
                ORDER BY COALESCE(number, id), start_time, id
                """,
                (self.incident_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_period_choices(self) -> list[tuple[int, str]]:
        choices: list[tuple[int, str]] = []
        for period in self.list_periods():
            if period.id is None:
                continue
            label = f"OP {period.number}"
            if period.start_time:
                label += f" ({period.start_time}"
                if period.end_time:
                    label += f" - {period.end_time}"
                label += ")"
            choices.append((period.id, label))
        return choices

    def get_period(self, period_id: int) -> OperationalPeriodRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM operationalperiods WHERE id=?",
                (int(period_id),),
            ).fetchone()
        if not row:
            raise ValueError(f"Operational period not found: {period_id}")
        return self._from_row(row)

    def next_number(self) -> int:
        periods = self.list_periods()
        if not periods:
            return 1
        return max(period.number for period in periods) + 1

    def validate_no_overlap(
        self,
        start_time: str,
        end_time: str,
        *,
        exclude_id: int | None = None,
    ) -> None:
        start_dt = _parse_dt(start_time)
        end_dt = _parse_dt(end_time)
        if start_dt is None or end_dt is None:
            raise ValueError("Start and end times are required.")
        if end_dt <= start_dt:
            raise ValueError("End time must be after start time.")
        for period in self.list_periods():
            if exclude_id is not None and period.id == exclude_id:
                continue
            other_start = _parse_dt(period.start_time)
            other_end = _parse_dt(period.end_time)
            if other_start is None or other_end is None:
                continue
            if start_dt < other_end and end_dt > other_start:
                raise ValueError(
                    f"Operational period overlaps OP {period.number} "
                    f"({period.start_time} to {period.end_time})."
                )

    def create_period(self, payload: dict[str, Any]) -> OperationalPeriodRecord:
        number = int(payload.get("number") or self.next_number())
        start_time = str(payload.get("start_time") or "").strip()
        end_time = str(payload.get("end_time") or "").strip()
        self.validate_no_overlap(start_time, end_time)
        now = _utcnow_iso()
        name = str(payload.get("name") or "").strip()
        status = str(payload.get("status") or "Planned").strip().title()
        if status not in self.STATUSES:
            status = "Planned"
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO operationalperiods (
                    incident_id, mission_id, number, op_number, name, status,
                    start_time, end_time, briefing_time, debrief_time,
                    objectives, weather_summary, safety_message,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.incident_id,
                    self.incident_id,
                    number,
                    f"OP{number}",
                    name,
                    status,
                    start_time,
                    end_time,
                    str(payload.get("briefing_time") or "").strip(),
                    str(payload.get("debrief_time") or "").strip(),
                    str(payload.get("objectives") or "").strip(),
                    str(payload.get("weather_summary") or "").strip(),
                    str(payload.get("safety_message") or "").strip(),
                    now,
                    now,
                ),
            )
            conn.commit()
            return self.get_period(int(cur.lastrowid))

    def update_period(self, period_id: int, payload: dict[str, Any]) -> OperationalPeriodRecord:
        current = self.get_period(period_id)
        merged = {
            "number": payload.get("number", current.number),
            "name": payload.get("name", current.name),
            "status": payload.get("status", current.status),
            "start_time": payload.get("start_time", current.start_time),
            "end_time": payload.get("end_time", current.end_time),
            "briefing_time": payload.get("briefing_time", current.briefing_time),
            "debrief_time": payload.get("debrief_time", current.debrief_time),
            "objectives": payload.get("objectives", current.objectives),
            "weather_summary": payload.get("weather_summary", current.weather_summary),
            "safety_message": payload.get("safety_message", current.safety_message),
        }
        self.validate_no_overlap(str(merged["start_time"]), str(merged["end_time"]), exclude_id=period_id)
        status = str(merged["status"]).strip().title()
        if status not in self.STATUSES:
            status = current.status
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE operationalperiods
                SET incident_id=?,
                    mission_id=?,
                    number=?,
                    op_number=?,
                    name=?,
                    status=?,
                    start_time=?,
                    end_time=?,
                    briefing_time=?,
                    debrief_time=?,
                    objectives=?,
                    weather_summary=?,
                    safety_message=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    self.incident_id,
                    self.incident_id,
                    int(merged["number"]),
                    f"OP{int(merged['number'])}",
                    str(merged["name"]).strip(),
                    status,
                    str(merged["start_time"]).strip(),
                    str(merged["end_time"]).strip(),
                    str(merged["briefing_time"]).strip(),
                    str(merged["debrief_time"]).strip(),
                    str(merged["objectives"]).strip(),
                    str(merged["weather_summary"]).strip(),
                    str(merged["safety_message"]).strip(),
                    _utcnow_iso(),
                    int(period_id),
                ),
            )
            conn.commit()
        return self.get_period(period_id)

    def clone_period(self, source_period_id: int) -> OperationalPeriodRecord:
        source = self.get_period(source_period_id)
        start_dt = _parse_dt(source.start_time) or datetime.utcnow().replace(microsecond=0)
        end_dt = _parse_dt(source.end_time) or (start_dt + timedelta(hours=12))
        duration = end_dt - start_dt
        periods = self.list_periods()
        next_period = max(periods, key=lambda item: item.number) if periods else source
        next_start = (_parse_dt(next_period.end_time) or end_dt).replace(microsecond=0)
        next_end = next_start + duration
        return self.create_period(
            {
                "number": self.next_number(),
                "name": source.name,
                "status": "Planned",
                "start_time": _format_storage_dt(next_start),
                "end_time": _format_storage_dt(next_end),
                "briefing_time": source.briefing_time,
                "debrief_time": source.debrief_time,
                "objectives": source.objectives,
                "weather_summary": source.weather_summary,
                "safety_message": source.safety_message,
            }
        )

    def set_active_period(self, period_id: int) -> OperationalPeriodRecord:
        selected = self.get_period(period_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE operationalperiods SET status='Planned' WHERE incident_id=? AND status='Active' AND id<>?",
                (self.incident_id, int(period_id)),
            )
            conn.execute(
                "UPDATE operationalperiods SET status='Active', updated_at=? WHERE id=?",
                (_utcnow_iso(), int(period_id)),
            )
            conn.commit()
        AppState.set_active_op_period(selected.number)
        return self.get_period(period_id)

    def get_active_period(self) -> OperationalPeriodRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM operationalperiods
                WHERE incident_id=? AND status='Active'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (self.incident_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def period_summary(self, period_id: int) -> dict[str, int]:
        summary = {
            "meetings": 0,
            "assignments": 0,
            "forms": 0,
            "objectives": 0,
        }
        period = self.get_period(period_id)
        with self._connect() as conn:
            if self._has_table(conn, "meetings"):
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM meetings WHERE operational_period_id=?",
                    (str(period_id),),
                ).fetchone()
                summary["meetings"] = int(row["c"]) if row else 0
            if self._has_table(conn, "work_assignments"):
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM work_assignments WHERE operational_period_id=? AND is_archived=0",
                    (int(period_id),),
                ).fetchone()
                summary["assignments"] = int(row["c"]) if row else 0
            if self._has_table(conn, "incident_form_instances"):
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM incident_form_instances WHERE operational_period_id=?",
                    (str(period_id),),
                ).fetchone()
                summary["forms"] = int(row["c"]) if row else 0
            if self._has_table(conn, "incident_objectives"):
                row = conn.execute("SELECT COUNT(*) AS c FROM incident_objectives").fetchone()
                summary["objectives"] = int(row["c"]) if row else 0
        if period.status == "Active":
            AppState.set_active_op_period(period.number)
        return summary

    def _has_table(self, conn: sqlite3.Connection, name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None

    def _from_row(self, row: sqlite3.Row | None) -> OperationalPeriodRecord:
        if row is None:
            raise ValueError("Operational period row is required")
        number = row["number"] if "number" in row.keys() else None
        number = int(number) if number not in (None, "") else _coerce_int(row["op_number"]) or int(row["id"])
        record = OperationalPeriodRecord(
            id=int(row["id"]),
            incident_id=str((row["incident_id"] if "incident_id" in row.keys() else None) or row["mission_id"] or self.incident_id),
            number=number,
            name=str(row["name"] or "") if "name" in row.keys() else "",
            status=str(row["status"] or "Planned") if "status" in row.keys() else "Planned",
            start_time=str(row["start_time"] or ""),
            end_time=str(row["end_time"] or ""),
            briefing_time=str(row["briefing_time"] or "") if "briefing_time" in row.keys() else "",
            debrief_time=str(row["debrief_time"] or "") if "debrief_time" in row.keys() else "",
            objectives=str(row["objectives"] or "") if "objectives" in row.keys() else "",
            weather_summary=str(row["weather_summary"] or "") if "weather_summary" in row.keys() else "",
            safety_message=str(row["safety_message"] or "") if "safety_message" in row.keys() else "",
            created_at=str(row["created_at"] or "") if "created_at" in row.keys() else "",
            updated_at=str(row["updated_at"] or "") if "updated_at" in row.keys() else "",
        )
        return record


__all__ = ["OperationalPeriodRecord", "OperationalPeriodRepository"]
