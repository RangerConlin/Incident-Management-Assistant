from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter

from modules.safety import services
from modules.safety .models import schemas

router = APIRouter()


@router.get("/api/safety/reports", response_model=List[schemas.SafetyReportRead])
def get_reports(
    incident_id: str,
    severity: Optional[str] = None,
    flagged: Optional[bool] = None,
    q: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    return services.list_safety_reports(
        incident_id,
        severity=severity,
        flagged=flagged,
        q=q,
        start=start,
        end=end,
    )


@router.post("/api/safety/reports", response_model=schemas.SafetyReportRead)
def create_report(incident_id: str, report: schemas.SafetyReportCreate):
    return services.create_safety_report(incident_id, report)


@router.get("/api/medical/incidents", response_model=List[schemas.MedicalIncidentRead])
def get_incidents(incident_id: str):
    return services.list_medical_incidents(incident_id)


@router.post("/api/medical/incidents", response_model=schemas.MedicalIncidentRead)
def create_incident(incident_id: str, incident: schemas.MedicalIncidentCreate):
    return services.create_medical_incident(incident_id, incident)


@router.get("/api/medical/triage", response_model=List[schemas.TriageEntryRead])
def get_triage(incident_id: str):
    return services.list_triage_entries(incident_id)


@router.post("/api/medical/triage", response_model=schemas.TriageEntryRead)
def create_triage(incident_id: str, entry: schemas.TriageEntryCreate):
    return services.create_triage_entry(incident_id, entry)


@router.get("/api/safety/zones", response_model=List[schemas.HazardZoneRead])
def get_zones(incident_id: str):
    return services.list_hazard_zones(incident_id)


@router.post("/api/safety/zones", response_model=schemas.HazardZoneRead)
def create_zone(incident_id: str, zone: schemas.HazardZoneCreate):
    return services.create_hazard_zone(incident_id, zone)


@router.post("/api/safety/caporm", response_model=schemas.CapOrmRead)
def create_cap_orm(incident_id: str, payload: schemas.CapOrmCreate):
    return services.create_cap_orm(incident_id, payload)


@router.post("/api/safety/ics206/build", response_model=schemas.ICS206Read)
def build_ics206(incident_id: str, payload: schemas.ICS206Create):
    return services.build_ics206(incident_id, payload)


# ---------------------------------------------------------------------------
# Weather Safety minimal endpoints (for optional API consumption)
# ---------------------------------------------------------------------------


@router.get("/api/safety/weather/summary")
def weather_summary(lat: float | None = None, lon: float | None = None):
    from .weather import WeatherSafetyManager

    mgr = WeatherSafetyManager()
    if lat is not None and lon is not None:
        mgr.set_location_override(lat, lon)
    return mgr.get_summary()


@router.get("/api/safety/weather/aviation")
def weather_aviation(stations: str):
    from .weather import WeatherSafetyManager

    mgr = WeatherSafetyManager()
    station_list = [s.strip().upper() for s in stations.split(",") if s.strip()]
    return mgr.get_aviation(station_list)

