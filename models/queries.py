from __future__ import annotations

from typing import List, Dict, Any, Optional


def fetch_team_personnel(team_id: int) -> List[Dict[str, Any]]:
    """Return personnel assigned to the given team.

    Team membership is stored as master personnel ids (see the incident
    teams collection's ``members_json``/``member_personnel_ids``), not a
    local SQLite row number — so this resolves each member through the
    master-id-aware identity chain (master roster + the incident's
    check-in copy), the same chain ``get_person_identity`` uses.
    """
    try:
        from utils.api_client import api_client
        from utils import incident_context
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return []
        team_doc = api_client.get(f"/api/incidents/{incident_id}/operations/teams/{int(team_id)}")
    except Exception:
        return []
    if not team_doc:
        return []

    member_ids: List[int] = []
    raw = team_doc.get("members_json")
    if raw:
        try:
            import json
            member_ids = [int(x) for x in json.loads(raw) or []]
        except Exception:
            member_ids = []
    if not member_ids:
        for v in (team_doc.get("member_person_records") or team_doc.get("member_personnel_ids") or []):
            try:
                member_ids.append(int(v))
            except (TypeError, ValueError):
                continue

    if not member_ids:
        return []

    from modules.logistics.checkin import repository as ci_repo
    out: List[Dict[str, Any]] = []
    for pid in member_ids:
        try:
            ident = ci_repo.get_person_identity(str(pid))
        except Exception:
            ident = None
        if ident is None:
            continue
        out.append({
            "id": pid,
            "name": ident.name,
            "role": ident.primary_role,
            "phone": ident.phone,
            "callsign": ident.callsign,
            "identifier": ident.callsign,
            "rank": ident.rank,
            "organization": ident.home_unit,
            "is_medic": bool(ident.is_medic),
        })
    return out


def _get_team_doc(team_id: int) -> Optional[Dict[str, Any]]:
    try:
        from utils.api_client import api_client
        from utils import incident_context
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return None
        return api_client.get(f"/api/incidents/{incident_id}/operations/teams/{int(team_id)}")
    except Exception:
        return None


def _team_resource_ids(team_doc: Dict[str, Any], json_key: str, list_key: str) -> List[Any]:
    raw = team_doc.get(json_key)
    if raw:
        try:
            import json
            ids = json.loads(raw) or []
            if ids:
                return ids
        except Exception:
            pass
    return list(team_doc.get(list_key) or [])


def fetch_team_vehicles(team_id: int) -> List[Dict[str, Any]]:
    """Vehicles assigned to a team, resolved against the master vehicle
    catalog — vehicle ids are master ids (``vehicle_id``), not local rows.
    """
    team_doc = _get_team_doc(team_id)
    if not team_doc:
        return []
    ids = _team_resource_ids(team_doc, "vehicles_json", "vehicle_ids")
    if not ids:
        return []
    from utils.api_client import api_client
    out: List[Dict[str, Any]] = []
    for vid in ids:
        try:
            doc = api_client.get(f"/api/master/vehicles/{vid}")
        except Exception:
            doc = None
        if not doc:
            continue
        name = " ".join(v for v in (doc.get("make"), doc.get("model")) if v).strip()
        out.append({
            "id": doc.get("id"),
            "name": name or f"Vehicle {doc.get('id')}",
            "callsign": doc.get("tags") or "",
            "type": doc.get("type_id"),
        })
    return out


def fetch_team_equipment(team_id: int) -> List[Dict[str, Any]]:
    """Equipment assigned to a team, resolved against the master equipment
    catalog — equipment ids are master ids (``int_id``), not local rows.
    """
    team_doc = _get_team_doc(team_id)
    if not team_doc:
        return []
    ids = _team_resource_ids(team_doc, "equipment_json", "equipment_ids")
    if not ids:
        return []
    from utils.api_client import api_client
    out: List[Dict[str, Any]] = []
    for eid in ids:
        try:
            doc = api_client.get(f"/api/master/equipment/{eid}")
        except Exception:
            doc = None
        if not doc:
            continue
        out.append({
            "id": doc.get("id"),
            "name": doc.get("name") or f"Equipment {doc.get('id')}",
            "type": doc.get("type"),
            "serial": doc.get("serial_number"),
        })
    return out


def fetch_team_aircraft(team_id: int) -> List[Dict[str, Any]]:
    """Aircraft assigned to a team, resolved against the master aircraft
    catalog — aircraft ids are master ids (``int_id``), not local rows.
    """
    team_doc = _get_team_doc(team_id)
    if not team_doc:
        return []
    ids = _team_resource_ids(team_doc, "aircraft_json", "aircraft_ids")
    if not ids:
        return []
    from utils.api_client import api_client
    out: List[Dict[str, Any]] = []
    for aid in ids:
        try:
            doc = api_client.get(f"/api/master/aircraft/{aid}")
        except Exception:
            doc = None
        if not doc:
            continue
        out.append({
            "id": doc.get("id"),
            "tail_number": doc.get("tail_number"),
            "type": doc.get("type"),
            "callsign": doc.get("callsign"),
            "status": doc.get("status"),
        })
    return out


def _resource_team_index(json_key: str, list_key: str) -> Dict[str, str]:
    """Map resource id (str) -> assigned team name/callsign.

    Vehicles/equipment have no team field on their master record — the
    team's own id list is the only record of assignment, so build a
    reverse index by scanning all teams in the active incident.
    """
    try:
        from utils.api_client import api_client
        from utils import incident_context
        incident_id = incident_context.get_active_incident_id()
        if not incident_id:
            return {}
        teams = api_client.get(f"/api/incidents/{incident_id}/operations/teams") or []
    except Exception:
        return {}
    index: Dict[str, str] = {}
    for t in teams:
        name = t.get("name") or t.get("callsign") or ""
        for rid in _team_resource_ids(t, json_key, list_key):
            index[str(rid)] = name
    return index


def list_incident_vehicles() -> List[Dict[str, Any]]:
    """Return the master vehicle catalog, annotated with each vehicle's
    current team assignment (if any) within the active incident."""
    try:
        from utils.api_client import api_client
        docs = api_client.get("/api/master/vehicles") or []
    except Exception:
        return []
    team_index = _resource_team_index("vehicles_json", "vehicle_ids")
    out: List[Dict[str, Any]] = []
    for d in docs:
        rid = str(d.get("id"))
        name = " ".join(v for v in (d.get("make"), d.get("model")) if v).strip()
        out.append({
            "id": d.get("id"),
            "name": name or f"Vehicle {rid}",
            "callsign": d.get("tags") or "",
            "type": d.get("type_id"),
            "team_id": None,
            "team_name": team_index.get(rid),
            "status": d.get("status_id"),
            "eta": None,
        })
    return out


def list_available_aircraft(include_team_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List master aircraft not currently assigned to any team in the
    active incident; optionally include those already on include_team_id."""
    try:
        from utils.api_client import api_client
        docs = api_client.get("/api/master/aircraft") or []
    except Exception:
        return []
    team_index = _resource_team_index("aircraft_json", "aircraft_ids")
    include_team_doc = _get_team_doc(include_team_id) if include_team_id is not None else None
    own_name = (include_team_doc or {}).get("name") if include_team_doc else None
    out: List[Dict[str, Any]] = []
    for d in docs:
        rid = str(d.get("id"))
        assigned_team_name = team_index.get(rid)
        if assigned_team_name and assigned_team_name != own_name:
            continue
        out.append({
            "id": d.get("id"),
            "tail_number": d.get("tail_number"),
            "callsign": d.get("callsign"),
            "team_id": include_team_id if assigned_team_name else None,
            "status": d.get("status"),
        })
    return out


def list_incident_equipment() -> List[Dict[str, Any]]:
    """Return the master equipment catalog, annotated with each item's
    current team assignment (if any) within the active incident."""
    try:
        from utils.api_client import api_client
        docs = api_client.get("/api/master/equipment") or []
    except Exception:
        return []
    team_index = _resource_team_index("equipment_json", "equipment_ids")
    out: List[Dict[str, Any]] = []
    for d in docs:
        rid = str(d.get("id"))
        out.append({
            "id": d.get("id"),
            "name": d.get("name") or f"Equipment {rid}",
            "type": d.get("type"),
            "serial": d.get("serial_number"),
            "team_id": None,
            "team_name": team_index.get(rid),
            "status": None,
            "eta": None,
        })
    return out
