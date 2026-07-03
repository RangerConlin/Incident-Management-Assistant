"""API-backed repository helpers for the Logistics Check-In module."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from .models import (
    CheckInRecord,
    CIStatus,
    HistoryItem,
    Location,
    PersonnelIdentity,
    PersonnelStatus,
    QueueItem,
    RosterFilters,
    RosterRow,
)

_BASE_PERSONNEL = "/api/master/personnel"


def _client():
    from utils.api_client import api_client
    return api_client


def _incident_base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}/checkin"


def _identity_from_doc(doc: dict) -> PersonnelIdentity:
    return PersonnelIdentity(
        person_record=int(doc.get("person_record") or 0),
        person_id=str(doc.get("person_id") or ""),
        name=doc.get("name") or "",
        primary_role=doc.get("primary_role") or doc.get("role"),
        phone=doc.get("phone"),
        callsign=doc.get("callsign"),
        certifications=doc.get("certifications"),
        rank=doc.get("rank"),
        is_medic=doc.get("is_medic"),
    )


# ---------------------------------------------------------------------------
# Master lookups
# ---------------------------------------------------------------------------

def get_person_identity(person_record: int) -> Optional[PersonnelIdentity]:
    """Resolve a person's display identity by person_record (internal integer key)."""
    try:
        from utils import incident_context
        incident_id = incident_context.get_active_incident_id()
    except Exception:
        incident_id = None
    if incident_id:
        try:
            doc = _client().get(f"/api/incidents/{incident_id}/operations/personnel/{person_record}")
            if doc:
                return _identity_from_doc(doc)
        except Exception:
            pass
    try:
        doc = _client().get(f"{_BASE_PERSONNEL}/{person_record}")
        return _identity_from_doc(doc) if doc else None
    except Exception:
        return None


def search_personnel(term: str, limit: int = 50) -> List[PersonnelIdentity]:
    try:
        docs = _client().get(f"{_BASE_PERSONNEL}/search", params={"q": term, "limit": limit}) or []
        return [_identity_from_doc(d) for d in docs]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Roster queries
# ---------------------------------------------------------------------------

def get_distinct_roles() -> List[str]:
    from utils import incident_context
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return []
    try:
        return _client().get(f"{_incident_base(incident_id)}/roles") or []
    except Exception:
        return []


def get_distinct_teams():
    from utils import incident_context
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return []
    try:
        docs = _client().get(f"{_incident_base(incident_id)}/teams") or []
        return [(d["team_id"], d["team_name"]) for d in docs if d.get("team_id")]
    except Exception:
        return []


def fetch_roster(filters: RosterFilters) -> List[RosterRow]:
    from utils import incident_context
    filters.apply_defaults()
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return []
    params: dict = {"include_no_show": filters.include_no_show}
    if filters.q:
        params["q"] = filters.q
    if filters.ci_status:
        params["ci_status"] = filters.ci_status.value
    if filters.personnel_status:
        params["personnel_status"] = filters.personnel_status.value
    if filters.role:
        params["role"] = filters.role
    if filters.team:
        params["team"] = filters.team
    try:
        rows = _client().get(f"{_incident_base(incident_id)}/roster", params=params) or []
    except Exception:
        return []

    result = []
    for row in rows:
        try:
            ci_status = CIStatus.normalize(row.get("ci_status") or "CheckedIn")
            personnel_status = PersonnelStatus.normalize(row.get("personnel_status") or "Available")
        except ValueError:
            continue
        from .models import UIFlags
        ui_flags_data = row.get("ui_flags") or {}
        ui_flags = UIFlags(
            hidden_by_default=bool(ui_flags_data.get("hidden_by_default")),
            grayed=bool(ui_flags_data.get("grayed")),
        )
        result.append(RosterRow(
            person_record=int(row.get("person_record") or 0),
            person_id=row.get("person_id") or "",
            name=row.get("name") or "",
            role=row.get("role"),
            team=row.get("team"),
            phone=row.get("phone"),
            callsign=row.get("callsign"),
            ci_status=ci_status,
            personnel_status=personnel_status,
            updated_at=row.get("updated_at") or "",
            team_id=row.get("team_id"),
            row_class=row.get("row_class"),
            ui_flags=ui_flags,
        ))
    return result


# ---------------------------------------------------------------------------
# Check-in persistence
# ---------------------------------------------------------------------------

def _resource_status_to_checkin(doc: dict) -> CheckInRecord:
    """Convert a resource_status document to CheckInRecord shape."""
    raw_status = doc.get("status") or "Pending"
    # resource_status uses "Checked In"; CIStatus uses "CheckedIn"
    if raw_status == "Checked In":
        raw_status = "CheckedIn"
    elif raw_status == "NoShow":
        raw_status = "Not Coming"
    try:
        ci_status = CIStatus.normalize(raw_status)
    except ValueError:
        ci_status = CIStatus.PENDING

    arrival = (
        doc.get("checked_in_time")
        or doc.get("created_at")
        or datetime.now().astimezone().isoformat(timespec="seconds")
    )
    location_str = doc.get("location") or "ICP"
    try:
        location = Location.normalize(location_str)
    except ValueError:
        location = Location.ICP

    return CheckInRecord(
        person_record=int(doc.get("record_id") or 0),
        status=ci_status,
        ci_status=ci_status,
        arrival_time=arrival,
        location=location,
        notes=doc.get("notes"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


_CHECKED_IN_STATUSES = {
    "Checked In",
    "Assigned",
    "Available",
    "Out of Service",
    "Preparing for Demobilization",
}

_CISTATUS_TO_RS = {
    "CheckedIn": "Checked In",
    "NoShow": "Not Coming",
}


def fetch_checkin(person_record: int) -> Optional[CheckInRecord]:
    from utils import incident_context
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return None
    try:
        doc = _client().get(
            f"/api/incidents/{incident_id}/resource-status/by-entity",
            params={"entity_type": "personnel", "record_id": str(person_record)},
        )
        return _resource_status_to_checkin(doc) if doc else None
    except Exception:
        return None


def save_checkin(record: CheckInRecord) -> CheckInRecord:
    from utils import incident_context
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return record

    ci_value = record.status.value
    rs_status = _CISTATUS_TO_RS.get(ci_value, ci_value)

    resource_name = str(record.person_record)
    person_id: Optional[str] = None
    try:
        master = _client().get(f"/api/master/personnel/{record.person_record}")
        if master:
            resource_name = master.get("name") or str(record.person_record)
            person_id = master.get("person_id") or None
    except Exception:
        pass

    payload: dict = {
        "entity_type": "personnel",
        "record_id": record.person_record,
        "resource_id": person_id or str(record.person_record),
        "resource_name": resource_name,
        "resource_type": "Personnel",
        "status": rs_status,
        "changed_by": "Check-In",
    }
    if record.notes:
        payload["notes"] = record.notes
    if rs_status in _CHECKED_IN_STATUSES and record.arrival_time:
        payload["checked_in_time"] = record.arrival_time
    if record.location:
        payload["location"] = record.location.value

    try:
        _client().post(f"/api/incidents/{incident_id}/resource-status", json=payload)
    except Exception:
        pass
    return record


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def log_history(person_record: int, actor: str, event_type: str, payload: Dict) -> None:
    from utils import incident_context
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return
    entry = {
        "person_record": person_record,
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
    }
    try:
        _client().post(f"{_incident_base(incident_id)}/history", json=entry)
    except Exception:
        pass


def list_history(person_record: int) -> List[HistoryItem]:
    from utils import incident_context
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        return []
    try:
        docs = _client().get(f"{_incident_base(incident_id)}/history/{person_record}") or []
    except Exception:
        return []
    result = []
    for i, row in enumerate(docs):
        result.append(HistoryItem(
            id=i,
            ts=row.get("ts") or "",
            actor=row.get("actor") or "",
            event_type=row.get("event_type") or "",
            payload=row.get("payload") or {},
        ))
    return result


def has_activity(person_record: int) -> bool:
    activity_events = {"ASSIGNMENT_CHANGE", "NOTE", "LOCATION_CHANGE"}
    items = list_history(person_record)
    return any(item.event_type in activity_events for item in items)


# ---------------------------------------------------------------------------
# Offline queue persistence (file-based, no SQLite dependency)
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
