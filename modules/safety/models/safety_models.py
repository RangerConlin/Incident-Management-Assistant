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


