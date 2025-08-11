from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MedicalIncident(Base):
    __tablename__ = "medical_incidents"

    id = Column(Integer, primary_key=True)
    person_id = Column(String, index=True)
    type = Column(String)
    time = Column(DateTime)
    description = Column(Text)
    treatment_given = Column(Text)
    evac_required = Column(Boolean, default=False)
    reported_by = Column(String)


class SafetyReport(Base):
    __tablename__ = "safety_reports"

    id = Column(Integer, primary_key=True)
    time = Column(DateTime)
    location = Column(String)
    severity = Column(String)
    notes = Column(Text)
    flagged = Column(Boolean, default=False)
    reported_by = Column(String)


class TriageEntry(Base):
    __tablename__ = "triage_entries"

    id = Column(Integer, primary_key=True)
    patient_tag = Column(String, index=True)
    location = Column(String)
    triage_level = Column(String)
    time_found = Column(DateTime)
    treated_by = Column(String)
    notes = Column(Text)
    disposition = Column(String)


class HazardZone(Base):
    __tablename__ = "hazard_zones"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    coordinates_json = Column(Text)
    severity = Column(String)
    description = Column(Text)


class CapOrmForm(Base):
    __tablename__ = "cap_orm_forms"

    id = Column(Integer, primary_key=True)
    mission_id = Column(String, index=True)
    form_type = Column(String)
    activity = Column(String)
    participants_json = Column(Text)
    hazards_json = Column(Text)
    mitigations_json = Column(Text)
    residual_risk = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
