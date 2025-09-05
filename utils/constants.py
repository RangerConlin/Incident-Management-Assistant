# utils/constants.py

USER_ROLES = [
    "Incident Commander",
    "Planning Section Chief",
    "Operations Section Chief",
    "Logistics Section Chief",
    "Finance/Admin Section Chief",
    "Safety Officer",
    "Liaison Officer",
    "Public Information Officer",
    "Communications Unit Leader",
    "Medical Unit Leader",
    "Team Leader",
    "Team Member",
    "Technical Specialist",
    "Other"
]
INCIDENT_STATUSES = [
    "Active",
    "Resolved",
    "Closed",
]
TEAM_STATUSES = [
    "At Other Location",
    "Arrival",
    "Assigned",
    "Available",
    "Break",
    "Briefed",
    "Rest",
    "Enroute",
    "Out of Service",
    "Report Writing",
    "Returning to Base",
    "To Other Location",
    "Wheels Down",
    "Post Incident Management",
    "Find",
    "Complete"
]
# Detailed team type metadata used throughout the UI. The `planned_only`
# flag hides options that are not yet fully supported.
TEAM_TYPE_DETAILS = {
    "GT": {"label": "Ground Team", "is_aircraft": False},
    "UDF": {"label": "Urban DF Team", "is_aircraft": False},
    "LSAR": {"label": "Land SAR", "is_aircraft": False},
    "DF": {"label": "Disaster Field Team", "is_aircraft": False},
    "GT/UAS": {"label": "Ground/UAS Team", "is_aircraft": True},
    "UDF/UAS": {"label": "Urban DF/UAS Team", "is_aircraft": True},
    "UAS": {"label": "UAS Team", "is_aircraft": True},
    "AIR": {"label": "Air Support", "is_aircraft": True},
    "K9": {"label": "K9 Team", "is_aircraft": False},
    "UTIL": {"label": "Utility/Support", "is_aircraft": False, "planned_only": True},
}

# Convenience list of codes in case callers need just the identifier set.
TEAM_TYPES = list(TEAM_TYPE_DETAILS.keys())
