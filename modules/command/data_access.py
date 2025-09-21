"""Data access helpers backing the IC overview widget."""
from __future__ import annotations

import logging
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from utils.state import AppState
from utils import timefmt

_ROOT_DIR = Path(__file__).resolve().parents[2]
_DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", str(_ROOT_DIR / "data")))

try:  # pragma: no cover - optional dependency available in runtime
    from utils.db import get_master_conn, get_incident_conn
except Exception:  # pragma: no cover
    def get_master_conn() -> sqlite3.Connection:
        conn = sqlite3.connect(_DATA_DIR / "master.db")
        conn.row_factory = sqlite3.Row
        return conn

    def get_incident_conn() -> sqlite3.Connection:
        incident_number = AppState.get_active_incident()
        if not incident_number:
            raise RuntimeError("Active incident not set")
        path = _DATA_DIR / "incidents" / f"{incident_number}.db"
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn


_LOGGER = logging.getLogger(__name__)

_CURRENT_OP = 1
_ALERT_STATUSES = {
    "enroute",
    "arrival",
    "returning to base",
    "returning",
    "at other location",
    "to other location",
    "find",
}

_ALERT_PRIORITY = {
    "CHECKIN_OVERDUE": 0,
    "EMERGENCY": 1,
    "NEEDS_ASSISTANCE": 2,
    "CHECKIN_WARNING": 3,
}

_DEMO_HEADER = {
    "incident_name": "Operation Demo",
    "incident_number": "25-D-9001",
    "operational_period": 1,
    "status": "Active",
    "icp_location": "Mock ICP",
    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
}

_DEMO_TEAMS: list[dict[str, Any]] = [
    {
        "team_id": 1,
        "team_name": "GT-Alpha",
        "status": "Enroute",
        "last_checkin_ts": datetime.now() - timedelta(minutes=35),
        "needs_assistance": False,
        "emergency": False,
    },
    {
        "team_id": 2,
        "team_name": "GT-Bravo",
        "status": "Arrival",
        "last_checkin_ts": datetime.now() - timedelta(minutes=58),
        "needs_assistance": True,
        "emergency": False,
    },
    {
        "team_id": 3,
        "team_name": "UDF-Charlie",
        "status": "Returning to Base",
        "last_checkin_ts": datetime.now() - timedelta(minutes=72),
        "needs_assistance": False,
        "emergency": True,
    },
    {
        "team_id": 4,
        "team_name": "Air-1",
        "status": "Available",
        "last_checkin_ts": datetime.now() - timedelta(minutes=15),
        "needs_assistance": False,
        "emergency": False,
    },
]

_DEMO_TASKS = [
    {
        "task_id": "T-101",
        "title": "Hasty Search Trailhead",
        "status": "In Progress",
        "due_time": (datetime.now() + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S"),
        "assigned_to": "GT-Alpha",
    },
    {
        "task_id": "T-102",
        "title": "Grid Search Sector 5",
        "status": "Planned",
        "due_time": (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S"),
        "assigned_to": "GT-Bravo",
    },
    {
        "task_id": "T-103",
        "title": "Medical Evacuation Staging",
        "status": "Completed",
        "due_time": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S"),
        "assigned_to": "Med-1",
    },
]

_DEMO_COMMS = [
    {
        "name": "Command 1",
        "function": "Command Net",
        "mode": "A",
        "remarks": "Primary",
        "last_updated": datetime.now() - timedelta(minutes=5),
    },
    {
        "name": "Air-Ground",
        "function": "Air Ops",
        "mode": "A",
        "remarks": "Contact Air-1 prior to ingress",
        "last_updated": datetime.now() - timedelta(minutes=20),
    },
    {
        "name": "Tactical 3",
        "function": "Ground Teams",
        "mode": "D",
        "remarks": "",
        "last_updated": datetime.now() - timedelta(minutes=120),
    },
]

_DEMO_LOGISTICS_COUNTS = {
    "Submitted": 2,
    "In Progress": 1,
    "Approved": 1,
    "Ordered": 0,
    "Fulfilled": 1,
    "Complete": 3,
    "Cancelled": 0,
    "Denied": 0,
}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    try:
        cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return cur.fetchone() is not None
    except sqlite3.Error:
        return False


def _resolve_incident_number(conn: Optional[sqlite3.Connection] = None) -> Optional[str]:
    number = AppState.get_active_incident()
    if number:
        return str(number)
    try:
        if conn is None:
            with get_master_conn() as master:
                row = master.execute(
                    "SELECT number FROM incidents WHERE status='Active' ORDER BY id DESC LIMIT 1"
                ).fetchone()
        else:
            row = conn.execute(
                "SELECT number FROM incidents WHERE status='Active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            return str(row[0])
    except sqlite3.Error:
        _LOGGER.exception("Failed to resolve active incident number")
    return None


def _incident_conn() -> Optional[sqlite3.Connection]:
    try:
        conn = get_incident_conn()
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        number = _resolve_incident_number()
        if not number:
            return None
        root = _DATA_DIR
        path = root / "incidents" / f"{number}.db"
        if not path.exists():
            # fall back to a sample database if present
            demo_path = root / "incidents" / "demo-incident.db"
            path = demo_path if demo_path.exists() else path
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error:
            _LOGGER.exception("Unable to open incident database at %s", path)
    return None


def get_incident_header() -> dict[str, Any]:
    header = dict(_DEMO_HEADER)
    try:
        with get_master_conn() as conn:
            number = _resolve_incident_number(conn)
            if number:
                row = conn.execute(
                    "SELECT name, number, status, icp_location, start_time FROM incidents WHERE number=?",
                    (number,),
                ).fetchone()
                if row:
                    header.update(
                        {
                            "incident_name": row["name"] or header["incident_name"],
                            "incident_number": row["number"] or header["incident_number"],
                            "status": row["status"] or header["status"],
                            "icp_location": row["icp_location"] or header["icp_location"],
                            "start_time": row["start_time"] or header["start_time"],
                        }
                    )
    except sqlite3.Error:
        _LOGGER.exception("Failed to load incident header; using demo content")

    header["operational_period"] = _CURRENT_OP
    return header


def get_operational_periods() -> list[int]:
    periods: list[int] = []
    conn = _incident_conn()
    if conn:
        try:
            if _table_exists(conn, "operationalperiods"):
                number = _resolve_incident_number()
                keys: list[str] = []
                if number:
                    keys.append(str(number))
                try:
                    incident_row = conn.execute(
                        "SELECT id FROM incidents WHERE number=?", (number,)
                    ).fetchone()
                    if incident_row:
                        keys.append(str(incident_row["id"]))
                except sqlite3.Error:
                    pass

                if keys:
                    placeholders = ",".join("?" for _ in keys)
                    rows = conn.execute(
                        f"SELECT DISTINCT op_number FROM operationalperiods WHERE mission_id IN ({placeholders})",
                        tuple(keys),
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT DISTINCT op_number FROM operationalperiods").fetchall()
                for row in rows:
                    op_raw = row["op_number"] if isinstance(row, sqlite3.Row) else row[0]
                    op_int = _normalize_op_number(op_raw)
                    if op_int is not None:
                        periods.append(op_int)
        except sqlite3.Error:
            _LOGGER.exception("Unable to query operational periods")
        finally:
            conn.close()

    if not periods:
        periods = [1]
    periods = sorted(set(periods))
    global _CURRENT_OP
    if _CURRENT_OP not in periods:
        _CURRENT_OP = periods[0]
    return periods


def set_operational_period(op_no: int) -> None:
    global _CURRENT_OP
    if op_no <= 0:
        op_no = 1
    _CURRENT_OP = op_no
    try:
        AppState.set_active_op_period(op_no)
    except Exception:
        # Optional; the wider app may not be initialised when running the demo harness.
        pass


def _normalize_op_number(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        try:
            return int(text)
        except ValueError:
            return None
    try:
        return int(digits)
    except ValueError:
        return None


def list_team_checkins(op_no: int) -> list[dict[str, Any]]:
    conn = _incident_conn()
    records: list[dict[str, Any]] = []
    if not conn:
        return [dict(item) for item in _DEMO_TEAMS]

    try:
        if not _table_exists(conn, "teams"):
            return [dict(item) for item in _DEMO_TEAMS]

        cols = _column_map(conn, "teams")
        extra_checkins: dict[int, datetime] = {}
        if _table_exists(conn, "task_teams"):
            extra_checkins = _task_team_checkins(conn)

        query = "SELECT id, name, status FROM teams"
        optional_fields = []
        for field in ("status_updated", "last_comm_ping", "needs_attention", "priority", "callsign"):
            if field in cols:
                optional_fields.append(field)
        if optional_fields:
            query = f"SELECT id, name, status, {', '.join(optional_fields)} FROM teams"

        rows = conn.execute(query).fetchall()
        for row in rows:
            team_id = int(row["id"])
            status = (row["status"] or "").strip()
            last_ts = None
            for field in ("last_comm_ping", "status_updated"):
                if field in row.keys() and row[field]:
                    last_ts = _parse_datetime(row[field])
                    if last_ts:
                        break
            if not last_ts:
                last_ts = extra_checkins.get(team_id)

            record = {
                "team_id": team_id,
                "team_name": row["name"] or f"Team {team_id}",
                "status": status or "Unknown",
                "last_checkin_ts": last_ts,
                "needs_assistance": bool(_row_value(row, "needs_attention", 0)),
                "emergency": _is_emergency(row),
            }
            records.append(record)
    except sqlite3.Error:
        _LOGGER.exception("Failed to list team check-ins")
        records = [dict(item) for item in _DEMO_TEAMS]
    finally:
        conn.close()

    return records


def _column_map(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        return set()


def _row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    try:
        if key in row.keys():
            return row[key]
    except Exception:
        pass
    return default


def _task_team_checkins(conn: sqlite3.Connection) -> dict[int, datetime]:
    results: dict[int, datetime] = {}
    try:
        rows = conn.execute(
            """
            SELECT teamid AS team_id,
                   MAX(COALESCE(time_cleared, time_complete, time_arrived, time_enroute, time_briefed, time_assigned)) AS last_ts
            FROM task_teams
            GROUP BY teamid
            """
        ).fetchall()
        for row in rows:
            if row["last_ts"]:
                parsed = _parse_datetime(row["last_ts"])
                if parsed:
                    results[int(row["team_id"])] = parsed
    except sqlite3.Error:
        _LOGGER.debug("task_teams check-in enrichment not available")
    return results


def _is_emergency(row: sqlite3.Row) -> bool:
    priority = _row_value(row, "priority")
    if priority is None:
        return False
    text = str(priority).strip().lower()
    return text in {"emergency", "critical"}


def list_task_summary(op_no: int) -> dict[str, Any]:
    conn = _incident_conn()
    if not conn:
        return _demo_task_summary()

    counts = Counter()
    due_items: list[dict[str, Any]] = []
    try:
        if not _table_exists(conn, "tasks"):
            return _demo_task_summary()
        rows = conn.execute(
            "SELECT id, task_id, title, status, due_time, primary_team, assignment FROM tasks"
        ).fetchall()
        for row in rows:
            status_key = _normalize_task_status(row["status"])
            counts[status_key] += 1
            due_ts = _parse_datetime(row["due_time"])
            if due_ts is not None:
                due_items.append(
                    {
                        "task_id": row["task_id"] or f"T-{row['id']}",
                        "title": row["title"] or "Untitled",
                        "due_time": due_ts,
                        "assigned_to": row["primary_team"]
                        or row["assignment"]
                        or "",
                    }
                )
    except sqlite3.Error:
        _LOGGER.exception("Failed to load task summary")
        return _demo_task_summary()
    finally:
        conn.close()

    due_items.sort(key=lambda item: item["due_time"])
    return {
        "counts": {
            "Draft": counts.get("draft", 0),
            "Planned": counts.get("planned", 0),
            "In Progress": counts.get("in_progress", 0),
            "Completed": counts.get("completed", 0),
            "Cancelled": counts.get("cancelled", 0),
        },
        "due": due_items[:3],
    }


def _normalize_task_status(value: Any) -> str:
    if value is None:
        return "draft"
    text = str(value).strip().lower()
    mapping = {
        "draft": "draft",
        "created": "draft",
        "planned": "planned",
        "assigned": "planned",
        "in progress": "in_progress",
        "progress": "in_progress",
        "complete": "completed",
        "completed": "completed",
        "closed": "completed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }
    return mapping.get(text, text or "draft")


def _demo_task_summary() -> dict[str, Any]:
    counts = Counter()
    due_items: list[dict[str, Any]] = []
    for task in _DEMO_TASKS:
        counts[_normalize_task_status(task.get("status"))] += 1
        due = _parse_datetime(task.get("due_time"))
        if due:
            due_items.append(
                {
                    "task_id": task["task_id"],
                    "title": task["title"],
                    "due_time": due,
                    "assigned_to": task.get("assigned_to", ""),
                }
            )
    due_items.sort(key=lambda item: item["due_time"])
    return {
        "counts": {
            "Draft": counts.get("draft", 0),
            "Planned": counts.get("planned", 0),
            "In Progress": counts.get("in_progress", 0),
            "Completed": counts.get("completed", 0),
            "Cancelled": counts.get("cancelled", 0),
        },
        "due": due_items[:3],
    }


def list_comms_channels(op_no: int) -> list[dict[str, Any]]:
    conn = _incident_conn()
    if not conn:
        return [dict(item) for item in _DEMO_COMMS]

    channels: list[dict[str, Any]] = []
    try:
        if not _table_exists(conn, "incident_channels"):
            return [dict(item) for item in _DEMO_COMMS]
        rows = conn.execute(
            """
            SELECT channel, function, mode, remarks, updated_at, include_on_205, sort_index
            FROM incident_channels
            WHERE include_on_205 IS NULL OR include_on_205 != 0
            ORDER BY (sort_index IS NULL), sort_index, channel
            """
        ).fetchall()
        for row in rows:
            channels.append(
                {
                    "name": row["channel"] or "",
                    "function": row["function"] or "",
                    "mode": (row["mode"] or "").strip()[:1].upper(),
                    "remarks": row["remarks"] or "",
                    "last_updated": _parse_datetime(_row_value(row, "updated_at")),
                }
            )
    except sqlite3.Error:
        _LOGGER.exception("Failed to load communications channels")
        channels = [dict(item) for item in _DEMO_COMMS]
    finally:
        conn.close()

    return channels


def list_logistics_requests(op_no: int) -> dict[str, int]:
    conn = _incident_conn()
    if not conn:
        return dict(_DEMO_LOGISTICS_COUNTS)

    counts = Counter()
    try:
        if not _table_exists(conn, "logistics_resource_requests"):
            return dict(_DEMO_LOGISTICS_COUNTS)
        rows = conn.execute("SELECT status FROM logistics_resource_requests").fetchall()
        for row in rows:
            status = (row["status"] or "").strip().title()
            counts[status] += 1
    except sqlite3.Error:
        _LOGGER.exception("Failed to load logistics requests")
        return dict(_DEMO_LOGISTICS_COUNTS)
    finally:
        conn.close()

    result = dict(_DEMO_LOGISTICS_COUNTS)
    result.update({k: counts.get(k, 0) for k in result.keys()})
    for status, value in counts.items():
        if status not in result:
            result[status] = value
    return result


def compute_alerts(op_no: int, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    now_dt = now or datetime.now()
    teams = list_team_checkins(op_no)
    alerts: list[dict[str, Any]] = []
    for team in teams:
        status = (team.get("status") or "").strip().lower()
        last_ts = team.get("last_checkin_ts")
        if team.get("emergency"):
            alerts.append(_make_alert("EMERGENCY", team, last_ts))
        if team.get("needs_assistance"):
            alerts.append(_make_alert("NEEDS_ASSISTANCE", team, last_ts))
        if status in _ALERT_STATUSES and last_ts:
            minutes = timefmt.minutes_since(last_ts, now=now_dt)
            if minutes is not None:
                if minutes >= 60:
                    alerts.append(_make_alert("CHECKIN_OVERDUE", team, last_ts))
                elif minutes >= 50:
                    alerts.append(_make_alert("CHECKIN_WARNING", team, last_ts))
    alerts.sort(key=lambda item: (_ALERT_PRIORITY.get(item["type"], 99), item.get("team_name", "")))
    return alerts


def _make_alert(alert_type: str, team: dict[str, Any], last_ts: Any) -> dict[str, Any]:
    return {
        "type": alert_type,
        "team_id": team.get("team_id"),
        "team_name": team.get("team_name"),
        "status": team.get("status"),
        "last_checkin_ts": last_ts,
    }


def _parse_datetime(value: Any) -> Optional[datetime]:
    return timefmt.to_datetime(value)


__all__ = [
    "get_incident_header",
    "get_operational_periods",
    "set_operational_period",
    "list_team_checkins",
    "list_task_summary",
    "list_comms_channels",
    "list_logistics_requests",
    "compute_alerts",
]
