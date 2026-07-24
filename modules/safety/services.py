from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Callable, List, Optional

from utils.api_client import api_client
from .models import schemas
from .print_ics_206 import generate as generate_ics206_pdf

_flagged_callbacks: List[Callable[[schemas.SafetyReportRead], None]] = []


def _cached_docs(incident_id: str, collection: str) -> Optional[List[dict]]:
    """Return cached incident-scoped docs for ``collection``, or None if the
    incident cache isn't loaded for this incident."""
    from utils.incident_cache import incident_cache

    if incident_cache.incident_id != str(incident_id):
        return None
    return incident_cache.get_all(collection)


def _sorted_by_id(docs: List[dict]) -> List[dict]:
    return sorted(docs, key=lambda d: d.get("id") if d.get("id") is not None else d.get("int_id", 0))


def register_flagged_callback(cb: Callable[[schemas.SafetyReportRead], None]):
    _flagged_callbacks.append(cb)


def _notify_flagged(report: schemas.SafetyReportRead):
    for cb in _flagged_callbacks:
        cb(report)


# ---------------------------------------------------------------------------
# Safety Reports
# ---------------------------------------------------------------------------

def list_safety_reports(
    incident_id: str,
    severity: Optional[str] = None,
    flagged: Optional[bool] = None,
    q: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[schemas.SafetyReportRead]:
    cached = _cached_docs(incident_id, "safety_reports")
    if cached is not None:
        rows = cached
        if severity:
            rows = [r for r in rows if r.get("severity") == severity]
        if flagged is not None:
            rows = [r for r in rows if bool(r.get("flagged")) == flagged]
        if start:
            start_iso = start.isoformat()
            rows = [r for r in rows if str(r.get("time") or "") >= start_iso]
        if end:
            end_iso = end.isoformat()
            rows = [r for r in rows if str(r.get("time") or "") <= end_iso]
        if q:
            needle = q.lower()
            rows = [r for r in rows if needle in str(r.get("notes") or "").lower()]
        rows = _sorted_by_id(rows)
        return [schemas.SafetyReportRead(**r) for r in rows]

    params: dict = {}
    if severity:
        params["severity"] = severity
    if flagged is not None:
        params["flagged"] = flagged
    if q:
        params["q"] = q
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    try:
        rows = api_client.get(f"/api/incidents/{incident_id}/safety/reports", params=params) or []
        return [schemas.SafetyReportRead(**r) for r in rows]
    except Exception:
        return []


def create_safety_report(incident_id: str, data: schemas.SafetyReportCreate) -> schemas.SafetyReportRead:
    row = api_client.post(
        f"/api/incidents/{incident_id}/safety/reports",
        json=data.dict(),
    )
    result = schemas.SafetyReportRead(**row)
    if getattr(result, "flagged", False):
        _notify_flagged(result)
    if getattr(result, "team_id", None):
        try:
            from modules.operations.data.repository import ics214_log_entry
            severity = getattr(result, "severity", None) or "Unknown"
            location = getattr(result, "location", None)
            loc_part = f" at {location}" if location else ""
            ics214_log_entry("team", result.team_id,
                             f"Safety report{loc_part}: {severity} severity", source="auto")
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# Medical Incidents
# ---------------------------------------------------------------------------

def list_medical_incidents(incident_id: str) -> List[schemas.MedicalIncidentRead]:
    cached = _cached_docs(incident_id, "medical_incidents")
    if cached is not None:
        return [schemas.MedicalIncidentRead(**r) for r in _sorted_by_id(cached)]
    try:
        rows = api_client.get(f"/api/incidents/{incident_id}/medical/incidents") or []
        return [schemas.MedicalIncidentRead(**r) for r in rows]
    except Exception:
        return []


def create_medical_incident(incident_id: str, data: schemas.MedicalIncidentCreate) -> schemas.MedicalIncidentRead:
    row = api_client.post(f"/api/incidents/{incident_id}/medical/incidents", json=data.dict())
    result = schemas.MedicalIncidentRead(**row)
    if getattr(result, "team_id", None):
        try:
            from modules.operations.data.repository import ics214_log_entry
            incident_type = getattr(result, "type", None) or "medical incident"
            evac = " — evacuation required" if getattr(result, "evac_required", False) else ""
            ics214_log_entry("team", result.team_id,
                             f"Medical incident: {incident_type}{evac}", source="auto")
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# Triage Entries
# ---------------------------------------------------------------------------

def list_triage_entries(incident_id: str) -> List[schemas.TriageEntryRead]:
    cached = _cached_docs(incident_id, "triage_entries")
    if cached is not None:
        return [schemas.TriageEntryRead(**r) for r in _sorted_by_id(cached)]
    try:
        rows = api_client.get(f"/api/incidents/{incident_id}/medical/triage") or []
        return [schemas.TriageEntryRead(**r) for r in rows]
    except Exception:
        return []


def create_triage_entry(incident_id: str, data: schemas.TriageEntryCreate) -> schemas.TriageEntryRead:
    row = api_client.post(f"/api/incidents/{incident_id}/medical/triage", json=data.dict())
    return schemas.TriageEntryRead(**row)


# ---------------------------------------------------------------------------
# Hazard Zones
# ---------------------------------------------------------------------------

def _hazard_zone_from_spatial_feature(row: dict) -> schemas.HazardZoneRead:
    geometry_wkt = row.get("geometry_wkt") or ""
    return schemas.HazardZoneRead(
        id=int(row.get("id") or row.get("int_id") or 0),
        incident_id=row.get("incident_id"),
        name=row.get("label") or "",
        coordinates_json=geometry_wkt,
        geometry_wkt=geometry_wkt,
        feature_subtype=row.get("feature_subtype"),
        severity=row.get("feature_subtype") or row.get("status") or "",
        description=row.get("description") or "",
        created_at=row.get("created_at") or "",
        updated_at=row.get("updated_at") or "",
    )


def list_hazard_zones(incident_id: str) -> List[schemas.HazardZoneRead]:
    cached = _cached_docs(incident_id, "spatial_features")
    if cached is not None:
        rows = [
            row
            for row in cached
            if row.get("feature_type") == "hazard_zone"
            and not bool(row.get("deleted"))
            and not bool(row.get("is_archived"))
        ]
        return [_hazard_zone_from_spatial_feature(r) for r in _sorted_by_id(rows)]
    try:
        rows = api_client.get(
            f"/api/incidents/{incident_id}/gis/features/by-type/hazard_zone"
        ) or []
        return [_hazard_zone_from_spatial_feature(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# ICS-206 Builder
# ---------------------------------------------------------------------------

def build_ics206(incident_id: str, payload: schemas.ICS206Create) -> schemas.ICS206Read:
    data = payload.dict()
    row = api_client.post(f"/api/incidents/{incident_id}/safety/ics206/build", json=data)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    from utils import incident_storage
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is not None:
        forms_dir = str(paths.forms_exports)
        os.makedirs(forms_dir, exist_ok=True)
        json_path = os.path.join(forms_dir, f"ICS206-{timestamp}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        html = "<html><body><pre>" + json.dumps(data, indent=2) + "</pre></body></html>"
        generate_ics206_pdf(incident_id, html)
    return schemas.ICS206Read(**data)


# ---------------------------------------------------------------------------
# ICS-208 — Safety Message
# ---------------------------------------------------------------------------

def get_ics208(incident_id: str, op_period: int) -> dict:
    try:
        return api_client.get(f"/api/incidents/{incident_id}/safety/ics208", params={"op": op_period}) or {}
    except Exception:
        return {}


def save_ics208(incident_id: str, data: dict) -> dict:
    return api_client.put(f"/api/incidents/{incident_id}/safety/ics208", json=data)


# ---------------------------------------------------------------------------
# IWI — Safety Incident Reports
# ---------------------------------------------------------------------------

def list_iwi_reports(
    incident_id: str,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    cached = _cached_docs(incident_id, "iwi_reports")
    if cached is not None:
        rows = cached
        if severity:
            rows = [r for r in rows if r.get("actual_severity") == severity]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return _sorted_by_id(rows)

    params: dict = {}
    if severity:
        params["severity"] = severity
    if status:
        params["status"] = status
    try:
        return api_client.get(f"/api/incidents/{incident_id}/safety/iwi", params=params) or []
    except Exception:
        return []


def get_iwi_report(incident_id: str, report_id: str) -> Optional[dict]:
    cached = _cached_docs(incident_id, "iwi_reports")
    if cached is not None:
        for doc in cached:
            if str(doc.get("_id")) == str(report_id):
                return dict(doc)
    try:
        return api_client.get(f"/api/incidents/{incident_id}/safety/iwi/{report_id}")
    except Exception:
        return None


def create_iwi_report(incident_id: str, data: dict) -> dict:
    return api_client.post(f"/api/incidents/{incident_id}/safety/iwi", json=data)


def update_iwi_report(incident_id: str, report_id: str, data: dict) -> dict:
    return api_client.put(f"/api/incidents/{incident_id}/safety/iwi/{report_id}", json=data)


def signoff_iwi_report(incident_id: str, report_id: str, role: str, name: str) -> dict:
    return api_client.post(
        f"/api/incidents/{incident_id}/safety/iwi/{report_id}/signoff",
        json={"role": role, "name": name},
    )


def delete_iwi_report(incident_id: str, report_id: str) -> None:
    try:
        api_client.delete(f"/api/incidents/{incident_id}/safety/iwi/{report_id}")
    except Exception:
        pass


__all__ = [
    "register_flagged_callback",
    "list_safety_reports",
    "create_safety_report",
    "list_medical_incidents",
    "create_medical_incident",
    "list_triage_entries",
    "create_triage_entry",
    "list_hazard_zones",
    "build_ics206",
    "list_iwi_reports",
    "get_iwi_report",
    "create_iwi_report",
    "update_iwi_report",
    "signoff_iwi_report",
    "delete_iwi_report",
]
