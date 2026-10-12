"""Window factory for the QtWidgets-based ICS-214 Activity Log."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import only for typing
    from .widgets.activity_log import Ics214ActivityLogPanel

__all__ = ["get_ics214_panel"]


def get_ics214_panel(
    incident_id: Any | None = None,
    launch_context: dict[str, Any] | None = None,
) -> "Ics214ActivityLogPanel":
    """Return the redesigned QtWidgets ICS-214 panel."""

    from .widgets.activity_log import Ics214ActivityLogPanel

    return Ics214ActivityLogPanel(
        incident_id=incident_id,
        launch_context=launch_context or {},
    )
