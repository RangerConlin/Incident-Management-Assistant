"""Incident Hazard Register module entry point.

The hazard register API is served by sarapp_db.api.routers.safety (MongoDB-backed,
registered in the main app at /api/incidents/{incident_id}/safety/hazards). This
module's service.py calls that API directly via api_client — there is no separate
local FastAPI router or repository for this module.
"""

from __future__ import annotations

__all__ = ["register_ui"]


def register_ui(menu_registry) -> None:
    """Register menu entry for the Incident Hazard Register window."""
    if menu_registry is None:
        return

    from .ui.risk_manager_window import RiskManagerWindow

    menu_registry.add_item(
        path="safety.risk_manager",
        title="Incident Hazard Register",
        factory=lambda: RiskManagerWindow(),
    )
