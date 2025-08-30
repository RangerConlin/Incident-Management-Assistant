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
TEAM_TYPES = [
    "GT",      # Ground Team
    "UDF",     # Urban Disaster Field Team
    "LSAR",    # Land Search and Rescue
    "DF",      # Disaster Field Team
    "GT/UAS",  # Ground Team with UAS capability
    "UDF/UAS", # Urban Disaster Field Team with UAS capability
    "UAS",     # Unmanned Aerial System (Drone) Team
    "AIR",     # Air Support Team
    "K9",      # Canine Search Team
    "UTIL"     # Utility or Support Team
]
