# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""Logistics module package init."""

try:  # FastAPI is optional for tests
    from .api import router  # type: ignore
except Exception:  # pragma: no cover
    router = None


def get_logistics_panel(mission_id: str):
    """Return the main logistics panel for the given mission."""
    from .panels.requests_panel import RequestsPanel

    return RequestsPanel(mission_id)


__all__ = ["router", "get_logistics_panel"]
