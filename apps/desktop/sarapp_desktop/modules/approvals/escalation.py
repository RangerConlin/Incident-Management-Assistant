from __future__ import annotations

# ICS standard escalation chains.
# Key: position title (must match org chart position titles exactly).
# Value: ordered list of fallback titles to try if the primary is vacant.
# The service walks this list until it finds a filled position.

ICS_ESCALATION: dict[str, list[str]] = {
    # Command
    "Incident Commander": [],
    "Deputy Incident Commander": ["Incident Commander"],
    "Safety Officer": ["Incident Commander"],
    "Public Information Officer": ["Incident Commander"],
    "Liaison Officer": ["Incident Commander"],

    # Operations Section
    "Operations Section Chief": ["Incident Commander"],
    "Deputy Operations Section Chief": ["Operations Section Chief", "Incident Commander"],
    "Staging Area Manager": ["Operations Section Chief", "Incident Commander"],

    # Planning Section
    "Planning Section Chief": ["Incident Commander"],
    "Resources Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Situation Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Documentation Unit Leader": ["Planning Section Chief", "Incident Commander"],
    "Demobilization Unit Leader": ["Planning Section Chief", "Incident Commander"],

    # Logistics Section
    "Logistics Section Chief": ["Incident Commander"],
    "Service Branch Director": ["Logistics Section Chief", "Incident Commander"],
    "Support Branch Director": ["Logistics Section Chief", "Incident Commander"],
    "Communications Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Medical Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Food Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Supply Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Facilities Unit Leader": ["Logistics Section Chief", "Incident Commander"],
    "Ground Support Unit Leader": ["Logistics Section Chief", "Incident Commander"],

    # Finance/Admin Section
    "Finance/Administration Section Chief": ["Incident Commander"],
    "Time Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
    "Procurement Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
    "Compensation/Claims Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
    "Cost Unit Leader": ["Finance/Administration Section Chief", "Incident Commander"],
}


def escalation_chain(role: str) -> list[str]:
    """Return the full ordered list to try for a role: [role] + fallbacks."""
    return [role] + ICS_ESCALATION.get(role, ["Incident Commander"])
