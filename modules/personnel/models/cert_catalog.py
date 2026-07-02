"""Hardcoded certification catalog (authoritative in production).

This module defines the certification catalog used by the application.
The code catalog is the single source of truth.

Notes
- IDs are stable integers and MUST NOT be reused once shipped. Bump
  CATALOG_VERSION any time entries change.
- Tags allow grouping certifications into qualification profiles.
- is_medical is the direct source of truth for the medic checkoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


CATALOG_VERSION = "1.2.0"


@dataclass(frozen=True)
class CertType:
    """Immutable certification type record."""

    id: int
    code: str
    name: str
    category: str
    issuing_org: str
    parent_id: Optional[int] = None
    tags: Tuple[str, ...] = tuple()
    is_medical: bool = False


CATALOG: List[CertType] = [
    # --- ICS/NIMS Courses ---
    CertType(1001, "IS-100", "Introduction to ICS", "ICS/NIMS", "FEMA"),
    CertType(1002, "IS-200", "Basic ICS", "ICS/NIMS", "FEMA"),
    CertType(1003, "ICS-300", "Intermediate ICS", "ICS/NIMS", "FEMA"),
    CertType(1004, "ICS-400", "Advanced ICS", "ICS/NIMS", "FEMA"),
    CertType(1005, "IS-700", "NIMS", "ICS/NIMS", "FEMA"),
    CertType(1006, "IS-800", "National Response Framework", "ICS/NIMS", "FEMA"),

    # --- ICS/NIMS Position Qualifications ---
    CertType(1007, "PIO", "Public Information Officer", "ICS/NIMS", "FEMA", tags=("PIO",)),
    CertType(1008, "LO", "Liaison Officer", "ICS/NIMS", "FEMA", tags=("LO",)),
    CertType(1012, "SITL", "Situation Unit Leader", "ICS/NIMS", "FEMA", tags=("SITL",)),
    CertType(1013, "RESL", "Resources Unit Leader", "ICS/NIMS", "FEMA", tags=("RESL",)),
    CertType(1014, "DOCL", "Documentation Unit Leader", "ICS/NIMS", "FEMA", tags=("DOCL",)),
    CertType(1015, "DMOB", "Demobilization Unit Leader", "ICS/NIMS", "FEMA", tags=("DMOB",)),
    CertType(1016, "GSUL", "Ground Support Unit Leader", "ICS/NIMS", "FEMA", tags=("GSUL",)),
    CertType(1017, "MEDL", "Medical Unit Leader", "ICS/NIMS", "FEMA", tags=("MEDL",)),
    CertType(1018, "FDUL", "Food Unit Leader", "ICS/NIMS", "FEMA", tags=("FDUL",)),
    CertType(1019, "FCLD", "Facilities Unit Leader", "ICS/NIMS", "FEMA", tags=("FCLD",)),

    # --- Medical ---
    CertType(2001, "FA-CPR", "First Aid / CPR", "Medical", "AHA/Red Cross"),
    CertType(2002, "MFR", "Medical First Responder", "Medical", "State EMS", tags=("MEDICAL",), is_medical=True),
    CertType(2003, "EMT", "Emergency Medical Technician", "Medical", "State EMS", tags=("MEDIC", "MEDICAL"), is_medical=True),
    CertType(2004, "EMT-A", "Emergency Medical Technician - Advanced", "Medical", "State EMS", tags=("MEDIC", "MEDICAL"), is_medical=True),
    CertType(2005, "EMT-P", "Paramedic", "Medical", "State EMS", tags=("MEDIC", "MEDICAL"), is_medical=True),
    CertType(2006, "WFA", "Wilderness First Aid", "Medical", "NOLS", tags=("MEDICAL",), is_medical=True),
    CertType(2007, "WFR", "Wilderness First Responder", "Medical", "NOLS", tags=("MEDIC", "MEDICAL"), is_medical=True),
    CertType(2008, "WEMT", "Wilderness EMT", "Medical", "NOLS", tags=("MEDIC", "MEDICAL"), is_medical=True),

    # --- SAR Roles ---
    CertType(3051, "LSAR", "Ground Search and Rescue Team Member", "SAR", "AHJ", tags=("SAR_FIELD",)),
    CertType(3052, "LSAR-TL", "Ground Search and Rescue Team Leader", "SAR", "AHJ", parent_id=3051, tags=("LSAR_TL", "SAR_FIELD", "DF_FIELD")),
    CertType(3053, "SARTECH IV", "SARTECH IV", "SAR", "NASAR", tags=("SAR_FIELD",)),
    CertType(3054, "SARTECH III", "SARTECH III", "SAR", "NASAR", tags=("SAR_FIELD",)),
    CertType(3055, "SARTECH II", "SARTECH II", "SAR", "NASAR", tags=("SAR_FIELD",)),
    CertType(3056, "SARTECH I", "SARTECH I", "SAR", "NASAR", tags=("SAR_FIELD","LSAR_TL",)),

    # --- Aviation ---
    CertType(3150, "PILOT", "Pilot", "Aviation", "FAA", tags=("PILOT",)),
    CertType(3151, "SAR-PILOT", "SAR Pilot", "Aviation", "FAA", parent_id=3150, tags=("PILOT", "SAR_PILOT")),
    CertType(3152, "AIRCREW", "Aviation Aircrew", "Aviation", "FAA", tags=("OBSERVER", "SCANNER")),

    # --- CAP Emergency Services ---
    CertType(6001, "GTM3", "CAP Ground Team Member Level 3", "CAP ES", "CAP", tags=("SAR_FIELD",)),
    CertType(6002, "GTM2", "CAP Ground Team Member Level 2", "CAP ES", "CAP", parent_id=6001, tags=("SAR_FIELD",)),
    CertType(6003, "GTM1", "CAP Ground Team Member Level 1", "CAP ES", "CAP", parent_id=6002, tags=("SAR_FIELD", "DF_FIELD")),
    CertType(6004, "GTL", "CAP Ground Team Leader", "CAP ES", "CAP", parent_id=6003, tags=("LSAR_TL", "SAR_FIELD", "DF_FIELD")),
    CertType(6005, "GBD", "Ground Branch Director", "CAP ES", "CAP", tags=("Branch Director")),
    CertType(6006, "UDF", "Urban Direction Finding Team Member", "CAP ES", "CAP", tags=("DF_FIELD",)),
    CertType(6050, "MS", "Mission Scanner", "CAP ES", "CAP", tags=("SCANNER",)),
    CertType(6051, "MO", "Mission Observer", "CAP ES", "CAP", tags=("OBSERVER",)),
    CertType(6052, "MP", "CAP Mission Pilot", "CAP ES", "CAP/FAA", tags=("PILOT", "SAR_PILOT")),
    CertType(6053, "TMP", "Transport Mission Pilot", "CAP ES", "CAP/FAA", tags=("PILOT",)),
    CertType(6012, "FLM", "Flight Line Marshaller", "CAP ES", "CAP"),
    CertType(6013, "FLS", "Flight Line Supervisor", "CAP ES", "CAP", parent_id=6012),
    CertType(6014, "AOBD", "Air Operations Branch Director", "CAP ES", "CAP", tags=("OPERATIONS",)),
    CertType(6016, "MSO", "Mission Safety Officer", "CAP ES", "CAP", tags=("SOFR",)),
    CertType(5005, "MRO", "Incident Radio Operator", "Radio", "CAP", tags=("RADO",)),
    CertType(5003, "CUL", "Communications Unit Leader", "Radio", "CAP", tags=("COMMS_TECH", "COML", "RADO")),
    # --- Incident Staff ---
    CertType(4001, "IC", "Incident Commander", "ICS/NIMS", "FEMA", tags=("IC",)),
    CertType(4002, "MSA", "Incident Staff Assistant", "ICS/NIMS", "FEMA", tags=("OPERATIONS",)),
    CertType(4003, "PSC", "Planning Section Chief", "ICS/NIMS", "FEMA", tags=("PSC",)),
    CertType(4004, "LSC", "Logistics Section Chief", "ICS/NIMS", "FEMA", tags=("LSC",)),
    CertType(4005, "FASC", "Finance/Administration Section Chief", "ICS/NIMS", "FEMA", tags=("FASC",)),
    CertType(4006, "OSC", "Operations Section Chief", "ICS/NIMS", "FEMA", tags=("OSC",)),
    CertType(4007, "SOFR", "Safety Officer", "ICS/NIMS", "FEMA", tags=("SOFR",)),

    # --- Communications ---
    CertType(5001, "COML", "Communications Unit Leader", "Radio", "All-Hazards", tags=("COMMS_TECH", "COML", "RADO")),
    CertType(5002, "COMT", "Communications Technician", "Radio", "All-Hazards", tags=("COMMS_TECH", "RADO")),
    CertType(5004, "RADO", "Radio Operator", "Radio", "All-Hazards", tags=("RADO",)),
    
]


__all__ = [
    "CATALOG_VERSION",
    "CertType",
    "CATALOG",
]
