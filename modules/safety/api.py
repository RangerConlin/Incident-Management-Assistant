from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter

from . import services
from .models import schemas

router = APIRouter()


@router.get("/api/safety/reports", response_model=List[schemas.SafetyReportRead])
def get_reports(
    mission_id: str,
    severity: Optional[str] = None,
    flagged: Optional[bool] = None,
    q: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    return services.list_safety_reports(
        mission_id,
        severity=severity,
        flagged=flagged,
        q=q,
        start=start,
        end=end,
    )


@router.post("/api/safety/reports", response_model=schemas.SafetyReportRead)
def create_report(mission_id: str, report: schemas.SafetyReportCreate):
    return services.create_safety_report(mission_id, report)


@router.get("/api/medical/incidents", response_model=List[schemas.MedicalIncidentRead])
def get_incidents(mission_id: str):
    return services.list_medical_incidents(mission_id)


@router.post("/api/medical/incidents", response_model=schemas.MedicalIncidentRead)
def create_incident(mission_id: str, incident: schemas.MedicalIncidentCreate):
    return services.create_medical_incident(mission_id, incident)


@router.get("/api/medical/triage", response_model=List[schemas.TriageEntryRead])
def get_triage(mission_id: str):
    return services.list_triage_entries(mission_id)


@router.post("/api/medical/triage", response_model=schemas.TriageEntryRead)
def create_triage(mission_id: str, entry: schemas.TriageEntryCreate):
    return services.create_triage_entry(mission_id, entry)


@router.get("/api/safety/zones", response_model=List[schemas.HazardZoneRead])
def get_zones(mission_id: str):
    return services.list_hazard_zones(mission_id)


@router.post("/api/safety/zones", response_model=schemas.HazardZoneRead)
def create_zone(mission_id: str, zone: schemas.HazardZoneCreate):
    return services.create_hazard_zone(mission_id, zone)


@router.post("/api/safety/caporm", response_model=schemas.CapOrmRead)
def create_cap_orm(mission_id: str, payload: schemas.CapOrmCreate):
    return services.create_cap_orm(mission_id, payload)


@router.post("/api/safety/ics206/build", response_model=schemas.ICS206Read)
def build_ics206(mission_id: str, payload: schemas.ICS206Create):
    return services.build_ics206(mission_id, payload)

