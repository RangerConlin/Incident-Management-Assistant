from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils import incident_context
from utils.api_client import api_client


FORM_ID_BY_OUTPUT_TYPE = {
    "ICS 204": "ics_204",
    "ICS 215": "ics_215",
    "ICS 215A": "ics_215a",
    "ICS 213RR": "ics_213rr",
}


@dataclass(frozen=True)
class OutputExportResult:
    output_type: str
    form_id: str
    output_path: Path
    generated_at: str


def _active_incident_id() -> str:
    incident_id = incident_context.get_active_incident_id()
    if not incident_id:
        raise RuntimeError("No active incident")
    return str(incident_id)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


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


def generate_work_assignment_output(
    work_assignment_id: int,
    output_type: str,
    *,
    form_set_id: str | None = None,
) -> OutputExportResult:
    from modules.forms_creator.engine import generate

    form_id = FORM_ID_BY_OUTPUT_TYPE.get(output_type)
    if not form_id:
        raise ValueError(f"No form mapping is configured for {output_type}.")

    incident_id = _active_incident_id()
    assignment = api_client.get(
        f"/api/incidents/{incident_id}/planning/work-assignments/{work_assignment_id}"
    ) or {}
    if not assignment:
        raise RuntimeError("Strategy not found.")

    generated_at = _utcnow()
    output_path = _output_path(output_type, assignment, generated_at)
    extra_data = _build_output_context(assignment, output_type, form_id)
    generate(
        form_id,
        output_path,
        incident_id=incident_id,
        form_set_id=form_set_id,
        extra_data=extra_data,
    )
    return OutputExportResult(
        output_type=output_type,
        form_id=form_id,
        output_path=output_path,
        generated_at=generated_at,
    )
