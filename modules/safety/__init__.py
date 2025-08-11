from .api import router
from .panels.safety_dashboard import SafetyDashboard


def get_safety_panel(mission_id: str):
    """Return an instance of the SafetyDashboard panel."""
    return SafetyDashboard(mission_id)

__all__ = ["router", "get_safety_panel"]
