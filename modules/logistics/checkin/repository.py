"""SQLite repository helpers for the Logistics Check-In module."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from utils.db import get_incident_conn, get_master_conn

from . import schema
from .models import (
    CIStatus,
    CheckInRecord,
    HistoryItem,
    PersonnelIdentity,
    PersonnelStatus,
    QueueItem,
    RosterFilters,
    RosterRow,
    UIFlags,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _row_to_dict(row) -> Dict:
    return dict(row) if row is not None else {}


# ---------------------------------------------------------------------------
# Master lookups
# ---------------------------------------------------------------------------

def get_person_identity(person_id: str) -> Optional[PersonnelIdentity]:
    """Fetch read-only identity information from ``master.db``."""
    with get_master_conn() as conn:
        schema.ensure_master_schema(conn)
        cur = conn.execute("SELECT * FROM personnel WHERE id = ?", (person_id,))
        row = cur.fetchone()
        return PersonnelIdentity.from_row(dict(row)) if row else None


def search_personnel(term: str, limit: int = 50) -> List[PersonnelIdentity]:
    """Return personnel whose id, name, or callsign match ``term``."""
    like = f"%{term.lower()}%"
    sql = (
        "SELECT * FROM personnel WHERE "
        "lower(id) LIKE ? OR lower(name) LIKE ? OR lower(callsign) LIKE ? ORDER BY name"
    )
    with get_master_conn() as conn:
        schema.ensure_master_schema(conn)
        rows = conn.execute(sql, (like, like, like)).fetchmany(limit)
        return [PersonnelIdentity.from_row(dict(row)) for row in rows]


# ---------------------------------------------------------------------------
# Roster queries
# ---------------------------------------------------------------------------

def get_distinct_roles() -> List[str]:
    """Return a sorted list of roles present in the roster."""
    roles: set[str] = set()
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        cur = conn.execute("SELECT DISTINCT role_on_team FROM checkins WHERE role_on_team IS NOT NULL")
        roles.update(r[0] for r in cur.fetchall() if r[0])
    with get_master_conn() as conn:
        schema.ensure_master_schema(conn)
        cur = conn.execute("SELECT DISTINCT primary_role FROM personnel WHERE primary_role IS NOT NULL")
        roles.update(r[0] for r in cur.fetchall() if r[0])
    return sorted(roles)


def get_distinct_teams() -> List[Tuple[str, str]]:
    """Return ``(team_id, name)`` tuples for roster filters."""
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        rows = conn.execute("SELECT team_id, COALESCE(name, team_id) FROM teams ORDER BY name").fetchall()
        return [(r[0], r[1]) for r in rows if r[0]]


def fetch_roster(filters: RosterFilters) -> List[RosterRow]:
    filters.apply_defaults()
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        sql = "SELECT c.*, t.name AS team_name FROM checkins c LEFT JOIN teams t ON t.team_id = c.team_id"
        conditions: List[str] = []
        params: List[str] = []
        if filters.ci_status:
            conditions.append("c.ci_status = ?")
            params.append(filters.ci_status.value)
        if filters.personnel_status:
            conditions.append("c.personnel_status = ?")
            params.append(filters.personnel_status.value)
        if filters.team:
            conditions.append("c.team_id = ?")
            params.append(filters.team)
        if not filters.include_no_show:
            conditions.append("c.ci_status != ?")
            params.append(CIStatus.NO_SHOW.value)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY c.updated_at DESC"
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

    roster: List[RosterRow] = []
    for row in rows:
        identity = get_person_identity(row["person_id"])
        if identity is None:
            # Skip orphaned records; log? For now just skip.
            continue
        role = row.get("role_on_team") or identity.primary_role
        if filters.role and (role or "") != filters.role:
            continue
        if filters.q:
            term = filters.q.lower()
            haystack = "|".join(
                filter(
                    None,
                    [
                        identity.person_id,
                        identity.name,
                        identity.callsign,
                        identity.phone,
                        row.get("incident_callsign"),
                        row.get("incident_phone"),
                    ],
                )
            ).lower()
            if term not in haystack:
                continue
        ci_status = CIStatus.normalize(row["ci_status"])
        personnel_status = PersonnelStatus.normalize(row["personnel_status"])
        team_label = row.get("team_name") or row.get("team_id")
        if not team_label:
            team_label = "—"
        ui_flags = UIFlags(
            hidden_by_default=ci_status is CIStatus.NO_SHOW,
            grayed=ci_status is CIStatus.DEMOBILIZED,
        )
        row_class = "row-demob" if ui_flags.grayed else None
        roster.append(
            RosterRow(
                person_id=row["person_id"],
                name=identity.name,
                role=role,
                team=team_label,
                phone=row.get("incident_phone") or identity.phone,
                callsign=row.get("incident_callsign") or identity.callsign,
                ci_status=ci_status,
                personnel_status=personnel_status,
                updated_at=row.get("updated_at"),
                team_id=row.get("team_id"),
                row_class=row_class,
                ui_flags=ui_flags,
            )
        )

    roster.sort(key=lambda r: r.name.lower())
    return roster


# ---------------------------------------------------------------------------
# Check-in persistence
# ---------------------------------------------------------------------------

def fetch_checkin(person_id: str) -> Optional[CheckInRecord]:
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        cur = conn.execute("SELECT * FROM checkins WHERE person_id = ?", (person_id,))
        row = cur.fetchone()
        return CheckInRecord.from_row(dict(row)) if row else None


def save_checkin(record: CheckInRecord) -> CheckInRecord:
    payload = record.to_payload()
    if payload.get("team_id") in {"—", ""}:
        payload["team_id"] = None
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        conn.execute(
            """
            INSERT INTO checkins (
                person_id, ci_status, personnel_status, arrival_time, location,
                location_other, shift_start, shift_end, notes, incident_callsign,
                incident_phone, team_id, role_on_team, operational_period,
                created_at, updated_at
            )
            VALUES (
                :person_id, :ci_status, :personnel_status, :arrival_time, :location,
                :location_other, :shift_start, :shift_end, :notes, :incident_callsign,
                :incident_phone, :team_id, :role_on_team, :operational_period,
                :created_at, :updated_at
            )
            ON CONFLICT(person_id) DO UPDATE SET
                ci_status=excluded.ci_status,
                personnel_status=excluded.personnel_status,
                arrival_time=excluded.arrival_time,
                location=excluded.location,
                location_other=excluded.location_other,
                shift_start=excluded.shift_start,
                shift_end=excluded.shift_end,
                notes=excluded.notes,
                incident_callsign=excluded.incident_callsign,
                incident_phone=excluded.incident_phone,
                team_id=excluded.team_id,
                role_on_team=excluded.role_on_team,
                operational_period=excluded.operational_period,
                updated_at=excluded.updated_at
            """,
            payload,
        )
        conn.commit()
    return record


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def log_history(person_id: str, actor: str, event_type: str, payload: Dict) -> None:
    entry = json.dumps(payload, separators=(",", ":"))
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        conn.execute(
            "INSERT INTO history (person_id, ts, actor, event_type, payload) VALUES (?, ?, ?, ?, ?)",
            (person_id, _now(), actor, event_type, entry),
        )
        conn.commit()


def list_history(person_id: str) -> List[HistoryItem]:
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        rows = conn.execute(
            "SELECT * FROM history WHERE person_id = ? ORDER BY ts DESC", (person_id,)
        ).fetchall()
    history: List[HistoryItem] = []
    for row in rows:
        payload = json.loads(row["payload"]) if row["payload"] else {}
        history.append(
            HistoryItem(
                id=row["id"],
                ts=row["ts"],
                actor=row["actor"],
                event_type=row["event_type"],
                payload=payload,
            )
        )
    return history


def has_activity(person_id: str) -> bool:
    """Return ``True`` if history contains activity beyond initial create."""
    activity_events = {"ASSIGNMENT_CHANGE", "NOTE", "LOCATION_CHANGE"}
    with get_incident_conn() as conn:
        schema.ensure_incident_schema(conn)
        rows = conn.execute(
            "SELECT event_type FROM history WHERE person_id = ?",
            (person_id,),
        ).fetchall()
    return any(row[0] in activity_events for row in rows)


# ---------------------------------------------------------------------------
# Offline queue persistence
# ---------------------------------------------------------------------------

def save_queue_items(path: str, items: Sequence[QueueItem]) -> None:
    payload = {
        "version": 1,
        "items": [item.to_dict() for item in items],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))


def load_queue_items(path: str) -> List[QueueItem]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return []
    items = payload.get("items", [])
    return [QueueItem.from_payload(item) for item in items]


__all__ = [
    "get_person_identity",
    "search_personnel",
    "get_distinct_roles",
    "get_distinct_teams",
    "fetch_roster",
    "fetch_checkin",
    "save_checkin",
    "log_history",
    "list_history",
    "has_activity",
    "save_queue_items",
    "load_queue_items",
]
