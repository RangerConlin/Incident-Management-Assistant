from __future__ import annotations

from typing import Protocol

from .models import ExportRequest, PreparedExport


class ExportBuilder(Protocol):
    """Builds data for a specific form export request."""

    def build(self, request: ExportRequest) -> PreparedExport:
        """Gather API data and return the prepared package for the form engine."""
