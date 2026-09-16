from __future__ import annotations

"""Single entry point for generating the ICS-213RR from any button/panel.

Usage from a widget::

    from modules.logistics.resource_requests.export_service import generate_ics213rr

    result = generate_ics213rr(request_id=self.current_request_id)
    os.startfile(str(result.output_path))
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from modules.forms_creator.exporting import ExportRequest, default_export_service


@dataclass(frozen=True)
class Ics213RrExportResult:
    output_path: Path
    generated_at: str
    request_id: str


def generate_ics213rr(
    *,
    request_id: str,
    incident_id: Optional[str] = None,
    form_set_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> Ics213RrExportResult:
    """Generate the ICS-213 Resource Request Message PDF for one request."""
    options: dict[str, Any] = {}
    if extra_data:
        options["extra_data"] = extra_data

    result = default_export_service().export(
        ExportRequest(
            form_key="ics_213rr",
            target_type="resource_request",
            target_id=request_id,
            incident_id=incident_id,
            form_set_id=form_set_id,
            options=options,
        )
    )
    return Ics213RrExportResult(
        output_path=result.output_path,
        generated_at=result.generated_at,
        request_id=str(request_id),
    )


__all__ = ["Ics213RrExportResult", "generate_ics213rr"]
