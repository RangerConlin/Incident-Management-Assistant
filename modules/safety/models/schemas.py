from datetime import datetime
from typing import List, Optional, Literal, Dict, Any
from unittest.mock import Base

from pydantic import BaseModel, Field

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

# --- Common lookups/enums used across 206 ---
CapabilityLevel = Literal["BLS", "ALS", "MFR", "Critical Care"]
TransportType = Literal["Ground", "Air"]
TraumaLevel = Literal["I", "II", "III", "IV", "None"]


# --- Medical Aid Station(s) ---
class MedicalAidStationBase(BaseModel):
    name: str = Field(..., description="Aid station name")
    location: Optional[str] = Field(None, description="Physical location / map grid")
    contact_name: Optional[str] = None
    phone_primary: Optional[str] = None
    phone_alternate: Optional[str] = None
    hours: Optional[str] = Field(None, description="Hours of operation")
    capability: Optional[CapabilityLevel] = Field(None, description="BLS/ALS")
    notes: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class MedicalAidStationCreate(MedicalAidStationBase):
    pass


class MedicalAidStationRead(MedicalAidStationBase):
    id: int


# --- Ambulance Agency(ies) ---
class AmbulanceAgencyBase(BaseModel):
    name: str = Field(..., description="Agency name")
    dispatch_center: Optional[str] = Field(None, description="Dispatch/PSAP or call center")
    contact_name: Optional[str] = None
    phone_primary: Optional[str] = None
    phone_alternate: Optional[str] = None
    capability: Optional[CapabilityLevel] = Field(None, description="BLS/ALS level typically provided")
    transport_type: Optional[TransportType] = Field(None, description="Ground or Air")
    typical_response_area: Optional[str] = None
    notes: Optional[str] = None


class AmbulanceAgencyCreate(AmbulanceAgencyBase):
    pass


class AmbulanceAgencyRead(AmbulanceAgencyBase):
    id: int


# --- Hospital(s) ---
class HospitalBase(BaseModel):
    name: str = Field(..., description="Hospital name")
    address: Optional[str] = None
    contact_name: Optional[str] = None
    phone_er: Optional[str] = Field(None, description="ED/ER direct line")
    phone_switchboard: Optional[str] = None
    travel_time_min: Optional[int] = Field(None, description="Estimated travel time in minutes")
    helipad: Optional[bool] = Field(None, description="Helipad/LZ availability")
    trauma_level: TraumaLevel = "None"
    burn_center: Optional[bool] = None
    pediatric_capability: Optional[bool] = None
    bed_available: Optional[int] = Field(None, description="Beds immediately available")
    diversion_status: Optional[str] = Field(None, description="Open/Divert/Conditional, time-stamped if possible")
    ambulance_radio_channel: Optional[str] = None
    notes: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class HospitalCreate(HospitalBase):
    pass


class HospitalRead(HospitalBase):
    id: int


# --- Medical Evacuation (Air/Ground) ---
class MedEvacBase(BaseModel):
    name: str = Field(..., description="Service name (e.g., Flight for Life)")
    transport_type: TransportType = "Air"
    contact_dispatch: Optional[str] = Field(None, description="Dispatch phone")
    radio_channel: Optional[str] = Field(None, description="Primary radio channel/name")
    activation_procedure: Optional[str] = Field(None, description="How to request/launch")
    availability_hours: Optional[str] = None
    lz_guidance: Optional[str] = Field(None, description="Landing zone guidance / hazards / coords")
    notes: Optional[str] = None


class MedEvacCreate(MedEvacBase):
    pass


class MedEvacRead(MedEvacBase):
    id: int


# --- Medical Emergency Procedures (the narrative block on ICS 206) ---
class MedicalEmergencyProcedure(BaseModel):
    report_instructions: Optional[str] = Field(
        None, description="How to report a medical emergency (who/what/how)"
    )
    on_scene_care_guidelines: Optional[str] = Field(
        None, description="Immediate actions/first aid/ALS/BLS expectations"
    )
    transport_decision: Optional[str] = Field(
        None, description="Ground vs air med-evac triggers; destination decision"
    )
    communications_plan: Optional[str] = Field(
        None, description="Primary/alt channels, who to notify, frequency/PL, call signs"
    )
    extraction_notes: Optional[str] = Field(
        None, description="Rescue/extraction considerations, hazards, special equipment"
    )
    additional_notes: Optional[str] = None


# --- Medical Communications slice (channels specific to medical traffic) ---
class MedicalCommChannel(BaseModel):
    channel_name: str = Field(..., description="Channel or talkgroup name")
    function: Optional[str] = Field(None, description="e.g., Medical Net / ER Handoff")
    zone: Optional[str] = None
    channel_number: Optional[str] = None
    rx_freq: Optional[str] = None
    rx_tone: Optional[str] = None
    tx_freq: Optional[str] = None
    tx_tone: Optional[str] = None
    mode: Optional[Literal["A", "D", "M"]] = Field(None, description="Analog/Digital/Mixed")
    remarks: Optional[str] = None


# --- ICS 206 container ---
class ICS206Create(BaseModel):
    incident_name: Optional[str] = None
    date_time_prepared: Optional[datetime] = None
    operational_period_start: Optional[datetime] = None
    operational_period_end: Optional[datetime] = None
    medical_aid_stations: List[MedicalAidStationCreate] = []
    ambulance_agencies: List[AmbulanceAgencyCreate] = []
    hospitals: List[HospitalCreate] = []
    med_evacs: List[MedEvacCreate] = []
    emergency_procedures: Optional[MedicalEmergencyProcedure] = None
    comms: List[MedicalCommChannel] = []
    prepared_by: Optional[str] = None
    approved_by: Optional[str] = None


class ICS206Read(ICS206Create):
    # If you’ll persist ICS-206 as a record, add an ID here:
    # id: int
    pass
