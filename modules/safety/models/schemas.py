from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ----------------------------------------------------------------------------
# Shared schemas
# ----------------------------------------------------------------------------


class PermissionOut(BaseModel):
    can_view: bool
    can_edit: bool
    can_publish: bool


# ----------------------------------------------------------------------------
# Safety Report
# ----------------------------------------------------------------------------


class SafetyReportBase(BaseModel):
    time: datetime
    location: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None
    flagged: bool = False
    reported_by: Optional[str] = None


class SafetyReportCreate(SafetyReportBase):
    pass


class SafetyReportRead(SafetyReportBase):
    id: int

    class Config:
        orm_mode = True


# ----------------------------------------------------------------------------
# Medical Incident
# ----------------------------------------------------------------------------


class MedicalIncidentBase(BaseModel):
    person_id: Optional[str] = None
    type: Optional[str] = None
    time: Optional[datetime] = None
    description: Optional[str] = None
    treatment_given: Optional[str] = None
    evac_required: bool = False
    reported_by: Optional[str] = None


class MedicalIncidentCreate(MedicalIncidentBase):
    pass


class MedicalIncidentRead(MedicalIncidentBase):
    id: int

    class Config:
        orm_mode = True


# ----------------------------------------------------------------------------
# Triage Entry
# ----------------------------------------------------------------------------


class TriageEntryBase(BaseModel):
    patient_tag: Optional[str] = None
    location: Optional[str] = None
    triage_level: Optional[str] = None
    time_found: Optional[datetime] = None
    treated_by: Optional[str] = None
    notes: Optional[str] = None
    disposition: Optional[str] = None


class TriageEntryCreate(TriageEntryBase):
    pass


class TriageEntryRead(TriageEntryBase):
    id: int

    class Config:
        orm_mode = True


# ----------------------------------------------------------------------------
# Hazard Zone
# ----------------------------------------------------------------------------


class HazardZoneBase(BaseModel):
    name: Optional[str] = None
    coordinates_json: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None


class HazardZoneCreate(HazardZoneBase):
    pass


class HazardZoneRead(HazardZoneBase):
    id: int

    class Config:
        orm_mode = True


# ----------------------------------------------------------------------------
# CAP ORM
# ----------------------------------------------------------------------------


class CapOrmBase(BaseModel):
    form_type: Optional[str] = None
    activity: Optional[str] = None
    participants_json: Optional[str] = None
    hazards_json: Optional[str] = None
    mitigations_json: Optional[str] = None
    residual_risk: Optional[str] = None
    created_by: Optional[str] = None


class CapOrmCreate(CapOrmBase):
    pass


class CapOrmRead(CapOrmBase):
    id: int
    mission_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ----------------------------------------------------------------------------
# ICS-206
# ----------------------------------------------------------------------------


class ICS206Create(BaseModel):
    contacts: List[str] = []
    hospitals: List[str] = []
    med_evacs: List[str] = []
    comms: List[str] = []


class ICS206Read(ICS206Create):
    pass
