"""WorkAssignmentRepository — proxies through SARApp API (MongoDB backend)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from modules.planning.tactics_resources.models.work_assignment_models import (
    OUTPUT_TYPE_VALUES,
    WorkAssignment,
    WorkAssignmentComms,
    WorkAssignmentHazard,
    WorkAssignmentLogEntry,
    WorkAssignmentOutputStatus,
    WorkAssignmentResourceAssignment,
    WorkAssignmentResourceRequirement,
    WorkAssignmentTaskLink,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


def _iid() -> str:
    from utils.incident_context import get_active_incident_id
    v = get_active_incident_id()
    if not v:
        raise RuntimeError("No active incident")
    return str(v)


def _base() -> str:
    return f"/api/incidents/{_iid()}/planning/work-assignments"


def _client():
    from utils.api_client import api_client
    return api_client


def _wa_from_dict(d: dict) -> WorkAssignment:
    return WorkAssignment(
        id=d.get("id"),
        assignment_number=str(d.get("assignment_number") or ""),
        assignment_name=str(d.get("assignment_name") or ""),
        objective_id=d.get("objective_id"),
        operational_period_id=d.get("operational_period_id"),
        branch=str(d.get("branch") or ""),
        division_group=str(d.get("division_group") or ""),
        location=str(d.get("location") or ""),
        location_facility_id=str(d.get("location_facility_id") or ""),
        assignment_kind=str(d.get("assignment_kind") or "Ground"),
        priority=str(d.get("priority") or "Normal"),
        planning_status=str(d.get("planning_status") or "Draft"),
        safety_status=str(d.get("safety_status") or "Unchecked"),
        resource_status=str(d.get("resource_status") or "Unreviewed"),
        description=str(d.get("description") or ""),
        tactics_summary=str(d.get("tactics_summary") or ""),
        special_instructions=str(d.get("special_instructions") or ""),
        prepared_by=d.get("prepared_by"),
        approved_by=d.get("approved_by"),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
        created_by=d.get("created_by"),
        updated_by=d.get("updated_by"),
        is_archived=int(bool(d.get("is_archived", False))),
        notes=str(d.get("notes") or ""),
    )


def _req_from_dict(d: dict) -> WorkAssignmentResourceRequirement:
    return WorkAssignmentResourceRequirement(
        id=d.get("id"),
        work_assignment_id=d.get("work_assignment_id"),
        resource_type_id=d.get("resource_type_id"),
        resource_type_text=str(d.get("resource_type_text") or ""),
        capability_id=d.get("capability_id"),
        capability_text=str(d.get("capability_text") or ""),
        quantity_required=int(d.get("quantity_required") or 1),
        quantity_assigned=int(d.get("quantity_assigned") or 0),
        quantity_available=int(d.get("quantity_available") or 0),
        quantity_gap=int(d.get("quantity_gap") or 0),
        unit=str(d.get("unit") or ""),
        priority=str(d.get("priority") or "Normal"),
        source_note=str(d.get("source_note") or ""),
        logistics_request_id=d.get("logistics_request_id"),
        notes=str(d.get("notes") or ""),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


def _ra_from_dict(d: dict) -> WorkAssignmentResourceAssignment:
    return WorkAssignmentResourceAssignment(
        id=d.get("id"),
        work_assignment_resource_id=d.get("work_assignment_resource_id"),
        resource_kind=str(d.get("resource_kind") or ""),
        resource_id=str(d.get("resource_id") or ""),
        display_name=str(d.get("display_name") or ""),
        status=str(d.get("status") or "Planned"),
        assigned_at=str(d.get("assigned_at") or ""),
        released_at=str(d.get("released_at") or ""),
        notes=str(d.get("notes") or ""),
    )


def _hazard_from_dict(d: dict) -> WorkAssignmentHazard:
    return WorkAssignmentHazard(
        id=d.get("id"),
        work_assignment_id=d.get("work_assignment_id"),
        hazard_type_id=d.get("hazard_type_id"),
        hazard_type_text=str(d.get("hazard_type_text") or ""),
        category=str(d.get("category") or ""),
        risk_level=str(d.get("risk_level") or "Unknown"),
        likelihood=str(d.get("likelihood") or "Unknown"),
        severity=str(d.get("severity") or "Unknown"),
        control_measure=str(d.get("control_measure") or ""),
        mitigation_text=str(d.get("mitigation_text") or ""),
        ppe_text=str(d.get("ppe_text") or ""),
        safety_message=str(d.get("safety_message") or ""),
        source=str(d.get("source") or ""),
        is_resolved=int(bool(d.get("is_resolved", False))),
        notes=str(d.get("notes") or ""),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


def _comms_from_dict(d: dict) -> WorkAssignmentComms:
    return WorkAssignmentComms(
        id=d.get("id"),
        work_assignment_id=d.get("work_assignment_id"),
        channel_id=d.get("channel_id"),
        channel_name=str(d.get("channel_name") or ""),
        function=str(d.get("function") or ""),
        zone=str(d.get("zone") or ""),
        channel_number=str(d.get("channel_number") or ""),
        rx_freq=str(d.get("rx_freq") or ""),
        rx_tone=str(d.get("rx_tone") or ""),
        tx_freq=str(d.get("tx_freq") or ""),
        tx_tone=str(d.get("tx_tone") or ""),
        mode=str(d.get("mode") or ""),
        remarks=str(d.get("remarks") or ""),
        is_primary=int(bool(d.get("is_primary", False))),
        notes=str(d.get("notes") or ""),
        created_at=str(d.get("created_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


def _link_from_dict(d: dict) -> WorkAssignmentTaskLink:
    return WorkAssignmentTaskLink(
        id=d.get("id"),
        work_assignment_id=d.get("work_assignment_id") or 0,
        task_id=int(d.get("task_id") or 0),
        link_type=str(d.get("link_type") or "Linked Existing"),
        created_at=str(d.get("created_at") or ""),
        created_by=d.get("created_by"),
        notes=str(d.get("notes") or ""),
    )


def _log_from_dict(d: dict) -> WorkAssignmentLogEntry:
    return WorkAssignmentLogEntry(
        id=d.get("id"),
        work_assignment_id=d.get("work_assignment_id"),
        timestamp=str(d.get("timestamp") or ""),
        entered_by=d.get("entered_by"),
        entry_type=str(d.get("entry_type") or "Note"),
        entry_text=str(d.get("entry_text") or ""),
        critical=bool(d.get("critical", False)),
    )


def _output_from_dict(d: dict) -> WorkAssignmentOutputStatus:
    return WorkAssignmentOutputStatus(
        id=d.get("id"),
        work_assignment_id=d.get("work_assignment_id"),
        output_type=str(d.get("output_type") or ""),
        status=str(d.get("status") or "Not Started"),
        generated_file_path=d.get("generated_file_path"),
        generated_at=d.get("generated_at"),
        generated_by=d.get("generated_by"),
        notes=str(d.get("notes") or ""),
    )


class WorkAssignmentRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        # db_path accepted but ignored — data lives in MongoDB via API
        pass

    def initialize_schema(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Work Assignment CRUD
    # ------------------------------------------------------------------

    def list_work_assignments(self, filters: dict[str, Any] | None = None) -> list[WorkAssignment]:
        filters = filters or {}
        params = {
            "show_archived": filters.get("show_archived", False),
        }
        for k in ("planning_status", "safety_status", "resource_status", "branch", "division_group"):
            if filters.get(k):
                params[k] = filters[k]
        if filters.get("op_period_id") is not None:
            params["op_period_id"] = filters["op_period_id"]
        if filters.get("objective_id") is not None:
            params["objective_id"] = filters["objective_id"]
        if filters.get("search"):
            params["search"] = filters["search"]
        try:
            return [_wa_from_dict(d) for d in _client().get(_base(), params=params)]
        except Exception:
            return []

    def get_work_assignment(self, work_assignment_id: int) -> WorkAssignment | None:
        try:
            d = _client().get(f"{_base()}/{work_assignment_id}")
            return _wa_from_dict(d)
        except Exception:
            return None

    def create_work_assignment(self, data: dict[str, Any]) -> int:
        d = _client().post(_base(), json=data)
        return int(d.get("id") or 0)

    def update_work_assignment(self, work_assignment_id: int, data: dict[str, Any]) -> bool:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}", json=data)
            return True
        except Exception:
            return False

    def archive_work_assignment(self, work_assignment_id: int) -> None:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/archive", json={})
        except Exception:
            pass

    def restore_work_assignment(self, work_assignment_id: int) -> None:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/restore", json={})
        except Exception:
            pass

    def delete_work_assignment(self, work_assignment_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}")
        except Exception:
            pass

    def clone_work_assignment(self, work_assignment_id: int) -> int | None:
        try:
            d = _client().post(f"{_base()}/{work_assignment_id}/clone", json={})
            return int(d.get("id") or 0)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Resource requirements
    # ------------------------------------------------------------------

    def list_resource_requirements(self, work_assignment_id: int) -> list[WorkAssignmentResourceRequirement]:
        try:
            data = _client().get(f"{_base()}/{work_assignment_id}/resources")
            return [_req_from_dict(d) for d in data]
        except Exception:
            return []

    def add_resource_requirement(self, work_assignment_id: int, data: dict[str, Any]) -> int:
        d = _client().post(f"{_base()}/{work_assignment_id}/resources", json=data)
        return int(d.get("id") or 0)

    def update_resource_requirement(self, requirement_id: int, data: dict[str, Any]) -> bool:
        # We need work_assignment_id; callers should use update_resource_requirement_for_wa
        return False

    def update_resource_requirement_for_wa(self, work_assignment_id: int, requirement_id: int, data: dict[str, Any]) -> bool:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/resources/{requirement_id}", json=data)
            return True
        except Exception:
            return False

    def remove_resource_requirement(self, requirement_id: int) -> None:
        pass  # needs work_assignment_id

    def remove_resource_requirement_for_wa(self, work_assignment_id: int, requirement_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/resources/{requirement_id}")
        except Exception:
            pass

    def recalculate_resource_gap(self, requirement_id: int) -> None:
        pass  # server recalculates on update

    def recalculate_all_resource_gaps(self, work_assignment_id: int) -> None:
        pass

    _LOGISTICS_PRIORITY_MAP = {"Low": "ROUTINE", "Normal": "ROUTINE", "High": "HIGH", "Urgent": "IMMEDIATE"}

    def create_logistics_request_from_requirement(
        self, work_assignment_id: int, requirement_id: int
    ) -> str | None:
        """Create a Logistics Resource Request (ICS-213RR) from a resource
        requirement line and link it back via ``logistics_request_id``."""
        wa = self.get_work_assignment(work_assignment_id)
        if not wa:
            return None
        reqs = self.list_resource_requirements(work_assignment_id)
        req = next((r for r in reqs if r.id == requirement_id), None)
        if not req:
            return None
        outstanding = max(req.quantity_required - req.quantity_assigned, 0) or req.quantity_required
        description = req.resource_type_text
        if req.capability_text:
            description = f"{description} ({req.capability_text})"
        body = {
            "title": f"{wa.assignment_number} {wa.assignment_name} - {req.resource_type_text}".strip(" -"),
            "requesting_section": "Operations",
            "priority": self._LOGISTICS_PRIORITY_MAP.get(req.priority, "ROUTINE"),
            "justification": req.source_note or req.notes or f"Resource requirement for strategy {wa.assignment_number}",
            "items": [{
                "kind": "SUPPLY",
                "description": description,
                "quantity": outstanding,
                "unit": req.unit or "unit",
            }],
        }
        try:
            d = _client().post(f"/api/incidents/{_iid()}/logistics/resource-requests", json=body)
        except Exception:
            return None
        request_id = d.get("id") if d else None
        if request_id:
            self.update_resource_requirement_for_wa(
                work_assignment_id, requirement_id, {"logistics_request_id": request_id}
            )
        return request_id

    # ------------------------------------------------------------------
    # Actual resource assignments
    # ------------------------------------------------------------------

    def list_assigned_resources(self, requirement_id: int) -> list[WorkAssignmentResourceAssignment]:
        return []  # needs work_assignment_id — use list_assigned_resources_for_wa

    def list_assigned_resources_for_wa(
        self, work_assignment_id: int, requirement_id: int
    ) -> list[WorkAssignmentResourceAssignment]:
        try:
            data = _client().get(f"{_base()}/{work_assignment_id}/resources")
        except Exception:
            return []
        for d in data:
            if d.get("id") == requirement_id:
                return [_ra_from_dict(a) for a in d.get("assignments", [])]
        return []

    def assign_actual_resource(self, requirement_id: int, resource_kind: str, resource_id: str, display_name: str = "") -> int:
        return 0  # needs work_assignment_id — use assign_actual_resource_for_wa

    def assign_actual_resource_for_wa(self, work_assignment_id: int, requirement_id: int, resource_kind: str, resource_id: str, display_name: str = "") -> int:
        d = _client().post(f"{_base()}/{work_assignment_id}/resources/{requirement_id}/assignments", json={
            "resource_kind": resource_kind,
            "resource_id": str(resource_id),
            "display_name": display_name,
        })
        return int(d.get("id") or 0)

    def remove_actual_resource(self, assignment_id: int) -> None:
        pass  # needs work_assignment_id and requirement_id — use remove_actual_resource_for_wa

    def remove_actual_resource_for_wa(self, work_assignment_id: int, requirement_id: int, assignment_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/resources/{requirement_id}/assignments/{assignment_id}")
        except Exception:
            pass

    def update_actual_resource_status(self, assignment_id: int, status: str) -> None:
        pass  # needs work_assignment_id and requirement_id — use update_actual_resource_status_for_wa

    def update_actual_resource_status_for_wa(
        self, work_assignment_id: int, requirement_id: int, assignment_id: int, status: str
    ) -> None:
        try:
            _client().patch(
                f"{_base()}/{work_assignment_id}/resources/{requirement_id}/assignments/{assignment_id}",
                json={"status": status},
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Hazards
    # ------------------------------------------------------------------

    def list_hazards(self, work_assignment_id: int) -> list[WorkAssignmentHazard]:
        try:
            return [_hazard_from_dict(d) for d in _client().get(f"{_base()}/{work_assignment_id}/hazards")]
        except Exception:
            return []

    def add_hazard(self, work_assignment_id: int, data: dict[str, Any]) -> int:
        d = _client().post(f"{_base()}/{work_assignment_id}/hazards", json=data)
        return int(d.get("id") or 0)

    def update_hazard(self, hazard_id: int, data: dict[str, Any]) -> bool:
        return False  # needs work_assignment_id

    def update_hazard_for_wa(self, work_assignment_id: int, hazard_id: int, data: dict[str, Any]) -> bool:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/hazards/{hazard_id}", json=data)
            return True
        except Exception:
            return False

    def remove_hazard(self, hazard_id: int) -> None:
        pass

    def remove_hazard_for_wa(self, work_assignment_id: int, hazard_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/hazards/{hazard_id}")
        except Exception:
            pass

    def mark_hazard_resolved(self, hazard_id: int, resolved: bool = True) -> None:
        pass

    def mark_hazard_resolved_for_wa(self, work_assignment_id: int, hazard_id: int, resolved: bool = True) -> None:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/hazards/{hazard_id}", json={"is_resolved": resolved})
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Communications
    # ------------------------------------------------------------------

    def list_comms(self, work_assignment_id: int) -> list[WorkAssignmentComms]:
        try:
            return [_comms_from_dict(d) for d in _client().get(f"{_base()}/{work_assignment_id}/comms")]
        except Exception:
            return []

    def add_comms_channel(self, work_assignment_id: int, data: dict[str, Any]) -> int:
        d = _client().post(f"{_base()}/{work_assignment_id}/comms", json=data)
        return int(d.get("id") or 0)

    def update_comms_channel(self, comms_id: int, data: dict[str, Any]) -> bool:
        return False  # needs work_assignment_id

    def update_comms_channel_for_wa(self, work_assignment_id: int, comms_id: int, data: dict[str, Any]) -> bool:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/comms/{comms_id}", json=data)
            return True
        except Exception:
            return False

    def remove_comms_channel(self, comms_id: int) -> None:
        pass

    def remove_comms_channel_for_wa(self, work_assignment_id: int, comms_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/comms/{comms_id}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Task links
    # ------------------------------------------------------------------

    def list_linked_tasks(self, work_assignment_id: int) -> list[WorkAssignmentTaskLink]:
        try:
            return [_link_from_dict(d) for d in _client().get(f"{_base()}/{work_assignment_id}/task-links")]
        except Exception:
            return []

    def link_existing_task(self, work_assignment_id: int, task_id: int, link_type: str = "Linked Existing", notes: str = "") -> int | None:
        try:
            d = _client().post(f"{_base()}/{work_assignment_id}/task-links", json={
                "task_id": task_id,
                "link_type": link_type,
                "notes": notes,
            })
            if d is None:
                return None
            return int(d.get("id") or 0)
        except Exception:
            return None

    def unlink_task(self, link_id: int) -> None:
        pass  # needs work_assignment_id

    def unlink_task_for_wa(self, work_assignment_id: int, link_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/task-links/{link_id}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Agency request links
    # ------------------------------------------------------------------

    def list_linked_agency_requests(self, work_assignment_id: int) -> list[dict]:
        try:
            return _client().get(f"{_base()}/{work_assignment_id}/agency-requests") or []
        except Exception:
            return []

    def link_agency_request(self, work_assignment_id: int, agency_request_id: int) -> int | None:
        try:
            d = _client().post(f"{_base()}/{work_assignment_id}/agency-requests", json={
                "agency_request_id": agency_request_id,
            })
            if d is None:
                return None
            return int(d.get("id") or 0)
        except Exception:
            return None

    def unlink_agency_request(self, work_assignment_id: int, link_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/agency-requests/{link_id}")
        except Exception:
            pass

    def list_strategies_for_task(self, task_id: int) -> list[dict]:
        try:
            iid = _iid()
            return _client().get(f"/api/incidents/{iid}/planning/tasks/{task_id}/work-assignments")
        except Exception:
            return []

    def create_task_from_work_assignment(self, work_assignment_id: int, task_payload: dict[str, Any] | None = None) -> int | None:
        wa = self.get_work_assignment(work_assignment_id)
        if not wa:
            return None
        try:
            from modules.operations.taskings.repository import create_task
        except ImportError:
            return None
        payload = task_payload or {}
        title = payload.get("title") or wa.assignment_name
        description_parts = []
        if wa.description:
            description_parts.append(wa.description)
        if wa.tactics_summary:
            description_parts.append(f"Tactics: {wa.tactics_summary}")
        if wa.special_instructions:
            description_parts.append(f"Special Instructions: {wa.special_instructions}")
        try:
            new_task_id = create_task(
                title=title,
                description="\n".join(description_parts) or None,
                priority=wa.priority,
                location=wa.location or None,
                location_facility_id=wa.location_facility_id or None,
            )
        except Exception:
            return None
        if new_task_id:
            self.link_existing_task(work_assignment_id, new_task_id, link_type="Generated")
        return new_task_id

    # ------------------------------------------------------------------
    # Log entries
    # ------------------------------------------------------------------

    def list_log_entries(self, work_assignment_id: int) -> list[WorkAssignmentLogEntry]:
        try:
            return [_log_from_dict(d) for d in _client().get(f"{_base()}/{work_assignment_id}/log")]
        except Exception:
            return []

    def add_log_entry(self, work_assignment_id: int, entry_text: str, entry_type: str = "Note", critical: bool = False) -> int:
        d = _client().post(f"{_base()}/{work_assignment_id}/log", json={
            "entry_text": entry_text,
            "entry_type": entry_type,
            "critical": critical,
        })
        return int(d.get("id") or 0)

    def update_log_entry(self, log_id: int, data: dict[str, Any]) -> bool:
        return False  # needs work_assignment_id — use update_log_entry_for_wa

    def update_log_entry_for_wa(self, work_assignment_id: int, log_id: int, data: dict[str, Any]) -> bool:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/log/{log_id}", json=data)
            return True
        except Exception:
            return False

    def remove_log_entry(self, log_id: int) -> None:
        pass  # needs work_assignment_id — use remove_log_entry_for_wa

    def remove_log_entry_for_wa(self, work_assignment_id: int, log_id: int) -> None:
        try:
            _client().delete(f"{_base()}/{work_assignment_id}/log/{log_id}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Output status
    # ------------------------------------------------------------------

    def list_outputs(self, work_assignment_id: int) -> list[WorkAssignmentOutputStatus]:
        try:
            return [_output_from_dict(d) for d in _client().get(f"{_base()}/{work_assignment_id}/outputs")]
        except Exception:
            return []

    def update_output_status(self, work_assignment_id: int, output_type: str, status: str, notes: str = "") -> None:
        try:
            _client().patch(f"{_base()}/{work_assignment_id}/outputs/{output_type}", json={"status": status, "notes": notes})
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status board
    # ------------------------------------------------------------------

    def list_work_assignment_status_rows(self) -> list[dict[str, Any]]:
        try:
            iid = _iid()
            return _client().get(f"/api/incidents/{iid}/planning/work-assignment-status-rows")
        except Exception:
            return []
