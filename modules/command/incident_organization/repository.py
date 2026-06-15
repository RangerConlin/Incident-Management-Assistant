from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence
from .models import (
    ACTIVE_ASSIGNMENT_TYPES,
    AssignmentHistoryEntry,
    GeneratedFormSnapshot,
    OrganizationPosition,
    OrganizationTemplate,
    PositionAssignment,
    POSITION_STATUSES,
)

class ApiIncidentOrganizationRepository:
    """MongoDB-backed implementation via the SARApp API server."""

    def __init__(self, incident_id: str):
        self.incident_id = str(incident_id)
        self._base = f"/api/incidents/{self.incident_id}/org"

    def _get(self, path: str, **params):
        from utils.api_client import api_client
        return api_client.get(self._base + path, params=params if params else None)

    def _post(self, path: str, body):
        from utils.api_client import api_client
        return api_client.post(self._base + path, json=body)

    def _patch(self, path: str, body=None, **params):
        from utils.api_client import api_client
        return api_client.patch(self._base + path, json=body, params=params if params else None)

    def _put(self, path: str, body):
        from utils.api_client import api_client
        return api_client.put(self._base + path, json=body)

    def _delete(self, path: str):
        from utils.api_client import api_client
        return api_client.delete(self._base + path)

    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        pass  # MongoDB is schemaless

    def upsert_position(self, position: OrganizationPosition) -> int:
        body = {
            "position_id": position.id,
            "title": position.title,
            "classification": position.classification,
            "parent_position_id": position.parent_position_id,
            "operational_period": position.operational_period,
            "required_qualifications": list(position.required_qualifications),
            "is_critical": position.is_critical,
            "is_custom": position.is_custom,
            "status": position.status,
            "sort_order": position.sort_order,
            "notes": position.notes,
        }
        result = self._post("/positions", body)
        return int(result["position_id"])

    def list_positions(self, include_inactive: bool = False) -> list[OrganizationPosition]:
        docs = self._get("/positions", include_inactive=str(include_inactive).lower())
        return [self._doc_to_position(d) for d in docs]

    def get_position(self, position_id: int) -> OrganizationPosition | None:
        try:
            doc = self._get(f"/positions/{position_id}")
            return self._doc_to_position(doc)
        except Exception:
            return None

    def move_position(self, position_id: int, parent_position_id: int | None) -> None:
        self._patch(f"/positions/{position_id}/move", {"parent_position_id": parent_position_id})

    def list_operational_units(
        self, classifications: set[str] | None = None
    ) -> list[OrganizationPosition]:
        from utils.api_client import api_client
        params: dict = {}
        if classifications:
            params["classifications"] = ",".join(classifications)
        docs = api_client.get(self._base + "/units", params=params if params else None)
        return [self._doc_to_position(d) for d in docs]

    def deactivate_position(self, position_id: int) -> None:
        self._delete(f"/positions/{position_id}")

    def list_templates(self) -> list[OrganizationTemplate]:
        docs = self._get("/templates")
        return [self._doc_to_template(d) for d in docs]

    def get_template_by_name(self, name: str) -> OrganizationTemplate | None:
        try:
            from utils.api_client import api_client
            doc = api_client.get(self._base + "/templates/by-name", params={"name": name})
            return self._doc_to_template(doc)
        except Exception:
            return None

    def save_template(self, template: OrganizationTemplate) -> int:
        body = {
            "template_id": template.id,
            "name": template.name,
            "description": template.description,
            "payload": template.payload,
        }
        result = self._post("/templates", body)
        return int(result["template_id"])

    def apply_template_payload(self, payload: Sequence[dict[str, object]]) -> list[int]:
        result = self._post("/templates/apply", {"payload": list(payload)})
        return [int(pid) for pid in result]

    def add_assignment(self, assignment: PositionAssignment) -> int:
        body = {
            "position_id": assignment.position_id,
            "personnel_id": assignment.personnel_id,
            "display_name": assignment.display_name,
            "assignment_type": assignment.assignment_type,
            "start_time": assignment.start_time,
            "end_time": assignment.end_time,
            "operational_period": assignment.operational_period,
            "assigned_by": assignment.assigned_by,
            "notes": assignment.notes,
        }
        result = self._post("/assignments", body)
        return int(result["assignment_id"])

    def end_assignment(
        self,
        assignment_id: int,
        *,
        end_time: str | None = None,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        self._patch(
            f"/assignments/{assignment_id}/end",
            {"end_time": end_time, "changed_by": changed_by, "notes": notes},
        )

    def list_assignments(
        self, position_id: int | None = None, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        from utils.api_client import api_client
        params: dict = {"active_only": str(active_only).lower()}
        if position_id is not None:
            params["position_id"] = position_id
        docs = api_client.get(self._base + "/assignments", params=params)
        return [self._doc_to_assignment(d) for d in docs]

    def list_assignments_for_person(
        self, personnel_id: str, *, active_only: bool = True
    ) -> list[PositionAssignment]:
        from utils.api_client import api_client
        params: dict = {"active_only": str(active_only).lower()}
        docs = api_client.get(
            self._base + f"/assignments/by-person/{personnel_id}", params=params
        )
        return [self._doc_to_assignment(d) for d in docs]

    def list_assignment_history(
        self, position_id: int | None = None
    ) -> list[AssignmentHistoryEntry]:
        from utils.api_client import api_client
        params: dict = {}
        if position_id is not None:
            params["position_id"] = position_id
        docs = api_client.get(self._base + "/history", params=params if params else None)
        return [self._doc_to_history(d) for d in docs]

    def replace_requirements(self, position_id: int, qualifications: Iterable[str]) -> None:
        self._put(f"/positions/{position_id}/requirements", {"qualifications": list(qualifications)})

    def save_generated_snapshot(self, snapshot: GeneratedFormSnapshot) -> int:
        body = {
            "form_type": snapshot.form_type,
            "generated_at": snapshot.generated_at,
            "operational_period": snapshot.operational_period,
            "source_version": snapshot.source_version,
            "payload": snapshot.payload,
        }
        result = self._post("/snapshots", body)
        return int(result["snapshot_id"])

    # ------------------------------------------------------------------

    @staticmethod
    def _doc_to_position(doc: dict) -> OrganizationPosition:
        return OrganizationPosition(
            id=doc.get("id") or doc.get("position_id"),
            incident_id=doc.get("incident_id", ""),
            title=doc.get("title", ""),
            classification=doc.get("classification", "position"),
            parent_position_id=doc.get("parent_position_id"),
            operational_period=doc.get("operational_period"),
            required_qualifications=list(doc.get("required_qualifications") or []),
            is_critical=bool(doc.get("is_critical", False)),
            is_custom=bool(doc.get("is_custom", False)),
            status=doc.get("status", "active"),
            sort_order=int(doc.get("sort_order", 0) or 0),
            notes=doc.get("notes"),
        )

    @staticmethod
    def _doc_to_template(doc: dict) -> OrganizationTemplate:
        return OrganizationTemplate(
            id=doc.get("id") or doc.get("template_id"),
            incident_id=doc.get("incident_id"),
            name=doc.get("name", ""),
            description=doc.get("description"),
            payload=list(doc.get("payload") or []),
        )

    @staticmethod
    def _doc_to_assignment(doc: dict) -> PositionAssignment:
        return PositionAssignment(
            id=doc.get("id") or doc.get("assignment_id"),
            incident_id=doc.get("incident_id", ""),
            position_id=int(doc.get("position_id", 0)),
            personnel_id=doc.get("personnel_id"),
            display_name=doc.get("display_name", ""),
            assignment_type=doc.get("assignment_type", "primary"),
            start_time=doc.get("start_time"),
            end_time=doc.get("end_time"),
            operational_period=doc.get("operational_period"),
            assigned_by=doc.get("assigned_by"),
            notes=doc.get("notes"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )

    @staticmethod
    def _doc_to_history(doc: dict) -> AssignmentHistoryEntry:
        return AssignmentHistoryEntry(
            id=doc.get("id") or doc.get("history_id"),
            incident_id=doc.get("incident_id", ""),
            assignment_id=doc.get("assignment_id"),
            position_id=int(doc.get("position_id", 0)),
            personnel_id=doc.get("personnel_id"),
            display_name=doc.get("display_name", ""),
            assignment_type=doc.get("assignment_type", "primary"),
            action=doc.get("action", ""),
            effective_time=doc.get("effective_time"),
            operational_period=doc.get("operational_period"),
            changed_by=doc.get("changed_by"),
            notes=doc.get("notes"),
        )
