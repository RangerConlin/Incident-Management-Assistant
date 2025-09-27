"""Hardcoded certification catalog (authoritative in production).

This module defines the certification catalog used by the application. On
startup, a seeding routine mirrors this catalog into the master SQLite
database for querying and joins. The code catalog remains the single source
of truth; the DB mirror is read-only in production (mutations are blocked
by API checks).

Notes
- IDs are stable integers and MUST NOT be reused once shipped. Bump the
  CATALOG_VERSION any time entries change (add/update/remove) so the seeder
  knows to re-sync.
- Tags allow grouping different certifications into common qualification
  profiles. Tags are mirrored to the DB as well for fast queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple


# Bump whenever the catalog content or tags change
CATALOG_VERSION = "1.0.0"


@dataclass(frozen=True)
class CertType:
    """Immutable certification type record.

    Fields map closely to the DB mirror. The `tags` field provides a fixed,
    code-defined set of tags used by validation profiles and other features.
    """

    id: int
    code: str
    name: str
    category: str
    issuing_org: str
    parent_id: Optional[int] = None
    tags: Tuple[str, ...] = tuple()

CATALOG: List[CertType] = [
# --- ICS/NIMS ---
    CertType(1001, "IS-100", "Introduction to ICS", "ICS/NIMS", "FEMA"),
    CertType(1002, "IS-200", "Basic ICS", "ICS/NIMS", "FEMA"),
    CertType(1003, "ICS-300", "Intermediate ICS", "ICS/NIMS", "FEMA"),
    CertType(1004, "ICS-400", "Advanced ICS", "ICS/NIMS", "FEMA"),
    CertType(1005, "IS-700", "NIMS", "ICS/NIMS", "FEMA"),
    CertType(1006, "IS-800", "National Response Framework", "ICS/NIMS", "FEMA"),

# --- Medical ---
    CertType(2001, "FA-CPR", "First Aid / CPR", "Medical", "AHA/Red Cross"),
    CertType(2002, "EMR", "Emergency Medical Responder", "Medical", "State EMS", tags=("MEDICAL",)),
    CertType(2003, "EMT", "Emergency Medical Technician", "Medical", "State EMS", tags=("MEDIC", "MEDICAL",)),
    CertType(2004, "EMT-A", "Emergency Medical Technician - Advanced", "Medical", "State EMS", tags=("MEDIC", "MEDICAL",)),
    CertType(2005, "EMT-P", "Paramedic", "Medical", "State EMS", tags=("MEDIC", "MEDICAL",)),
    CertType(2006, "WFA", "Wilderness First Aid", "Medical", "NOLS", tags=("MEDICAL",)),
    CertType(2007, "WFR", "Wilderness First Responder", "Medical", "NOLS", tags=("MEDIC", "MEDICAL",)),
    CertType(2008, "WEMT", "Wilderness EMT", "Medical", "NOLS", tags=("MEDIC", "MEDICAL")),

# --- SAR Roles (examples) ---
# Note: These are example SAR roles. Actual SAR certifications vary widely by organization and region.
    CertType(3051, "LSAR", "Ground Search and Rescue Team Member", "SAR", "AHJ", tags=("SAR_FIELD",)),
    CertType(3052, "LSAR-TL", "Ground Search and Rescue Team Leader", "SAR", "AHJ", parent_id=3051, tags=("LSAR_TL", "SAR_FIELD", "DF_FIELD")),
    CertType(3053, "DF", "Direction Finding Team Member", "SAR", "AHJ", tags=("DF_FIELD",)),

# --- Aviation ---
    CertType(3150, "PILOT", "Pilot", "Aviation", "FAA", tags=("PILOT",)),
    CertType(3151, "SAR-PILOT", "SAR Pilot", "Aviation", "FAA", parent_id=3150, tags=("PILOT", "SAR_PILOT")),
    CertType(3152, "AIRCREW", "Aviation Aircrew", "Aviation", "FAA", tags=("OBSERVER", "SCANNER")),

# --- Incident Staff ---
    CertType(4001, "IC", "Incident Commander", "Incident Staff", "All-Hazards", tags=("IC")),
    CertType(4002, "MSA",  "Mission Staff Assistant", "All-Hazards", "FEMA", tags=("OPERATIONS",)),
    CertType(4003, "PSC",  "Planning Section Chief", "All-Hazards", "FEMA", tags=("PSC",)),
    CertType(4004, "LSC",  "Logistics Section Chief", "All-Hazards", "FEMA", tags=("LSC",)),
    CertType(4005, "FASC",  "Finance/Administration Section Chief", "All-Hazards", "FEMA", tags=("FASC",)),
    CertType(4006, "OSC",  "Operations Section Chief", "All-Hazards", "FEMA", tags=("OSC",)),
    CertType(4007, "SOFR",  "Safety Officer", "All-Hazards", "FEMA", tags=("SOFR",)),

# --- Communications ---
    CertType(5001, "COML", "Communications Unit Leader", "Radio", "All-Hazards", tags=("COMMS_TECH", "COML", "RADO")),
    CertType(5002, "COMT", "Communications Technician", "Radio", "All-Hazards", tags=("COMMS_TECH","RADO")),
    CertType(5003, "CUL", "Communications Technician", "Radio", "CAP", tags=("COMMS_TECH", "COML", "RADO")),
    CertType(5004, "RADO", "Radio Operator", "Radio", "All-Hazards", tags=("RADO")),
    CertType(5005, "MRO",  "Mission Radio Operator", "SAR", "CAP", tags=("RADO")),
]

"""
# The complete catalog for future use. Keep IDs stable and NEVER reuse removed IDs.  To be used later.
CATALOG: List[CertType] = [
    # --- ICS/NIMS ---
    CertType(1001, "IS-100", "Introduction to ICS", "ICS/NIMS", "FEMA"),
    CertType(1002, "IS-200", "Basic ICS", "ICS/NIMS", "FEMA"),
    CertType(1003, "ICS-300", "Intermediate ICS", "ICS/NIMS", "FEMA"),
    CertType(1004, "ICS-400", "Advanced ICS", "ICS/NIMS", "FEMA"),
    CertType(1005, "IS-700", "NIMS", "ICS/NIMS", "FEMA"),
    CertType(1006, "IS-800", "National Response Framework", "ICS/NIMS", "FEMA"),


    # --- Medical ---
    CertType(2001, "FA-CPR", "First Aid / CPR", "Medical", "AHA/Red Cross"),
    CertType(2002, "EMR", "Emergency Medical Responder", "Medical", "State EMS", tags=("MEDICAL",)),
    CertType(2003, "EMT", "Emergency Medical Technician", "Medical", "State EMS", tags=("MEDIC", "MEDICAL",)),
    CertType(2004, "EMT-A", "Emergency Medical Technician - Advanced", "Medical", "State EMS", tags=("MEDIC", "MEDICAL",)),
    CertType(2005, "EMT-P", "Paramedic", "Medical", "State EMS", tags=("MEDIC", "MEDICAL",)),
    CertType(2006, "WFA", "Wilderness First Aid", "Medical", "NOLS", tags=("MEDICAL",)),
    CertType(2007, "WFR", "Wilderness First Responder", "Medical", "NOLS", tags=("MEDIC", "MEDICAL",)),
    CertType(2008, "WEMT", "Wilderness EMT", "Medical", "NOLS", tags=("MEDIC", "MEDICAL")),

    # --- SAR Roles (examples) ---
    CertType(3001, "GTM3", "Ground Team Member 3", "SAR", "CAP", tags=("SAR_FIELD",)),
    CertType(3002, "GTM2", "Ground Team Member 2", "SAR", "CAP", parent_id=3001, tags=("SAR_FIELD",)),
    CertType(3003, "GTM1", "Ground Team Member 1", "SAR", "CAP", parent_id=3002, tags=("SAR_FIELD",)),
    CertType(3004, "GTL", "Ground Team Leader", "SAR", "CAP", parent_id=3003, tags=("LSAR_TL", "SAR_FIELD")),
    CertType(3005, "UDF",  "Urban Direction Finding", "SAR", "CAP", tags=("DF_FIELD",)),
    CertType(3006, "SARTECH-1", "NASAR SARTECH I", "SAR", "NASAR", tags=("LSAR_TL", "SAR_FIELD")),
    CertType(3007, "SARTECH-2", "NASAR SARTECH II", "SAR", "NASAR", parent_id=3006, tags=("SAR_FIELD")),
    CertType(3008, "SARTECH-3", "NASAR SARTECH III", "SAR", "NASAR", parent_id=3007, tags=("SAR_FIELD")),
    CertType(3009, "SARTECH-4", "NASAR SARTECH IV", "SAR", "NASAR", parent_id=3008,),

    # --- Aviation ---
    CertType(3100, "MP", "Mission Pilot", "Aviation", "CAP", tags=("PILOT", "SAR_PILOT")),
    CertType(3101, "TMP", "Transport Mission Pilot", "Aviation", "CAP", tags=("PILOT",)),
    CertType(3102, "MO", "Mission Observer", "Aviation", "CAP", tags=("OBSERVER", "SCANNER")),
    CertType(3103, "MS", "Mission Scanner", "Aviation", "CAP", tags=("SCANNER",)),


    # --- Incident Staff ---
    CertType(6001, "IC", "Incident Commander", "Incident Staff", "All-Hazards", tags=("IC")),
    CertType(6002, "IC3",  "Incident Commander 3", "SAR", "CAP", tags=("IC")),
    CertType(6003, "IC2",  "Incident Commander 2", "SAR", "CAP", parent_id=6002, tags=("IC")),
    CertType(6004, "IC1",  "Incident Commander 1", "SAR", "CAP", parent_id=6003, tags=("IC")),
    CertType(6005, "MSA",  "Mission Staff Assistant", "SAR", "CAP", tags=("OPERATIONS",)),

    # --- Communications ---
    CertType(4001, "COML", "Communications Unit Leader", "Radio", "All-Hazards", tags=("COMMS_TECH", "COML", "RADO")),
    CertType(4002, "COMT", "Communications Technician", "Radio", "All-Hazards", tags=("COMMS_TECH","RADO")),
    CertType(4003, "CUL", "Communications Technician", "Radio", "CAP", tags=("COMMS_TECH", "COML", "RADO")),
    CertType(4004, "RADO", "Radio Operator", "Radio", "All-Hazards", tags=("RADO")),
    CertType(4005, "MRO",  "Mission Radio Operator", "SAR", "CAP", tags=("RADO")),

    # --- Safety ---
    CertType(5001, "SOFR", "Safety Officer", "Safety", "All-Hazards", tags=("SAFETY",)),
    ]
"""

__all__ = [
    "CATALOG_VERSION",
    "CertType",
    "CATALOG",
]
