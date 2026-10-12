"""QtWidgets panel wrapper for the ICS-214 Activity Log."""
from __future__ import annotations

from typing import Any

from ..widgets import Ics214ActivityLogPanel


class ICS214Panel(Ics214ActivityLogPanel):
    """Backward-compatible wrapper around :class:`Ics214ActivityLogPanel`."""

    def __init__(
        self,
        parent=None,
        services: Any | None = None,
        styles: Any | None = None,
    ) -> None:
        super().__init__(
            incident_id=None,
            parent=parent,
            services=services,
            styles=styles,
        )
