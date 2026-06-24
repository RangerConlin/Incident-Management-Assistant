"""Safety ORM module entry point.

The ORM API is served by sarapp_db.api.routers.safety (MongoDB-backed,
registered in the main app at /api/incidents/{incident_id}/safety/orm/...).
This module's service.py calls that API directly via api_client — there is
no separate local FastAPI router or repository for this module.
"""

from __future__ import annotations

__all__ = ["register_ui"]


def register_ui(menu_registry) -> None:
    """Register menu entry for the ORM window."""
    if menu_registry is None:
        return

    from .ui.orm_window import ORMWindow

    menu_registry.add_item(
        path="safety.cap_orm_singleton",
        title="CAP ORM (Per OP)",
        factory=lambda: ORMWindow(),
    )
