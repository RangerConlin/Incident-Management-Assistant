from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Callable, List, Optional

from .models import safety_models as models
from .models import schemas
from .print_ics_206 import generate as generate_ics206_pdf
from .repository import with_incident_session

# In-memory audit log and notification hooks
_audit_log: List[dict] = []
_flagged_callbacks: List[Callable[[schemas.SafetyReportRead], None]] = []


def register_flagged_callback(cb: Callable[[schemas.SafetyReportRead], None]):
    """Register a callback for flagged safety reports."""
    _flagged_callbacks.append(cb)


def _notify_flagged(report: schemas.SafetyReportRead):
    for cb in _flagged_callbacks:
        cb(report)


def _audit(action: str, model: str, data: dict):
    _audit_log.append({
        "ts": datetime.utcnow().isoformat(),
        "action": action,
        "model": model,
        "data": data,
    })


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
    with with_incident_session(incident_id) as session:
        query = session.query(models.SafetyReport)
        if severity:
            query = query.filter_by(severity=severity)
        if flagged is not None:
            query = query.filter_by(flagged=flagged)
        if start:
            query = query.filter(models.SafetyReport.time >= start)
        if end:
            query = query.filter(models.SafetyReport.time <= end)
        if q:
            like = f"%{q}%"
            query = query.filter(models.SafetyReport.notes.ilike(like))
        return [schemas.SafetyReportRead.from_orm(r) for r in query.all()]


def create_safety_report(incident_id: str, data: schemas.SafetyReportCreate) -> schemas.SafetyReportRead:
    with with_incident_session(incident_id) as session:
        report = models.SafetyReport(**data.dict())
        session.add(report)
        session.commit()
        session.refresh(report)
        result = schemas.SafetyReportRead.from_orm(report)
        _audit("create", "SafetyReport", data.dict())
        if report.flagged:
            _notify_flagged(result)
        return result


# ---------------------------------------------------------------------------
# Medical Incidents
# ---------------------------------------------------------------------------

def list_medical_incidents(incident_id: str) -> List[schemas.MedicalIncidentRead]:
    with with_incident_session(incident_id) as session:
        incidents = session.query(models.MedicalIncident).all()
        return [schemas.MedicalIncidentRead.from_orm(i) for i in incidents]


def create_medical_incident(incident_id: str, data: schemas.MedicalIncidentCreate) -> schemas.MedicalIncidentRead:
    with with_incident_session(incident_id) as session:
        incident = models.MedicalIncident(**data.dict())
        session.add(incident)
        session.commit()
        session.refresh(incident)
        _audit("create", "MedicalIncident", data.dict())
        return schemas.MedicalIncidentRead.from_orm(incident)


# ---------------------------------------------------------------------------
# Triage Entries
# ---------------------------------------------------------------------------

def list_triage_entries(incident_id: str) -> List[schemas.TriageEntryRead]:
    with with_incident_session(incident_id) as session:
        entries = session.query(models.TriageEntry).all()
        return [schemas.TriageEntryRead.from_orm(e) for e in entries]


def create_triage_entry(incident_id: str, data: schemas.TriageEntryCreate) -> schemas.TriageEntryRead:
    with with_incident_session(incident_id) as session:
        entry = models.TriageEntry(**data.dict())
        session.add(entry)
        session.commit()
        session.refresh(entry)
        _audit("create", "TriageEntry", data.dict())
        return schemas.TriageEntryRead.from_orm(entry)


# ---------------------------------------------------------------------------
# Hazard Zones
# ---------------------------------------------------------------------------

def list_hazard_zones(incident_id: str) -> List[schemas.HazardZoneRead]:
    with with_incident_session(incident_id) as session:
        zones = session.query(models.HazardZone).all()
        return [schemas.HazardZoneRead.from_orm(z) for z in zones]


def create_hazard_zone(incident_id: str, data: schemas.HazardZoneCreate) -> schemas.HazardZoneRead:
    with with_incident_session(incident_id) as session:
        zone = models.HazardZone(**data.dict())
        session.add(zone)
        session.commit()
        session.refresh(zone)
        _audit("create", "HazardZone", data.dict())
        return schemas.HazardZoneRead.from_orm(zone)


# ---------------------------------------------------------------------------
# CAP ORM
# ---------------------------------------------------------------------------

def create_cap_orm(incident_id: str, data: schemas.CapOrmCreate) -> schemas.CapOrmRead:
    with with_incident_session(incident_id) as session:
        orm = models.CapOrmForm(incident_id=incident_id, **data.dict())
        session.add(orm)
        session.commit()
        session.refresh(orm)
        _audit("create", "CapOrmForm", data.dict())
        return schemas.CapOrmRead.from_orm(orm)


# ---------------------------------------------------------------------------
# ICS-206 Builder
# ---------------------------------------------------------------------------

def build_ics206(incident_id: str, payload: schemas.ICS206Create) -> schemas.ICS206Read:
    data = payload.dict()
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    forms_dir = os.path.join("data", "incidents", incident_id, "forms")
    os.makedirs(forms_dir, exist_ok=True)

    json_path = os.path.join(forms_dir, f"ICS206-{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    html = "<html><body><pre>" + json.dumps(data, indent=2) + "</pre></body></html>"
    generate_ics206_pdf(incident_id, html)

    _audit("build", "ICS206", data)
    return schemas.ICS206Read(**data)


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
]
