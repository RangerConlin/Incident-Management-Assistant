from __future__ import annotations

from dataclasses import replace
from typing import Any

from modules.forms_creator.exporting.builders.generic import _active_incident_id, _output_path
from modules.forms_creator.exporting.builders.ics import ics_form_key, ics_form_label
from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from utils.api_client import api_client


def _request_number(request_data: dict[str, Any]) -> str:
    raw_id = str(request_data.get("id") or "")
    return raw_id.upper()


def _resource_request_export_context(request_data: dict[str, Any]) -> dict[str, Any]:
    items = [
        {
            "qty": item.get("quantity"),
            "kind": item.get("kind"),
            "description": item.get("description"),
        }
        for item in (request_data.get("items") or [])
    ]
    resource_request = {
        "request_number": _request_number(request_data),
        "title": request_data.get("title") or "",
        "requesting_section": request_data.get("requesting_section") or "",
        "priority": request_data.get("priority") or "",
        "status": request_data.get("status") or "",
        "created_utc": request_data.get("created_utc") or "",
        "needed_by_utc": request_data.get("needed_by_utc") or "",
        "delivery_location": request_data.get("delivery_location") or "",
        "justification": request_data.get("justification") or "",
        "comms_requirements": request_data.get("comms_requirements") or "",
    }
    return {
        "resource_request": resource_request,
        "resource_request_items": items,
    }


class ResourceRequestFormBuilder:
    """Prepares an ICS 213RR export for one Logistics Resource Request record.

    Pulls from the `resource_requests` domain (modules/logistics/resource_requests),
    not from work-assignment resource requirement gaps -- those are a different
    data source entirely (see WorkAssignmentOutputBuilder).
    """

    form_id = "ics_213rr"

    def build(self, request: ExportRequest) -> PreparedExport:
        if request.target_id in (None, ""):
            raise ValueError("ics_213rr export requires target_id (a resource request id)")

        incident_id = _active_incident_id(request)
        request_data = api_client.get(
            f"/api/incidents/{incident_id}/logistics/resource-requests/{request.target_id}"
        )
        if not request_data:
            raise RuntimeError(f"Resource request not found: {request.target_id}")

        generated_at = utcnow_seconds()
        extra_data = _resource_request_export_context(request_data)
        manual = request.options.get("extra_data")
        if isinstance(manual, dict):
            extra_data = {**extra_data, **manual}

        output_request = (
            request if request.target_type else replace(request, target_type="resource_request")
        )
        return PreparedExport(
            form_id=self.form_id,
            output_path=_output_path(self.form_id, output_request, generated_at),
            incident_id=incident_id,
            form_set_id=request.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": ics_form_label(self.form_id),
                "builder_level": self.form_id,
                "data_domain": "resource_request",
                "target_type": request.target_type or "resource_request",
                "target_id": request.target_id,
            },
        )


def register_resource_request_builders(registry: ExportRegistry) -> None:
    builder = ResourceRequestFormBuilder()
    registry.register(ics_form_key(builder.form_id), builder)
    registry.register(builder.form_id, builder)
    registry.register(ics_form_label(builder.form_id), builder)
