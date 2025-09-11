"""Role-based permissions for the safety module."""

EDIT_ROLES = {"Incident Commander", "Safety Officer", "Deputy IC", "Planning Section Chief"}
VIEW_ROLES = "*"  # everyone

def can_edit_safety(role: str) -> bool:
    """Return True if the given role is allowed to edit safety data."""
    return role in EDIT_ROLES
