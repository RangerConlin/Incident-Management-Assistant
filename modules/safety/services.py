from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Callable, List, Optional

from utils.api_client import api_client
from .models import schemas
from .print_ics_206 import generate as generate_ics206_pdf

_flagged_callbacks: List[Callable[[schemas.SafetyReportRead], None]] = []


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
    return result


# ---------------------------------------------------------------------------
# Medical Incidents
# ---------------------------------------------------------------------------

def list_medical_incidents(incident_id: str) -> List[schemas.MedicalIncidentRead]:
    try:
        rows = api_client.get(f"/api/incidents/{incident_id}/medical/incidents") or []
        return [schemas.MedicalIncidentRead(**r) for r in rows]
    except Exception:
        return []


def create_medical_incident(incident_id: str, data: schemas.MedicalIncidentCreate) -> schemas.MedicalIncidentRead:
    row = api_client.post(f"/api/incidents/{incident_id}/medical/incidents", json=data.dict())
    return schemas.MedicalIncidentRead(**row)


# ---------------------------------------------------------------------------
# Triage Entries
# ---------------------------------------------------------------------------

def list_triage_entries(incident_id: str) -> List[schemas.TriageEntryRead]:
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

def list_hazard_zones(incident_id: str) -> List[schemas.HazardZoneRead]:
    try:
        rows = api_client.get(f"/api/incidents/{incident_id}/safety/zones") or []
        return [schemas.HazardZoneRead(**r) for r in rows]
    except Exception:
        return []


def create_hazard_zone(incident_id: str, data: schemas.HazardZoneCreate) -> schemas.HazardZoneRead:
    row = api_client.post(f"/api/incidents/{incident_id}/safety/zones", json=data.dict())
    return schemas.HazardZoneRead(**row)


# ---------------------------------------------------------------------------
# CAP ORM
# ---------------------------------------------------------------------------

def create_cap_orm(incident_id: str, data: schemas.CapOrmCreate) -> schemas.CapOrmRead:
    row = api_client.post(f"/api/incidents/{incident_id}/safety/caporm", json=data.dict())
    return schemas.CapOrmRead(**row)


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
    "create_hazard_zone",
    "create_cap_orm",
    "build_ics206",
    "list_iwi_reports",
    "get_iwi_report",
    "create_iwi_report",
    "update_iwi_report",
    "signoff_iwi_report",
    "delete_iwi_report",
]
