from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from utils import incident_context
from utils.api_client import api_client


WORK_ASSIGNMENT_FORM_IDS = {
    "ICS 204": "ics_204",
    "ICS 215": "ics_215",
    "ICS 215A": "ics_215a",
    "ICS 213RR": "ics_213rr",
}


def work_assignment_form_key(output_type: str) -> str:
    return f"work_assignment:{output_type}"


def _active_incident_id(request: ExportRequest) -> str:
    incident_id = request.incident_id or incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("No active incident")
    return str(incident_id)


def _safe_filename_part(value: object, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    text = re.sub(r'[<>:"/\\|?*]+', "-", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._-]", "-", text)
    return text.strip(" .") or fallback


def _output_path(output_type: str, assignment: dict[str, Any], generated_at: str) -> Path:
    paths = incident_context.get_active_incident_paths()
    paths.forms_generated.mkdir(parents=True, exist_ok=True)
    assignment_number = _safe_filename_part(
        assignment.get("assignment_number"),
        f"strategy-{assignment.get('id') or assignment.get('int_id') or 'new'}",
    )
    form_name = _safe_filename_part(output_type.replace(" ", "-"), "form")
    timestamp = _safe_filename_part(generated_at[:19].replace(":", "-").replace(" ", "_"), "generated")
    return paths.forms_generated / f"{assignment_number}_{form_name}_{timestamp}.pdf"


def _build_output_context(assignment: dict[str, Any], output_type: str, form_id: str) -> dict[str, Any]:
    resources = list(assignment.get("resources") or [])
    hazards = list(assignment.get("hazards") or [])
    task_links = list(assignment.get("task_links") or [])
    agency_request_links = list(assignment.get("agency_request_links") or [])

    assigned_resources: list[dict[str, Any]] = []
    for requirement in resources:
        for resource in requirement.get("assignments") or []:
            assigned = dict(resource)
            assigned["requirement_id"] = requirement.get("id")
            assigned["requirement"] = requirement.get("resource_type_text") or ""
            assigned["capability"] = requirement.get("capability_text") or ""
            assigned_resources.append(assigned)

    strategy = {
        "id": assignment.get("id") or assignment.get("int_id"),
        "assignment_number": assignment.get("assignment_number") or "",
        "assignment_name": assignment.get("assignment_name") or "",
        "objective_id": assignment.get("objective_id") or "",
        "operational_period_id": assignment.get("operational_period_id") or "",
        "branch": assignment.get("branch") or "",
        "division_group": assignment.get("division_group") or "",
        "location": assignment.get("location") or "",
        "location_facility_id": assignment.get("location_facility_id") or "",
        "assignment_kind": assignment.get("assignment_kind") or "",
        "priority": assignment.get("priority") or "",
        "planning_status": assignment.get("planning_status") or "",
        "safety_status": assignment.get("safety_status") or "",
        "resource_status": assignment.get("resource_status") or "",
        "description": assignment.get("description") or "",
        "tactics_summary": assignment.get("tactics_summary") or "",
        "special_instructions": assignment.get("special_instructions") or "",
        "prepared_by": assignment.get("prepared_by") or "",
        "approved_by": assignment.get("approved_by") or "",
        "notes": assignment.get("notes") or "",
        "resources": resources,
        "resource_requirements": resources,
        "assigned_resources": assigned_resources,
        "hazards": hazards,
        "task_links": task_links,
        "agency_request_links": agency_request_links,
        "outputs": list(assignment.get("outputs") or []),
    }

    resource_summary = {
        "required": sum(int(row.get("quantity_required") or 0) for row in resources),
        "assigned": sum(int(row.get("quantity_assigned") or 0) for row in resources),
        "available": sum(int(row.get("quantity_available") or 0) for row in resources),
        "gap": sum(int(row.get("quantity_gap") or 0) for row in resources),
    }
    hazard_summary = {
        "total": len(hazards),
        "open": sum(1 for hazard in hazards if not hazard.get("is_resolved")),
        "resolved": sum(1 for hazard in hazards if hazard.get("is_resolved")),
    }

    return {
        "output": {"type": output_type, "form_id": form_id},
        "strategy": strategy,
        "work_assignment": strategy,
        "resource_requirements": resources,
        "assigned_resources": assigned_resources,
        "assignment_resources": resources,
        "assignment_hazards": hazards,
        "linked_tasks": task_links,
        "agency_request_links": agency_request_links,
        "resource_summary": resource_summary,
        "hazard_summary": hazard_summary,
    }


class WorkAssignmentOutputBuilder:
    """Prepares a work-assignment output for the form engine."""

    def __init__(self, output_type: str) -> None:
        self.output_type = output_type
        self.form_id = WORK_ASSIGNMENT_FORM_IDS[output_type]

    def build(self, request: ExportRequest) -> PreparedExport:
        if request.target_id is None:
            raise ValueError("work_assignment export requires target_id")
        incident_id = _active_incident_id(request)
        assignment = api_client.get(
            f"/api/incidents/{incident_id}/planning/work-assignments/{request.target_id}"
        ) or {}
        if not assignment:
            raise RuntimeError("Strategy not found.")

        generated_at = utcnow_seconds()
        output_path = _output_path(self.output_type, assignment, generated_at)
        extra_data = _build_output_context(assignment, self.output_type, self.form_id)
        return PreparedExport(
            form_id=self.form_id,
            output_path=output_path,
            incident_id=incident_id,
            form_set_id=request.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "output_type": self.output_type,
                "target_type": request.target_type or "work_assignment",
                "target_id": request.target_id,
            },
        )


def register_work_assignment_builders(registry: ExportRegistry) -> None:
    for output_type in WORK_ASSIGNMENT_FORM_IDS:
        builder = WorkAssignmentOutputBuilder(output_type)
        registry.register(work_assignment_form_key(output_type), builder)
